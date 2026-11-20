@echo off
setlocal

echo ======================================
echo Starting Norfae Intelligence OS
echo ======================================

pushd "%~dp0"

call "%~dp0..\.venv\Scripts\activate.bat"
if errorlevel 1 (
    echo Failed to activate the project virtual environment.
    popd
    pause
    exit /b 1
)

python -m uvicorn app.main:app --host 127.0.0.1 --port 8000

popd
pause
