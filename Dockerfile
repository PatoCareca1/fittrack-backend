FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV POETRY_VERSION=2.3.3
ENV POETRY_NO_INTERACTION=1
ENV POETRY_VIRTUALENVS_CREATE=false

WORKDIR /app

RUN pip install "poetry==$POETRY_VERSION"

COPY pyproject.toml poetry.lock* ./
RUN poetry install

ENV REDIS_HOST=redis

COPY . .

EXPOSE 8000
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]