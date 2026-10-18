FROM python:3.10-slim

WORKDIR /app

COPY hw2/hw/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY hw2/hw/shop_api ./shop_api
COPY hw4 ./hw4

EXPOSE 8000

CMD ["uvicorn", "shop_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
