@echo off
title Cybersecurity RAG Engine Launcher
echo ========================================================================
echo   Launching RAG Engine, Migrations, and Server
echo ========================================================================
cd /d "%~dp0"

IF EXIST ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" start_rag.py %*
) ELSE (
    python start_rag.py %*
)
pause
