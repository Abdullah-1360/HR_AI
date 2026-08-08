"""
app/utils/pdf_extractor.py
PDF text extraction using pdfplumber.
Accepts raw bytes (from upload or MinIO) and returns plain text.
"""
import io
import logging
from typing import Optional

import pdfplumber

logger = logging.getLogger(__name__)


def extract_text_from_bytes(pdf_bytes: bytes) -> str:
    """
    Extract all text from a PDF given its raw bytes.
    Returns concatenated page text separated by newlines.
    Raises ValueError if no text could be extracted.
    """
    try:
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            pages_text = []
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    pages_text.append(text.strip())

        full_text = "\n\n".join(pages_text)
        if not full_text.strip():
            raise ValueError("No text content found in PDF (possibly image-only or encrypted)")
        return full_text

    except ValueError:
        raise
    except Exception as exc:
        logger.error("PDF extraction failed: %s", exc)
        raise ValueError(f"Failed to extract text from PDF: {exc}") from exc


def extract_text_from_path(pdf_path: str) -> str:
    """Convenience wrapper: read a file from disk then extract text."""
    with open(pdf_path, "rb") as f:
        return extract_text_from_bytes(f.read())
