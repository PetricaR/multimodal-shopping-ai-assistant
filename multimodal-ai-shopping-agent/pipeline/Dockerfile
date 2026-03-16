# Bringo Full Pipeline - Cloud Run Job
# Optimized for parallel category scraping with maximum resources
# Build context: project root (agent-bringo/)

FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements from pipeline folder first for better caching
COPY pipeline/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy all necessary modules
COPY bringo_catalog/ ./bringo_catalog/
COPY data/ ./data/
COPY embeddings/ ./embeddings/
COPY vector_search/ ./vector_search/
COPY features/ ./features/
COPY config/ ./config/
COPY pipeline/ ./pipeline/

# Set Python path and optimization environment variables
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Scraping optimizations
ENV AIOHTTP_NO_EXTENSIONS=1
# Sequential execution is now default (one category at a time)

# Default command: run full pipeline
CMD ["python", "pipeline/run_parallel_scraper.py"]
