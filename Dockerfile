# Base image with Python 3.13.9 and minimal Debian packages
FROM python:3.13.9-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8501 \
    STREAMLIT_SERVER_PORT=8501 \
    STREAMLIT_SERVER_ENABLECORS=true \
    STREAMLIT_SERVER_ADDRESS=0.0.0.0 \
    STREAMLIT_BROWSER_GATHER_USAGE_STATS=false \
    UV_PROJECT_ENVIRONMENT=/app/.venv \
    UV_NO_DEV=1

WORKDIR /app

# System deps required by Prophet and friends
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      build-essential gcc g++ python3-dev git libgomp1 \
 && rm -rf /var/lib/apt/lists/*

# Install uv (copy binary from official uv image)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Copy dependency file first (better layer cache)
COPY requirements.txt ./requirements.txt

# If the project doesn't have pyproject.toml yet, create one;
# then import dependencies from requirements.txt
RUN test -f pyproject.toml || uv init --app \
 && uv add -r requirements.txt

# Copy source
COPY . .

EXPOSE 8501

# Run Streamlit inside the uv-managed environment
CMD ["uv", "run", "streamlit", "run", "main.py", "--server.port=8501", "--server.address=0.0.0.0"]
