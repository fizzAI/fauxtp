"""Edge case and error condition tests.

Goal: assert real behavior (exit reasons, actual exceptions) rather than
"structure exists" placeholders, and avoid fixed sleeps.
"""

from __future__ import annotations

import anyio
import pytest

from src.fauxtp import ANY, Actor, GenServer, call, cast, send
from src.fauxtp.primitives.mailbox import Mailbox, ReceiveTimeout
from src.fauxtp.primitives.pid import PID


pytestmark = pytest.mark.anyio


async def test_actor_not_started_error():
    class SomeActor(Actor):
        async def run(self, state):
            return state

    actor = SomeActor()
    with pytest.raises(RuntimeError, match="Actor not started"):
        _ = actor.pid


async def test_actor_receive_not_started_raises_runtime_error():
    class SomeActor(Actor):
        async def run(self, state):
            return state

    actor = SomeActor()
    with pytest.raises(RuntimeError, match="Actor not started"):
        await actor.receive((ANY, lambda m: m), timeout=0.1)


async def test_mailbox_timeout_exception_message_contains_timeout():
    mailbox = Mailbox()

    with pytest.raises(ReceiveTimeout, match=r"No matching message within 0\.05s"):
        await mailbox.receive((("never",), lambda: None), timeout=0.05)


async def test_genserver_handle_call_not_implemented_crashes_and_reports_reason():
    class IncompleteGenServer(GenServer):
        async def init(self):
            return {}

    exited = anyio.Event()
    reasons: list[str] = []

    async def on_exit(_pid: PID, reason: str) -> None:
        reasons.append(reason)
        exited.set()

    async with anyio.create_task_group() as tg:
        handle = await IncompleteGenServer.start_link(task_group=tg, on_exit=on_exit)

        # Trigger a $call, which will invoke handle_call -> NotImplementedError.
        # The caller will time out waiting for a reply because the server crashes.
        with pytest.raises(ReceiveTimeout):
            await call(handle.pid, "ping", timeout=0.05)

        with anyio.fail_after(1.0):
            await exited.wait()

        assert any("NotImplementedError" in r for r in reasons)
        assert any("handle_call/3 not implemented" in r for r in reasons)

        tg.cancel_scope.cancel()


async def test_actor_terminate_called_on_cancel_and_reason_is_cancelled():
    terminated = anyio.Event()
    reasons: list[str] = []

    class TerminatingActor(Actor):
        async def run(self, state):
            return await self.receive((ANY, lambda _m: state), timeout=10.0)

        async def terminate(self, reason: str, state):
            reasons.append(reason)
            terminated.set()

    async with anyio.create_task_group() as tg:
        handle = await TerminatingActor.start_link(task_group=tg)
        handle.cancel_scope.cancel()

        with anyio.fail_after(1.0):
            await terminated.wait()

        assert "cancelled" in reasons

        tg.cancel_scope.cancel()


async def test_genserver_handle_cast_default_does_not_change_state():
    class MinimalGenServer(GenServer):
        async def init(self):
            return {"value": 1}

        async def handle_call(self, request, from_ref, state):
            if request == "get":
                return (state["value"], state)
            return (None, state)

    async with anyio.create_task_group() as tg:
        pid = await MinimalGenServer.start(task_group=tg)

        await cast(pid, "some_cast")
        assert await call(pid, "get", timeout=1.0) == 1

        tg.cancel_scope.cancel()


async def test_genserver_handle_info_default_does_not_change_state():
    class MinimalGenServer(GenServer):
        async def init(self):
            return {"value": 1}

        async def handle_call(self, request, from_ref, state):
            if request == "get":
                return (state["value"], state)
            return (None, state)

    async with anyio.create_task_group() as tg:
        pid = await MinimalGenServer.start(task_group=tg)

        await send(pid, ("info", "message"))
        assert await call(pid, "get", timeout=1.0) == 1

        tg.cancel_scope.cancel()


async def test_send_to_mailbox_fifo_receive():
    mailbox = Mailbox()
    await mailbox.put("test1")
    await mailbox.put("test2")
    await mailbox.put("test3")

    msg1 = await mailbox.receive((ANY, lambda x: x), timeout=0.5)
    msg2 = await mailbox.receive((ANY, lambda x: x), timeout=0.5)
    msg3 = await mailbox.receive((ANY, lambda x: x), timeout=0.5)

    assert msg1 == "test1"
    assert msg2 == "test2"
    assert msg3 == "test3"


async def test_mailbox_handler_return_types_sync_and_async():
    mailbox = Mailbox()

    # Sync handler
    await mailbox.put("sync")
    result = await mailbox.receive(
        ("sync", lambda: "sync_result"),
        timeout=0.5,
    )
    assert result == "sync_result"

    # Async handler
    await mailbox.put("async")

    async def async_handler():
        await anyio.sleep(0.01)
        return "async_result"

    result = await mailbox.receive(
        ("async", async_handler),
        timeout=0.5,
    )
    assert result == "async_result"


async def test_mailbox_handler_with_multiple_args():
    mailbox = Mailbox()

    # No args
    await mailbox.put("msg1")
    result = await mailbox.receive(
        ("msg1", lambda: "zero_args"),
        timeout=0.5,
    )
    assert result == "zero_args"

    # One arg
    await mailbox.put(("tag", "value"))
    result = await mailbox.receive(
        (("tag", str), lambda x: f"one_arg:{x}"),
        timeout=0.5,
    )
    assert result == "one_arg:value"

    # Multiple args
    await mailbox.put(("tag", "val1", "val2"))
    result = await mailbox.receive(
        (("tag", str, str), lambda x, y: f"two_args:{x},{y}"),
        timeout=0.5,
    )
    assert result == "two_args:val1,val2"