FROM python:3.12

WORKDIR /service

COPY hw3/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY hw2/hw/shop_api ./hw2/hw/shop_api
COPY hw3/__init__.py hw3/main.py ./hw3/

EXPOSE 8080

CMD ["uvicorn", "hw3.main:app", "--host", "0.0.0.0", "--port", "8080"]