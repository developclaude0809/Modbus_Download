@echo off
setlocal

rem Build Modbus download.exe from main.py using Nuitka
set "SCRIPT_DIR=%~dp0"
set "ENTRY_POINT=%SCRIPT_DIR%main.py"

if not exist "%ENTRY_POINT%" (
  echo [ERROR] main.py not found at "%ENTRY_POINT%".
  exit /b 1
)

pushd "%SCRIPT_DIR%" >nul

rem Clean previous Nuitka outputs
for %%d in (
  "main.build" "main.dist" "main.onefile-build"
  "Modbus download.build" "Modbus download.dist"
) do (
  if exist "%%~d" rmdir /s /q "%%~d"
)
if exist "Modbus download.exe" del /f /q "Modbus download.exe"

python -m nuitka ^
  --onefile ^
  --windows-disable-console ^
  --enable-plugin=tk-inter ^
  --assume-yes-for-downloads ^
  --output-filename="Modbus download.exe" ^
  --msvc=latest ^
  main.py

set "BUILD_RESULT=%ERRORLEVEL%"
if %BUILD_RESULT% neq 0 (
  echo.
  echo Build failed with error level %BUILD_RESULT%.
  popd
  exit /b %BUILD_RESULT%
)

echo.
echo Done: "%SCRIPT_DIR%Modbus download.exe"
popd
pause
