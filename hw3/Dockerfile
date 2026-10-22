FROM python:3.12-slim

WORKDIR /app

# Говорим pip доверять серверам PyPI несмотря на корпоративные сертификаты
ENV PIP_TRUSTED_HOST="pypi.org files.pythonhosted.org pypi.python.org"

COPY requirements.txt .

# Добавляем флаги --trusted-host напрямую в команду установки
RUN pip install --trusted-host pypi.org --trusted-host files.pythonhosted.org --no-cache-dir -r requirements.txt

COPY . .

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
