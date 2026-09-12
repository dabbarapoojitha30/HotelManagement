# Base image
FROM python:3.11-slim

# Python environment settings
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000

# Root app directory
WORKDIR /app

# 1. Install python dependencies first for Docker layer caching
COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir -r /app/backend/requirements.txt

# 2. Copy frontend assets
COPY index.html login.html owner.html /app/

# 3. Copy backend application code (excluding .env via .dockerignore)
COPY backend/ /app/backend/

# 4. Copy and set executable permissions on entrypoint script
COPY entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

# 5. Create uploads directory for Aadhaar / document storage
RUN mkdir -p /app/backend/uploads

# Working directory where FastAPI app module is located
WORKDIR /app/backend

# Document default container port
EXPOSE 8000

# Entrypoint handles dynamic port resolution (CLI arg, $PORT env var, or 8000)
ENTRYPOINT ["/app/entrypoint.sh"]
