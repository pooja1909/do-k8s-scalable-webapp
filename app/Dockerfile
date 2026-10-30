# Small, secure image: Alpine-based Node.js, no build tools, runs as a non-root user.
FROM node:22-alpine

ENV NODE_ENV=production \
    PORT=8080

WORKDIR /app

# The app has no npm dependencies, so we only copy the source.
COPY package.json server.js ./

# The official node image ships with a non-root "node" user.
USER node

EXPOSE 8080

# Docker-level health check (Kubernetes uses its own probes defined in k8s/deployment.yaml).
HEALTHCHECK --interval=30s --timeout=3s CMD wget -qO- http://localhost:8080/healthz || exit 1

CMD ["node", "server.js"]
