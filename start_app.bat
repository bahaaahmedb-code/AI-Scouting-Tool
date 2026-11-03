@echo off
title Moneyball EPL Starter
echo ==============================================
echo       Starting Moneyball EPL Webapp
echo ==============================================

cd /d "%~dp0backend"
echo [1/2] Starting Backend (FastAPI on port 8000)...
start "Moneyball Backend" cmd /k ".\.venv\Scripts\uvicorn.exe app.api:app --port 8000"

timeout /t 2 /nobreak >nul

cd /d "%~dp0frontend"
echo [2/2] Starting Frontend (Vite on port 5173)...
start "Moneyball Frontend" cmd /k "npm run dev"

timeout /t 2 /nobreak >nul

echo Opening browser at http://localhost:5173 ...
start http://localhost:5173

echo ==============================================
echo Moneyball EPL is now running!
echo You can leave these windows open while using the app.
echo ==============================================
