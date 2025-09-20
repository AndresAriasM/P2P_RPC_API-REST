from __future__ import annotations
from typing import Dict, List
import time

class PeerState:
    def __init__(self, self_url: str):
        self.self_url = self_url
        self.known_peers: Dict[str, float] = {}  # url -> last_seen epoch

    def register_peer(self, url: str):
        self.known_peers[url] = time.time()

    def list_peers(self) -> List[str]:
        # include self as well
        peers = list(self.known_peers.keys())
        if self.self_url not in peers:
            peers.insert(0, self.self_url)
        return peers

    def prune(self, ttl_seconds: int = 300):
        now = time.time()
        to_del = [u for u, ts in self.known_peers.items() if now - ts > ttl_seconds]
        for u in to_del:
            self.known_peers.pop(u, None)
