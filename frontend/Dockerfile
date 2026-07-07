# =============================================================================
# RegulaForge - Frontend Dockerfile
# Multi-stage: build -> nginx runtime
# =============================================================================

FROM node:18-alpine AS builder

WORKDIR /app

ENV NODE_ENV=production

COPY frontend/package.json frontend/package-lock.json ./

RUN npm ci

COPY frontend/ ./

RUN npm run build


FROM nginx:1.25-alpine

ENV NGINX_PORT=80

RUN apk add --no-cache curl && \
    rm -rf /var/cache/apk/*

COPY --from=builder /app/dist /usr/share/nginx/html
COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf

HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl --fail http://localhost:${NGINX_PORT}/health || exit 1

EXPOSE 80

STOPSIGNAL SIGQUIT

CMD ["nginx", "-g", "daemon off;"]
