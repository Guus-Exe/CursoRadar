FROM python:3.12-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PATH="/root/.local/bin:$PATH"

WORKDIR /app

# Install curl and ca-certificates to install uv
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    && curl -LsSf https://astral.sh/uv/install.sh | sh \
    && apt-get purge -y curl \
    && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/*

# Copy project definition files
COPY pyproject.toml README.md ./

# Install dependencies using uv
RUN uv sync --no-dev

# Copy application source code
COPY services/monitor/app/ ./services/monitor/app/

# Run the monitoring service
CMD ["uv", "run", "python", "-m", "app.main"]
