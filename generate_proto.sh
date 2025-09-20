#!/usr/bin/env bash
set -euo pipefail
python -m grpc_tools.protoc -I peer/protos   --python_out=peer/protos   --grpc_python_out=peer/protos   peer/protos/filetransfer.proto
