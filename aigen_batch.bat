@echo off
rem Generates the images of every request in a folder (docs/options.md):     aigen_batch.bat requests_folder output_folder
rem Python comes from bin\_python.bat (the same lookup as bin/_python.sh). Exit code 2 without it.
setlocal
set "PY="
call "%~dp0bin\_python.bat"
if not defined PY exit /b 2
"%PY%" -m aigen.batch %*
exit /b %ERRORLEVEL%
