FROM python:3.12-alpine
WORKDIR /service
COPY hw/requirements.txt .
RUN pip install -r requirements.txt
COPY hw ./
EXPOSE 8000
ENTRYPOINT ["uvicorn", "shop_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
