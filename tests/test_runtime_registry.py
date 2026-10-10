import asyncio

import pytest

from brain.runtime.runtime_registry import RuntimeRegistry


class CompletingRuntime:
    def __init__(self, mission_id):
        self.mission_id = mission_id
        self._task = None

    def start(self):
        self._task = asyncio.create_task(asyncio.sleep(0))

    async def stop(self):
        if self._task is not None:
            await self._task


@pytest.mark.asyncio
async def test_registry_removes_runtime_after_execution_task_finishes():
    registry = RuntimeRegistry()
    runtime = CompletingRuntime("mission-1")
    registry.register(runtime)

    await registry.start("mission-1")
    await runtime._task
    await asyncio.sleep(0)

    assert registry.list_active() == []


@pytest.mark.asyncio
async def test_old_runtime_completion_does_not_unregister_replacement():
    registry = RuntimeRegistry()
    old_runtime = CompletingRuntime("mission-1")
    registry.register(old_runtime)
    await registry.start("mission-1")

    replacement = CompletingRuntime("mission-1")
    registry.register(replacement)
    await old_runtime._task
    await asyncio.sleep(0)

    assert registry.get_runtime("mission-1") is replacement
