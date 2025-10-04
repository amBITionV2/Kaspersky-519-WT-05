:: DailyHelper - Blockchain Watcher
:: Activates virtual environment and runs the blockchain watcher for live mining

@echo off
title DailyHelper - Blockchain Watcher

:: Activate virtual environment and run blockchain watcher
echo Starting blockchain watcher...
echo.
echo Watching internal app blocks (DB) for live mining...
echo You will see HTTP requests being mined into blocks in real-time!
echo Press Ctrl+C to stop watching
echo.
call myenv\Scripts\activate.bat && python watch_blocks.py

:: If the watcher exits, keep the window open
echo.
echo Blockchain watcher stopped.
pause
