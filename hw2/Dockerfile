FROM python:3.12 AS base

ARG APP_ROOT=/app \
    PYTHONFAULTHANDLER=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONHASHSEED=random \
    PIP_NO_CACHE_DIR=on \
    PIP_DISABLE_PIP_VERSION_CHECK=on \
    PIP_DEFAULT_TIMEOUT=500

RUN apt-get update
RUN python -m pip install --upgrade pip

WORKDIR $APP_ROOT/src
COPY . ./hw2/

ENV VIRTUAL_ENV=$APP_ROOT/src/.venv \
    PATH=$APP_ROOT/src/.venv/bin:$PATH \
    PYTHONPATH=$APP_ROOT/src:$APP_ROOT/src/hw2

RUN pip install -r hw2/requirements.txt

FROM base as local

CMD ["uvicorn", "shop_api.main:app", "--port", "8080", "--host", "0.0.0.0"]