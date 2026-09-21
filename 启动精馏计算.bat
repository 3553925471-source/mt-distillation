@echo off
setlocal
pushd "%~dp0"
if not exist "skills\mt-distillation\.venv\Scripts\pythonw.exe" (
    call "%~dp0setup.bat"
    if errorlevel 1 exit /b 1
)
start "" "skills\mt-distillation\.venv\Scripts\pythonw.exe" "skills\mt-distillation\scripts\launch.py" %*
popd
