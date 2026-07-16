# Runs the proposal generator with zero host dependencies: Python, Chromium
# and fonts are all inside. ~1.3GB — honest for a bundled browser; size golf
# (alpine/distroless) is a non-goal: Chromium needs glibc and fonts anyway.
#
#   docker build -t proposal-gen .
#   docker run --rm -e LLM_API_KEY=... -v ./output:/app/output proposal-gen
FROM python:3.12-slim

# Chromium renders the PDF; the template's brand fonts are vendored in-repo
# (proposal_gen/fonts), fontconfig + DejaVu cover any fallback glyphs.
RUN apt-get update && apt-get install -y --no-install-recommends \
    chromium fonts-dejavu-core fontconfig \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app
COPY pyproject.toml uv.lock ./
# Virtual uv project (package = false): install dependencies only, from the
# same lockfile CI verifies.
RUN uv sync --locked --no-dev --no-install-project

COPY proposal_gen/ proposal_gen/
COPY data/ data/

ENV PATH="/app/.venv/bin:$PATH"
# Chromium runs as root inside the container, where its kernel sandbox is
# unavailable — an accepted, documented tradeoff for a batch CLI tool.
ENV CHROME_EXTRA_ARGS="--no-sandbox --disable-dev-shm-usage"
ENV CHROME_PATH=/usr/bin/chromium

ENTRYPOINT ["python", "-m", "proposal_gen"]
CMD []
