@echo off
rem What the AIGenerator shortcut runs (setup.bat creates it; docs/windows.md): if the interface already answers on
rem its port, it only opens the browser; otherwise it starts the interface in this console window and opens the
rem browser when it is ready. Closing this window stops the interface and frees the GPU memory.
setlocal
set "PY="
call "%~dp0bin\_python.bat"
if not defined PY goto :no_python
set "PORT=7860"
set "PORT_FILE=%TEMP%\aigen_port_%RANDOM%.txt"
"%PY%" -c "from aigen import config; print(config.read().port)" > "%PORT_FILE%" 2>nul
if not errorlevel 1 set /p PORT=<"%PORT_FILE%"
del "%PORT_FILE%" >nul 2>&1
curl -fs -o nul --max-time 2 "http://127.0.0.1:%PORT%/" >nul 2>&1
if errorlevel 1 goto :start
start "" "http://127.0.0.1:%PORT%/"
exit /b 0

:start
echo AIGenerator: the interface opens in the browser when it is ready.
echo Close this window to stop it (and free the GPU memory).
echo.
"%PY%" -m aigen.web --open %*
set "CODE=%ERRORLEVEL%"
echo.
echo The interface stopped (code %CODE%).
pause
exit /b %CODE%

:no_python
pause
exit /b 2
