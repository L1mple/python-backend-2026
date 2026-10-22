FROM python:3.14

WORKDIR ./hw2/rest_example
COPY rest_example .
RUN pip install -r ./requirements.txt

WORKDIR /
CMD ["uvicorn", "hw2.rest_example.main:app", "--port", "8080", "--host", "0.0.0.0"]
