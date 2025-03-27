FROM python:3.11-slim

WORKDIR /app

# Copy requirements first to leverage Docker cache
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application code and entrypoint script
COPY graylogHUB.py .
COPY entrypoint.sh .

# Make entrypoint script executable
RUN chmod +x entrypoint.sh

# Create a non-root user
RUN useradd -m appuser && chown -R appuser:appuser /app
USER appuser

# Expose the GELF TCP port (will be specified at runtime)
EXPOSE ${GELF_PORT}

# Set environment variables
ENV PYTHONUNBUFFERED=1

# Use the entrypoint script
ENTRYPOINT ["./entrypoint.sh"]