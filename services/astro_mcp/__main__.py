"""Entry point so ``python -m services.astro_mcp`` runs the stdio server."""
from __future__ import annotations

from .server import main

if __name__ == "__main__":
    main()
