from __future__ import annotations
import asyncio
import os
import re
from typing import Dict, Any, List

import httpx
from fastapi import FastAPI, HTTPException, Body, Query
from pydantic import BaseModel

from .config import load_config
from .indexer import list_files
from .state import PeerState

CFG = load_config(os.environ.get("PEER_CONFIG"))

app = FastAPI(title=f"P2P Peer REST - {CFG.name}")
STATE = PeerState(CFG.self_url)

class RegisterPayload(BaseModel):
    url: str

@app.get("/health")
async def health():
    return {"status": "ok", "peer": CFG.name}

@app.post("/register")
async def register(payload: RegisterPayload):
    STATE.register_peer(payload.url)
    return {"ok": True, "peers": STATE.list_peers()}

@app.get("/peers")
async def peers():
    return {"peers": STATE.list_peers()}

@app.get("/files")
async def files():
    return {
        "peer": CFG.name,
        "base": CFG.self_url,
        "files": [
            {**f, "rest_url": f"{CFG.self_url}/files/{f['name']}", "grpc": f"grpc://{CFG.ip}:{CFG.grpc_port}"}
            for f in list_files(CFG.shared_dir)
        ],
    }

@app.get("/search")
async def search(query: str = Query(""), fanout: int = Query(2)):
    """Search locally and across known peers (breadth-limited)."""
    # local
    local = [f for f in list_files(CFG.shared_dir) if query.lower() in f["name"].lower()]
    results: List[Dict[str, Any]] = [{"peer": CFG.self_url, "files": local}]

    # remote
    peers = [p for p in STATE.list_peers() if p != CFG.self_url]
    peers = peers[:max(0, fanout)]
    async with httpx.AsyncClient(timeout=5) as client:
        tasks = [client.get(f"{p}/files") for p in peers]
        if tasks:
            responses = await asyncio.gather(*tasks, return_exceptions=True)
            for resp in responses:
                if isinstance(resp, Exception):
                    continue
                try:
                    j = resp.json()
                    filtered = [f for f in j.get("files", []) if query.lower() in f["name"].lower()]
                    results.append({"peer": j.get("base", ""), "files": filtered})
                except Exception:
                    continue
    return {"query": query, "results": results}

@app.post("/bootstrap")
async def bootstrap():
    """Called on startup (or manually) to register with friend peers."""
    for friend in [CFG.friend_primary, CFG.friend_secondary]:
        if not friend:
            continue
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                # Register ourselves there and also record them here
                await client.post(f"{friend}/register", json={"url": CFG.self_url})
                STATE.register_peer(friend)
        except Exception:
            # best-effort
            pass
    # Always self-register
    STATE.register_peer(CFG.self_url)
    return {"ok": True, "known": STATE.list_peers()}
