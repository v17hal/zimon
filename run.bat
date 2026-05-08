@echo off
REM ZIMON Version 2 — modular UI (main_v2.py)
REM PySpin / FLIR is optional (only for FLIR cameras). Webcam and Basler do not need it.

cd /d "%~dp0"

echo Starting ZIMON Version 2...
echo.

where py >nul 2>&1
if %ERRORLEVEL% equ 0 (
  py -3 main_v2.py
  goto :done
)

where python >nul 2>&1
if %ERRORLEVEL% equ 0 (
  python main_v2.py
  goto :done
)

echo ERROR: Python was not found on PATH.
echo Install Python 3.10+ from https://www.python.org/downloads/ ^(enable "Add python.exe to PATH"^).
pause
exit /b 1

:done
if errorlevel 1 (
  echo.
  echo The application exited with an error. Read the messages above.
  pause
)
exit /b %ERRORLEVEL%
