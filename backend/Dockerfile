# Multi-stage backend runtime (all apps in one image; command selects the app)
FROM python:3.12-slim AS runtime
WORKDIR /srv
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*
COPY pyproject.toml ./
COPY packages ./packages
RUN pip install --no-cache-dir .
COPY apps ./apps
COPY migrations ./migrations
COPY alembic.ini ./
RUN useradd -m -u 10001 bhctf && chown -R bhctf /srv
USER bhctf
EXPOSE 8000 8001 8002
CMD ["python", "-m", "app.main"]
