ARG PYTHON_VERSION=3.13
FROM python:${PYTHON_VERSION}-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /workspace
COPY hw2/hw/requirements.txt hw2/hw/requirements.txt
COPY hw3/requirements.txt hw3/requirements.txt
COPY hw5/requirements.txt hw5/requirements.txt
RUN pip install --no-cache-dir -r hw5/requirements.txt
COPY hw2/hw hw2/hw
COPY hw3/main.py hw3/test_monitoring.py hw3/
COPY hw4/tests hw4/tests
COPY hw5/pytest.ini hw5/pytest.ini
COPY hw5/tests hw5/tests

WORKDIR /workspace/hw5
CMD ["python", "-m", "pytest", "-q"]
