# Multi-stage backend runtime (all apps in one image; command selects the app)
FROM python:3.12-slim AS runtime
WORKDIR /srv
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*
COPY backend/pyproject.toml ./pyproject.toml
COPY backend/packages ./packages
RUN pip install --no-cache-dir .
COPY backend/apps ./apps
COPY backend/migrations ./migrations
COPY backend/alembic.ini ./
COPY openapi ./openapi
COPY copy ./copy
ENV BHCTF_REPO_ROOT=/srv
RUN useradd -m -u 10001 bhctf && chown -R bhctf /srv
USER bhctf
EXPOSE 8000 8001 8002
CMD ["python", "-m", "app.main"]
