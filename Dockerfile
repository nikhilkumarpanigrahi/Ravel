# syntax=docker/dockerfile:1
# -----------------------------------------------------------------------------
# RAVEL Forensic Workstation - Production Multi-Stage Container
# -----------------------------------------------------------------------------

FROM ghcr.io/astral-sh/uv:python3.11-bookworm-slim AS builder

WORKDIR /app

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

# Install dependencies first for maximum layer caching
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --no-dev

# Copy source and build package
COPY src ./src
COPY README.md ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

# -----------------------------------------------------------------------------
# Runtime stage
# -----------------------------------------------------------------------------
FROM python:3.11-slim-bookworm AS runtime

WORKDIR /app

# Create a non-root system user for security
RUN groupadd -r ravel && useradd -r -g ravel -d /app -s /sbin/nologin raveluser

# Copy virtual environment from builder
COPY --from=builder --chown=raveluser:ravel /app/.venv /app/.venv
COPY --from=builder --chown=raveluser:ravel /app/src /app/src
COPY --chown=raveluser:ravel cases /app/cases
RUN mkdir -p /app/data && chown -R raveluser:ravel /app/data

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    RAVEL_ENV="production" \
    RAVEL_STATE_DB_URL="sqlite:////app/data/ravel.db"

USER raveluser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python3 -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

ENTRYPOINT ["uvicorn", "ravel.interfaces.api:app", "--host", "0.0.0.0", "--port", "8000"]
