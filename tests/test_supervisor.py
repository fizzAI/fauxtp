"""Tests for Supervisor behavior (restart strategies, restart types, max-restart)."""

from __future__ import annotations

import uuid

import anyio
import pytest

from src.fauxtp import Actor, GenServer, Supervisor, send
from src.fauxtp.primitives.mailbox import Mailbox
from src.fauxtp.primitives.pid import PID
from src.fauxtp.supervisor.base import MaxRestartsExceeded
from src.fauxtp.supervisor.child_spec import ChildSpec, RestartStrategy, RestartType


def make_monitor() -> tuple[PID, Mailbox]:
    """Create a PID+Mailbox pair usable as a message sink for tests."""
    mb = Mailbox()
    pid = PID(_id=uuid.uuid4(), _mailbox=mb)
    return pid, mb


class CrashyWorker(Actor):
    """Worker that can be asked to crash or exit normally and reports starts."""

    def __init__(self, child_id: str, monitor: PID):
        super().__init__()
        self._child_id = child_id
        self._monitor = monitor

    async def init(self):
        # Report our PID to the test harness so it can target messages.
        await send(self._monitor, ("started", self._child_id, self.pid))
        return {}

    async def run(self, state):
        async def do_crash():
            raise RuntimeError(f"boom:{self._child_id}")

        async def do_stop():
            self.stop("normal")

        return await self.receive(
            (("crash",), do_crash),
            (("stop_normal",), do_stop),
            timeout=10.0,
        )


class InstrumentedSupervisor(Supervisor):
    """
    Supervisor that starts 2 children and forwards child-down events to a monitor.

    We intentionally *observe* behavior via messages emitted by children (started)
    and the supervisor (down) rather than reaching into private state.
    """

    strategy: RestartStrategy = RestartStrategy.ONE_FOR_ONE
    max_restarts: int = 10
    max_seconds: float = 5.0

    def __init__(self, monitor: PID, restart_type_child2: RestartType = RestartType.PERMANENT):
        super().__init__()
        self._monitor = monitor
        self._restart_type_child2 = restart_type_child2

    def child_specs(self) -> list[ChildSpec]:
        return [
            ChildSpec(
                id="child1",
                actor_class=CrashyWorker,
                args=("child1", self._monitor),
                restart=RestartType.PERMANENT,
            ),
            ChildSpec(
                id="child2",
                actor_class=CrashyWorker,
                args=("child2", self._monitor),
                restart=self._restart_type_child2,
            ),
        ]

    async def _start_child(self, spec: ChildSpec):
        async def _on_exit(pid: PID, reason: str) -> None:
            # Mirror the down event to the monitor for assertion.
            await send(self._monitor, ("down", spec.id, pid, reason))
            if self._mailbox is not None:
                await self._mailbox.put(("$child_down", spec.id, pid, reason))

        handle = await self.spawn_child_actor(
            spec.actor_class,
            *spec.args,
            on_exit=_on_exit,
            **spec.kwargs,
        )

        return {"spec": spec, "pid": handle.pid, "handle": handle}


async def recv_started(mb: Mailbox, child_id: str, *, timeout: float = 1.0) -> PID:
    return await mb.receive(
        (("started", child_id, PID), lambda pid: pid),
        timeout=timeout,
    )


async def recv_down(mb: Mailbox, child_id: str, pid: PID, *, timeout: float = 1.0) -> str:
    return await mb.receive(
        (("down", child_id, pid, str), lambda reason: reason),
        timeout=timeout,
    )


@pytest.mark.anyio
async def test_supervisor_one_for_one_restarts_only_failed_child():
    monitor_pid, monitor_mb = make_monitor()

    async with anyio.create_task_group() as tg:
        _sup_pid = await InstrumentedSupervisor.start(monitor_pid, task_group=tg)

        # Observe initial starts
        c1_pid_1 = await recv_started(monitor_mb, "child1")
        c2_pid_1 = await recv_started(monitor_mb, "child2")
        assert c1_pid_1 != c2_pid_1

        # Crash child1 and observe down + restart of only child1
        await send(c1_pid_1, ("crash",))
        reason = await recv_down(monitor_mb, "child1", c1_pid_1)
        assert "error" in reason.lower()
        c1_pid_2 = await recv_started(monitor_mb, "child1")
        assert c1_pid_2 != c1_pid_1

        # Ensure child2 did NOT restart (no "started child2" message)
        with anyio.move_on_after(0.2) as scope:
            await recv_started(monitor_mb, "child2", timeout=0.2)
        assert scope.cancelled_caught is True

        tg.cancel_scope.cancel()


@pytest.mark.anyio
async def test_supervisor_one_for_all_restarts_all_children_when_one_fails():
    monitor_pid, monitor_mb = make_monitor()

    class OneForAllSup(InstrumentedSupervisor):
        strategy = RestartStrategy.ONE_FOR_ALL

    async with anyio.create_task_group() as tg:
        _sup_pid = await OneForAllSup.start(monitor_pid, task_group=tg)

        c1_pid_1 = await recv_started(monitor_mb, "child1")
        c2_pid_1 = await recv_started(monitor_mb, "child2")

        await send(c1_pid_1, ("crash",))
        _ = await recv_down(monitor_mb, "child1", c1_pid_1)

        # Both children should restart (order depends on dict insertion; allow either order)
        new_pids: dict[str, PID] = {}
        with anyio.fail_after(1.0):
            while set(new_pids.keys()) != {"child1", "child2"}:
                child_id, pid = await monitor_mb.receive(
                    (("started", str, PID), lambda cid, p: (cid, p)),
                    timeout=1.0,
                )
                # Only capture the post-crash restarts
                if child_id == "child1" and pid != c1_pid_1:
                    new_pids["child1"] = pid
                if child_id == "child2" and pid != c2_pid_1:
                    new_pids["child2"] = pid

        assert new_pids["child1"] != c1_pid_1
        assert new_pids["child2"] != c2_pid_1

        tg.cancel_scope.cancel()


@pytest.mark.anyio
async def test_supervisor_transient_child_not_restarted_on_normal_exit():
    monitor_pid, monitor_mb = make_monitor()

    async with anyio.create_task_group() as tg:
        _sup_pid = await InstrumentedSupervisor.start(
            monitor_pid,
            RestartType.TRANSIENT,
            task_group=tg,
        )

        c1_pid_1 = await recv_started(monitor_mb, "child1")
        c2_pid_1 = await recv_started(monitor_mb, "child2")

        # Ask child2 to exit normally -> transient should not restart
        await send(c2_pid_1, ("stop_normal",))
        reason = await recv_down(monitor_mb, "child2", c2_pid_1)
        assert reason == "normal"

        with anyio.move_on_after(0.2) as scope:
            await recv_started(monitor_mb, "child2", timeout=0.2)
        assert scope.cancelled_caught is True

        # Child1 still alive; ensure it can be restarted on crash (permanent)
        await send(c1_pid_1, ("crash",))
        _ = await recv_down(monitor_mb, "child1", c1_pid_1)
        c1_pid_2 = await recv_started(monitor_mb, "child1")
        assert c1_pid_2 != c1_pid_1

        tg.cancel_scope.cancel()


@pytest.mark.anyio
async def test_supervisor_temporary_child_never_restarted_even_on_error():
    monitor_pid, monitor_mb = make_monitor()

    async with anyio.create_task_group() as tg:
        _sup_pid = await InstrumentedSupervisor.start(
            monitor_pid,
            RestartType.TEMPORARY,
            task_group=tg,
        )

        _c1_pid_1 = await recv_started(monitor_mb, "child1")
        c2_pid_1 = await recv_started(monitor_mb, "child2")

        await send(c2_pid_1, ("crash",))
        reason = await recv_down(monitor_mb, "child2", c2_pid_1)
        assert "error" in reason.lower()

        # Temporary -> no restart
        with anyio.move_on_after(0.2) as scope:
            await recv_started(monitor_mb, "child2", timeout=0.2)
        assert scope.cancelled_caught is True

        tg.cancel_scope.cancel()


@pytest.mark.anyio
async def test_supervisor_max_restarts_exceeded_causes_supervisor_exit():
    monitor_pid, monitor_mb = make_monitor()

    class LimitedSup(InstrumentedSupervisor):
        max_restarts = 1
        max_seconds = 5.0

    sup_reasons: list[str] = []

    async def on_exit(_pid: PID, reason: str) -> None:
        sup_reasons.append(reason)

    async with anyio.create_task_group() as tg:
        _handle = await LimitedSup.start_link(monitor_pid, task_group=tg, on_exit=on_exit)

        c1_pid_1 = await recv_started(monitor_mb, "child1")
        _c2_pid_1 = await recv_started(monitor_mb, "child2")

        # Two crashes in the window should exceed max_restarts=1 and kill supervisor.
        await send(c1_pid_1, ("crash",))
        _ = await recv_down(monitor_mb, "child1", c1_pid_1)
        c1_pid_2 = await recv_started(monitor_mb, "child1")

        await send(c1_pid_2, ("crash",))
        _ = await recv_down(monitor_mb, "child1", c1_pid_2)

        # Supervisor should exit with an error containing MaxRestartsExceeded
        with anyio.fail_after(1.0):
            while not sup_reasons:
                await anyio.sleep(0)

        assert any("error" in r.lower() for r in sup_reasons)
        assert any(MaxRestartsExceeded.__name__ in r for r in sup_reasons)

        tg.cancel_scope.cancel()