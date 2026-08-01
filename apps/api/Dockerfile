FROM python:3.13.14-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

RUN groupadd --gid 10001 corehr \
    && useradd --uid 10001 --gid corehr --create-home corehr

COPY requirements.lock .
RUN pip install --no-cache-dir --require-hashes -r requirements.lock

COPY pyproject.toml .
COPY alembic.ini .
COPY alembic ./alembic
COPY src ./src

ENV PYTHONPATH=/app/src

USER corehr
EXPOSE 8000

CMD ["uvicorn", "hris.main:app", "--host", "0.0.0.0", "--port", "8000"]

