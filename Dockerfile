##############################
# Dockerfile for SRP
##############################

# Use a multi-stage build to keep the final image slim
FROM python:3.11-slim as builder

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Create a virtual environment for installing dependencies
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Final runtime stage
FROM python:3.11-slim
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create a non-root user and directories for data and cache
RUN useradd -m -u 1000 srp && \
    mkdir -p /app /data /cache && \
    chown -R srp:srp /app /data /cache

# Copy the virtual environment from the builder stage
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Set working directory
WORKDIR /app

# Copy the application code and install it in editable mode
COPY --chown=srp:srp . .
RUN pip install -e .

# Switch to non-root user
USER srp

# Expose port 8000 for the web server
EXPOSE 8000

# Healthcheck to verify the server is responding
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/ || exit 1

# Default command; can be overridden at runtime
CMD ["srp", "serve", "--host", "0.0.0.0", "--port", "8000"]