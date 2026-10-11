FROM python:3.12-slim

ENV PYTHONFAULTHANDLER=1 \
  PYTHONUNBUFFERED=1 \
  PYTHONDONTWRITEBYTECODE=1 \
  PIP_NO_CACHE_DIR=1 \
  PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

COPY hw3/requirements.txt .
RUN python -m pip install -r requirements.txt

COPY hw2/hw/shop_api ./shop_api
COPY hw2/hw/store ./store
COPY hw3/main.py .

EXPOSE 8080

CMD ["uvicorn", "main:app", "--port", "8080", "--host", "0.0.0.0"]
