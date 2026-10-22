FROM python:3.12 AS base

ARG PYTHONFAULTHANDLER=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONHASHSEED=random \
    PIP_NO_CACHE_DIR=on \
    PIP_DISABLE_PIP_VERSION_CHECK=on \
    PIP_DEFAULT_TIMEOUT=500

RUN apt-get update && apt-get install -y gcc
RUN python -m pip install --upgrade pip

WORKDIR /app

# Контекст сборки - корень репозитория (см. docker-compose.yml), поэтому
# берём уже готовый сервис из hw2, ничего не дублируя.
COPY hw2/hw/ ./

RUN pip install -r requirements.txt

ENV PYTHONPATH=/app

FROM base AS local

CMD ["uvicorn", "shop_api.main:app", "--host", "0.0.0.0", "--port", "8080"]
