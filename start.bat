@echo off
setlocal
cd /d "%~dp0"
title NeuralDeck

rem Prefer the project's own virtual environment when it exists.
if exist ".venv\Scripts\python.exe" (
    set "PYTHON_EXE=.venv\Scripts\python.exe"
    goto :run
)

where py >nul 2>&1
if not errorlevel 1 (
    set "PYTHON_EXE=py -3"
    goto :run
)
where python >nul 2>&1
if not errorlevel 1 (
    set "PYTHON_EXE=python"
    goto :run
)
where python3 >nul 2>&1
if not errorlevel 1 (
    set "PYTHON_EXE=python3"
    goto :run
)

echo What: Python 3.10+ was not found in PATH.
echo Why: NeuralDeck needs Python to run main.py.
echo Fix: install Python 3.10+ from https://www.python.org/ and double-click start.bat again.
echo.
pause
exit /b 1

:run
echo Starting NeuralDeck with %PYTHON_EXE% ...
%PYTHON_EXE% main.py %*
if errorlevel 1 (
    echo.
    echo What: NeuralDeck exited with an error.
    echo Why: see the traceback above.
    echo Fix: run "pip install -r requirements.txt", start LM Studio on port 1234,
    echo       then double-click start.bat again.
    echo.
    pause
)

endlocal
