@echo off
rem Starts NetMonitor. On first run it creates a virtual environment
rem and installs the packages listed in requirements.txt.
cd /d "%~dp0"
if not exist .venv (
    echo Setting up for first run, please wait...
    python -m venv .venv
    .venv\Scripts\python -m pip install -r requirements.txt
)
.venv\Scripts\python main.py
