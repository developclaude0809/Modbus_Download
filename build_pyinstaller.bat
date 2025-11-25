@echo off
setlocal

rem ================================================================
rem Build RS485 Serial Tool using PyInstaller (alternative to Nuitka)
rem PyInstaller is easier to use but may have slightly higher AV detection
rem ================================================================

set "SCRIPT_DIR=%~dp0"
set "ENTRY_POINT=%SCRIPT_DIR%main.py"
set "OUTPUT_NAME=RS485_Modbus_Tool"

echo ================================================================
echo RS485 Serial Communication Tool - PyInstaller Build
echo ================================================================
echo.

rem Check if main.py exists
if not exist "%ENTRY_POINT%" (
  echo [ERROR] main.py not found at "%ENTRY_POINT%".
  pause
  exit /b 1
)

rem Check if PyQt5 is installed
python -c "import PyQt5" 2>nul
if %ERRORLEVEL% neq 0 (
  echo [ERROR] PyQt5 is not installed.
  echo Please install it first: pip install PyQt5
  pause
  exit /b 1
)

rem Check if pyserial is installed
python -c "import serial" 2>nul
if %ERRORLEVEL% neq 0 (
  echo [ERROR] pyserial is not installed.
  echo Please install it first: pip install pyserial
  pause
  exit /b 1
)

rem Check if PyInstaller is installed
python -c "import PyInstaller" 2>nul
if %ERRORLEVEL% neq 0 (
  echo [ERROR] PyInstaller is not installed.
  echo Please install it first: pip install pyinstaller
  pause
  exit /b 1
)

pushd "%SCRIPT_DIR%" >nul

echo Cleaning previous build outputs...
rem Clean previous PyInstaller outputs
for %%d in (
  "build" "dist" "__pycache__"
) do (
  if exist "%%~d" (
    echo   Removing %%~d
    rmdir /s /q "%%~d"
  )
)

if exist "%OUTPUT_NAME%.spec" (
  echo   Removing old spec file
  del /f /q "%OUTPUT_NAME%.spec"
)

echo.
echo Building with PyInstaller...
echo This may take a few minutes...
echo.

rem PyInstaller build with options to reduce AV detection
pyinstaller ^
  --onefile ^
  --console ^
  --name="%OUTPUT_NAME%" ^
  --noupx ^
  --clean ^
  --noconfirm ^
  --add-data "README.md;." ^
  main.py

set "BUILD_RESULT=%ERRORLEVEL%"
if %BUILD_RESULT% neq 0 (
  echo.
  echo ================================================================
  echo Build FAILED with error level %BUILD_RESULT%
  echo ================================================================
  popd
  pause
  exit /b %BUILD_RESULT%
)

rem Move executable to root directory
if exist "dist\%OUTPUT_NAME%.exe" (
  echo.
  echo Moving executable to root directory...
  move /y "dist\%OUTPUT_NAME%.exe" "%SCRIPT_DIR%" >nul
)

echo.
echo ================================================================
echo Build SUCCESS!
echo ================================================================
echo.
echo Output: "%SCRIPT_DIR%%OUTPUT_NAME%.exe"
echo.
echo IMPORTANT: To minimize antivirus false positives:
echo - This build uses --console to show transparency
echo - UPX compression is disabled (--noupx)
echo - Consider code signing the executable
echo - Submit false positives to AV vendors
echo.
echo Cleaning up build folders...
rmdir /s /q "build" 2>nul
rmdir /s /q "dist" 2>nul
echo Done!
echo.
popd
pause
