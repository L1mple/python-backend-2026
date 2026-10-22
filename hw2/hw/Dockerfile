FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

COPY requirements.txt ./requirements.txt
RUN python -m pip install --upgrade pip && python -m pip install -r requirements.txt

RUN useradd --create-home --shell /usr/sbin/nologin appuser
COPY --chown=appuser:appuser shop_api ./shop_api
USER appuser

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "shop_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
