FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies for Chrome/Chromium
RUN apt-get update && apt-get install -y \
    chromium \
    chromium-driver \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application code
COPY src/ /app/src/
COPY pyproject.toml /app/

# Install the package
RUN pip install -e .

# Expose the API port
EXPOSE 8000

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app
ENV PORT=8765

# Run the API server
CMD uvicorn src.api.main:app --host 0.0.0.0 --port ${PORT}

