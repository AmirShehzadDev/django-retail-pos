@echo off
setlocal
title Retail POS Shutdown

set "POS_DIRECTORY=C:\RetailPOS"
set "DOCKER_CLI=%ProgramFiles%\Docker\Docker\DockerCli.exe"

if not exist "%POS_DIRECTORY%\.env" goto pos_missing

where docker >nul 2>&1
if errorlevel 1 goto docker_missing

docker info >nul 2>&1
if errorlevel 1 goto backup_unavailable

echo Creating verified shutdown backup...
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%POS_DIRECTORY%\deploy\Backup-Database.ps1" -Purpose shutdown
if errorlevel 1 goto backup_failed

echo Stopping Retail POS...
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%POS_DIRECTORY%\deploy\Stop-POS.ps1"
if errorlevel 1 goto pos_failed

echo.
echo Retail POS stopped. Web and database containers are stopped.
echo Data and backups were retained.

:stop_desktop
echo Shutting down Docker Desktop...
docker desktop stop --timeout 120 >nul 2>&1
if not errorlevel 1 goto desktop_stopped

if exist "%DOCKER_CLI%" (
    "%DOCKER_CLI%" -Shutdown >nul 2>&1
    if not errorlevel 1 goto desktop_stopped
)
goto desktop_failed

:desktop_stopped
echo Docker Desktop stopped. All Docker containers on this computer are now stopped.
timeout /t 5 /nobreak >nul
goto finished

:pos_missing
echo Retail POS is not installed at %POS_DIRECTORY%.
goto failed

:docker_missing
echo The Docker command is unavailable. Install or repair Docker Desktop.
goto failed

:pos_failed
echo Retail POS could not be stopped. Check Docker Desktop and the POS logs.
goto failed

:backup_failed
echo Shutdown was cancelled because a verified database backup could not be created.
echo Retail POS and Docker Desktop remain running. Resolve the backup error before retrying.
goto failed

:backup_unavailable
echo Shutdown was not performed because Docker Desktop is not ready for a verified backup.
echo If Docker Desktop is already stopped, no further action is required.
goto failed

:desktop_failed
echo Retail POS containers were stopped, but Docker Desktop could not be shut down gracefully.
echo Close Docker Desktop manually. Do not force-end database processes.

:failed
pause
exit /b 1

:finished
endlocal
exit /b 0
