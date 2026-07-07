FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    POETRY_VERSION=2.1.4

WORKDIR /app

RUN pip install --no-cache-dir "poetry==$POETRY_VERSION"

COPY pyproject.toml README.md ./
RUN poetry config virtualenvs.create false && poetry install --only main --no-root

COPY src ./src
COPY alembic.ini ./alembic.ini

CMD ["uvicorn", "src.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
