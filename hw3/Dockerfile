FROM python:3.10-alpine

WORKDIR /app

COPY hw2/hw/requirements.txt ./
RUN pip install -r requirements.txt

COPY hw2/hw/shop_api ./shop_api
COPY hw2/hw/store ./store

EXPOSE 8000
CMD ["uvicorn", "shop_api.main:app", "--port", "8000", "--host", "0.0.0.0"]