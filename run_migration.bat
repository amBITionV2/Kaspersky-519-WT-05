:: Migration script launcher
:: Activates virtual environment and runs migration

@echo off
call myenv\Scripts\activate.bat
python scripts\migrate_sqlite.py
