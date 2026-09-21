@echo off
setlocal
pushd "%~dp0"
where py >nul 2>&1
if not errorlevel 1 (
    py -3 "skills\mt-distillation\scripts\bootstrap.py" %*
) else (
    python "skills\mt-distillation\scripts\bootstrap.py" %*
)
set "MT_SETUP_EXIT=%ERRORLEVEL%"
if not "%MT_SETUP_EXIT%"=="0" (
    echo Setup failed. Install Python 3.10+ with Tcl/Tk and pip, then retry.
    pause
)
popd
exit /b %MT_SETUP_EXIT%
