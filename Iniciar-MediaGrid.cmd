@echo off
cd /d "%~dp0"
if not exist ".env" goto setup
if not exist ".venv" goto setup
if not exist "node_modules" goto setup
goto start

:setup
echo Preparando o MediaGrid neste computador...
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\bootstrap.ps1"
if errorlevel 1 goto failed

:start
echo Abrindo http://localhost:3000
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\dev.ps1"
if errorlevel 1 goto failed
goto end

:failed
echo.
echo O MediaGrid nao iniciou. Veja a mensagem acima e o arquivo SETUP.md.
pause

:end
