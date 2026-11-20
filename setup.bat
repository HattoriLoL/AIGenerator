@echo off
rem Installs AIGenerator on Windows with one command: double-click it, or run it in a Command Prompt (docs/windows.md).
rem     setup.bat [--no-models] [--no-shortcut] [--verify] [--no-gpu-check] [--icon FILE] [--remove-shortcut]
rem Safe to run again: it skips what is already done and never overwrites your files. The steps:
rem   1. the NVIDIA GPU check (nvidia-smi);
rem   2. uv, installed with its official installer when it is missing;
rem   3. "uv sync": the environment (Python 3.12 and PyTorch for CUDA 12.8, from pyproject.toml);
rem   4. "python -m aigen.install" with that Python: the folders, the models, config.local.ini and the shortcut.
rem The same options as setup.sh (Linux). Exit code: 0 done, 1 a step failed, 2 a wrong option or no NVIDIA GPU.
rem Started by a double-click, it waits for a key at the end, so the window does not close before it can be read.
setlocal
set "SETUP_ROOT=%~dp0"
set "GPU_CHECK=1"
set "REMOVE="
set "CODE=0"
set "PAUSE_AT_END="
set "_CMDLINE=%cmdcmdline:"=%"
if /i not "%_CMDLINE:/c=%"=="%_CMDLINE%" set "PAUSE_AT_END=1"

:options
if "%~1"=="" goto :gpu
if "%~1"=="--no-gpu-check" (set "GPU_CHECK=" & goto :next)
if "%~1"=="--remove-shortcut" (set "REMOVE=1" & goto :next)
if "%~1"=="--no-models" goto :next
if "%~1"=="--no-shortcut" goto :next
if "%~1"=="--verify" goto :next
if "%~1"=="--icon" goto :icon
if "%~1"=="--help" goto :help
if "%~1"=="-h" goto :help
1>&2 echo ERROR: unknown option: %1
goto :usage
:icon
if "%~2"=="" (1>&2 echo ERROR: --icon needs a file & goto :usage)
shift
:next
shift
goto :options

:gpu
if defined REMOVE goto :install
if not defined GPU_CHECK goto :uv
nvidia-smi -L >nul 2>&1
if not errorlevel 1 goto :uv
1>&2 echo ERROR: no NVIDIA GPU found ^(nvidia-smi is missing or did not answer^). AIGenerator needs an NVIDIA GPU
1>&2 echo with its driver installed. To install anyway: setup.bat --no-gpu-check
set "CODE=2"
goto :end

:uv
set "UV="
for /f "delims=" %%p in ('where uv 2^>nul') do if not defined UV set "UV=%%p"
if not defined UV call :uv_in_home
if defined UV goto :sync
echo == Installing uv (https://docs.astral.sh/uv/)
powershell -NoProfile -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
call :uv_in_home
if defined UV goto :sync
1>&2 echo ERROR: uv could not be installed. Install it by hand ^(https://docs.astral.sh/uv/getting-started/installation/^)
1>&2 echo and run setup.bat again.
set "CODE=1"
goto :end

:sync
echo == uv: %UV%
echo == The environment (uv sync: Python 3.12 and PyTorch for CUDA 12.8; a few GB the first time)
pushd "%SETUP_ROOT%"
"%UV%" sync
set "SYNC=%ERRORLEVEL%"
popd
if "%SYNC%"=="0" goto :install
1>&2 echo ERROR: "uv sync" failed ^(code %SYNC%^): see the messages above, then run setup.bat again.
set "CODE=1"
goto :end

:install
echo == Folders, models, configuration and shortcut
set "PY="
call "%~dp0bin\_python.bat"
if not defined PY goto :no_python
"%PY%" -m aigen.install %*
set "CODE=%ERRORLEVEL%"
goto :end

:no_python
set "CODE=2"
goto :end

:help
echo usage: setup.bat [--no-models] [--no-shortcut] [--verify] [--no-gpu-check] [--icon FILE] [--remove-shortcut]
echo   --no-models        do not download the models
echo   --no-shortcut      do not create the shortcuts
echo   --verify           check the SHA256 of the models already in place too
echo   --no-gpu-check     continue without an NVIDIA GPU
echo   --icon FILE        the shortcuts' icon (an .ico file)
echo   --remove-shortcut  only remove the shortcuts, and stop
goto :end

:usage
1>&2 echo usage: setup.bat [--no-models] [--no-shortcut] [--verify] [--no-gpu-check] [--icon FILE] [--remove-shortcut]
set "CODE=2"
goto :end

rem ---- UV = uv.exe where its installer puts it, when the PATH of this window does not have it yet
:uv_in_home
if exist "%USERPROFILE%\.local\bin\uv.exe" (set "UV=%USERPROFILE%\.local\bin\uv.exe" & exit /b 0)
if exist "%USERPROFILE%\.cargo\bin\uv.exe" set "UV=%USERPROFILE%\.cargo\bin\uv.exe"
exit /b 0

:end
if defined PAUSE_AT_END pause
exit /b %CODE%
