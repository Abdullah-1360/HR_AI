import sys
from minio import Minio
import pdfplumber
import io
import os
from dotenv import load_dotenv

load_dotenv()

client = Minio(
    endpoint=os.environ.get("MINIO_ENDPOINT", "localhost:9000"),
    access_key=os.environ.get("MINIO_ACCESS_KEY", "hr_ai_minio"),
    secret_key=os.environ.get("MINIO_SECRET_KEY", "hr_ai_minio_secret"),
    secure=False
)

response = client.get_object("resumes", "resumes/Abdullah Shahid_Abdullah_Shahid_Premium_Resume.pdf")
pdf_bytes = io.BytesIO(response.read())
with pdfplumber.open(pdf_bytes) as pdf:
    text = ""
    for page in pdf.pages:
        text += page.extract_text() + "\n"

with open("/home/ubuntu/.gemini/antigravity-ide/brain/7f8db609-acfa-4594-8499-6ed4b1ad5743/abdullah_resume_extracted.md", "w") as f:
    f.write("# Extracted Resume Text\n\n```text\n")
    f.write(text)
    f.write("\n```\n")

response.close()
response.release_conn()
