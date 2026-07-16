# Runs the proposal generator with zero host dependencies: Python, Chromium
# and fonts are all inside. ~1.3GB — honest for a bundled browser; size golf
# (alpine/distroless) is a non-goal: Chromium needs glibc and fonts anyway.
#
#   docker build -t proposal-gen .
#   docker run --rm -e LLM_API_KEY=... -v ./output:/app/output proposal-gen
# Digest-pinned like the SHA-pinned GitHub Actions — same supply-chain bar
# everywhere; dependabot's docker ecosystem keeps both pins fresh.
FROM python:3.14-slim@sha256:d3400aa122fa42cf0af0dbe8ec3091b047eac5c8f7e3539f7135e86d855dc015

# Chromium renders the PDF; the template's brand fonts are vendored in-repo
# (proposal_gen/fonts), fontconfig + DejaVu cover any fallback glyphs.
RUN apt-get update && apt-get install -y --no-install-recommends \
    chromium fonts-dejavu-core fontconfig \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:0.10.2@sha256:94a23af2d50e97b87b522d3cea24aaf8a1faedec1344c952767434f69585cbf9 /uv /usr/local/bin/uv

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
