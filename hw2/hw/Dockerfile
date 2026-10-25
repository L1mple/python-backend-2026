FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY hw2/hw/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY hw2/hw/shop_api /app/shop_api
COPY hw2/hw/transaction_isolation.py /app/transaction_isolation.py

EXPOSE 8000

CMD ["uvicorn", "shop_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
