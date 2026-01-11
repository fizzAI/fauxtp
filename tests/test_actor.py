"""Tests for Actor base class.

These tests avoid fixed sleeps by using explicit "reply-to" mailboxes and
lifecycle events.
"""

from __future__ import annotations

import uuid

import anyio
import pytest

from src.fauxtp import Actor, ANY, send
from src.fauxtp.primitives.mailbox import Mailbox
from src.fauxtp.primitives.pid import PID


class CounterActor(Actor):
    """Actor that maintains a counter and can reply with its current count."""

    async def init(self):
        return {"count": 0}

    async def run(self, state):
        async def handle_get(reply_to: PID):
            await send(reply_to, ("count", state["count"]))
            return state

        return await self.receive(
            (("increment",), lambda: {**state, "count": state["count"] + 1}),
            (("increment_by", int), lambda n: {**state, "count": state["count"] + n}),
            (("get", PID), handle_get),
            (("stop",), lambda: self.stop("normal")),
            (ANY, lambda _msg: state),
            timeout=1.0,
        )


@pytest.mark.anyio
async def test_actor_message_round_trip_without_sleeps():
    async with anyio.create_task_group() as tg:
        pid = await CounterActor.start(task_group=tg)

        reply_mailbox = Mailbox()
        reply_pid = PID(_id=uuid.uuid4(), _mailbox=reply_mailbox)

        await send(pid, ("increment",))
        await send(pid, ("increment_by", 2))
        await send(pid, ("get", reply_pid))

        count = await reply_mailbox.receive(
            (("count", int), lambda n: n),
            timeout=1.0,
        )
        assert count == 3

        tg.cancel_scope.cancel()


@pytest.mark.anyio
async def test_actor_stop_calls_terminate_and_on_exit_reason_is_normal():
    terminated = anyio.Event()
    exit_reasons: list[str] = []

    class StoppingActor(Actor):
        async def run(self, state):
            self.stop("normal")

        async def terminate(self, reason: str, state):
            exit_reasons.append(reason)
            terminated.set()

    async def on_exit(_pid: PID, reason: str) -> None:
        exit_reasons.append(f"on_exit:{reason}")

    async with anyio.create_task_group() as tg:
        handle = await StoppingActor.start_link(task_group=tg, on_exit=on_exit)

        with anyio.fail_after(1.0):
            await terminated.wait()

        # terminate() runs and on_exit callback runs with the same reason.
        assert "normal" in exit_reasons
        assert "on_exit:normal" in exit_reasons

        # Idempotent: cancelling after exit should be safe.
        handle.cancel_scope.cancel()
        tg.cancel_scope.cancel()


@pytest.mark.anyio
async def test_actor_cancel_scope_results_in_cancelled_reason_and_terminate_runs():
    terminated = anyio.Event()
    reasons: list[str] = []

    class BlockingActor(Actor):
        async def run(self, state):
            # Wait "forever" for a message; we'll cancel the actor.
            return await self.receive((ANY, lambda _m: state), timeout=10)

        async def terminate(self, reason: str, state):
            reasons.append(reason)
            terminated.set()

    async def on_exit(_pid: PID, reason: str) -> None:
        reasons.append(f"on_exit:{reason}")

    async with anyio.create_task_group() as tg:
        handle = await BlockingActor.start_link(task_group=tg, on_exit=on_exit)

        # Trigger cancellation and wait for termination deterministically.
        handle.cancel_scope.cancel()

        with anyio.fail_after(1.0):
            await terminated.wait()

        assert "cancelled" in reasons
        assert "on_exit:cancelled" in reasons

        tg.cancel_scope.cancel()