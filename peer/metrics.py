import time
from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
from typing import Dict, Any

# Metrics definitions
REQUEST_COUNT = Counter('p2p_requests_total', 'Total P2P requests', ['method', 'endpoint', 'peer'])
REQUEST_DURATION = Histogram('p2p_request_duration_seconds', 'Request duration', ['method', 'endpoint'])
SEARCH_COUNT = Counter('p2p_searches_total', 'Total search requests', ['peer'])
SEARCH_RESULTS = Histogram('p2p_search_results_count', 'Number of results per search', ['peer'])
FILE_TRANSFERS = Counter('p2p_file_transfers_total', 'File transfer operations', ['operation', 'peer'])
TRANSFER_BYTES = Counter('p2p_transfer_bytes_total', 'Bytes transferred', ['operation', 'peer'])
PEER_COUNT = Gauge('p2p_known_peers_count', 'Number of known peers', ['peer'])
HEALTHY_PEER_COUNT = Gauge('p2p_healthy_peers_count', 'Number of healthy peers', ['peer'])
RATE_LIMIT_HITS = Counter('p2p_rate_limit_hits_total', 'Rate limit violations', ['peer', 'type'])

class MetricsCollector:
    def __init__(self, peer_name: str):
        self.peer_name = peer_name

    def record_request(self, method: str, endpoint: str, duration: float):
        REQUEST_COUNT.labels(method=method, endpoint=endpoint, peer=self.peer_name).inc()
        REQUEST_DURATION.labels(method=method, endpoint=endpoint).observe(duration)

    def record_search(self, result_count: int):
        SEARCH_COUNT.labels(peer=self.peer_name).inc()
        SEARCH_RESULTS.labels(peer=self.peer_name).observe(result_count)

    def record_file_transfer(self, operation: str, bytes_count: int):
        FILE_TRANSFERS.labels(operation=operation, peer=self.peer_name).inc()
        TRANSFER_BYTES.labels(operation=operation, peer=self.peer_name).inc(bytes_count)

    def update_peer_counts(self, total_peers: int, healthy_peers: int):
        PEER_COUNT.labels(peer=self.peer_name).set(total_peers)
        HEALTHY_PEER_COUNT.labels(peer=self.peer_name).set(healthy_peers)

    def record_rate_limit_hit(self, limit_type: str):
        RATE_LIMIT_HITS.labels(peer=self.peer_name, type=limit_type).inc()

    def get_metrics(self) -> str:
        return generate_latest()

    def get_content_type(self) -> str:
        return CONTENT_TYPE_LATEST

# Global metrics instance
_metrics: MetricsCollector = None

def init_metrics(peer_name: str):
    global _metrics
    _metrics = MetricsCollector(peer_name)

def get_metrics() -> MetricsCollector:
    return _metrics