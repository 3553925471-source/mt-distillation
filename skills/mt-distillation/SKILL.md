---
name: mt-distillation
license: MIT
description: Calculate binary distillation theoretical trays with constant relative volatility, generate McCabe–Thiele diagrams, launch the local input window, or export editable Origin projects on Windows. Use for stepwise tray calculations and feed-tray placement under this model.
---

# MT Distillation

Use the bundled numerical solver for results. This skill requires local command execution; opening the desktop window also requires a local graphical session. Do not claim that a browser-only conversation can open the user's desktop.

## Locate and prepare

Resolve all paths relative to this SKILL.md directory, not the shell's current directory. In the commands below, `<skill>` is its absolute directory and `<python>` is an available Python 3.10+ interpreter. Quote paths, including paths containing spaces. In PowerShell, invoke a quoted executable using `&`.

Check the environment without installing:

```text
<python> <skill>/scripts/bootstrap.py --check
```

If missing, and dependency installation is within the user's request and the host's permissions, run the same command without `--check`. This installs matplotlib into `<skill>/.venv`. For explicitly requested Origin output, add `--origin` during setup. Origin itself must already be installed and usable on Windows; the Python package does not install or license Origin. Do not require Origin for ordinary calculation.

Use `<skill>/.venv/Scripts/python.exe` on Windows or `<skill>/.venv/bin/python` elsewhere. Do not copy a virtual environment between machines. Tkinter must be provided by the user's Python distribution; this release's desktop workflow is tested on Windows.

## Choose the requested workflow

- **Open the calculator:** on Windows, start `<skill>/.venv/Scripts/pythonw.exe` with `<skill>/scripts/launch.py` using the host's local process-launch facility. The launcher records errors and shows an error dialog. Do not wait for the user to close the window before acknowledging launch. For a foreground or diagnostic launch, run `scripts/mt_distillation.py` without `--cli`. `--config` can prefill known inputs. Opening a window alone does not mean a calculation was performed.
- **Calculate from a problem:** read [model.md](references/model.md), collect inputs, write a JSON file in the user's working/output directory, and run the CLI below. Use a new output directory each time. Do not substitute the bundled example or GUI defaults for missing user inputs. If only the flow-rate basis is unspecified, explain an assumed basis before reporting absolute flows; plate count is independent of that scale.

```text
<runtime> <skill>/scripts/mt_distillation.py --cli --config <input.json> --out <new-output-directory>
```

Append `--origin` only when requested. The CLI requires a config file and does not open the input window. If the user requests a headless calculation, do not launch the GUI.

## Read and report

Read `results.json` from the output directory. Report `summary.N_trays_fractional` as an approximate fractional tower tray count, `summary.N_trays_integer` as the rounded-up count, and `summary.feed_stage_from_top` for the feed tray. These tray counts exclude the reboiler. Link the PNG/SVG and, if created, OPJU file. Use `operating` for flow rates, minimum reflux and operating-line coefficients; use `stages` for individual compositions.

The total equilibrium-stage fields are internal audit data, not the requested tower tray count. The final row is the reboiler-equivalent terminal step, not an additional numbered tower tray. The fractional count is endpoint interpolation, not a fractional physical tray. Preserve numeric labels below horizontal staircase segments.

Exit code 0 means success; 1 is an input/environment/runtime error; 2 is CLI usage error; 3 means ordinary calculation succeeded but Origin export failed. For code 3, report available results and read `origin_error.txt`; do not claim that an OPJU file was produced. If execution fails or is unavailable, explain that limit rather than inventing a result.

Use [example_7_15.json](references/example_7_15.json) only for the textbook example or an explicit installation check. Its expected tower tray count is about 13.2758 with feed tray 8.
