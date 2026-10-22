FROM ghcr.io/astral-sh/uv:0.9.17-python3.13-bookworm-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev --no-install-project
COPY hw2/hw/shop_api ./hw2/hw/shop_api

USER 10001:10001
EXPOSE 8000
CMD ["uvicorn", "shop_api.main:app", "--app-dir", "hw2/hw", "--host", "0.0.0.0", "--port", "8000"]
