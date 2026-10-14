FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

COPY hw3/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY hw2/hw/shop_api ./shop_api
COPY hw3/main.py ./main.py

USER 10001:10001
EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
