@echo off
REM ============================================================
REM  Sk7ld-AI - Windows launcher
REM  Runs the GUI.  Use:  run.bat --cli   for terminal mode.
REM ============================================================
setlocal
cd /d "%~dp0"

where py >nul 2>nul
if %errorlevel%==0 (
    py sk7ld_ai.py %*
) else (
    python sk7ld_ai.py %*
)
endlocal
