FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV POETRY_VIRTUALENVS_CREATE=false
ENV POETRY_NO_INTERACTION=1

WORKDIR /app

RUN pip install --no-cache-dir "poetry>=1.8,<2.0"

COPY pyproject.toml README.md ./
COPY lib ./lib
COPY alembic.ini ./alembic.ini
COPY alembic ./alembic
RUN poetry install --only main

EXPOSE 8000

CMD ["poetry", "run", "uvicorn", "--app-dir", "/app/lib", "presentation.http.main:app", "--host", "0.0.0.0", "--port", "8000"]
