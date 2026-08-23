# ==== INFRA — do not edit ====
FROM node:20-slim AS frontend-build
WORKDIR /fe
RUN echo "rollup_skip_nodejs_native=true" >> /root/.npmrc
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --include=dev
COPY frontend/ ./
RUN npm run build

# >>> module:cache
# >>> service:valkey
FROM valkey/valkey:8-bookworm AS valkey
# <<< service:valkey
# <<< module:cache

# >>> service:dbgate
FROM dbgate/dbgate:latest AS dbgate
# <<< service:dbgate

FROM python:3.13-slim-bookworm

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    nginx \
    supervisor \
    libssl3 \
    && rm -rf /var/lib/apt/lists/*

# >>> service:postgres
RUN apt-get update && apt-get install -y --no-install-recommends \
    postgresql \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*
# <<< service:postgres

COPY deploy/certs/ /usr/local/share/ca-certificates/
RUN update-ca-certificates

ENV SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt \
    REQUESTS_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt \
    PIP_CERT=/etc/ssl/certs/ca-certificates.crt \
    NODE_EXTRA_CA_CERTS=/etc/ssl/certs/ca-certificates.crt \
    UV_SYSTEM_CERTS=1

ARG TARGETARCH=amd64

# >>> module:jobs
# >>> service:temporal
ARG TEMPORAL_CLI_VERSION=1.8.0
RUN curl -fSL "https://temporal.download/cli/archive/v${TEMPORAL_CLI_VERSION}?platform=linux&arch=${TARGETARCH}" -o /tmp/temporal.tar.gz \
    && tar -xzf /tmp/temporal.tar.gz -C /usr/local/bin temporal \
    && chmod +x /usr/local/bin/temporal \
    && rm /tmp/temporal.tar.gz \
    && /usr/local/bin/temporal --version
# <<< service:temporal
# <<< module:jobs

# >>> service:openobserve
ARG OPENOBSERVE_VERSION=0.14.4
RUN curl -fSL "https://github.com/openobserve/openobserve/releases/download/v${OPENOBSERVE_VERSION}/openobserve-v${OPENOBSERVE_VERSION}-linux-${TARGETARCH}.tar.gz" -o /tmp/o2.tar.gz \
    && tar -xzf /tmp/o2.tar.gz -C /usr/local/bin openobserve \
    && chmod +x /usr/local/bin/openobserve \
    && rm /tmp/o2.tar.gz
# <<< service:openobserve

# >>> module:cache
# >>> service:valkey
COPY --from=valkey /usr/local/bin/valkey-server /usr/local/bin/valkey-server
# <<< service:valkey
# <<< module:cache

# >>> service:dbgate
COPY --from=dbgate /usr/local/bin/node /usr/local/bin/node
COPY --from=dbgate /home/dbgate-docker /home/dbgate-docker
# <<< service:dbgate

RUN pip install --no-cache-dir uv
COPY backend/pyproject.toml backend/uv.lock /app/backend/
WORKDIR /app/backend
RUN uv sync --frozen --no-dev
# >>> module:analytics
RUN uv run --no-sync python -c "import duckdb; duckdb.connect().execute('INSTALL postgres')"
# <<< module:analytics
WORKDIR /app

COPY backend/ /app/backend/
COPY --from=frontend-build /fe/dist /app/frontend/dist

COPY deploy/nginx.conf /etc/nginx/nginx.conf

# >>> topology:single
COPY deploy/supervisord.conf /etc/supervisor/conf.d/supervisord.conf
COPY deploy/entrypoint.sh /usr/local/bin/entrypoint.sh
COPY deploy/fatal_listener.py /usr/local/bin/fatal_listener.py
RUN chmod +x /usr/local/bin/entrypoint.sh
# <<< topology:single

RUN mkdir -p /var/log/supervisor /data && chmod -R 777 /var/log

# >>> service:postgres
RUN mkdir -p /data/postgres && chown -R postgres:postgres /data/postgres
# <<< service:postgres

# >>> service:openobserve
RUN mkdir -p /data/openobserve
# <<< service:openobserve

# >>> service:dbgate
RUN mkdir -p /data/dbgate
# <<< service:dbgate

# >>> module:jobs
# >>> service:temporal
RUN mkdir -p /data/temporal
# <<< service:temporal
# <<< module:jobs

# >>> module:cache
# >>> service:valkey
RUN mkdir -p /data/valkey
# <<< service:valkey
# <<< module:cache

EXPOSE 80

# >>> topology:single
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
# <<< topology:single
