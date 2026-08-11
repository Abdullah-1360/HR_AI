#!/usr/bin/env python3
import asyncio
import os
import asyncpg
from dotenv import load_dotenv

load_dotenv()

async def main():
    conn = await asyncpg.connect(os.environ["DATABASE_URL"])
    try:
        updated = await conn.execute("UPDATE candidates SET tenant_id = 'default' WHERE tenant_id IS NULL OR tenant_id = 'default_tenant'")
        print(f"Updated existing candidate records: {updated}")
    finally:
        await conn.close()

asyncio.run(main())
