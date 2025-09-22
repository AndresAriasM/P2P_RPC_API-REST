#!/usr/bin/env bash
set -euo pipefail

echo "=== P2P Enhanced Demo ==="
echo

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Wait for services to be ready
wait_for_service() {
    local url=$1
    local name=$2
    local max_attempts=30
    local attempt=1
    
    log_info "Waiting for $name to be ready..."
    while [ $attempt -le $max_attempts ]; do
        if curl -s -f "$url/health" > /dev/null 2>&1; then
            log_info "$name is ready!"
            return 0
        fi
        sleep 2
        ((attempt++))
    done
    
    log_error "$name failed to start after $max_attempts attempts"
    return 1
}

# Check if jq is available
if ! command -v jq &> /dev/null; then
    log_warn "jq not found. Output will be raw JSON."
    JQ_CMD="cat"
else
    JQ_CMD="jq ."
fi

echo "1. Waiting for all peers to start..."
wait_for_service "http://localhost:8001" "Peer1"
wait_for_service "http://localhost:8002" "Peer2"  
wait_for_service "http://localhost:8003" "Peer3"
wait_for_service "http://localhost:8004" "Peer4"

echo
echo "2. Bootstrapping peers..."
for port in 8001 8002 8003 8004; do
    log_info "Bootstrapping peer on port $port"
    curl -s -X POST "http://localhost:$port/bootstrap" | $JQ_CMD || log_warn "Bootstrap failed for port $port"
done

echo
echo "3. Checking peer status..."
for port in 8001 8002 8003 8004; do
    echo "--- Peer $port status ---"
    curl -s "http://localhost:$port/status" | $JQ_CMD || log_error "Failed to get status for port $port"
    echo
done

echo "4. Listing files on each peer..."
for port in 8001 8002 8003 8004; do
    echo "--- Files on peer $port ---"
    curl -s "http://localhost:$port/files" | $JQ_CMD || log_error "Failed to list files for port $port"
    echo
done

echo "5. Testing distributed search..."
log_info "Searching for '.txt' files with fanout=3"
curl -s "http://localhost:8001/search?query=.txt&fanout=3" | $JQ_CMD || log_error "Search failed"

echo
log_info "Searching for 'hello' files with fanout=2"
curl -s "http://localhost:8002/search?query=hello&fanout=2" | $JQ_CMD || log_error "Search failed"

echo
echo "6. Testing gRPC file transfers..."
log_info "Testing download from peer1"
docker exec -it peer1 bash -c "python client.py --download hello1.txt --grpc-host localhost --grpc-port 50051" || log_warn "Download test failed"

echo
log_info "Testing upload to peer2 (1MB)"
docker exec -it peer2 bash -c "python client.py --upload-mb 1 --grpc-host localhost --grpc-port 50052" || log_warn "Upload test failed"

echo
echo "7. Testing rate limiting..."
log_info "Making rapid requests to test rate limiting"
for i in {1..5}; do
    curl -s "http://localhost:8001/files" > /dev/null &
done
wait
log_info "Rate limiting test completed"

echo
echo "8. Health and metrics check..."
log_info "Checking peer health"
curl -s "http://localhost:8001/peers" | $JQ_CMD || log_error "Peers check failed"

echo
log_info "Checking metrics (first few lines)"
curl -s "http://localhost:8001/metrics" | head -20 || log_warn "Metrics not available"

echo
echo "9. Concurrent search test..."
log_info "Running concurrent searches to test concurrency"
for i in {1..3}; do
    curl -s "http://localhost:800$((i+1))/search?query=.txt&fanout=2" | $JQ_CMD &
done
wait
log_info "Concurrent search test completed"

echo
echo "=== Demo completed successfully! ==="
echo
echo "You can now:"
echo "- Open Grafana at http://localhost:3000 (admin/admin)"
echo "- Open Prometheus at http://localhost:9090"
echo "- Use the enhanced client: python client.py --help"
echo "- Check individual peer status: curl http://localhost:8001/status"
echo