FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/hw2/hw

WORKDIR /app
COPY hw3/requirements.txt hw3/requirements.txt
RUN pip install --no-cache-dir -r hw3/requirements.txt \
    && useradd --create-home app
COPY hw2/hw/shop_api hw2/hw/shop_api
COPY hw3/main.py hw3/main.py
COPY hw4/isolation.py hw4/isolation.py

USER app
EXPOSE 8080
CMD ["uvicorn", "hw3.main:app", "--host", "0.0.0.0", "--port", "8080"]
