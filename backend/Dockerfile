FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install system dependencies (git needed for repository cloning)
RUN apt-get update && apt-get install -y --no-install-recommends git && rm -rf /var/lib/apt/lists/*

# Copy project metadata and code
COPY pyproject.toml alembic.ini ./
COPY alembic ./alembic
COPY app ./app

# Install dependencies and package
RUN pip install --no-cache-dir .

EXPOSE 8000

# Run Alembic migrations then start the server
CMD alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000
