"""Tests for Registry."""

from __future__ import annotations

import anyio
import pytest

from src.fauxtp import Registry, call, cast
from src.fauxtp.primitives.pid import PID
from src.fauxtp.actor.base import Actor


class DummyActor(Actor):
    """A simple actor for testing registration."""

    async def init(self):
        return {}

    async def run(self, state):
        await anyio.sleep_forever()
        return state


@pytest.mark.anyio
async def test_registry_get_returns_none_for_unregistered_name():
    """Getting a non-existent name returns None."""
    async with anyio.create_task_group() as tg:
        registry_pid = await Registry.start(task_group=tg)

        result = await call(registry_pid, ("get", "nonexistent"), timeout=1.0)
        assert result is None

        tg.cancel_scope.cancel()


@pytest.mark.anyio
async def test_registry_register_and_get():
    """Registering a PID allows it to be retrieved."""
    async with anyio.create_task_group() as tg:
        registry_pid = await Registry.start(task_group=tg)
        dummy_pid = await DummyActor.start(task_group=tg)

        # Register the dummy actor
        await cast(registry_pid, ("register", "my_actor", dummy_pid))

        # Retrieve it
        result = await call(registry_pid, ("get", "my_actor"), timeout=1.0)
        assert result._id == dummy_pid._id

        tg.cancel_scope.cancel()


@pytest.mark.anyio
async def test_registry_unregister_removes_entry():
    """Unregistering a name removes it from the registry."""
    async with anyio.create_task_group() as tg:
        registry_pid = await Registry.start(task_group=tg)
        dummy_pid = await DummyActor.start(task_group=tg)

        # Register and verify
        await cast(registry_pid, ("register", "temp_actor", dummy_pid))
        assert await call(registry_pid, ("get", "temp_actor"), timeout=1.0) == dummy_pid

        # Unregister and verify it's gone
        await cast(registry_pid, ("unregister", "temp_actor"))
        assert await call(registry_pid, ("get", "temp_actor"), timeout=1.0) is None

        tg.cancel_scope.cancel()


@pytest.mark.anyio
async def test_registry_multiple_registrations():
    """Multiple actors can be registered with different names."""
    async with anyio.create_task_group() as tg:
        registry_pid = await Registry.start(task_group=tg)
        pid1 = await DummyActor.start(task_group=tg)
        pid2 = await DummyActor.start(task_group=tg)
        pid3 = await DummyActor.start(task_group=tg)

        # Register multiple actors
        await cast(registry_pid, ("register", "actor1", pid1))
        await cast(registry_pid, ("register", "actor2", pid2))
        await cast(registry_pid, ("register", "actor3", pid3))

        # Verify all can be retrieved (compare by _id since mailbox may differ)
        assert (await call(registry_pid, ("get", "actor1"), timeout=1.0))._id == pid1._id
        assert (await call(registry_pid, ("get", "actor2"), timeout=1.0))._id == pid2._id
        assert (await call(registry_pid, ("get", "actor3"), timeout=1.0))._id == pid3._id

        tg.cancel_scope.cancel()


@pytest.mark.anyio
async def test_registry_register_overwrites_existing():
    """Registering a name that already exists overwrites the previous PID."""
    async with anyio.create_task_group() as tg:
        registry_pid = await Registry.start(task_group=tg)
        pid1 = await DummyActor.start(task_group=tg)
        pid2 = await DummyActor.start(task_group=tg)

        # Register first PID
        await cast(registry_pid, ("register", "shared_name", pid1))
        assert (await call(registry_pid, ("get", "shared_name"), timeout=1.0))._id == pid1._id

        # Register second PID with same name
        await cast(registry_pid, ("register", "shared_name", pid2))
        assert (await call(registry_pid, ("get", "shared_name"), timeout=1.0))._id == pid2._id

        tg.cancel_scope.cancel()


@pytest.mark.anyio
async def test_registry_unregister_nonexistent_is_noop():
    """Unregistering a non-existent name does nothing."""
    async with anyio.create_task_group() as tg:
        registry_pid = await Registry.start(task_group=tg)

        # This should not raise
        await cast(registry_pid, ("unregister", "never_registered"))

        # Verify registry still works
        assert await call(registry_pid, ("get", "never_registered"), timeout=1.0) is None

        tg.cancel_scope.cancel()


@pytest.mark.anyio
async def test_registry_concurrent_registrations():
    """Multiple concurrent registrations are handled correctly."""
    async with anyio.create_task_group() as tg:
        registry_pid = await Registry.start(task_group=tg)

        # Create multiple actors
        pids = [await DummyActor.start(task_group=tg) for _ in range(10)]

        # Register all concurrently
        async def register_actor(name: str, pid: PID):
            await cast(registry_pid, ("register", name, pid))

        async with anyio.create_task_group() as reg_tg:
            for i, pid in enumerate(pids):
                reg_tg.start_soon(register_actor, f"actor_{i}", pid)

        # Verify all registrations succeeded (compare by _id)
        for i, pid in enumerate(pids):
            result = await call(registry_pid, ("get", f"actor_{i}"), timeout=1.0)
            assert result._id == pid._id

        tg.cancel_scope.cancel()


@pytest.mark.anyio
async def test_registry_state_isolation_between_instances():
    """Different registry instances have isolated state."""
    async with anyio.create_task_group() as tg:
        registry1 = await Registry.start(task_group=tg)
        registry2 = await Registry.start(task_group=tg)
        pid = await DummyActor.start(task_group=tg)

        # Register in first registry only
        await cast(registry1, ("register", "my_actor", pid))

        # Verify it's in first but not second
        assert (await call(registry1, ("get", "my_actor"), timeout=1.0))._id == pid._id
        assert await call(registry2, ("get", "my_actor"), timeout=1.0) is None

        tg.cancel_scope.cancel()


@pytest.mark.anyio
async def test_registry_empty_name_allowed():
    """Empty string can be used as a name."""
    async with anyio.create_task_group() as tg:
        registry_pid = await Registry.start(task_group=tg)
        pid = await DummyActor.start(task_group=tg)

        await cast(registry_pid, ("register", "", pid))
        assert (await call(registry_pid, ("get", ""), timeout=1.0))._id == pid._id

        tg.cancel_scope.cancel()


@pytest.mark.anyio
async def test_registry_handles_unexpected_call_patterns():
    """Unknown call patterns return None without error."""
    async with anyio.create_task_group() as tg:
        registry_pid = await Registry.start(task_group=tg)

        # Various unexpected patterns
        assert await call(registry_pid, "unexpected", timeout=1.0) is None
        assert await call(registry_pid, ("wrong", "pattern"), timeout=1.0) is None
        assert await call(registry_pid, ("get",), timeout=1.0) is None  # Missing name
        assert await call(registry_pid, ("get", "name", "extra"), timeout=1.0) is None

        tg.cancel_scope.cancel()