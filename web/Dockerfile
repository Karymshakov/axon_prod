# --- Stage 1: Build ---
FROM node:20-alpine AS build

WORKDIR /app

# Install dependencies (uses package-lock.json for reproducible installs)
COPY package*.json ./
RUN npm ci

# Copy source code and build
COPY . .
RUN npm run build

# --- Stage 2: Serve ---
FROM nginx:1.25-alpine

# Copy compiled Vite output to Nginx html root
COPY --from=build /app/dist /usr/share/nginx/html

# The nginx.conf is mounted at runtime via docker-compose volume:
#   - ./nginx.conf:/etc/nginx/conf.d/default.conf:ro

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
