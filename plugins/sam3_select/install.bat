@echo off
REM ============================================================
REM  gimp-sam-select — one-click installer for Windows.
REM  Usage: download this repo (ZIP or git clone), then
REM  DOUBLE-CLICK this file. Nothing else to do: it copies the
REM  plugin into your GIMP user folder. Then restart GIMP.
REM ============================================================
setlocal
cd /d "%~dp0"

set SRC=%~dp0sam3_select
if not exist "%SRC%\sam3_select.py" (
  echo [ERROR] sam3_select\sam3_select.py not found next to this script.
  echo         Run install.bat from the repo folder you downloaded.
  pause
  exit /b 1
)

REM Pick the newest existing GIMP 3 user folder; otherwise assume 3.2
REM (GIMP creates it on first launch and will pick our files up).
REM NOTE: the loop overwrites DEST, so list OLDEST first — newest wins.
set DEST=
for %%V in (2.99 3.0 3.2) do (
  if exist "%APPDATA%\GIMP\%%V\plug-ins" set DEST=%APPDATA%\GIMP\%%V\plug-ins\sam3_select
)
if not defined DEST set DEST=%APPDATA%\GIMP\3.2\plug-ins\sam3_select

mkdir "%DEST%" 2>nul
mkdir "%DEST%\models" 2>nul
copy /Y "%SRC%\sam3_select.py" "%DEST%\" >nul
if errorlevel 1 (
  echo [ERROR] Could not copy to "%DEST%".
  pause
  exit /b 1
)

REM Carry any weights you already have (e.g. copied from another PC).
if exist "%SRC%\models\*.pt" copy /Y "%SRC%\models\*.pt" "%DEST%\models\" >nul

echo.
echo [OK] Installed to: %DEST%
echo.
echo Next steps:
echo   1. Restart GIMP (close it fully first).
echo   2. Open an image: Select -^> SAM3 Interactive Select.
echo   3. First AI run downloads the SAM 2 tiny model (~156 MB) into
echo      the models folder by itself. No setup needed for that.
echo.
echo Optional, for the big guns (needs Python on PATH):
echo   python "%DEST%\sam3_select.py" --setup
echo   (adds GrabCut support; --setup --with-ai adds SAM 3, ~3.4 GB)
echo.
pause
