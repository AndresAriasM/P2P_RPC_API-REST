import asyncio
import httpx
import logging
from typing import List, Dict, Any
from .state import PeerState

logger = logging.getLogger(__name__)

class HealthChecker:
    def __init__(self, state: PeerState, check_interval: int = 30):
        self.state = state
        self.check_interval = check_interval
        self.running = False
        self._task = None

    async def start(self):
        if self.running:
            return
        
        self.running = True
        self._task = asyncio.create_task(self._health_check_loop())
        logger.info(f"Health checker started with {self.check_interval}s interval")

    async def stop(self):
        self.running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def _health_check_loop(self):
        while self.running:
            try:
                await self._check_all_peers()
                await asyncio.sleep(self.check_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Health check error: {e}")
                await asyncio.sleep(5)

    async def _check_all_peers(self):
        peers = [p for p in self.state.list_peers() if p != self.state.self_url]
        if not peers:
            return

        async with httpx.AsyncClient(timeout=10) as client:
            tasks = [self._check_peer_health(client, peer) for peer in peers]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for peer, result in zip(peers, results):
                if isinstance(result, Exception) or not result:
                    self.state.mark_peer_failed(peer)
                else:
                    self.state.mark_peer_healthy(peer)

        self.state.prune()

    async def _check_peer_health(self, client: httpx.AsyncClient, peer_url: str) -> bool:
        try:
            response = await client.get(f"{peer_url}/health")
            return response.status_code == 200
        except Exception:
            return False

    async def check_peer_immediate(self, peer_url: str) -> bool:
        async with httpx.AsyncClient(timeout=5) as client:
            return await self._check_peer_health(client, peer_url)