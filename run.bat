@echo off
REM Job Search Agent — Windows Launcher

echo Starting Job Search Agent...
cd /d %~dp0

REM Check if setup has been done
if not exist ".env" (
    echo First time? Running setup wizard...
    python setup.py
    if errorlevel 1 (
        echo Setup failed. Exiting.
        pause
        exit /b 1
    )
)

REM Run the agent
python main.py --find
pause
