# Python 3.11 slim
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl \
    && rm -rf /var/lib/apt/lists/*

# Install deps
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
 && pip install --no-cache-dir -r requirements.txt

# Copy code
COPY app ./app
COPY static ./static

# Expose the app port
EXPOSE 8000

# Start the API
CMD ["uvicorn", "app.app_api:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
