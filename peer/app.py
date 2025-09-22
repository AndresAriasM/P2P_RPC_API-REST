from __future__ import annotations
import asyncio
import hashlib
import os
import time
from typing import Dict, Any, List

import httpx
from fastapi import FastAPI, HTTPException, Body, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .config import load_config
from .indexer import list_files
from .state import PeerState
from .health import HealthChecker
from .metrics import init_metrics, get_metrics

CFG = load_config(os.environ.get("PEER_CONFIG"))

app = FastAPI(title=f"P2P Peer REST - {CFG.name}")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize global state
STATE = PeerState(CFG.self_url)
health_checker = HealthChecker(STATE, CFG.health_check_interval)
init_metrics(CFG.name)

class RegisterPayload(BaseModel):
    url: str

@app.on_event("startup")
async def startup_event():
    await health_checker.start()

@app.on_event("shutdown")
async def shutdown_event():
    await health_checker.stop()

@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    duration = time.time() - start_time
    
    metrics = get_metrics()
    if metrics:
        metrics.record_request(
            method=request.method,
            endpoint=request.url.path,
            duration=duration
        )
    
    return response

@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    client_ip = request.client.host if request.client else "unknown"
    
    # Check rate limit for non-health endpoints
    if request.url.path not in ["/health", "/metrics"]:
        if not STATE.check_rate_limit(client_ip, "requests", CFG.rate_limit.requests_per_minute):
            metrics = get_metrics()
            if metrics:
                metrics.record_rate_limit_hit("requests")
            raise HTTPException(status_code=429, detail="Rate limit exceeded")
    
    return await call_next(request)

@app.get("/health")
async def health():
    stats = STATE.get_stats()
    return {
        "status": "ok",
        "peer": CFG.name,
        "url": CFG.self_url,
        "stats": stats
    }

@app.get("/metrics")
async def metrics():
    metrics = get_metrics()
    if not metrics:
        return Response("Metrics not initialized", status_code=500)
    
    # Update peer counts
    stats = STATE.get_stats()
    metrics.update_peer_counts(stats["total_peers"], stats["healthy_peers"])
    
    return Response(
        content=metrics.get_metrics(),
        media_type=metrics.get_content_type()
    )

@app.post("/register")
async def register(payload: RegisterPayload):
    STATE.register_peer(payload.url)
    
    # Immediate health check for new peer
    is_healthy = await health_checker.check_peer_immediate(payload.url)
    if is_healthy:
        STATE.mark_peer_healthy(payload.url)
    else:
        STATE.mark_peer_failed(payload.url)
    
    return {"ok": True, "peers": STATE.list_healthy_peers()}

@app.get("/peers")
async def peers():
    return {
        "peers": STATE.list_healthy_peers(),
        "all_peers": STATE.list_peers(),
        "stats": STATE.get_stats()
    }

@app.get("/files")
async def files():
    file_list = list_files(CFG.shared_dir)
    
    return {
        "peer": CFG.name,
        "base": CFG.self_url,
        "files": [
            {
                **f,
                "rest_url": f"{CFG.self_url}/files/{f['name']}",
                "grpc": f"grpc://{CFG.ip}:{CFG.grpc_port}",
                "checksum": f.get("checksum", "")
            }
            for f in file_list
        ],
    }

@app.get("/search")
async def search(query: str = Query(""), fanout: int = Query(2), ttl: int = Query(3)):
    """Enhanced search with TTL, caching, and better fanout control."""
    
    # Create query hash for deduplication
    query_hash = hashlib.md5(f"{query}:{fanout}".encode()).hexdigest()
    
    # Check if we searched this recently
    if not STATE.should_search_again(query_hash, min_interval=10):
        # Return cached results if available
        cached = STATE.get_cached_files(CFG.self_url, max_age=60)
        if cached:
            local_filtered = [f for f in cached if query.lower() in f["name"].lower()]
            return {
                "query": query,
                "cached": True,
                "results": [{"peer": CFG.self_url, "files": local_filtered}]
            }
    
    # Local search
    local_files = list_files(CFG.shared_dir)
    local_filtered = [f for f in local_files if query.lower() in f["name"].lower()]
    results: List[Dict[str, Any]] = [{"peer": CFG.self_url, "files": local_filtered}]
    
    # Remote search with improved fanout and health checking
    if ttl > 0:
        healthy_peers = [p for p in STATE.list_healthy_peers() if p != CFG.self_url]
        
        # Limit fanout
        target_fanout = min(fanout, CFG.max_fanout, len(healthy_peers))
        selected_peers = healthy_peers[:target_fanout]
        
        async with httpx.AsyncClient(timeout=10) as client:
            tasks = []
            for peer in selected_peers:
                # Check cache first
                cached_files = STATE.get_cached_files(peer, max_age=300)
                if cached_files:
                    filtered = [f for f in cached_files if query.lower() in f["name"].lower()]
                    results.append({"peer": peer, "files": filtered, "cached": True})
                else:
                    # Make remote request
                    task = _search_peer(client, peer, query, ttl - 1)
                    tasks.append((peer, task))
            
            if tasks:
                responses = await asyncio.gather(*[task for _, task in tasks], return_exceptions=True)
                for (peer, _), resp in zip(tasks, responses):
                    if isinstance(resp, Exception):
                        STATE.mark_peer_failed(peer)
                        continue
                    
                    try:
                        if resp and resp.status_code == 200:
                            data = resp.json()
                            # Cache the files
                            if "files" in data:
                                STATE.cache_files(peer, data["files"])
                            
                            # Add to results
                            filtered = [f for f in data.get("files", []) if query.lower() in f["name"].lower()]
                            results.append({"peer": data.get("base", peer), "files": filtered})
                        else:
                            STATE.mark_peer_failed(peer)
                    except Exception:
                        STATE.mark_peer_failed(peer)
    
    # Record metrics
    metrics = get_metrics()
    if metrics:
        total_results = sum(len(r["files"]) for r in results)
        metrics.record_search(total_results)
    
    return {
        "query": query,
        "ttl": ttl,
        "fanout_used": min(fanout, CFG.max_fanout),
        "results": results
    }

async def _search_peer(client: httpx.AsyncClient, peer: str, query: str, ttl: int):
    """Search a specific peer with TTL"""
    try:
        return await client.get(
            f"{peer}/files",
            params={"ttl": ttl} if ttl > 0 else {}
        )
    except Exception:
        return None

@app.post("/bootstrap")
async def bootstrap():
    """Enhanced bootstrap with better error handling and health checks."""
    registered_peers = []
    failed_peers = []
    
    for friend in [CFG.friend_primary, CFG.friend_secondary]:
        if not friend:
            continue
        
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                # Register ourselves
                resp = await client.post(f"{friend}/register", json={"url": CFG.self_url})
                if resp.status_code == 200:
                    STATE.register_peer(friend)
                    
                    # Immediate health check
                    is_healthy = await health_checker.check_peer_immediate(friend)
                    if is_healthy:
                        STATE.mark_peer_healthy(friend)
                        registered_peers.append(friend)
                    else:
                        STATE.mark_peer_failed(friend)
                        failed_peers.append(friend)
                else:
                    failed_peers.append(friend)
        except Exception as e:
            failed_peers.append(friend)
    
    # Always self-register
    STATE.register_peer(CFG.self_url)
    STATE.mark_peer_healthy(CFG.self_url)
    
    return {
        "ok": True,
        "peer": CFG.name,
        "registered": registered_peers,
        "failed": failed_peers,
        "known_peers": STATE.list_healthy_peers()
    }

@app.get("/status")
async def status():
    """Detailed status endpoint for monitoring"""
    stats = STATE.get_stats()
    
    return {
        "peer": CFG.name,
        "url": CFG.self_url,
        "config": {
            "rest_port": CFG.rest_port,
            "grpc_port": CFG.grpc_port,
            "shared_dir": CFG.shared_dir,
            "max_fanout": CFG.max_fanout,
            "search_ttl": CFG.search_ttl
        },
        "stats": stats,
        "healthy_peers": STATE.list_healthy_peers(),
        "all_peers": STATE.list_peers(),
        "uptime": time.time()
    }