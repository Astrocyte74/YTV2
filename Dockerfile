# Simple Dockerfile for YTV2 Dashboard
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# No extra OS packages needed (keep image small and builds fast)

# Copy requirements first for better caching
COPY requirements.txt .

# Speed pip a bit and reduce noise
ENV PIP_DISABLE_PIP_VERSION_CHECK=1
# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

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
