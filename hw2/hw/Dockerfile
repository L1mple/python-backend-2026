FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=on \
    PIP_DISABLE_PIP_VERSION_CHECK=on

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY shop_api ./shop_api

EXPOSE 8080

CMD ["uvicorn", "shop_api.main:app", "--host", "0.0.0.0", "--port", "8080"]