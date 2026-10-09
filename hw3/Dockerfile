FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && useradd --create-home --uid 10001 appuser

COPY --chown=appuser:appuser shop_api ./shop_api
USER appuser
EXPOSE 8000

# The in-memory store must stay within one worker process.
CMD ["uvicorn", "shop_api.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
