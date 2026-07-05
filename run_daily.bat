@echo off
rem Daily stock-agent run — invoked by Windows Task Scheduler every weekday morning.
cd /d C:\Users\eriku\stock-agent
echo ================================ >> reports\run_log.txt
echo Run started %date% %time% >> reports\run_log.txt
venv\Scripts\python.exe -m src.main >> reports\run_log.txt 2>&1
echo Run finished %date% %time% (exit %errorlevel%) >> reports\run_log.txt
