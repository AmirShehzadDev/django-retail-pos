@echo off
setlocal
title Retail POS Startup

set "POS_DIRECTORY=C:\RetailPOS"
set "DOCKER_DESKTOP=%ProgramFiles%\Docker\Docker\Docker Desktop.exe"
set "POS_HOSTNAME=retailpos"
set "POS_PORT=8000"

if not exist "%POS_DIRECTORY%\.env" goto pos_missing

for /f "tokens=1,* delims==" %%A in ('findstr /B /C:"POS_LOCAL_HOSTNAME=" "%POS_DIRECTORY%\.env"') do set "POS_HOSTNAME=%%B"
for /f "tokens=1,* delims==" %%A in ('findstr /B /C:"POS_APP_PORT=" "%POS_DIRECTORY%\.env"') do set "POS_PORT=%%B"
set "POS_URL=http://%POS_HOSTNAME%:%POS_PORT%"

where docker >nul 2>&1
if errorlevel 1 goto docker_missing

docker info >nul 2>&1
if not errorlevel 1 goto docker_ready

if not exist "%DOCKER_DESKTOP%" goto docker_desktop_missing

echo Starting Docker Desktop...
start "" "%DOCKER_DESKTOP%"
set attempts=0

:wait_for_docker
docker info >nul 2>&1
if not errorlevel 1 goto docker_ready
set /a attempts+=1
if %attempts% GEQ 60 goto docker_timeout
echo Waiting for Docker Desktop...
timeout /t 3 /nobreak >nul
goto wait_for_docker

:docker_ready
echo Starting Retail POS...
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%POS_DIRECTORY%\deploy\Start-POS.ps1"
if errorlevel 1 goto pos_failed

if exist "%ProgramFiles%\Google\Chrome\Application\chrome.exe" (
    start "" "%ProgramFiles%\Google\Chrome\Application\chrome.exe" "%POS_URL%"
    goto finished
)
if exist "%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe" (
    start "" "%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe" "%POS_URL%"
    goto finished
)
start "" "%POS_URL%"
goto finished

:pos_missing
echo Retail POS is not installed at %POS_DIRECTORY%.
goto failed

:docker_missing
echo The Docker command is unavailable. Install or repair Docker Desktop.
goto failed

:docker_desktop_missing
echo Docker Desktop was not found at %DOCKER_DESKTOP%.
goto failed

:docker_timeout
echo Docker Desktop did not become ready within three minutes.
goto failed

:pos_failed
echo Retail POS failed to start. Check Docker Desktop and the POS logs.

:failed
pause
exit /b 1

:finished
endlocal
exit /b 0
