# Standard production Dockerfile for Lanvan
FROM python:3.10-slim

# Prevent Python from writing .pyc files and enable unbuffered logging
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    LANVAN_ENV=production \
    PRODUCTION=true

WORKDIR /app

# Install system dependencies required for cryptography / networking
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency definition & install Python packages
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY app/ ./app/
COPY certs/ ./certs/
COPY data/ ./data/
COPY build.py run.py docker-entrypoint.sh ./

# Make entrypoint executable & pre-build production assets
RUN chmod +x docker-entrypoint.sh && python build.py

# Expose standard HTTP and HTTPS ports
EXPOSE 80 443

# Establish persistent volume target
VOLUME ["/app/data"]

# Define container entrypoint
ENTRYPOINT ["/app/docker-entrypoint.sh"]
