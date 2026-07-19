@echo off

start "BackendServer" uv run serve --backend
timeout /t 2 /nobreak >nul

start "FrontendServer" uv run serve --frontend
timeout /t 2 /nobreak >nul

start msedge http://localhost:5173