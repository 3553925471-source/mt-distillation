# MT Distillation · 精馏塔理论板计算与 Agent Skill

版本 1.0.0。二元精馏逐板计算、McCabe–Thiele 图、Windows 输入窗口及可选的可编辑 Origin 项目。塔内板数不计再沸器，支持小数插值估算，塔板编号在线下方。

本仓库同时提供桌面程序和自包含 Agent Skill。Skill 是 AI 的操作说明和可执行资源，需要支持 Skill 且能执行本地命令的客户端；普通网页聊天不能仅通过安装本仓库打开本地窗口。本版本不是某一客户端插件市场的专有插件包。

## 网页版与离线网页版

在线使用：**[MT Distillation 精馏计算器](https://3553925471-source.github.io/mt-distillation/)**。

无需安装 Python 或 Origin，在浏览器中输入工况即可逐板计算并绘制 MT 图。支持手机界面、塔内理论板数（不含再沸器）、最佳进料板、操作线、逐板组成，以及 PNG、SVG、JSON 和 Origin 曲线 CSV 下载。塔板编号位于水平阶梯线下方。

点击页面“下载离线网页版”，保存单个 HTML 文件，之后双击即可离线使用。也可直接下载本仓库 `docs/index.html`。计算全部在浏览器内进行；网页不直接控制本机 Origin。生成可编辑 OPJU 项目仍使用下方的 Python 本地版。

网页算法通过 `tests/test_web_model.py` 与 Python 原版交叉验证（需要 Node.js）；GitHub Pages 发布源为 `main` 分支的 `/docs` 目录。

## Windows 双击使用

1. 下载 Release 压缩包或 GitHub 的 Code → Download ZIP，完整解压到可写目录。可使用中文、空格路径；不要求 D 盘。不要直接在压缩包内运行。
2. 安装 Python 3.10 或更高版本，包含 pip 和 Tcl/Tk。建议使用 python.org 的 Windows 安装包。
3. 双击 `setup.bat`，首次安装需要网络，会在 `skills/mt-distillation/.venv` 创建独立环境。
4. 双击 `启动精馏计算.bat`，填写工况并点击“计算并绘图”。首次没有环境时，启动文件也会调用初始化程序。

基础安装不要求 Origin。要导出 Origin，在仓库目录的 PowerShell 中运行：

```powershell
.\setup.bat --origin
```

随后勾选窗口中的 Origin 导出选项。需要用户自己的 Windows Origin 安装和可用许可；依赖安装只安装 Python 接口。Origin 导出失败时保留普通图片和数据。

默认工作根目录为用户的 `Documents\MT_Distillation`，图片和结果位于其中的 `outputs`。启动失败可查看 `logs` 目录，也可在命令行直接运行脚本。虚拟环境不可随文件夹搬到另一台电脑；移动已初始化的项目后，请在新位置重新初始化一个干净的源码副本。

## AI 安装和使用

安装目标是仓库内整个 `skills/mt-distillation` 文件夹，不能只复制 SKILL.md。它包含运行脚本、独立安装器、依赖清单、示例与计数规则，不依赖仓库根目录。

- 支持从 GitHub 子目录安装 Skill 的客户端：提供仓库地址，并指定 `skills/mt-distillation`。
- 手动安装：将整个文件夹复制到该客户端文档指定的 Skills 目录，再按该客户端要求刷新或重启。
- 不同客户端的安装目录、命令和授权方式不同；本项目不假定存在跨平台通用安装命令。

AI 首次运行时，可根据 SKILL.md 执行本 Skill 自带的 `scripts/bootstrap.py`。安装过程需要本地写入和网络权限；运行已安装的普通计算无需联网。客户端应在用户授权的本地环境中执行。

可对 AI 说：

> 使用 mt-distillation 打开精馏计算器。

或：

> 用 mt-distillation 计算：alpha=2.16，zF=0.35，xD=0.94，xW=0.04606060606，q=1.05，R=2.91221014，F=100 kmol/h。给出塔内理论板数、进料板并生成 MT 图。

明确要求 Origin 项目时，AI 才启用 Origin 导出。GUI 示例输入不代表用户工况；CLI 强制要求 JSON 输入文件以避免误用默认值。

## 命令行和 VS Code

从仓库根目录运行（先完成 setup）：

```powershell
& '.\skills\mt-distillation\.venv\Scripts\python.exe' `
  '.\skills\mt-distillation\scripts\mt_distillation.py' `
  --cli `
  --config '.\skills\mt-distillation\references\example_7_15.json' `
  --out '.\outputs\example-7-15'
```

`--out` 必须是尚不存在的结果目录。再次计算时换一个名称，或者省略它以自动生成时间戳目录。追加 `--origin` 可导出 Origin。无 `--cli` 时打开窗口；`--config` 预填窗口，`--out` 指定窗口的结果根目录。

在 VS Code 中选择 `skills/mt-distillation/.venv/Scripts/python.exe` 为解释器，打开 `scripts/mt_distillation.py` 即可运行。也可直接用已装 matplotlib 的 Python 执行；脚本发现 Skill 内的虚拟环境时会优先复用该环境。

需要自定义默认工作目录时，在启动程序前设置环境变量，例如：

```powershell
$env:MT_OUTPUT_DIR = 'D:\MT_Distillation'
& '.\skills\mt-distillation\.venv\Scripts\python.exe' '.\skills\mt-distillation\scripts\mt_distillation.py'
```

若需要安装仅 Skill 的环境，以实际 Skill 路径运行：

```text
python <Skill目录>/scripts/bootstrap.py
python <Skill目录>/scripts/bootstrap.py --check
```

## 模型和结果

适用：恒定相对挥发度、恒摩尔流、全凝器、泡点回流、平衡部分再沸器、单股进料和最佳加料板切换。不是多组分或非理想严格模拟。详情见 [模型说明](skills/mt-distillation/references/model.md)。

7-15 示例应得到塔内理论板数约 **13.2758**、完整板数 **14**、进料板 **8**。小数值是末级线性插值近似，不是实际物理塔板数；最后再沸器等效阶梯不编号。普通 MT 图和 Origin 图均把编号放在水平阶梯线下方。

输出包含 JSON、CSV、PNG、SVG、结果文本；可选 OPJU。JSON 中保留总平衡级数用于复核，但图和用户结果摘要只报告塔内板数。退出码：0 成功；1 计算或环境错误；2 CLI 用法错误；3 普通结果成功、Origin 导出失败。

## 开发验证

从仓库根目录执行：

```powershell
& '.\skills\mt-distillation\.venv\Scripts\python.exe' -m unittest discover -s tests -v
& '.\skills\mt-distillation\.venv\Scripts\python.exe' '.\skills\mt-distillation\scripts\mt_distillation.py' --gui-check
```

普通测试覆盖示例结果、衡算、不同 q、错误输入、非 D 盘且包含空格和中文的 CLI 输出、无 Origin 模块的普通计算、已有目录保护。GUI 检查在本地 Windows 会话运行；GitHub Actions 只验证无窗口计算。Origin 需在有安装和许可的电脑上验证，不能用云端 CI 通过来替代。

## 上传到自己的 GitHub

本地交付不自动创建远程仓库。下面示例需要先安装 Git/GitHub CLI 并完成 `gh auth login`；可自行选择仓库可见性。

```powershell
git init
git add .
git commit -m "Release MT Distillation v1.0.0"
gh repo create mt-distillation --public --source . --remote origin --push
git tag v1.0.0
git push origin v1.0.0
gh release create v1.0.0 --title "MT Distillation v1.0.0" --notes "Windows calculator and self-contained Agent Skill."
```

也可以在 GitHub 网页新建仓库再上传源码。不要上传 `.venv`、缓存、个人输入/计算结果或 Origin 安装文件。MIT 许可仅覆盖本项目文件，第三方软件遵循各自许可。

如需出现在某个 AI 客户端的插件市场中，可在这个 Skill 的基础上添加对应平台的插件清单；当前交付首先提供可从 GitHub 分发的 Skill 和桌面源码包。
