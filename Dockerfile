# syntax=docker/dockerfile:1
FROM node:22-bookworm-slim AS node

FROM python:3.12-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy \
    PATH="/app/.venv/bin:/usr/local/bin:${PATH}"
COPY --from=node /usr/local/bin/node /usr/local/bin/node
COPY --from=node /usr/local/lib/node_modules /usr/local/lib/node_modules
RUN ln -s /usr/local/lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm \
    && ln -s /usr/local/lib/node_modules/npm/bin/npx-cli.js /usr/local/bin/npx
COPY --from=ghcr.io/astral-sh/uv:0.12.19 /uv /usr/local/bin/uv

WORKDIR /app
COPY pyproject.toml uv.lock package.json package-lock.json ./
COPY apps/web/package.json apps/web/package.json
COPY apps/renderer/package.json apps/renderer/package.json
RUN --mount=type=secret,id=proxy_ca,required=false \
    if [ -s /run/secrets/proxy_ca ]; then \
      SSL_CERT_FILE=/run/secrets/proxy_ca uv sync --frozen --no-dev; \
      NODE_EXTRA_CA_CERTS=/run/secrets/proxy_ca npm ci; \
    else \
      uv sync --frozen --no-dev && npm ci; \
    fi
COPY . .
RUN npm run build --workspace @mediagrid/web \
    && npm prune --omit=dev \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
      chromium ffmpeg ca-certificates fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/* \
    && python -m compileall -q apps workers \
    && useradd -u 10001 -m mediagrid \
    && mkdir -p /app/data /app/apps/web/.next/cache /home/mediagrid/.cache \
    && chmod -R a+rX /app \
    && chmod 755 /app/scripts/start-production.sh \
    && chown -R mediagrid:mediagrid \
      /app/data /app/apps/web/.next/cache /home/mediagrid
USER mediagrid
ENV NODE_ENV=production
EXPOSE 3000
CMD ["./scripts/start-production.sh"]
