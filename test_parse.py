import asyncio
import os
from dotenv import load_dotenv

load_dotenv()

from app.ai.agents.resume_agent import parse_resume

async def main():
    with open("/home/ubuntu/.gemini/antigravity-ide/brain/7f8db609-acfa-4594-8499-6ed4b1ad5743/abdullah_resume_extracted.md", "r") as f:
        text = f.read()
    
    res = await parse_resume(text)
    print("----- EXTRACTED JSON -----")
    print(res.model_dump_json(indent=2))

asyncio.run(main())
