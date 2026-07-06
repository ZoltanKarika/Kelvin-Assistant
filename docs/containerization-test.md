# Kelvin Backend Containerization Test Guide

This guide describes how to build, run, and verify the containerized Kelvin FastAPI server using Docker and Docker Compose on a separate development port.

This is a trial setup for testing purposes; the production installation remains managed under `systemd` on the `kelvin-ai` VM.

## 1. Prerequisites

Ensure you have Docker and Docker Compose installed on your host/VM:
```bash
docker --version
docker compose version
```

## 2. Configuration files

The following files are located in the repository root:
* [Dockerfile.backend](file:///c:/Users/Zoltan/Documents/Kelvin%20Assistant/Dockerfile.backend) — Multi-stage production-ready backend image builder.
* [docker-compose.test.yaml](file:///c:/Users/Zoltan/Documents/Kelvin%20Assistant/docker-compose.test.yaml) — Docker Compose configuration for starting the backend on development port `8080` (mapping to container port `8000`).

## 3. How to Run the Trial Stack

To build the Docker image and start the containerized service, run the following command in the repository root:
```bash
docker compose -f docker-compose.test.yaml up --build -d
```

Verify that the container is running:
```bash
docker compose -f docker-compose.test.yaml ps
```

To view logs:
```bash
docker compose -f docker-compose.test.yaml logs -f
```

## 4. Verification Procedures

### A. Health & Readiness Check
Query the containerized FastAPI server on the development port (`8080`):

```bash
# Health Check (unauthenticated)
curl http://127.0.0.1:8080/health

# Readiness Check (requires active API auth setup / token if enabled)
curl http://127.0.0.1:8080/ready
```

### B. Running Tests Against the Container
Ensure the local server behaves identically to the systemd-deployed version. You can configure tests to target port `8080` by updating your local `.env` or temporary test environment variables:

```bash
KELVIN_API_URL=http://127.0.0.1:8080 uv run pytest tests/ -q
```

## 5. Teardown
Once testing is completed, stop and remove the test container:
```bash
docker compose -f docker-compose.test.yaml down
```
