FROM python:3.13-slim AS base

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src

COPY pyproject.toml README.md ./
COPY src ./src

FROM base AS development

CMD ["python", "-m", "mail_exporter"]

FROM base AS production

RUN useradd --create-home --shell /usr/sbin/nologin exporter \
    && chown -R exporter:exporter /app

USER exporter

CMD ["python", "-m", "mail_exporter"]
