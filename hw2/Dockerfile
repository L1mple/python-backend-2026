FROM python:3.12

WORKDIR /app

COPY hw/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY hw ./hw

CMD ["uvicorn", "hw.shop_api.main:app", "--host", "0.0.0.0", "--port", "8080"]