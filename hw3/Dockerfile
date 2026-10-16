FROM python:3.13-slim

WORKDIR /app

COPY hw2/hw/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY hw2/hw/shop_api ./shop_api

EXPOSE 8000
CMD ["uvicorn", "shop_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
