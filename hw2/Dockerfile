FROM python:3.12-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

COPY hw/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY hw/ ./hw/

ENV PYTHONPATH=/app/hw

FROM base AS local

EXPOSE 8080

CMD ["uvicorn", "shop_api.main:app", "--host", "0.0.0.0", "--port", "8080"]
