FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Сначала только зависимости: этот слой берётся из кеша,
# пока requirements.txt не изменился, и пересборка после правки кода быстрая
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY shop_api ./shop_api

# Сервис не нужно запускать от root
RUN useradd --create-home app
USER app

EXPOSE 8080
CMD ["uvicorn", "shop_api.main:app", "--host", "0.0.0.0", "--port", "8080"]
