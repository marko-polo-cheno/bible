# Stage 1: Fetch LFS data
FROM python:3.12-slim AS fetcher

RUN apt-get update && apt-get install -y --no-install-recommends git git-lfs \
    && git lfs install \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /src
COPY .git/ ./.git/
COPY backend/testimonies.jsonl ./backend/testimonies.jsonl
RUN git lfs pull

# Stage 2: Production image
FROM python:3.12-slim

WORKDIR /app

# 1. Copy the entire backend folder first
COPY backend/ ./

# 2. Overwrite the LFS pointer with the real data from the fetcher
COPY --from=fetcher /src/backend/testimonies.jsonl ./testimonies.jsonl

RUN pip install poetry==1.8.0 \
    && poetry config virtualenvs.create false \
    && poetry install --no-dev --no-interaction --no-ansi

EXPOSE 8000
CMD ["sh", "-c", "uvicorn app:app --host 0.0.0.0 --port ${PORT:-8000}"]
