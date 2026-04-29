# ── Frontend Dockerfile ─────────────────────────────────────────────────────
# Stage 1 – build
FROM node:22-alpine AS builder

WORKDIR /app

COPY package.json package-lock.json* ./
RUN npm install --legacy-peer-deps

COPY . .
RUN npm run build

# Stage 2 – serve with nginx
FROM nginx:alpine

COPY --from=builder /app/dist /usr/share/nginx/html

# nginx config that rewrites all paths to index.html (SPA routing)
RUN printf 'server {\n  listen 80;\n  root /usr/share/nginx/html;\n  index index.html;\n  location / {\n    try_files $uri $uri/ /index.html;\n  }\n  location /api/ {\n    proxy_pass http://backend:8000/;\n    proxy_set_header Host $host;\n  }\n}\n' \
    > /etc/nginx/conf.d/default.conf

EXPOSE 80
