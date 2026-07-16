# Deploying the astro MCP server

The skill is the product: any MCP-speaking runtime gets astrology tools by
running this server. The recommended path is Docker, but you can also run it
straight from a Python environment.

## Option A — Docker (recommended)

There are two images. The [`Dockerfile`](../Dockerfile) at the repo root is
the **default, slim** image: Python + dependencies + bundled fonts and
ephemeris, no Chromium — it builds fast and stays small enough for registry
build limits (e.g. Glama). Call `generate_pdf_report` with
`renderer="reportlab"` there. [`Dockerfile.full`](../Dockerfile.full) adds
Chromium/Playwright for the polished Devanagari HTML PDF renderer, at the cost
of a 1GB+ image — build it explicitly with `docker build -f Dockerfile.full -t
astro-skill .` for VPS/self-hosted deploys that need `renderer="html"`.

```bash
# Build (slim, default)
docker build -t astro-skill .

# Build (full, with Chromium)
docker build -f Dockerfile.full -t astro-skill .

# Smoke-test the image (computes a reference kundali inside the container)
docker run --rm --entrypoint python astro-skill -c \
  'import sys; sys.path.insert(0, "astro/scripts"); \
   from kundali_calculator import BirthInput, calculate_kundali; \
   r = calculate_kundali(BirthInput("26/12/2019","09:15","Delhi",28.6139,77.2090,"Asia/Kolkata")); \
   print("ok lagna=" + r["lagna"])'

# Run the MCP server (stdio)
docker run --rm -i astro-skill
```

Persist the SQLite store and generated reports with volumes:

```bash
docker run --rm -i \
  -v astro_data:/app/data \
  -v astro_out:/app/output \
  astro-skill
```

## Option B — local Python

```bash
pip install -e ".[dev]"
python -m playwright install chromium   # only if you need HTML/Chromium PDFs
python -m services.astro_mcp            # start the MCP server (stdio)
```

## Wiring into an MCP client

The server speaks the Model Context Protocol over stdio, so any MCP client
(Claude Desktop, a Codex agent, or your own) can attach it. Point the client's
MCP config at the run command — for the Docker image:

```json
{
  "command": "docker",
  "args": ["run", "--rm", "-i", "-v", "astro_data:/app/data", "astro-skill"]
}
```

or, for a local install:

```json
{ "command": "python", "args": ["-m", "services.astro_mcp"] }
```

Once attached, the client sees the tools listed in
[`services/astro_mcp/README.md`](../services/astro_mcp/README.md)
(`calculate_kundali`, `calculate_dasha`, `calculate_panchang`,
`generate_pdf_report`, …). Scope the tools to whichever agent should have them
using your client's own tool-policy mechanism.

## One-off runs

Override the container command to run a single script instead of the server —
for example, render a PDF report:

```bash
docker run --rm -v "$PWD/out:/app/output" --entrypoint python astro-skill \
  astro/scripts/pdf_report.py --kundali-json chart.json --output output/report.pdf
```
