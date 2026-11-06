@echo off
REM ============================================================
REM  GIMP Pro Suite — Installer for Windows
REM  Installs ALL 6 Pro Plugins into your GIMP user plug-ins directory:
REM    1. Mesh Warp & Transform Presets (mesh-warp)
REM    2. SAM 3 AI Interactive Select (sam3_select)
REM    3. Adjustment Layers & Layer Effects (adjustment-layer)
REM    4. Vector Shape Generator (gimp-shape-tool)
REM    5. Quick Selection Brush Suite (GIMP-Quick-Selection)
REM    6. Content-Aware Fill (content-aware-fill)
REM ============================================================
setlocal enabledelayedexpansion
cd /d "%~dp0"

echo ============================================================
echo   Installing GIMP Pro Suite (All 6 Plugins)
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

REM --- 1. Mesh Warp ---
echo [1/6] Installing Mesh Warp & Transform Presets...
set MESH_SRC=%~dp0plugins\mesh-warp
set MESH_DEST=%PLUGINS_DIR%\mesh-warp
if exist "%MESH_SRC%\mesh-warp.py" (
  mkdir "%MESH_DEST%" 2>nul
  copy /Y "%MESH_SRC%\*.py" "%MESH_DEST%\" >nul
  echo       [OK] Installed to: %MESH_DEST%
) else (
  echo       [WARN] plugins\mesh-warp files not found. Skipping.
)

REM --- 2. SAM 3 Interactive Select ---
echo [2/6] Installing SAM 3 AI Interactive Select...
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

REM --- 3. Adjustment Layers & Layer Effects ---
echo [3/6] Installing Adjustment Layers & Layer Effects...
set ADJ_SRC=%~dp0plugins\adjustment-layer
set ADJ_DEST=%PLUGINS_DIR%\adjustment-layer
if exist "%ADJ_SRC%\adjustment-layer.py" (
  mkdir "%ADJ_DEST%" 2>nul
  copy /Y "%ADJ_SRC%\*.py" "%ADJ_DEST%\" >nul
  echo       [OK] Installed to: %ADJ_DEST%
) else (
  echo       [WARN] plugins\adjustment-layer files not found. Skipping.
)

REM --- 4. Vector Shape Tool ---
echo [4/6] Installing Vector Shape Tool...
set SHAPE_SRC=%~dp0plugins\gimp-shape-tool
set SHAPE_DEST=%PLUGINS_DIR%\gimp-shape-tool
if exist "%SHAPE_SRC%\gimp-shape-tool.py" (
  mkdir "%SHAPE_DEST%" 2>nul
  copy /Y "%SHAPE_SRC%\*.py" "%SHAPE_DEST%\" >nul
  echo       [OK] Installed to: %SHAPE_DEST%
) else (
  echo       [WARN] plugins\gimp-shape-tool files not found. Skipping.
)

REM --- 5. Quick Selection Brush Suite ---
echo [5/6] Installing Quick Selection Brush Suite...
set QS_SRC=%~dp0plugins\GIMP-Quick-Selection
set QS_DEST=%PLUGINS_DIR%\GIMP-Quick-Selection
if exist "%QS_SRC%\GIMP-Quick-Selection.py" (
  mkdir "%QS_DEST%" 2>nul
  copy /Y "%QS_SRC%\*.py" "%QS_DEST%\" >nul
  echo       [OK] Installed to: %QS_DEST%
) else (
  echo       [WARN] plugins\GIMP-Quick-Selection files not found. Skipping.
)

REM --- 6. Content-Aware Fill ---
echo [6/6] Installing Content-Aware Fill...
set CAF_SRC=%~dp0plugins\content-aware-fill
set CAF_DEST=%PLUGINS_DIR%\content-aware-fill
if exist "%CAF_SRC%\content-aware-fill.py" (
  mkdir "%CAF_DEST%" 2>nul
  copy /Y "%CAF_SRC%\*.py" "%CAF_DEST%\" >nul
  if exist "%CAF_SRC%\caf_engine" (
    mkdir "%CAF_DEST%\caf_engine" 2>nul
    copy /Y "%CAF_SRC%\caf_engine\*.py" "%CAF_DEST%\caf_engine\" >nul
  )
  echo       [OK] Installed to: %CAF_DEST%
) else (
  echo       [WARN] plugins\content-aware-fill files not found. Skipping.
)

echo.
echo ============================================================
echo   All 6 Plugins Installed Successfully!
echo ============================================================
echo.
echo Next steps:
echo   1. Restart GIMP 3.
echo   2. Access your new tools in GIMP menus:
echo      - Mesh Warp:        Filters -^> Distorts -^> Mesh Warp...
echo      - SAM 3 AI Select:  Select -^> SAM3 Interactive Select
echo      - Adjustment Layer: Layer -^> Adjustment Layer / Layer Effects
echo      - Vector Shapes:    Image / Tools -^> Vector Shape Generator...
echo      - Quick Selection:  Select -^> Quick Selection Brush...
echo      - Content-Aware:    Edit -^> Content-Aware Fill...
echo.
pause
