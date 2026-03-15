# Production-ready Dockerfile for Bringo Product Similarity API
# Optimized for Cloud Run deployment

FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    curl \
    gnupg \
    wget \
    unzip \
    && rm -rf /var/lib/apt/lists/*

# Install Google Chrome (using new APT key method)
RUN wget -q -O /tmp/google-chrome-stable_current_amd64.deb \
    https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb \
    && apt-get update \
    && apt-get install -y /tmp/google-chrome-stable_current_amd64.deb \
    && rm /tmp/google-chrome-stable_current_amd64.deb \
    && rm -rf /var/lib/apt/lists/*

# Install ChromeDriver provided by the package manager or matching version
# For simplicity in this env, we rely on webdriver-manager in python code to handle driver binary,
# BUT we need to ensure dependencies are met.
# Installing chrome-stable is usually enough if we use webdriver-manager.


# Copy requirements first (for better caching)
COPY requirements.txt .

# Install Python dependencies
# Install uv for fast package management
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# Install Python dependencies with uv
RUN uv pip install --system -r requirements.txt

# Explicitly copy only necessary application code
COPY api ./api
COPY config ./config
COPY services ./services
COPY database ./database
COPY data ./data
COPY features ./features
COPY ranking ./ranking
COPY substitution ./substitution
COPY vector_search ./vector_search
COPY embeddings ./embeddings

# Create logs directory
RUN mkdir -p logs

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PORT=8080
ENV PYTHONPATH=/app

# Expose port
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8080/ || exit 1

# Run the application
CMD ["python", "-m", "api.main"]
