@echo off
echo ========================================
echo  ZIMON Desktop App — Build Installer
echo ========================================
echo.

REM Clean previous builds
if exist dist rmdir /s /q dist
if exist build rmdir /s /q build
echo [1/3] Cleaned previous build artifacts.

REM Run PyInstaller
echo [2/3] Building executable...
pyinstaller zimon.spec --noconfirm
if errorlevel 1 (
    echo ERROR: Build failed.
    pause
    exit /b 1
)

echo [3/3] Build complete!
echo.
echo Output: dist\ZIMON\ZIMON.exe
echo.
echo To distribute: zip the entire dist\ZIMON\ folder
echo   or use Inno Setup / NSIS to create a proper installer from dist\ZIMON\
echo.
pause
