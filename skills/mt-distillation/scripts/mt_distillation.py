"""MT Distillation 1.0.0：可迁移的精馏计算器与自包含 Agent Skill。

无参数打开输入窗口；--cli --config input.json 进行无窗口计算。
--out 指定新的结果目录；MT_OUTPUT_DIR 设置默认结果根目录。
图中只显示不含再沸器的塔内理论板数，编号位于水平阶梯线下方。
全凝器不计级，平衡部分再沸器计一级。组成均为轻组分摩尔分数。
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import os
import queue
import subprocess
import sys
import threading
import warnings
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path


@dataclass(frozen=True)
class Inputs:
    alpha: float = 2.5
    zF: float = 0.5
    xD: float = 0.95
    xW: float = 0.05
    q: float = 1.0
    R: float = 2.0
    F: float = 100.0  # kmol/h；不影响固定工况下的级数
    max_stages: int = 10000
    tol: float = 1e-12

    def validate(self):
        for key in ('alpha', 'zF', 'xD', 'xW', 'q', 'R', 'F', 'tol'):
            value = getattr(self, key)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                raise ValueError(f'{key} 必须为有限数值。')
        if self.alpha <= 1:
            raise ValueError('alpha 必须大于 1，组成按易挥发组分定义。')
        if not 0 < self.xW < self.zF < self.xD < 1:
            raise ValueError('必须满足 0 < xW < zF < xD < 1。')
        if self.F <= 0 or self.R <= 0:
            raise ValueError('F 和 R 必须大于 0。')
        if not 0 < self.tol <= 1e-8:
            raise ValueError('tol 必须位于 (0, 1e-8]。')
        if isinstance(self.max_stages, bool) or not isinstance(self.max_stages, int) or self.max_stages < 2:
            raise ValueError('max_stages 必须是至少为 2 的整数。')


def y_eq(x, alpha):
    return alpha * x / (1 + (alpha - 1) * x)


def x_eq(y, alpha):
    return y / (alpha - (alpha - 1) * y)


def operating_parameters(p: Inputs):
    p.validate()
    # q*x - (q-1)*y = zF；避免 q=0 或 q=1 的特殊斜率。
    lo, hi = 0.0, 1.0
    for _ in range(100):
        mid = (lo + hi) / 2
        residual = p.q * mid - (p.q - 1) * y_eq(mid, p.alpha) - p.zF
        if residual > 0:
            hi = mid
        else:
            lo = mid
    xe = (lo + hi) / 2
    ye = y_eq(xe, p.alpha)
    # 第一版限定为进料夹点控制的常规双塔段分离。
    if not p.xW < xe < p.xD or not ye < p.xD:
        raise ValueError('该进料/产品条件超出第一版的常规进料夹点范围；需要端点夹点或单塔段模型。')
    Rmin = (p.xD - ye) / (ye - xe)
    if p.R <= Rmin + p.tol * max(1.0, Rmin):
        raise ValueError(f'R={p.R:g} 必须大于 Rmin={Rmin:.10g}；等于时趋于无穷级，小于时不可行。')
    D = p.F * (p.zF - p.xW) / (p.xD - p.xW)
    W = p.F - D
    L = p.R * D
    V = (p.R + 1) * D
    Ls = L + p.q * p.F
    Vs = V - (1 - p.q) * p.F
    if Ls <= 0 or Vs <= 0:
        raise ValueError('提馏段气液流量必须为正；请检查 q、R 和产品规格。')
    mr, br = L / V, D * p.xD / V
    ms, bs = Ls / Vs, -W * p.xW / Vs
    xI = (bs - br) / (mr - ms)
    yI = mr * xI + br
    if not p.xW < xI < p.xD or not xI < yI < y_eq(xI, p.alpha):
        raise ValueError('操作线交点不处于可行双塔段区域；该工况超出第一版范围。')
    return dict(D=D, W=W, L=L, V=V, L_strip=Ls, V_strip=Vs,
                mr=mr, br=br, ms=ms, bs=bs, xe=xe, ye=ye,
                xI=xI, yI=yI, Rmin=Rmin)


def solve(p: Inputs):
    """返回输入、衡算、汇总、逐级组成、阶梯顶点；不启动 Origin。"""
    op = operating_parameters(p)
    stages, staircase = [], [(p.xD, p.xD)]
    y, x_previous = p.xD, p.xD
    feed_stage = None
    for n in range(1, p.max_stages + 1):
        x = x_eq(y, p.alpha)
        if not 0 <= x < x_previous - p.tol:
            raise ValueError(f'第 {n} 级无法推进：接近夹点或数值精度不足。')
        # 第一次在交点左侧结束水平步的平衡级记作进料级。
        # 此级本身满足相平衡，其后的竖直步采用提馏段操作线。
        if feed_stage is None and x <= op['xI']:
            feed_stage = n
        section = 'rectifying' if feed_stage is None else ('feed' if n == feed_stage else 'stripping')
        staircase.append((x, y))
        terminal = x <= p.xW
        y_next = None if terminal else ((op['mr'] * x + op['br']) if feed_stage is None else (op['ms'] * x + op['bs']))
        stages.append(dict(stage=n, section=section, x_previous=x_previous,
                           x=x, y=y, y_next=y_next, terminal_step=terminal))
        if terminal:
            break
        staircase.append((x, y_next))
        x_previous, y = x, y_next
    else:
        raise ValueError(f'超过 max_stages={p.max_stages}；可能接近夹点。')
    if feed_stage is None or feed_stage >= len(stages):
        raise ValueError('进料将落入终端再沸器等效级；第一版仅支持进料位于塔内的双塔段工况。')
    # 末个水平步按组成线性插值；这是 MT 读图估算，不是完整整数级严格设计。
    last = stages[-1]
    last_fraction = (last['x_previous'] - p.xW) / (last['x_previous'] - last['x'])
    N_fractional = len(stages) - 1 + last_fraction
    summary = dict(
        N_equilibrium_integer=len(stages),
        N_trays_integer=len(stages) - 1,
        N_equilibrium_fractional=N_fractional,
        N_trays_fractional=N_fractional - 1,
        feed_stage_from_top=feed_stage,
        trays_above_feed=feed_stage - 1,
        trays_below_feed=len(stages) - 1 - feed_stage,
        terminal_x=last['x'], target_xW=p.xW,
        Nmin_Fenske=math.log((p.xD / (1 - p.xD)) * ((1 - p.xW) / p.xW)) / math.log(p.alpha),
        count_convention='Total condenser excluded; one partial reboiler included in equilibrium stages.',
        terminal_note='Last horizontal step can overshoot xW. Rounded MT counts are preliminary, not an exact integer-stage boundary-value solution.'
    )
    return dict(inputs=asdict(p), operating=op, summary=summary, stages=stages, staircase=staircase)


def plot_series(result):
    p, o = result['inputs'], result['operating']
    grid = [i / 500 for i in range(501)]
    # 参数化 q-line：x=zF+(q-1)t，y=zF+qt；裁切至单位正方形。
    tlo, thi = -math.inf, math.inf
    for slope in (p['q'] - 1, p['q']):
        if slope != 0:
            bounds = sorted((-p['zF'] / slope, (1 - p['zF']) / slope))
            tlo, thi = max(tlo, bounds[0]), min(thi, bounds[1])
    qpoints = [(p['zF'] + (p['q'] - 1) * t, p['zF'] + p['q'] * t) for t in (tlo, thi)]
    return [
        ('Equilibrium', list(zip(grid, [y_eq(x, p['alpha']) for x in grid])), '#187c80', '-'),
        ('Diagonal', [(0, 0), (1, 1)], '#9ca3af', '--'),
        ('Rectifying', [(o['xI'], o['yI']), (p['xD'], p['xD'])], '#2563a6', '-'),
        ('Stripping', [(p['xW'], p['xW']), (o['xI'], o['yI'])], '#8465a5', '-'),
        ('q-line', qpoints, '#a88739', '--'),
        ('MT stages', result['staircase'], '#c74632', '-'),
        ('Pinch (xe, ye)', [(o['xe'], o['ye'])], '#187c80', 'o'),
        ('Intersection (xI, yI)', [(o['xI'], o['yI'])], '#202c3b', 'o'),
    ]


def save_matplotlib(result, folder):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 10, 'svg.fonttype': 'none'})
    fig, ax = plt.subplots(figsize=(10, 9))
    fig.subplots_adjust(left=0.10, right=0.94, bottom=0.18, top=0.9)
    for label, points, color, style in plot_series(result):
        xx, yy = zip(*points)
        ax.plot(xx, yy, style, color=color, linewidth=1.6, markersize=5, label=label)
    s, p, o = result['summary'], result['inputs'], result['operating']
    for row in result['stages'][:-1]:
        if len(result['stages']) <= 35 or row['stage'] in (1, s['feed_stage_from_top'], s['N_trays_integer']):
            ax.annotate(str(row['stage']), ((row['x_previous'] + row['x']) / 2, row['y']),
                        xytext=(0, -5), textcoords='offset points', fontsize=8, ha='center', va='top', color='#9c3324')
    feed = result['stages'][s['feed_stage_from_top'] - 1]
    ax.annotate(f"Feed: stage {feed['stage']}", (feed['x'], feed['y']), xytext=(-75, 30),
                textcoords='offset points', fontsize=10, arrowprops={'arrowstyle': '->', 'color': '#202c3b'})
    ax.annotate('(xe, ye)', (o['xe'], o['ye']), xytext=(8, 10), textcoords='offset points', fontsize=9)
    ax.annotate('(xI, yI)', (o['xI'], o['yI']), xytext=(9, -19), textcoords='offset points', fontsize=9)
    ax.axvline(p['xW'], color='#9ca3af', linewidth=0.7, linestyle=':')
    ax.set(xlim=(0, 1), ylim=(0, 1), xlabel='Liquid light-component mole fraction, x',
           ylabel='Vapor light-component mole fraction, y')
    ax.set_aspect('equal', adjustable='box')
    ax.set_xticks([i / 10 for i in range(11)])
    ax.set_yticks([i / 10 for i in range(11)])
    ax.grid(alpha=0.17)
    ax.legend(loc='lower right', fontsize=8.5, frameon=False)
    fig.suptitle('McCabe-Thiele | Constant relative volatility', fontsize=17, y=0.97)
    ax.set_title(f"alpha={p['alpha']:g}   R={p['R']:g}   q={p['q']:g}   zF={p['zF']:g}   xD={p['xD']:g}   xW={p['xW']:g}", fontsize=10, pad=12)
    fig.text(0.13, 0.10, f"{s['N_trays_fractional']:.3f} theoretical trays  |  feed tray {s['feed_stage_from_top']}", fontsize=12)
    fig.text(0.13, 0.065, f"Rmin={o['Rmin']:.4f}   D={o['D']:.3f}   W={o['W']:.3f} kmol/h", fontsize=10)
    fig.text(0.13, 0.032, 'Trays exclude reboiler. Fractional count uses terminal-step interpolation.', color='#6b7280', fontsize=9)
    for suffix in ('png', 'svg'):
        fig.savefig(folder / f'MT.{suffix}', dpi=180)
    plt.close(fig)


def write_csv(path, rows):
    with path.open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def save_data(result, folder):
    (folder / 'results.json').write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')
    write_csv(folder / 'stages.csv', result['stages'])
    write_csv(folder / 'staircase.csv', [dict(x=x, y=y) for x, y in result['staircase']])
    rows = [dict(series=label, point=i, x=x, y=y) for label, points, _, _ in plot_series(result) for i, (x, y) in enumerate(points)]
    write_csv(folder / 'curves.csv', rows)


def save_origin(result, folder):
    """外部 Python 的独立 Origin 实例；每条曲线绑定工作簿数据，可编辑。"""
    if os.name != 'nt':
        raise RuntimeError('Origin 导出需要 Windows 和已安装、可正常启动的 Origin。')
    import originpro as op
    if not op.oext:
        raise RuntimeError('请在外部 Python 运行 --origin，以便创建独立 Origin 项目。')
    try:
        op.set_show(False)
        book = op.new_book('w', lname='MT calculation')
        data = book[0]
        data.name = 'Curves'
        graph = op.new_graph(template='line', lname='McCabe-Thiele')
        layer = graph[0]
        graph.activate()
        op.lt_exec('layer.fixed=1; layer.factor=1; page.kar=0; page.updatetoprinter=0; page.width=8*page.resx; page.height=8*page.resy; layer.unit=1; layer.left=15; layer.top=12; layer.width=76; layer.height=76;')
        for i, (label, points, color, style) in enumerate(plot_series(result)):
            xx, yy = zip(*points)
            data.from_list(2 * i, list(xx), lname=label + ' x', axis='X')
            data.from_list(2 * i + 1, list(yy), lname=label, axis='Y')
            plot = layer.add_plot(data, coly=2 * i + 1, colx=2 * i, type='s' if style == 'o' else 'l')
            plot.color = color
            if style != 'o':
                plot.set_cmd('-w 1000' if label == 'MT stages' else '-w 750')
                if style == '--':
                    plot.set_cmd('-d 1')
            else:
                plot.symbol_size = 5
        sheet = book.add_sheet('Stages')
        for col, key in enumerate(result['stages'][0]):
            values = [row[key] for row in result['stages']]
            # Origin 的缺失值用 NaN，布尔值用 0/1。
            values = [math.nan if v is None else int(v) if isinstance(v, bool) else v for v in values]
            sheet.from_list(col, values, lname=key)
        sheet = book.add_sheet('Parameters')
        items = [(group + '.' + key, str(value)) for group in ('inputs', 'operating', 'summary')
                 for key, value in result[group].items()
                 if key not in ('N_equilibrium_integer', 'N_equilibrium_fractional', 'Nmin_Fenske', 'count_convention')]
        sheet.from_list(0, [k for k, _ in items], lname='Parameter')
        sheet.from_list(1, [v for _, v in items], lname='Value')
        graph.activate()
        layer.set_xlim(0, 1, 0.1)
        layer.set_ylim(0, 1, 0.1)
        layer.axis('x').title = 'Liquid light-component mole fraction, x'
        layer.axis('y').title = 'Vapor light-component mole fraction, y'
        op.lt_exec('layer.x.label.pt=11; layer.y.label.pt=11; xb.fsize=12; yl.fsize=12;')
        legend = layer.label('legend')
        if legend:
            legend.text = '\n'.join('\\l(%d) %s' % (i + 1, series[0]) for i, series in enumerate(plot_series(result)))
            legend.set_float('fsize', 10)
            legend.set_float('x', 0.79)
            legend.set_float('y', 0.23)
        # 文本标注只含程序生成的数值，不执行用户提供的字符串。
        def add_text(name, text, x, y, size):
            op.lt_exec(f'label -a {x} {y} -n {name} placeholder;')
            obj = layer.label(name)
            obj.text = text
            obj.set_float('fsize', size)
            obj.set_float('x', x)
            obj.set_float('y', y)

        s, o = result['summary'], result['operating']
        text = f"N_trays={s['N_trays_fractional']:.3f} | Feed={s['feed_stage_from_top']}"
        add_text('MTsummary', text, 0.5, 1.10, 13)
        p = result['inputs']
        add_text('MTinputs', f"alpha={p['alpha']:g}  R={p['R']:g}  q={p['q']:g}  zF={p['zF']:g}  xD={p['xD']:g}  xW={p['xW']:g}", 0.5, 1.045, 10)
        add_text('MTpinch', '(xe, ye)', o['xe'] + 0.06, o['ye'] + 0.035, 10)
        add_text('MTintersection', '(xI, yI)', o['xI'] + 0.065, o['yI'] - 0.03, 10)
        for row in result['stages'][:-1]:
            if len(result['stages']) <= 35 or row['stage'] in (1, s['feed_stage_from_top'], s['N_trays_integer']):
                name = f'MTstage{row["stage"]}'
                label = str(row['stage'])
                add_text(name, label, (row['x_previous'] + row['x']) / 2, row['y'] - 0.015, 9)
        project = folder / 'MT_origin.opju'
        if not op.save(str(project)) or not project.is_file():
            raise RuntimeError('Origin 未能保存 OPJU 项目。')
        graph.save_fig(str(folder / 'MT_origin.png'), width=1400)
        return project
    finally:
        failed = sys.exc_info()[0] is not None
        try:
            op.exit()
        except Exception as exc:
            if not failed:
                warnings.warn(f'Origin 已导出，但关闭实例时出错：{exc}')


VERSION = '1.0.0'
SKILL_DIR = Path(__file__).resolve().parent.parent
APP_DIR = Path(os.environ.get('MT_OUTPUT_DIR') or (Path.home() / 'Documents' / 'MT_Distillation')).expanduser().resolve()
OUTPUT_DIR = APP_DIR / 'outputs'
DEFAULT_EXPORT_ORIGIN = False


def runtime_python():
    # pythonw.exe 的 GUI 也要用 python.exe 子进程，以便捕获结果与错误日志。
    executable = Path(sys.executable)
    return executable.with_name('python.exe') if executable.name.lower() == 'pythonw.exe' else executable


def _child_options():
    return {'creationflags': subprocess.CREATE_NO_WINDOW} if os.name == 'nt' else {}


def ensure_runtime():
    """复用随 Skill 安装的环境；计算运行期间不隐式联网安装依赖。"""
    APP_DIR.mkdir(parents=True, exist_ok=True)
    (APP_DIR / 'cache').mkdir(exist_ok=True)
    (APP_DIR / 'work').mkdir(exist_ok=True)
    os.environ['MPLCONFIGDIR'] = str(APP_DIR / 'cache' / 'matplotlib')
    os.environ['PIP_CACHE_DIR'] = str(APP_DIR / 'cache' / 'pip')
    os.environ['PYTHONUTF8'] = '1'
    os.environ['PYTHONIOENCODING'] = 'utf-8'
    runtime = SKILL_DIR / '.venv' / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
    if runtime.is_file() and Path(sys.prefix).resolve() != runtime.parent.parent.resolve():
        return subprocess.call(
            [str(runtime), str(Path(__file__).resolve()), *sys.argv[1:]],
            stdout=sys.stdout, stderr=sys.stderr, **_child_options())
    try:
        import matplotlib
    except ImportError as exc:
        raise RuntimeError('缺少绘图依赖。请先运行 setup.bat 或 python scripts/bootstrap.py。') from exc
    return None


def result_text(result, folder):
    s, o = result['summary'], result['operating']
    return (
        f"塔内理论板数（小数估算）：{s['N_trays_fractional']:.4f}\n"
        f"塔内理论板数（完整板数）：{s['N_trays_integer']}\n"
        f"进料板（从塔顶起）：第 {s['feed_stage_from_top']} 块\n"
        f"Rmin：{o['Rmin']:.6f}\n"
        f"D = {o['D']:.4f}，W = {o['W']:.4f} kmol/h\n"
        f"夹点 (xe, ye) = ({o['xe']:.6f}, {o['ye']:.6f})\n"
        f"操作线交点 (xI, yI) = ({o['xI']:.6f}, {o['yI']:.6f})\n\n"
        f"保存位置：{folder}\n"
        "计数口径：全凝器不计级；Origin 图和显示数字不包含再沸器。\n"
        "最后一个完整阶梯可能跨过目标 xW，小数结果为 MT 末级插值估算。"
    )


def log_message(message, error=False):
    """Diagnostics must not abort an imported calculation on a legacy console."""
    stream = sys.stderr if error else sys.stdout
    if stream is None:
        return
    try:
        print(message, file=stream, flush=True)
    except UnicodeEncodeError:
        encoding = getattr(stream, 'encoding', None) or 'utf-8'
        safe = message.encode(encoding, errors='backslashreplace').decode(encoding)
        print(safe, file=stream, flush=True)


def calculate_and_save(params, folder, export_origin):
    result = solve(params)
    folder = Path(folder).resolve()
    folder.mkdir(parents=True, exist_ok=False)
    save_data(result, folder)
    save_matplotlib(result, folder)
    (folder / '计算结果.txt').write_text(result_text(result, folder), encoding='utf-8')
    log_message(result_text(result, folder))
    if export_origin:
        try:
            project = save_origin(result, folder)
            log_message(f'可编辑 Origin 项目：{project}')
        except Exception as exc:
            message = f'Origin 导出失败：{type(exc).__name__}: {exc}\n普通 MT 图和数据已保存。'
            (folder / 'origin_error.txt').write_text(message, encoding='utf-8')
            log_message(message, error=True)
            return 3
    return 0


class MTWindow:
    """输入工况、启动计算、显示 MT 图和逐板组成。"""
    def __init__(self, root, smoke=False, params=None, export_origin=False, output_root=None):
        import tkinter as tk
        from tkinter import ttk, messagebox
        self.tk, self.ttk, self.messagebox = tk, ttk, messagebox
        self.root, self.smoke = root, smoke
        self.events = queue.Queue()
        self.busy = False
        self.folder = None
        self.result = None
        self.smoke_passed = False
        self.output_root = output_root or OUTPUT_DIR
        root.title('精馏塔理论板计算 · Python + Origin')
        root.geometry('1180x820')
        root.minsize(980, 680)
        root.protocol('WM_DELETE_WINDOW', self.close)

        shell = ttk.Frame(root, padding=16)
        shell.pack(fill='both', expand=True)
        left = ttk.Frame(shell, width=310)
        left.pack(side='left', fill='y', padx=(0, 18))
        ttk.Label(left, text='工况输入', font=('Microsoft YaHei UI', 17, 'bold')).pack(anchor='w', pady=(0, 14))
        form = ttk.Frame(left)
        form.pack(fill='x')
        defaults = asdict(params or Inputs())
        self.values = {}
        specs = [('alpha', '相对挥发度 α'), ('zF', '进料摩尔分数 zF'),
                 ('xD', '塔顶摩尔分数 xD'), ('xW', '塔底摩尔分数 xW'),
                 ('q', '进料热状态 q'), ('R', '实际回流比 R'), ('F', '进料量 F (kmol/h)')]
        for i, (key, label) in enumerate(specs):
            ttk.Label(form, text=label).grid(row=i, column=0, sticky='w', pady=6)
            var = tk.StringVar(value=str(defaults[key]))
            self.values[key] = var
            ttk.Entry(form, textvariable=var, width=13).grid(row=i, column=1, padx=(12, 0), pady=6)
        ttk.Label(left, text='q=1：饱和液体；q=0：饱和蒸气\n组成均为轻组分摩尔分数。', foreground='#555555').pack(anchor='w', pady=12)
        self.origin = tk.BooleanVar(value=export_origin and not smoke)
        ttk.Checkbutton(left, text='同时导出可编辑 Origin 项目', variable=self.origin).pack(anchor='w', pady=5)
        ttk.Label(left, text=f'结果目录：{self.output_root}', wraplength=300, foreground='#555555').pack(anchor='w')
        self.run_button = ttk.Button(left, text='计算并绘图', command=self.calculate)
        self.run_button.pack(fill='x', pady=(16, 8))
        self.open_button = ttk.Button(left, text='打开本次结果文件夹', command=self.open_folder, state='disabled')
        self.open_button.pack(fill='x', pady=4)
        self.status = tk.StringVar(value='就绪。')
        ttk.Label(left, textvariable=self.status, wraplength=300).pack(anchor='w', pady=12)
        self.summary = tk.Text(left, width=36, height=18, wrap='word', relief='flat', background='#f5f5f5', font=('Microsoft YaHei UI', 10))
        self.summary.pack(fill='both', expand=True)
        self.summary.insert('1.0', '修改工况后点击“计算并绘图”。\n每次计算创建独立结果文件夹。\n\nOrigin 中只显示塔内理论板数。')
        self.summary.configure(state='disabled')

        notebook = ttk.Notebook(shell)
        notebook.pack(side='left', fill='both', expand=True)
        self.plot_frame = ttk.Frame(notebook)
        self.preview = ttk.Label(self.plot_frame, text='MT 图将在计算完成后显示', anchor='center')
        self.preview.pack(fill='both', expand=True)
        notebook.add(self.plot_frame, text='MT 图')
        table_frame = ttk.Frame(notebook)
        notebook.add(table_frame, text='逐级组成')
        columns = ('stage', 'section', 'x', 'y', 'y_next')
        self.table = ttk.Treeview(table_frame, columns=columns, show='headings')
        for key, label in zip(columns, ('级号', '塔段', '液相 x', '气相 y', '下一气相 y')):
            self.table.heading(key, text=label)
            self.table.column(key, width=120, anchor='center')
        scroll = ttk.Scrollbar(table_frame, orient='vertical', command=self.table.yview)
        self.table.configure(yscrollcommand=scroll.set)
        scroll.pack(side='right', fill='y')
        self.table.pack(fill='both', expand=True)
        root.after(200, self.poll)
        if smoke:
            root.after(300, self.calculate)

    def calculate(self):
        if self.busy:
            return
        try:
            params = Inputs(**{key: float(var.get()) for key, var in self.values.items()})
            solve(params)
        except Exception as exc:
            self.status.set(f'输入有误：{exc}')
            if not self.smoke:
                self.messagebox.showerror('请检查工况', str(exc))
            return
        self.busy = True
        self.run_button.configure(state='disabled')
        self.status.set('正在计算、绘图和导出……')
        self.folder = self.output_root / ('MT_' + datetime.now().strftime('%Y%m%d_%H%M%S_%f'))
        config = APP_DIR / 'work' / (self.folder.name + '_input.json')
        config.write_text(json.dumps(asdict(params), ensure_ascii=False, indent=2), encoding='utf-8')
        args = [str(runtime_python()), str(Path(__file__).resolve()), '--cli', '--config', str(config), '--out', str(self.folder)]
        if self.origin.get():
            args.append('--origin')
        threading.Thread(target=self.worker, args=(args,), daemon=True).start()

    def worker(self, args):
        try:
            done = subprocess.run(args, capture_output=True, encoding='utf-8', errors='replace', **_child_options())
            log_dir = self.folder if self.folder and self.folder.is_dir() else APP_DIR / 'work'
            log_dir.mkdir(parents=True, exist_ok=True)
            (log_dir / (self.folder.name + '_run.log')).write_text(done.stdout + '\n' + done.stderr, encoding='utf-8')
            self.events.put((done.returncode, done.stderr or done.stdout))
        except Exception as exc:
            self.events.put((1, str(exc)))

    def poll(self):
        try:
            code, message = self.events.get_nowait()
        except queue.Empty:
            self.root.after(200, self.poll)
            return
        self.busy = False
        self.run_button.configure(state='normal')
        result_file = self.folder / 'results.json'
        if result_file.is_file():
            self.result = json.loads(result_file.read_text(encoding='utf-8'))
            self.summary.configure(state='normal')
            self.summary.delete('1.0', 'end')
            self.summary.insert('1.0', result_text(self.result, self.folder))
            self.summary.configure(state='disabled')
            self.table.delete(*self.table.get_children())
            sections = {'rectifying': '精馏段', 'feed': '进料板', 'stripping': '提馏段'}
            for row in self.result['stages']:
                section = '再沸器等效末级' if row['terminal_step'] else sections[row['section']]
                self.table.insert('', 'end', values=(row['stage'], section, f"{row['x']:.7f}", f"{row['y']:.7f}", '' if row['y_next'] is None else f"{row['y_next']:.7f}"))
            if (self.folder / 'MT.png').is_file():
                self.root.update_idletasks()
                photo = self.tk.PhotoImage(file=str(self.folder / 'MT.png'))
                factor = max(1, math.ceil(photo.width() / max(400, self.preview.winfo_width())), math.ceil(photo.height() / max(400, self.preview.winfo_height())))
                self.photo = photo.subsample(factor, factor)
                self.preview.configure(image=self.photo, text='')
            self.open_button.configure(state='normal')
        self.status.set('完成，结果已保存。' if code == 0 else ('计算完成，但 Origin 导出失败，请查看 origin_error.txt。' if code == 3 else '运行失败，请查看结果目录中的运行日志。'))
        if code not in (0, 3) and not self.smoke:
            self.messagebox.showerror('运行失败', message[-2500:])
        if self.smoke:
            assert code == 0, message
            assert self.result['summary']['N_trays_integer'] == 10
            assert len(self.table.get_children()) == 11
            assert hasattr(self, 'photo')
            self.smoke_passed = True
            print('GUI PASS: calculation button, tray count, 11 stage rows, preview loaded; ' + str(self.folder), flush=True)
            self.root.after(200, self.root.destroy)
        else:
            self.root.after(200, self.poll)

    def open_folder(self):
        if self.folder and self.folder.is_dir() and hasattr(os, 'startfile'):
            os.startfile(self.folder)

    def close(self):
        if self.busy:
            self.messagebox.showinfo('计算进行中', '请等待本次计算完成后关闭窗口。')
        else:
            self.root.destroy()


def main():
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cli', action='store_true', help='命令行计算，不打开输入窗口。')
    parser.add_argument('--config', type=Path, help='JSON 工况；省略时使用默认工况。')
    parser.add_argument('--out', type=Path, help='CLI：新结果目录；GUI：每次计算的结果根目录。')
    parser.add_argument('--version', action='version', version=VERSION)
    parser.add_argument('--origin', action='store_true', help='导出可编辑 Origin 项目。')
    parser.add_argument('--gui-check', action='store_true', help='自动检查输入窗口，不显示窗口。')
    args = parser.parse_args()
    if args.cli and args.config is None:
        parser.error('--cli 必须提供 --config JSON，避免把示例工况当作用户输入。')
    try:
        relaunch = ensure_runtime()
        if relaunch is not None:
            return relaunch
        params = Inputs(**json.loads(args.config.read_text(encoding='utf-8-sig'))) if args.config else Inputs()
        if args.cli:
            folder = args.out or OUTPUT_DIR / ('MT_' + datetime.now().strftime('%Y%m%d_%H%M%S_%f'))
            return calculate_and_save(params, folder, args.origin)
        import tkinter as tk
        root = tk.Tk()
        app = MTWindow(root, smoke=args.gui_check, params=params, export_origin=args.origin,
                       output_root=args.out.expanduser().resolve() if args.out else None)
        if args.gui_check:
            root.withdraw()
            root.after(180000, lambda: root.destroy())
        root.mainloop()
        return 0 if not args.gui_check or app.smoke_passed else 1
    except Exception as exc:
        if sys.stderr is not None:
            print(f'运行失败：{exc}', file=sys.stderr, flush=True)
        else:
            from tkinter import messagebox
            messagebox.showerror('精馏计算启动失败', str(exc))
        return 1


if __name__ == '__main__':
    sys.exit(main())
