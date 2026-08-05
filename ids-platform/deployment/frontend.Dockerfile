# Frontend Dockerfile - multi-stage: node builder compiles the Vite app,
# nginx:1.27-alpine serves the static build with the custom nginx.conf.

FROM node:22-alpine AS builder

WORKDIR /build

COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend/ ./
RUN npm run build

# ---------------- runtime ----------------
FROM nginx:1.27-alpine

COPY deployment/nginx/nginx.conf /etc/nginx/nginx.conf
COPY --from=builder /build/dist /usr/share/nginx/html

EXPOSE 80 443

CMD ["nginx", "-g", "daemon off;"]
