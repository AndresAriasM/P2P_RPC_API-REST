#!/usr/bin/env bash
set -euo pipefail

echo "Bootstrapping peers..."
for p in 8001 8002 8003; do
  curl -s -X POST http://localhost:${p}/bootstrap > /dev/null || true
done

echo "Peers:"
curl -s http://localhost:8001/peers | jq . || true

echo "Files on peer1:"
curl -s http://localhost:8001/files | jq . || true

echo "Search '*.txt' vía peer1 (fanout=2):"
curl -s "http://localhost:8001/search?query=.txt&fanout=2" | jq . || true

echo "Done."
