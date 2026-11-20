@echo off
rem The whole suite on Windows (tests/run.sh on Linux): tests\test_contract.py and tests\test_pure.py, on any Python
rem 3.11+, without torch or a GPU. No test generates an image (AGENTS.md, "Testing"). The Python: the
rem AIGEN_PYTHON_TESTS variable, else the one bin\_python.bat finds (exit code 2 without it). Exit code 0 when
rem everything passes.
setlocal
for %%i in ("%~dp0..") do set "ROOT=%%~fi\"
set "PY="
if not defined AIGEN_PYTHON_TESTS goto :lookup
set "PY=%AIGEN_PYTHON_TESTS:"=%"
goto :run
:lookup
call "%~dp0..\bin\_python.bat"
if not defined PY exit /b 2
:run
set "FAILED=0"
for %%t in (test_contract.py test_pure.py) do (
    echo == %%t
    "%PY%" "%ROOT%tests\%%t" || set "FAILED=1"
)
if "%FAILED%"=="0" (echo == all passed) else (1>&2 echo == FAILED)
exit /b %FAILED%
