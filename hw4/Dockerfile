FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/hw2/hw

WORKDIR /app

COPY hw4/requirements.txt /app/hw4/requirements.txt
RUN pip install --no-cache-dir -r /app/hw4/requirements.txt

COPY hw2/hw/shop_api/ /app/hw2/hw/shop_api/
COPY hw4/isolation_demo.py /app/hw4/isolation_demo.py

EXPOSE 8080

CMD ["uvicorn", "shop_api.main:app", "--host", "0.0.0.0", "--port", "8080"]
