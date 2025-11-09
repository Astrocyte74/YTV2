# Simple Dockerfile for YTV2 Dashboard
FROM python:3.11.8-slim-bookworm

# Set working directory
WORKDIR /app

# No extra OS packages needed (keep image small and builds fast)

# Copy minimal dashboard requirements first for better caching
COPY requirements-dashboard.txt ./

# Speed pip a bit and reduce noise
ENV PIP_DISABLE_PIP_VERSION_CHECK=1
# Install Python dependencies (quiet, no cache)
ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_DEFAULT_TIMEOUT=60
RUN pip install --no-cache-dir --progress-bar off -r requirements-dashboard.txt

# Copy application code
COPY . .

# Create necessary directories
RUN mkdir -p data exports

# Expose port
EXPOSE 10000

# Health check via small Python script (no OS packages needed)
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 CMD ["python", "healthcheck.py"]

# Run the dashboard server
CMD ["python", "server.py"]
