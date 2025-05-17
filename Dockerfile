# Use the full Python image to avoid missing system dependencies
FROM python:3.11-slim-bookworm
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    UV_NO_INDEX=1 \
    DEBIAN_FRONTEND=noninteractive

# Set the working directory inside the container
WORKDIR /app

# Copy project files
COPY pyproject.toml uv.lock ./
COPY src/ ./src/

EXPOSE 8000

# Install dependencies
RUN uv pip install --system --no-cache -r pyproject.toml

# ENV OAUTH2_PROXY_VERSION=7.4.0
# RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates && \
#     curl -fsSL https://github.com/oauth2-proxy/oauth2-proxy/releases/download/v${OAUTH2_PROXY_VERSION}/oauth2-proxy-v${OAUTH2_PROXY_VERSION}.linux-amd64.tar.gz \
#     | tar -xz --strip-components=1 -C /usr/local/bin oauth2-proxy-v${OAUTH2_PROXY_VERSION}.linux-amd64/oauth2-proxy && \
#     chmod +x /usr/local/bin/oauth2-proxy && \
#     apt-get purge -y curl && apt-get autoremove -y && rm -rf /var/lib/apt/lists/*

# # Add entrypoint script
# COPY start.sh /start.sh
# RUN chmod +x /start.sh

# EXPOSE 4180

# ENTRYPOINT ["/start.sh"]

# Set the entry point
CMD ["uv", "run", "python", "-m", "src.app", "--transport", "streamable-http", "--host", "0.0.0.0", "--port", "8000"]

