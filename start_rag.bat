@echo off
title Cybersecurity RAG Engine & Migrations Launcher
echo ========================================================================
echo   Launching Cybersecurity RAG Engine, Migrations, and Server
echo ========================================================================
cd /d "%~dp0"

IF EXIST "chatbot\.venv\Scripts\python.exe" (
    "chatbot\.venv\Scripts\python.exe" start_rag.py %*
) ELSE IF EXIST ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" start_rag.py %*
) ELSE (
    python start_rag.py %*
)
pause

