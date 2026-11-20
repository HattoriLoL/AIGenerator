@echo off
rem The Python of the AIGenerator environment, for the Windows launchers (the same lookup as bin/_python.sh on Linux).
rem Called with "call" and without setlocal: PY (the Python) and ROOT (the repository root, with the backslash at the
rem end) stay for the caller, and the root goes on PYTHONPATH. The order: the AIGEN_PYTHON variable and the root's
rem .venv\Scripts\python.exe (the one setup.bat creates). With neither: ERROR on stderr, PY stays empty and the caller
rem ends with exit code 2.
for %%i in ("%~dp0..") do set "ROOT=%%~fi\"
set "PY="
if not defined AIGEN_PYTHON goto :venv
set "PY=%AIGEN_PYTHON:"=%"
goto :path
:venv
if exist "%ROOT%.venv\Scripts\python.exe" set "PY=%ROOT%.venv\Scripts\python.exe"
if defined PY goto :path
1>&2 echo ERROR: the AIGenerator environment is not installed: run setup.bat ^(or set AIGEN_PYTHON^)
:path
if defined PYTHONPATH goto :append
set "PYTHONPATH=%ROOT:~0,-1%"
exit /b 0
:append
set "PYTHONPATH=%ROOT:~0,-1%;%PYTHONPATH%"
exit /b 0
