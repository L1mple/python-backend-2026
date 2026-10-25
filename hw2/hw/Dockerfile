FROM python:3.12 AS base
LABEL authors="menth"

ARG PYTHONFAULTHANDLER=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONHASHSEED=random \
    PIP_NO_CACHE_DIR=on \
    PIP_DISABLE_PIP_VERSION_CHECK=on \
    PIP_DEFAULT_TIMEOUT=500

ARG APP_ROOT=/opt/app

RUN apt-get update && apt-get install -y --no-install-recommends gcc \
    && rm -rf /var/lib/apt/lists/*
RUN python -m pip install --upgrade pip

WORKDIR ${APP_ROOT}/src

COPY requirements.txt ./
RUN pip install -r requirements.txt

COPY shop_api ./shop_api
COPY store ./store

ENV PYTHONPATH=${APP_ROOT}/src \
    PYTHONFAULTHANDLER=${PYTHONFAULTHANDLER} \
    PYTHONUNBUFFERED=${PYTHONUNBUFFERED} \
    PYTHONHASHSEED=${PYTHONHASHSEED}

FROM base AS local

EXPOSE 8080
CMD ["uvicorn", "shop_api.main:app", "--port", "8080", "--host", "0.0.0.0"]