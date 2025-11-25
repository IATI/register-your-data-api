FROM python:3.12.11-slim-bookworm

RUN apt-get update -y && \
    apt-get upgrade -y && \
    apt-get install -y git

WORKDIR /api

COPY requirements.txt .
COPY pyproject.toml .
COPY licences.json .

RUN pip install -r requirements.txt
RUN pip install -e .

COPY src/ src
COPY alembic/ alembic

ENTRYPOINT ["fastapi", "run", "src/main.py", "--port", "8000"]
