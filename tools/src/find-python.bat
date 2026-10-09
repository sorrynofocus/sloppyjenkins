@echo off
setlocal EnableExtensions
set "FOUND_PY="

where py >nul 2>nul
if not errorlevel 1 (
    for /f "usebackq delims=" %%P in (`py -3 -c "import sys; print(sys.executable)" 2^>nul`) do set "FOUND_PY=%%P"
)

if not defined FOUND_PY (
    where python >nul 2>nul
    if not errorlevel 1 (
        for /f "usebackq delims=" %%P in (`python -c "import sys; print(sys.executable)" 2^>nul`) do set "FOUND_PY=%%P"
    )
)

if not defined FOUND_PY goto python_missing

"%FOUND_PY%" "%~dp0sloppy_tool.py" check-python >nul
if errorlevel 1 goto python_missing

endlocal & set "PY=%FOUND_PY%"
exit /b 0

:python_missing
echo ERROR: Python 3.10 or newer is required ^(for example: winget install Python.Python.3.12^).
endlocal
exit /b 1
