"""Astro MCP service package.

Generic stateful tool layer for Vedic astrology. Wraps the portable ``astro``
calculators with SQLite storage, report persistence, and a registry that the
stdio MCP server in ``services.astro_mcp.server`` binds onto.
"""
from __future__ import annotations

from .tools import TOOLS

__all__ = ["TOOLS"]
