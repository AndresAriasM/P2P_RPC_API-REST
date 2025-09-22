from __future__ import annotations
import json
import os
import time
import asyncio
from typing import Dict, List, Set, Optional
from pathlib import Path

class PeerState:
    def __init__(self, self_url: str, storage_dir: str = "storage"):
        self.self_url = self_url
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(exist_ok=True)
        
        # Peer management
        self.known_peers: Dict[str, float] = {}  # url -> last_seen
        self.healthy_peers: Set[str] = set()
        self.failed_peers: Set[str] = set()
        
        # Rate limiting
        self.request_counts: Dict[str, List[float]] = {}  # peer_url -> timestamps
        self.download_counts: Dict[str, List[float]] = {}
        
        # File cache
        self.file_cache: Dict[str, Dict] = {}  # peer_url -> file_list
        self.cache_timestamps: Dict[str, float] = {}  # peer_url -> last_cache_time
        
        # Search tracking
        self.search_history: Dict[str, float] = {}  # query_hash -> timestamp
        
        self._load_persistent_state()

    def _load_persistent_state(self):
        """Load persistent state from disk"""
        state_file = self.storage_dir / "peer_state.json"
        if state_file.exists():
            try:
                with open(state_file, "r") as f:
                    data = json.load(f)
                    self.known_peers = data.get("known_peers", {})
                    self.file_cache = data.get("file_cache", {})
                    self.cache_timestamps = data.get("cache_timestamps", {})
            except Exception:
                pass

    def _save_persistent_state(self):
        """Save state to disk"""
        state_file = self.storage_dir / "peer_state.json"
        try:
            data = {
                "known_peers": self.known_peers,
                "file_cache": self.file_cache,
                "cache_timestamps": self.cache_timestamps
            }
            with open(state_file, "w") as f:
                json.dump(data, f)
        except Exception:
            pass

    def register_peer(self, url: str):
        """Register a peer and mark as healthy"""
        self.known_peers[url] = time.time()
        self.healthy_peers.add(url)
        self.failed_peers.discard(url)
        self._save_persistent_state()

    def mark_peer_failed(self, url: str):
        """Mark peer as failed"""
        self.failed_peers.add(url)
        self.healthy_peers.discard(url)

    def mark_peer_healthy(self, url: str):
        """Mark peer as healthy"""
        self.healthy_peers.add(url)
        self.failed_peers.discard(url)
        if url in self.known_peers:
            self.known_peers[url] = time.time()

    def list_peers(self) -> List[str]:
        """List all known peers including self"""
        peers = list(self.known_peers.keys())
        if self.self_url not in peers:
            peers.insert(0, self.self_url)
        return peers

    def list_healthy_peers(self) -> List[str]:
        """List only healthy peers"""
        return [p for p in self.list_peers() if p in self.healthy_peers or p == self.self_url]

    def check_rate_limit(self, peer_url: str, limit_type: str, limit_per_minute: int) -> bool:
        """Check if peer has exceeded rate limit"""
        now = time.time()
        counts_dict = self.request_counts if limit_type == "requests" else self.download_counts
        
        if peer_url not in counts_dict:
            counts_dict[peer_url] = []
        
        # Remove old timestamps (older than 1 minute)
        counts_dict[peer_url] = [t for t in counts_dict[peer_url] if now - t < 60]
        
        # Check if limit exceeded
        if len(counts_dict[peer_url]) >= limit_per_minute:
            return False
        
        # Add current timestamp
        counts_dict[peer_url].append(now)
        return True

    def get_cached_files(self, peer_url: str, max_age: int = 300) -> Optional[List[Dict]]:
        """Get cached file list for peer if not expired"""
        if peer_url not in self.file_cache:
            return None
        
        cache_time = self.cache_timestamps.get(peer_url, 0)
        if time.time() - cache_time > max_age:
            return None
        
        return self.file_cache[peer_url]

    def cache_files(self, peer_url: str, files: List[Dict]):
        """Cache file list for peer"""
        self.file_cache[peer_url] = files
        self.cache_timestamps[peer_url] = time.time()
        self._save_persistent_state()

    def should_search_again(self, query_hash: str, min_interval: int = 10) -> bool:
        """Check if enough time has passed since last search"""
        last_search = self.search_history.get(query_hash, 0)
        if time.time() - last_search < min_interval:
            return False
        
        self.search_history[query_hash] = time.time()
        return True

    def prune(self, ttl_seconds: int = 300):
        """Remove old peers and clean up state"""
        now = time.time()
        
        # Remove old peers
        to_del = [u for u, ts in self.known_peers.items() if now - ts > ttl_seconds]
        for u in to_del:
            self.known_peers.pop(u, None)
            self.healthy_peers.discard(u)
            self.failed_peers.discard(u)
            self.file_cache.pop(u, None)
            self.cache_timestamps.pop(u, None)
        
        # Clean old rate limit data
        for peer_url in list(self.request_counts.keys()):
            self.request_counts[peer_url] = [t for t in self.request_counts[peer_url] if now - t < 60]
            if not self.request_counts[peer_url]:
                del self.request_counts[peer_url]
        
        for peer_url in list(self.download_counts.keys()):
            self.download_counts[peer_url] = [t for t in self.download_counts[peer_url] if now - t < 60]
            if not self.download_counts[peer_url]:
                del self.download_counts[peer_url]
        
        # Clean old search history
        self.search_history = {k: v for k, v in self.search_history.items() if now - v < 3600}
        
        self._save_persistent_state()

    def get_stats(self) -> Dict:
        """Get state statistics"""
        return {
            "total_peers": len(self.known_peers),
            "healthy_peers": len(self.healthy_peers),
            "failed_peers": len(self.failed_peers),
            "cached_file_lists": len(self.file_cache),
            "active_rate_limited_peers": len(self.request_counts) + len(self.download_counts)
        }