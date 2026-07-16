# Generic Astro Platform

This document describes the repo as a **generic Vedic astrology platform**:
calculators, an agent skill, and an MCP server that any number of products can
reuse. Product-specific workflows (a web panel, a chat delivery shim, a voice
front-end) sit on top of this base layer and never live in it.

## Layered Architecture

```
┌─────────────────────────────────────────────────────────────┐
│ apps/                Optional products (web panels, bots)    │
├─────────────────────────────────────────────────────────────┤
│ services/astro_mcp/  Generic MCP API (stdio server, SQLite)  │
├─────────────────────────────────────────────────────────────┤
│ astro/               Portable skill + calculator scripts     │
├─────────────────────────────────────────────────────────────┤
│ Swiss Ephemeris (pyswisseph), ReportLab                      │
└─────────────────────────────────────────────────────────────┘
   docs/deploy.md  Generic deployment guide (Docker / MCP client)
```

Rules of thumb:

- Logic flows down. Higher layers may call lower layers; lower layers must
  never reference a specific product.
- Each layer owns its own README; product use-cases get their own doc.
- Tests pin behaviour at the layer that owns it.

## Layers

### `astro/` — portable skill and calculators

- **What it owns:** kundali, dasha, panchang, structured report JSON, PDF
  report, Hindi/English/Hinglish localisation defaults, safety boundaries.
- **What it does not own:** persistence, networking, MCP wiring, product UX.
- **Reusable as:** an agent skill, a pip-importable Python module, or via the
  CLI scripts under `astro/scripts/`.

### `services/astro_mcp/` — generic MCP server

- **What it owns:** a stable 11-tool surface, SQLite-backed client profile +
  report storage, an MCP stdio server, and JSON Schemas for each tool.
- **What it does not own:** delivery channels, voice, web UI, any product wording.
- **Reusable as:** an MCP server for any MCP client (Claude Desktop, a Codex
  agent, or a custom one). Requires no environment variables.

### `apps/` — optional products

- **What it owns:** product-shaped surfaces — for example a web panel or a chat
  bot — that compose the MCP tools into a specific workflow.
- **What it does not own:** astrology calculation, schema, or persistence.
- **Status:** `apps/pandit_web/` is a placeholder scaffold for one such
  product. Other products can live here too; nothing else in the repo depends
  on this folder.

### Deployment — `docs/deploy.md`

- **What it owns:** how to run the MCP server (Docker image or local Python)
  and wire it into an MCP client.
- **What it does not own:** any astrology behaviour, or any single host's setup.

## Reuse Patterns

The base layers are designed to be dropped into multiple products without
forking. Patterns we explicitly support:

1. **Standalone skill** — point an agent at `astro/` and use the CLI scripts
   directly.
2. **Generic MCP backend** — launch `python -m services.astro_mcp` and register
   it with any MCP client.
3. **Product wrapper** — wrap the MCP tools with a specific UX (chat, voice, or
   web). The wrapper owns delivery and access; the base layers stay untouched.
4. **Future integrations** — voice transcription, web panel, or any other
   product can call the same MCP tools without re-implementing astrology logic.

## Safety Invariants (apply across every layer)

- Outputs are calculation-backed drafts. They are intended for review by an
  astrologer or operator before any final reading is shared with an end client.
- Missing birth details must be requested from the operator rather than guessed.
- Approximate or partial inputs must be marked clearly in any output.
- Do not generate death, accident, medical, or unavoidable-harm certainty
  predictions.

These invariants are not negotiable per-product. Any downstream product is
expected to preserve them.

## Out Of Scope For The Base Layers

- Public/client-facing bots or APIs.
- Final predictive judgement — that always sits with the reviewing operator.
- Per-product UX (chat, voice, web panels).
- Live deployment to any specific host.

When a product needs one of those, it goes in `apps/` (or its own deployment
notes), not in `astro/` or `services/astro_mcp/`.
