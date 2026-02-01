"""Tests for Supervisor.

These tests focus on:
- child registration/unregistration via Registry
- restart behavior for ONE_FOR_ONE and ONE_FOR_ALL

They avoid fixed sleeps by using explicit probe mailboxes and timeouts.
"""

from __future__ import annotations

import uuid

import anyio
import pytest

from src.fauxtp import ANY, Actor, Mailbox, ReceiveTimeout, call, send
from src.fauxtp.primitives.pid import PID
from src.fauxtp.registry import Registry
from src.fauxtp.supervisor import ChildSpec, RestartStrategy, Supervisor


def _make_probe() -> tuple[Mailbox, PID]:
    mailbox = Mailbox()
    pid = PID(_id=uuid.uuid4(), _mailbox=mailbox)
    return mailbox, pid


async def _await_registry_pid(registry: PID, name: str, *, timeout: float = 1.0) -> PID:
    """Wait until the Registry resolves a name to a PID."""
    with anyio.fail_after(timeout):
        while True:
            pid = await call(registry, ("get", name), timeout=timeout)
            if pid is not None:
                return pid
            # Yield to allow actor tasks to progress without fixed sleeps.
            await anyio.sleep(0)


async def _await_registry_none(registry: PID, name: str, *, timeout: float = 1.0) -> None:
    """Wait until the Registry returns None for a name."""
    with anyio.fail_after(timeout):
        while True:
            pid = await call(registry, ("get", name), timeout=timeout)
            if pid is None:
                return
            await anyio.sleep(0)


class NotifyingWorker(Actor):
    """Test worker that can be stopped or crashed and notifies a probe mailbox."""

    def __init__(self, name: str, probe: PID):
        super().__init__()
        self._name = name
        self._probe = probe

    async def init(self):
        await send(self._probe, ("started", self._name, self.pid))
        return {}

    async def run(self, state):
        async def boom() -> None:
            raise RuntimeError(f"boom:{self._name}")

        def stop() -> None:
            self.stop("normal")

        return await self.receive(
            (("boom",), boom),
            (("stop",), stop),
            (ANY, lambda _m: state),
        )

    async def terminate(self, reason: str, state) -> None:  # pyright: ignore[reportUnknownParameterType]
        await send(self._probe, ("terminated", self._name, reason))


@pytest.mark.anyio
async def test_supervisor_starts_children_and_registers_names_in_registry():
    async with anyio.create_task_group() as tg:
        registry = await Registry.start(task_group=tg)
        probe_mb, probe_pid = _make_probe()

        await Supervisor.start(
            children=[
                ChildSpec(actor=NotifyingWorker, name="w1", args=("w1", probe_pid)),
                ChildSpec(actor=NotifyingWorker, name="w2", args=("w2", probe_pid)),
            ],
            strategy=RestartStrategy.ONE_FOR_ONE,
            registry=registry,
            task_group=tg,
        )

        # Registry eventually contains both names.
        w1 = await _await_registry_pid(registry, "w1", timeout=1.0)
        w2 = await _await_registry_pid(registry, "w2", timeout=1.0)
        assert w1._id != w2._id

        # Children did start (probe messages are observable).
        started = {
            await probe_mb.receive((("started", str, PID), lambda name, pid: (name, pid)), timeout=1.0),
            await probe_mb.receive((("started", str, PID), lambda name, pid: (name, pid)), timeout=1.0),
        }
        assert {name for name, _pid in started} == {"w1", "w2"}

        tg.cancel_scope.cancel()


@pytest.mark.anyio
async def test_supervisor_one_for_one_restarts_crashed_child_and_updates_registry():
    async with anyio.create_task_group() as tg:
        registry = await Registry.start(task_group=tg)
        probe_mb, probe_pid = _make_probe()

        await Supervisor.start(
            children=[ChildSpec(actor=NotifyingWorker, name="w1", args=("w1", probe_pid))],
            strategy=RestartStrategy.ONE_FOR_ONE,
            registry=registry,
            task_group=tg,
        )

        # Drain the initial start notification so subsequent reads observe only restart behavior.
        started_pid = await probe_mb.receive(
            (("started", "w1", PID), lambda pid: pid),
            timeout=1.0,
        )

        old_pid = await _await_registry_pid(registry, "w1", timeout=1.0)
        assert old_pid._id == started_pid._id

        # Crash it.
        await send(old_pid, ("boom",))

        reason = await probe_mb.receive(
            (("terminated", "w1", str), lambda r: r),
            timeout=1.0,
        )
        assert reason.startswith("error:")

        new_pid_from_probe = await probe_mb.receive(
            (("started", "w1", PID), lambda pid: pid),
            timeout=1.0,
        )
        assert new_pid_from_probe._id != old_pid._id

        new_pid_from_registry = await _await_registry_pid(registry, "w1", timeout=1.0)
        assert new_pid_from_registry._id == new_pid_from_probe._id

        tg.cancel_scope.cancel()


@pytest.mark.anyio
async def test_supervisor_does_not_restart_on_normal_exit_and_unregisters_name():
    async with anyio.create_task_group() as tg:
        registry = await Registry.start(task_group=tg)
        probe_mb, probe_pid = _make_probe()

        await Supervisor.start(
            children=[ChildSpec(actor=NotifyingWorker, name="w1", args=("w1", probe_pid))],
            strategy=RestartStrategy.ONE_FOR_ONE,
            registry=registry,
            task_group=tg,
        )

        # Drain the initial start notification.
        _ = await probe_mb.receive((("started", "w1", PID), lambda pid: pid), timeout=1.0)

        pid = await _await_registry_pid(registry, "w1", timeout=1.0)

        await send(pid, ("stop",))
        reason = await probe_mb.receive((("terminated", "w1", str), lambda r: r), timeout=1.0)
        assert reason == "normal"

        await _await_registry_none(registry, "w1", timeout=1.0)

        # Ensure it was not restarted (no additional started message).
        with pytest.raises(ReceiveTimeout):
            await probe_mb.receive((("started", "w1", PID), lambda pid: pid), timeout=0.1)

        tg.cancel_scope.cancel()


@pytest.mark.anyio
async def test_supervisor_one_for_all_restarts_all_children_after_one_crashes():
    async with anyio.create_task_group() as tg:
        registry = await Registry.start(task_group=tg)
        probe_mb, probe_pid = _make_probe()

        await Supervisor.start(
            children=[
                ChildSpec(actor=NotifyingWorker, name="a", args=("a", probe_pid)),
                ChildSpec(actor=NotifyingWorker, name="b", args=("b", probe_pid)),
            ],
            strategy=RestartStrategy.ONE_FOR_ALL,
            registry=registry,
            task_group=tg,
        )

        # Drain initial start notifications.
        initial_starts: dict[str, PID] = {}
        while set(initial_starts.keys()) != {"a", "b"}:
            name, pid = await probe_mb.receive(
                (("started", str, PID), lambda n, p: (n, p)),
                timeout=1.0,
            )
            initial_starts[name] = pid

        a1 = await _await_registry_pid(registry, "a", timeout=1.0)
        b1 = await _await_registry_pid(registry, "b", timeout=1.0)
        assert a1._id != b1._id
        assert initial_starts["a"]._id == a1._id
        assert initial_starts["b"]._id == b1._id

        # Crash 'a' (should cancel 'b' and then restart both).
        await send(a1, ("boom",))

        terminations: dict[str, str] = {}
        while set(terminations.keys()) != {"a", "b"}:
            name, reason = await probe_mb.receive(
                (("terminated", str, str), lambda n, r: (n, r)),
                timeout=2.0,
            )
            terminations[name] = reason

        assert terminations["a"].startswith("error:")
        assert terminations["b"] == "cancelled"

        # Both should start again.
        restarts: dict[str, PID] = {}
        while set(restarts.keys()) != {"a", "b"}:
            name, pid = await probe_mb.receive(
                (("started", str, PID), lambda n, p: (n, p)),
                timeout=2.0,
            )
            # Ignore any duplicate starts for the old pids (shouldn't happen after draining,
            # but keep this defensive).
            if name == "a" and pid._id == a1._id:
                continue
            if name == "b" and pid._id == b1._id:
                continue
            restarts[name] = pid

        assert restarts["a"]._id != a1._id
        assert restarts["b"]._id != b1._id

        # Registry should point at the restarted PIDs.
        a2 = await _await_registry_pid(registry, "a", timeout=1.0)
        b2 = await _await_registry_pid(registry, "b", timeout=1.0)
        assert a2._id == restarts["a"]._id
        assert b2._id == restarts["b"]._id

        tg.cancel_scope.cancel()


@pytest.mark.anyio
async def test_supervisor_can_start_with_internal_registry_when_registry_none():
    async with anyio.create_task_group() as tg:
        probe_mb, probe_pid = _make_probe()

        await Supervisor.start(
            children=[ChildSpec(actor=NotifyingWorker, name="w1", args=("w1", probe_pid))],
            strategy=RestartStrategy.ONE_FOR_ONE,
            registry=None,
            task_group=tg,
        )

        # If internal registry start failed, supervisor would crash before starting children.
        name, pid = await probe_mb.receive(
            (("started", str, PID), lambda n, p: (n, p)),
            timeout=1.0,
        )
        assert name == "w1"
        assert isinstance(pid, PID)

        tg.cancel_scope.cancel()
