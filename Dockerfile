# syntax=docker/dockerfile:1.7

# ---- Stage 1: build the React panel -----------------------------------------
FROM node:20-slim AS web-builder
WORKDIR /web
COPY web/package.json web/package-lock.json* ./
# Use ci when a lockfile is present, fall back to install otherwise (first build).
RUN if [ -f package-lock.json ]; then npm ci --no-audit --no-fund; else npm install --no-audit --no-fund; fi
COPY web/ .
RUN npm run build

# ---- Stage 2: install Python deps -------------------------------------------
FROM python:3.12-slim AS py-builder
WORKDIR /app
ENV PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
COPY pyproject.toml requirements.txt ./
RUN python -m pip install --upgrade pip \
    && python -m pip install -r requirements.txt

# ---- Stage 3: runtime image -------------------------------------------------
FROM python:3.12-slim AS runtime
WORKDIR /app

# Bring over the installed site-packages from the builder layer.
COPY --from=py-builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=py-builder /usr/local/bin /usr/local/bin

# App sources
COPY src/ ./src/
COPY cli.py main.py serve.py entrypoint.sh ./
COPY pyproject.toml requirements.txt config-example.yaml ./

# Embed the built panel
COPY --from=web-builder /web/dist ./web/dist

# Ensure entrypoint is executable + create runtime dirs
RUN chmod +x entrypoint.sh \
    && mkdir -p /app/local/data /app/local/logs

ENV PYTHONPATH=/app/src \
    PYTHONUNBUFFERED=1 \
    CF_AIGW_STORAGE__DATA_DIR=/app/local/data \
    CF_AIGW_CONTROL__HOST=0.0.0.0 \
    CF_AIGW_CONTROL__PORT=8765

EXPOSE 8765

ENTRYPOINT ["./entrypoint.sh"]
CMD ["serve"]
