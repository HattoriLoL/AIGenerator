@echo off
rem The web interface, at http://127.0.0.1:7860 (docs/web.md):     aigen_web.bat [--port N] [--open]
rem Python comes from bin\_python.bat (the same lookup as bin/_python.sh). Exit code 2 without it.
setlocal
set "PY="
call "%~dp0bin\_python.bat"
if not defined PY exit /b 2
"%PY%" -m aigen.web %*
exit /b %ERRORLEVEL%
