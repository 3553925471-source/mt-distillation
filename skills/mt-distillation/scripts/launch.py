"""Launch the desktop window without a console; retain diagnostic output."""
import os
from pathlib import Path
import subprocess
import sys
from datetime import datetime
from tkinter import messagebox


def main():
    logs = Path(os.environ.get('MT_OUTPUT_DIR') or (Path.home() / 'Documents' / 'MT_Distillation')).expanduser() / 'logs'
    logs.mkdir(parents=True, exist_ok=True)
    log = logs / ('launch_' + datetime.now().strftime('%Y%m%d_%H%M%S_%f') + '.log')
    runtime = Path(sys.executable)
    if runtime.name.lower() == 'pythonw.exe':
        runtime = runtime.with_name('python.exe')
    env = dict(os.environ, PYTHONUTF8='1', PYTHONIOENCODING='utf-8')
    options = {'creationflags': subprocess.CREATE_NO_WINDOW} if os.name == 'nt' else {}
    with log.open('w', encoding='utf-8') as stream:
        result = subprocess.run([str(runtime), str(Path(__file__).with_name('mt_distillation.py')), *sys.argv[1:]],
                                stdout=stream, stderr=stream, env=env, **options)
    if result.returncode:
        messagebox.showerror('精馏计算运行失败', f'请查看日志：\n{log}\n\n也可在命令行运行程序查看错误。')
    return result.returncode


if __name__ == '__main__':
    try:
        sys.exit(main())
    except Exception as exc:
        messagebox.showerror('精馏计算启动失败', str(exc))
        sys.exit(1)
