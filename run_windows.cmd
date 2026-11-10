@echo off
setlocal
cd /d "%~dp0"
if defined CONDA_PREFIX (
    python "%~dp0extract_flir.py" --interactive
) else (
    where py >nul 2>nul
    if not errorlevel 1 (
        py -3 "%~dp0extract_flir.py" --interactive
    ) else (
        python "%~dp0extract_flir.py" --interactive
    )
)
echo.
echo See README.md for installation and configuration.
pause
