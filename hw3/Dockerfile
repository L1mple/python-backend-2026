FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY hw3/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Берём готовый магазин из ДЗ2
COPY hw2/hw/shop_api/ ./shop_api/
COPY hw3/monitored_app.py ./monitored_app.py

EXPOSE 8000
CMD ["uvicorn", "monitored_app:app", "--host", "0.0.0.0", "--port", "8000"]
