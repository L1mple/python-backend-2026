FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/hw2/hw \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app/hw3

COPY hw3/requirements.txt ./requirements.txt
RUN python -m pip install -r requirements.txt

COPY hw2/hw/shop_api /app/hw2/hw/shop_api
COPY hw3/monitored_app.py ./

USER 10001:10001

EXPOSE 8080

CMD ["uvicorn", "monitored_app:app", "--host", "0.0.0.0", "--port", "8080"]
