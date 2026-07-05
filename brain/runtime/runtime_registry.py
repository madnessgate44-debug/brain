"""Runtime registry for managing active mission runtimes."""

import asyncio
import logging
from typing import Dict, Optional

from brain.runtime.mission_runtime import MissionRuntime

logger = logging.getLogger("brain.runtime.runtime_registry")


class RuntimeRegistry:
    """Registry for tracking active mission runtimes."""
    
    def __init__(self):
        self._runtimes: Dict[str, MissionRuntime] = {}
        self._lock = asyncio.Lock()
    
    def register(self, runtime: MissionRuntime) -> None:
        """Register a runtime."""
        self._runtimes[runtime.mission_id] = runtime
    
    def unregister(self, mission_id: str) -> None:
        """Unregister a runtime."""
        if mission_id in self._runtimes:
            del self._runtimes[mission_id]
    
    async def start(self, mission_id: str) -> None:
        """Start a runtime."""
        async with self._lock:
            runtime = self._runtimes.get(mission_id)
            if not runtime:
                raise RuntimeError(f"Runtime for mission {mission_id} not found")
            
            runtime.start()
    
    async def stop(self, mission_id: str) -> None:
        """Stop a runtime."""
        async with self._lock:
            runtime = self._runtimes.get(mission_id)
            if runtime:
                await runtime.stop()
                self.unregister(mission_id)
    
    def get_runtime(self, mission_id: str) -> Optional[MissionRuntime]:
        """Get a runtime by mission ID."""
        return self._runtimes.get(mission_id)
    
    def list_active(self) -> list[str]:
        """List active mission IDs."""
        return list(self._runtimes.keys())
    
    async def stop_all(self) -> None:
        """Stop all active runtimes."""
        for mission_id in list(self._runtimes.keys()):
            await self.stop(mission_id)