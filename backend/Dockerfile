# Use Python 3.13 as base image
FROM python:3.13-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install uv for fast Python package management
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# Copy project files
COPY pyproject.toml ./
COPY uv.lock* ./

# Install dependencies (generate lock file if it doesn't exist, otherwise use frozen)
RUN if [ -f "uv.lock" ]; then \
    uv sync --frozen; \
    else \
    uv sync; \
    fi

# Copy source code
COPY . .

# Expose port
EXPOSE 8000

# Command to run the application
CMD ["uv", "run", "uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
