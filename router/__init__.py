"""
router/__init__.py
Exports the main RouterNode and convenience helpers.
"""

from dotenv import load_dotenv
load_dotenv()

from .router import RouterNode
from .db import get_pool, close_pool
from .chat_model import ChatRouter

__all__ = ["RouterNode", "get_pool", "close_pool", "ChatRouter"]
