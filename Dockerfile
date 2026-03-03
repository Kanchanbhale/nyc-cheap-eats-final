FROM python:3.11-slim

WORKDIR /app

COPY . /app

RUN pip install --no-cache-dir uv
RUN uv sync --frozen

EXPOSE 8080

CMD ["sh", "-c", "uv run uvicorn app:app --host 0.0.0.0 --port ${PORT:-8080}"]
