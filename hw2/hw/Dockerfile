FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=on \
    PIP_DISABLE_PIP_VERSION_CHECK=on \
    PIP_DEFAULT_TIMEOUT=500

RUN apt-get update && apt-get install -y gcc
RUN python -m pip install --upgrade pip

WORKDIR /app

COPY requirements.txt .
RUN pip install --retries 10 --timeout 120 -r requirements.txt

COPY . .

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=on \
    PIP_DISABLE_PIP_VERSION_CHECK=on \
    PIP_DEFAULT_TIMEOUT=500

RUN apt-get update && apt-get install -y gcc
RUN python -m pip install --upgrade pip

WORKDIR /app

COPY requirements.txt .
RUN pip install --retries 10 --timeout 120 -r requirements.txt

COPY . .

CMD ["sh", "-c", "alembic upgrade head && exec fastapi run --entrypoint shop_api.main:app --port 8080 --host 0.0.0.0"]