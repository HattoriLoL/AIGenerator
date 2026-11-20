@echo off
rem Generates images (docs/options.md):     aigen.bat output.png [options]     (aigen.bat --help)
rem Python comes from bin\_python.bat (the same lookup as bin/_python.sh). Exit code 2 without it.
setlocal
set "PY="
call "%~dp0bin\_python.bat"
if not defined PY exit /b 2
"%PY%" -m aigen.generate %*
exit /b %ERRORLEVEL%
