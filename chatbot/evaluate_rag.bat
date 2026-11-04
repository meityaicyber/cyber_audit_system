@echo off
title Cybersecurity RAG Evaluation Benchmark Suite
echo ========================================================================
echo   Running Cybersecurity RAG Evaluation Benchmark Suite
echo ========================================================================
cd /d "%~dp0"

IF EXIST "ragengine\.venv\Scripts\python.exe" (
    "ragengine\.venv\Scripts\python.exe" evaluate_rag.py %*
) ELSE IF EXIST ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" evaluate_rag.py %*
) ELSE IF EXIST "E:\rag\ragengine\.venv\Scripts\python.exe" (
    "E:\rag\ragengine\.venv\Scripts\python.exe" evaluate_rag.py %*
) ELSE (
    python evaluate_rag.py %*
)
pause
