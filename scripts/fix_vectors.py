#!/usr/bin/env python3
"""Run the vector dimension fix migration."""
import asyncio
import os
from dotenv import load_dotenv
import asyncpg

load_dotenv()

async def main():
    dsn = os.environ["DATABASE_URL"]
    conn = await asyncpg.connect(dsn)
    try:
        await conn.execute("ALTER TABLE jobs ALTER COLUMN embedding TYPE VECTOR(1024)")
        print("✅ jobs.embedding → VECTOR(1024)")
        await conn.execute("ALTER TABLE candidates ALTER COLUMN embedding TYPE VECTOR(1024)")
        print("✅ candidates.embedding → VECTOR(1024)")
    finally:
        await conn.close()

asyncio.run(main())
