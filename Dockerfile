# astro-skill — slim image: Python + deps + the skill code. No Chromium, so it
# builds fast and stays small enough for registry build limits (e.g. Glama).
# All MCP tools work; generate_pdf_report should be called with
# renderer="reportlab" here. For the Playwright/Chromium HTML renderer
# (polished Devanagari shaping) build the full image instead:
#
#     docker build -f Dockerfile.full -t astro-skill .

# 1. Base: a small official Python image (Debian slim). Pinned for reproducibility.
FROM python:3.12-slim

# 2. Sensible runtime defaults.
ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1

# 3. All app files live under /app inside the container.
WORKDIR /app

# 4. Python dependencies. pyswisseph is a C extension, so install a compiler +
#    Python headers to build it, then purge them so the image stays small.
#    playwright is deliberately omitted — the code imports it lazily and only
#    the html PDF renderer needs it (see Dockerfile.full).
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential python3-dev \
    && pip install --no-cache-dir \
        "mcp>=1.27.0" \
        "pyswisseph>=2.10.3.2" \
        "python-dateutil>=2.9.0" \
        "reportlab>=4.5.1" \
        "tzdata>=2025.2" \
    && apt-get purge -y build-essential python3-dev \
    && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/*

# 5. The skill code. The bundled Noto Devanagari font travels inside
#    astro/scripts/fonts and the Swiss Ephemeris .se1 data travels inside
#    astro/ephe, so both Hindi rendering and high-precision positions need
#    nothing from the host.
COPY astro ./astro
COPY services ./services
COPY pyproject.toml README.md ./

# 5b. Point Swiss Ephemeris at the bundled .se1 data so calc uses the precise
#     SWIEPH ephemeris instead of the lower-precision Moshier fallback. The
#     calculators also fall back to this same path automatically, but setting it
#     explicitly keeps the tier correct regardless of working directory.
ENV SE_EPHE_PATH=/app/astro/ephe

# 6. Drop root: the server only needs to write reports/SQLite under
#    /app/data, so create that dir, hand it to a dedicated user and run as
#    that user from here on.
RUN useradd --create-home --uid 10001 astro \
    && mkdir -p /app/data \
    && chown -R astro:astro /app/data
USER astro

# 7. Default process: the astro MCP server (stdio). Override the command to run
#    one-off scripts (e.g. generate a PDF) — see README/compose.
CMD ["python", "-m", "services.astro_mcp"]
