# Build React
FROM node:24-bookworm-slim AS frontend

WORKDIR /frontend

COPY web/package.json web/package-lock.json ./
RUN npm ci

COPY web/ ./
RUN npm run build


# Python server
FROM python:3.14-slim-bookworm

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_PYTHON_DOWNLOADS=never \
    UV_LINK_MODE=copy \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml uv.lock README.md ./

RUN uv sync \
    --locked \
    --no-dev \
    --no-install-project \
    --python /usr/local/bin/python

COPY server/ ./server/
COPY shared/ ./shared/
COPY --from=frontend /frontend/dist/ ./web/dist/

RUN groupadd --gid 10001 studygroup \
    && useradd --uid 10001 --gid studygroup --create-home studygroup \
    && mkdir -p /app/data \
    && chown studygroup:studygroup /app/data

USER studygroup

EXPOSE 8000

CMD ["python", "-m", "server.web"]