FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=on \
    PIP_DISABLE_PIP_VERSION_CHECK=on

WORKDIR /service

# Сначала зависимости: пока requirements.txt не менялся, этот слой берется из кэша
COPY requirements.txt ./
RUN pip install -r requirements.txt

COPY shop_api ./shop_api

# Не запускаем сервис от root
RUN useradd --create-home --uid 1000 app
USER app

EXPOSE 8080

CMD ["uvicorn", "shop_api.main:app", "--host", "0.0.0.0", "--port", "8080"]
