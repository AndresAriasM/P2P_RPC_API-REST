FROM python:3.11-slim

WORKDIR /app

# System deps
RUN apt-get update && apt-get install -y \
    build-essential \
    bash \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Generate gRPC code
RUN ./generate_proto.sh

# Create storage directory
RUN mkdir -p /app/storage

# Default environment (overridden by compose)
ENV PEER_CONFIG=configs/peer1.json

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8001/health || exit 1

# Enhanced entrypoint with better error handling
CMD bash -c " \
    echo 'Starting P2P peer services...' && \
    python -m peer.grpc_server & \
    GRPC_PID=$! && \
    echo 'gRPC server started (PID: $GRPC_PID)' && \
    sleep 2 && \
    CONFIG_FILE=\${PEER_CONFIG:-configs/peer1.json} && \
    REST_PORT=\$(python -c \"import json; print(json.load(open('\$CONFIG_FILE'))['rest_port'])\") && \
    echo \"Starting REST server on port \$REST_PORT\" && \
    python -c \"import uvicorn; from peer.app import app; uvicorn.run(app, host='0.0.0.0', port=\$REST_PORT, log_level='info')\" & \
    REST_PID=$! && \
    echo 'REST server started (PID: $REST_PID)' && \
    wait \
"