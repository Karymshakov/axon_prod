# --- Stage 1: Build ---
ARG NODE_IMAGE=mirror.gcr.io/library/node:20-alpine
FROM ${NODE_IMAGE} AS build

WORKDIR /app

# Install dependencies (uses package-lock.json for reproducible installs)
COPY package*.json ./
RUN npm ci

# Copy source code and build
COPY . .
RUN npm run build

# --- Stage 2: Serve ---
ARG NGINX_IMAGE=mirror.gcr.io/library/nginx:1.25-alpine
FROM ${NGINX_IMAGE}

# Copy compiled Vite output to Nginx html root
COPY --from=build /app/dist /usr/share/nginx/html

# The nginx.conf is mounted at runtime via docker-compose volume:
#   - ./nginx.conf:/etc/nginx/conf.d/default.conf:ro

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
