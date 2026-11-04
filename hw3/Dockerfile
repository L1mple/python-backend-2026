FROM python:3.13-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=on \
    PIP_DISABLE_PIP_VERSION_CHECK=on

WORKDIR /service

# Сначала зависимости: пока requirements.txt не менялся, этот слой берется из кэша
COPY requirements.txt ./
RUN pip install -r requirements.txt

COPY shop_api ./shop_api
COPY load.py ./

# Не запускаем сервис от root
RUN useradd --create-home --uid 1000 app
USER app

EXPOSE 8080

HEALTHCHECK --interval=10s --timeout=3s --start-period=5s --retries=5 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/metrics')" || exit 1

CMD ["uvicorn", "shop_api.main:app", "--host", "0.0.0.0", "--port", "8080"]
