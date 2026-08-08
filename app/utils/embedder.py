"""
app/utils/embedder.py
Cohere Embed v3 client for generating 1024-dimensional text embeddings.
Falls back to a deterministic dummy embedding if COHERE_API_KEY is unset.
"""
import hashlib
import logging
import math
from functools import lru_cache
from typing import List, Optional

import cohere

from app.core.config import get_settings

logger = logging.getLogger(__name__)

# Input type required by Cohere Embed v3
_EMBED_INPUT_TYPE_DOCUMENT = "search_document"
_EMBED_INPUT_TYPE_QUERY = "search_query"


@lru_cache(maxsize=1)
def _get_cohere_client() -> Optional[cohere.AsyncClient]:
    settings = get_settings()
    if not settings.cohere_api_key:
        logger.warning("COHERE_API_KEY not set — embedder will use dummy fallback")
        return None
    return cohere.AsyncClient(api_key=settings.cohere_api_key)


def _dummy_embedding(text: str, dim: int = 1024) -> List[float]:
    """
    Deterministic hash-based unit vector — used when Cohere is unavailable.
    NOT suitable for semantic search; only for local development/testing.
    """
    digest = hashlib.sha256(text.encode()).digest()
    raw = [(b / 255.0) * 2 - 1 for b in digest]
    # Repeat pattern to fill `dim` dimensions
    repeated = (raw * (dim // len(raw) + 1))[:dim]
    # Normalise to unit vector
    magnitude = math.sqrt(sum(x ** 2 for x in repeated)) or 1.0
    return [x / magnitude for x in repeated]


async def embed_document(text: str) -> List[float]:
    """
    Generate an embedding for a document (resume or job description).
    Uses Cohere embed-english-v3.0 with input_type='search_document'.
    """
    return await _embed(text, input_type=_EMBED_INPUT_TYPE_DOCUMENT)


async def embed_query(text: str) -> List[float]:
    """
    Generate an embedding for a search query.
    Uses Cohere embed-english-v3.0 with input_type='search_query'.
    """
    return await _embed(text, input_type=_EMBED_INPUT_TYPE_QUERY)


async def _embed(text: str, input_type: str) -> List[float]:
    settings = get_settings()
    client = _get_cohere_client()

    if client is None:
        logger.debug("Using dummy embedding (no Cohere key)")
        return _dummy_embedding(text, dim=settings.embed_dimension)

    try:
        response = await client.embed(
            texts=[text],
            model=settings.cohere_embed_model,
            input_type=input_type,
            embedding_types=["float"],
        )
        embedding = response.embeddings.float[0]  # type: ignore[index]
        return embedding
    except Exception as exc:
        logger.error("Cohere embedding failed (%s), using dummy fallback: %s", input_type, exc)
        return _dummy_embedding(text, dim=settings.embed_dimension)
