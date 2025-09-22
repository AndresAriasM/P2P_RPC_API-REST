import json
import os
from dataclasses import dataclass
from typing import Dict, Any

@dataclass
class RateLimitConfig:
    requests_per_minute: int = 100
    downloads_per_minute: int = 10

@dataclass
class PeerConfig:
    name: str
    ip: str
    rest_port: int
    grpc_port: int
    metrics_port: int
    shared_dir: str
    friend_primary: str
    friend_secondary: str
    self_url: str
    health_check_interval: int = 30
    search_ttl: int = 3
    max_fanout: int = 3
    rate_limit: RateLimitConfig = None

def load_config(path: str | None = None) -> PeerConfig:
    path = path or os.environ.get("PEER_CONFIG", "configs/peer1.json")
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    rate_limit_data = data.get("rate_limit", {})
    rate_limit = RateLimitConfig(
        requests_per_minute=rate_limit_data.get("requests_per_minute", 100),
        downloads_per_minute=rate_limit_data.get("downloads_per_minute", 10)
    )
    
    return PeerConfig(
        name=data["name"],
        ip=data.get("ip", "0.0.0.0"),
        rest_port=int(data["rest_port"]),
        grpc_port=int(data["grpc_port"]),
        metrics_port=int(data.get("metrics_port", 9000)),
        shared_dir=data["shared_dir"],
        friend_primary=data.get("friend_primary", ""),
        friend_secondary=data.get("friend_secondary", ""),
        self_url=data["self_url"],
        health_check_interval=int(data.get("health_check_interval", 30)),
        search_ttl=int(data.get("search_ttl", 3)),
        max_fanout=int(data.get("max_fanout", 3)),
        rate_limit=rate_limit
    )