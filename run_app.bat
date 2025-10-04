:: DailyHelper - Community Help Platform Launcher
:: Activates virtual environment and runs the Flask application

@echo off
title DailyHelper - Community Help Platform

:: Activate virtual environment and run Flask app
echo Starting DailyHelper application...
echo.
echo The app will be available at: http://127.0.0.1:5000
echo Press Ctrl+C to stop the server
echo.
call myenv\Scripts\activate.bat && python app.py

:: If the app exits, keep the window open
echo.
echo Application stopped.
pause
