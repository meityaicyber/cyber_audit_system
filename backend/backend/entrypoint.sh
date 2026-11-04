#!/bin/bash
set -e

echo "Waiting for PostgreSQL to be ready..."
until python -c "
import asyncio, asyncpg, sys, os
async def check():
    try:
        dsn = os.environ.get('DATABASE_URL','').replace('postgresql+asyncpg://','postgresql://')
        conn = await asyncpg.connect(dsn)
        await conn.close()
    except Exception:
        sys.exit(1)
asyncio.run(check())
" 2>/dev/null; do
    echo "PostgreSQL is unavailable - retrying in 2s..."
    sleep 2
done

echo "PostgreSQL is ready!"

echo "Running database migrations..."
cd /app && PYTHONPATH=/app alembic upgrade head

echo "Starting FastAPI server..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8002 --workers 1
