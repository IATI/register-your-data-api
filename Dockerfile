FROM python:3.12.16-slim-bookworm

RUN apt-get update -y && \
    apt-get upgrade -y && \
    apt-get install -y git

WORKDIR /api

# The base image's pip trusts its own vendored certifi, which includes the compromised eMudhra
# intermediates, so replace it with a release that doesn't before it installs anything.  The
# sha256 pins the wheel so this download can't be tampered with either.
RUN pip install --no-cache-dir "pip @ https://files.pythonhosted.org/packages/3f/06/3e4420302363fbb71be3c7f35ce042f54bfca330e3e66b3a2e3c4cca579f/pip-26.2.2-py3-none-any.whl#sha256=fd7f4dfa8190e014013b9f08f3e973f4e4c26ffd179a204895533a7254813a70"

COPY requirements.txt .
COPY pyproject.toml .
COPY licences.json .
COPY ryd-client-applications-metadata.json .
COPY cors-allowed-origins.json .

RUN pip install -r requirements.txt
RUN pip install -e .

COPY src/ src
COPY alembic/ alembic
COPY email_templates/ email_templates

ENTRYPOINT ["fastapi", "run", "src/main.py", "--port", "8000"]
