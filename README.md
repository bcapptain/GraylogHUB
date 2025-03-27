# GELF to Azure Function Forwarder

A Docker containerized service that forwards GELF (Graylog Extended Log Format) messages from TCP to an Azure Function endpoint.

## Features

- TCP server for receiving GELF messages
- HTTP forwarding to Azure Functions
- Automatic retry with exponential backoff
- Connection timeout handling
- Message size limits
- Basic metrics tracking
- Docker and Docker Compose support
- Health checks
- Log rotation

## Prerequisites

- Docker
- Docker Compose
- Azure Function URL

## Setup

1. Clone this repository
2. Copy the environment file:
   ```bash
   cp .env.example .env
   ```
3. Edit `.env` and set your Azure Function URL

## Usage

### Using Docker Compose (Recommended)

```bash
# Start the service
docker-compose up -d

# View logs
docker-compose logs -f

# Stop the service
docker-compose down
```

### Using Docker directly

```bash
# Build the image
docker build -t graylog-forwarder .

# Run the container
docker run -d \
  --name graylog-forwarder \
  -p 12202:12202 \
  -e FUNCTION_URL=your-azure-function-url \
  graylog-forwarder
```

## Configuration

The service can be configured using environment variables:

- `FUNCTION_URL`: Azure Function URL (required)
- `TZ`: Timezone (default: UTC)

Additional configuration options can be passed as command-line arguments to the Python script:

- `--host`: TCP server host (default: 0.0.0.0)
- `--port`: TCP server port (default: 12202)
- `--debug`: Enable debug logging
- `--connection-timeout`: Connection timeout in seconds (default: 60)
- `--max-message-size`: Maximum message size in bytes (default: 1MB)

## Health Checks

The container includes a health check that verifies the TCP port is listening. You can check the container's health status with:

```bash
docker inspect --format='{{.State.Health.Status}}' graylog-forwarder
```

## Logs

Logs are written to stdout/stderr and can be viewed using:

```bash
docker-compose logs -f
```

Logs are automatically rotated using Docker's json-file logging driver with a maximum size of 10MB and 3 rotated files.

## Security

- The container runs as a non-root user
- All dependencies are installed from official PyPI
- Regular security updates through base image updates

## License

MIT 