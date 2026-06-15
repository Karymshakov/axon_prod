ARG PYTHON_IMAGE=mirror.gcr.io/library/python:3.12-slim
FROM ${PYTHON_IMAGE}

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Copy project files
COPY . /app/

# Create directory for logs, static, and media files
RUN mkdir -p /app/logs /app/staticfiles /app/media

# Create a non-root user with home directory and change ownership
RUN useradd -m -u 8888 appuser && chown -R appuser:appuser /app
USER appuser

# Expose port
EXPOSE 8000

# Auto-populate media volume if empty, then start Gunicorn
CMD ["sh", "-c", "mkdir -p /app/media/hotel_media && cp -rn /app/initial_media/. /app/media/ && gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 3"]
