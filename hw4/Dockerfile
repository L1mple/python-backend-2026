FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && useradd --create-home --uid 10001 appuser

COPY --chown=appuser:appuser shop_api ./shop_api
COPY --chown=appuser:appuser transaction_demos ./transaction_demos
USER appuser
EXPOSE 8000

CMD ["uvicorn", "shop_api.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
