# MedMatch AI — single-container deploy (Cloud Run / any Docker host)
# One public URL: Express BFF + React build (PORT), FastAPI engine internal :8765.
FROM node:22-bookworm-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 python3-pip tini && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# --- medical engine (FastAPI + SQLite DB + seed data) ---
COPY medmatch/requirements.txt /app/medmatch/requirements.txt
RUN pip3 install --break-system-packages --no-cache-dir -r /app/medmatch/requirements.txt
COPY medmatch/backend /app/medmatch/backend
COPY medmatch/tests /app/medmatch/tests

# --- scanner: build React + bundle BFF ---
COPY personalized-product-scanner/package.json personalized-product-scanner/bun.lock* /app/scanner/
COPY personalized-product-scanner/index.html personalized-product-scanner/vite.config.ts \
     personalized-product-scanner/tsconfig.json personalized-product-scanner/metadata.json /app/scanner/
COPY personalized-product-scanner/src /app/scanner/src
WORKDIR /app/scanner
RUN npm install --no-audit --no-fund
COPY personalized-product-scanner/server.ts /app/scanner/server.ts
COPY personalized-product-scanner/server /app/scanner/server
RUN npm run build

COPY deploy/start.sh /app/start.sh
RUN chmod +x /app/start.sh

EXPOSE 8080
ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["/app/start.sh"]
