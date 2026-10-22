FROM python:3-alpine

LABEL authors="v_tryapitsyna"

WORKDIR /shop_api

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8080

ENV PYTHONPATH=/shop_api

ENTRYPOINT ["python3", "-m", "shop_api.main"]
