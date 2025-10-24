FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# non-root user
RUN adduser --disabled-password --gecos '' appuser && mkdir /app/data && chown -R appuser:appuser /app
USER appuser

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/

EXPOSE 8080

ENV DATABASE_PATH=/app/data/dedup.db

CMD ["python", "-m", "src.main"]