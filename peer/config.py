import json
import os
from dataclasses import dataclass
from typing import List

@dataclass
class PeerConfig:
    name: str
    ip: str
    rest_port: int
    grpc_port: int
    shared_dir: str
    friend_primary: str
    friend_secondary: str
    self_url: str

def load_config(path: str | None = None) -> PeerConfig:
    path = path or os.environ.get("PEER_CONFIG", "configs/peer1.json")
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return PeerConfig(
        name=data["name"],
        ip=data.get("ip", "0.0.0.0"),
        rest_port=int(data["rest_port"]),
        grpc_port=int(data["grpc_port"]),
        shared_dir=data["shared_dir"],
        friend_primary=data.get("friend_primary",""),
        friend_secondary=data.get("friend_secondary",""),
        self_url=data["self_url"],
    )
