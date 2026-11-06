@echo off
REM ============================================================
REM  GIMP Pro Suite — Installer for Windows
REM  Installs both plugins into your GIMP user plug-ins directory:
REM    - Mesh Warp & Transform Presets (mesh-warp)
REM    - SAM 3 AI Interactive Select (sam3_select)
REM ============================================================
setlocal
cd /d "%~dp0"

echo ============================================================
echo   Installing GIMP Pro Suite Plugins
echo ============================================================
echo.

REM Determine GIMP plug-ins folder
set PLUGINS_DIR=
for %%V in (2.99 3.0 3.2) do (
  if exist "%APPDATA%\GIMP\%%V\plug-ins" set PLUGINS_DIR=%APPDATA%\GIMP\%%V\plug-ins
)
if not defined PLUGINS_DIR set PLUGINS_DIR=%APPDATA%\GIMP\3.2\plug-ins

echo Target plug-ins directory:
echo   %PLUGINS_DIR%
echo.

REM --- 1. Install Mesh Warp ---
echo [1/2] Installing Mesh Warp & Transform Presets...
set MESH_SRC=%~dp0plugins\mesh-warp
set MESH_DEST=%PLUGINS_DIR%\mesh-warp
if exist "%MESH_SRC%\mesh-warp.py" (
  mkdir "%MESH_DEST%" 2>nul
  copy /Y "%MESH_SRC%\*.py" "%MESH_DEST%\" >nul
  echo       [OK] Installed to: %MESH_DEST%
) else (
  echo       [WARN] plugins\mesh-warp files not found. Skipping.
)

REM --- 2. Install SAM 3 Interactive Select ---
echo [2/2] Installing SAM 3 AI Interactive Select...
set SAM_SRC=%~dp0plugins\sam3_select
set SAM_DEST=%PLUGINS_DIR%\sam3_select
if exist "%SAM_SRC%\sam3_select.py" (
  mkdir "%SAM_DEST%" 2>nul
  mkdir "%SAM_DEST%\models" 2>nul
  copy /Y "%SAM_SRC%\sam3_select.py" "%SAM_DEST%\" >nul
  if exist "%SAM_SRC%\models\*.pt" copy /Y "%SAM_SRC%\models\*.pt" "%SAM_DEST%\models\" >nul
  echo       [OK] Installed to: %SAM_DEST%
) else (
  echo       [WARN] plugins\sam3_select files not found. Skipping.
)

echo.
echo ============================================================
echo   Installation Complete!
echo ============================================================
echo.
echo Next steps:
echo   1. Restart GIMP 3.
echo   2. Find Mesh Warp in:
echo      Filters -^> Distorts -^> Mesh Warp...
echo   3. Find SAM 3 AI Selection in:
echo      Select -^> SAM3 Interactive Select
echo.
pause
