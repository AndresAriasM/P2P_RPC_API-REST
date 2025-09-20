FROM python:3.11-slim

WORKDIR /app

# System deps
RUN apt-get update && apt-get install -y build-essential bash curl && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Generate gRPC code
RUN ./generate_proto.sh

# Default environment (overridden by compose)
ENV PEER_CONFIG=configs/peer1.json

# Entrypoint: start gRPC and REST in the same container
CMD bash -lc "python -m peer.grpc_server & python -c 'import json,os,uvicorn; from peer.app import app; port=int(json.load(open(os.environ.get("PEER_CONFIG","configs/peer1.json")))['rest_port']); uvicorn.run(app, host="0.0.0.0", port=port)'"
