FROM python:3.13-slim AS base

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src

COPY exporter/pyproject.toml ./pyproject.toml
COPY README.md ./README.md
COPY exporter/src ./src

RUN pip install --no-cache-dir .

FROM base AS development

ENTRYPOINT ["python", "-m", "mail_exporter"]

FROM base AS production

RUN useradd --create-home --shell /usr/sbin/nologin exporter \
    && chown -R exporter:exporter /app

USER exporter

ENTRYPOINT ["python", "-m", "mail_exporter"]
