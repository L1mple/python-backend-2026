FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY hw2/hw/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY hw2/hw/shop_api ./shop_api

USER 10001:10001

EXPOSE 8080

CMD ["uvicorn", "shop_api.main:app", "--host", "0.0.0.0", "--port", "8080"]
