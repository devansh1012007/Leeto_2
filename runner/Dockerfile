# Runner image (dev/staging same-host profile; prod runs on a separate VM).
# Unprivileged, no DB, no secrets — the gateway is the only peer.
FROM python:3.12-slim
WORKDIR /srv
RUN apt-get update && apt-get install -y --no-install-recommends unshare && rm -rf /var/lib/apt/lists/*
COPY service.py .
RUN useradd -m -u 10002 runner && mkdir -p /work && chown runner /work
USER runner
# The sandbox needs unshare for user+net namespaces (escape tests #1/#2)
CMD ["python", "service.py", "--pull", "--gateway", "${GATEWAY_URL}"]
