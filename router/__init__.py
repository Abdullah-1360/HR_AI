"""
router/__init__.py
Exports the main RouterNode and convenience helpers.
"""

from .router import RouterNode
from .db import get_pool, close_pool

__all__ = ["RouterNode", "get_pool", "close_pool"]
