FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends git git-lfs \
    && git lfs install \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY backend/ ./
COPY .git/ ./.git/
RUN git lfs pull

RUN pip install poetry==1.8.0 \
    && poetry config virtualenvs.create false \
    && poetry install --no-dev --no-interaction --no-ansi

EXPOSE 8000
CMD ["sh", "-c", "uvicorn app:app --host 0.0.0.0 --port ${PORT:-8000}"]
