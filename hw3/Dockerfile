from python:3.11-slim

workdir /app

copy hw2/hw/requirements.txt ./requirements.txt

run pip install --no-cache-dir -r requirements.txt

copy hw2/hw/ ./

copy hw4/ ./hw4/

cmd ["uvicorn", "shop_api.main:app", "--host", "0.0.0.0", "--port", "8080"]