FROM python:3.14

WORKDIR ./hw2/hw
COPY hw .
RUN pip install -r ./requirements.txt

WORKDIR /
CMD ["uvicorn", "hw2.hw.shop_api.main:app", "--port", "8080", "--host", "0.0.0.0"]
