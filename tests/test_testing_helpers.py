"""Tests for testing utilities."""

from __future__ import annotations

import anyio
import pytest

from src.fauxtp import Actor, ANY, send
from src.fauxtp.primitives.mailbox import ReceiveTimeout
from src.fauxtp.testing.helpers import (
    TestActor,
    assert_receives,
    wait_for,
    with_timeout,
)


pytestmark = pytest.mark.anyio


async def test_with_timeout_success():
    async def quick_task():
        await anyio.sleep(0.01)
        return "done"

    result = await with_timeout(quick_task(), timeout=1.0)
    assert result == "done"


async def test_with_timeout_fails_with_timeout_error():
    async def slow_task():
        await anyio.sleep(5.0)
        return "done"

    with pytest.raises(TimeoutError):
        await with_timeout(slow_task(), timeout=0.05)


async def test_wait_for_success():
    flag = {"value": False}

    async def set_flag():
        await anyio.sleep(0.02)
        flag["value"] = True

    async with anyio.create_task_group() as tg:
        tg.start_soon(set_flag)
        await wait_for(lambda: flag["value"], timeout=1.0, interval=0.005)


async def test_wait_for_timeout():
    with pytest.raises(TimeoutError, match=r"Condition not met within 0\.05s"):
        await wait_for(lambda: False, timeout=0.05, interval=0.005)


async def test_assert_receives_reads_from_running_actor_mailbox():
    # We need an *Actor instance* to pass to assert_receives(), but the public API
    # only gives us a PID. Capture the constructed instance via a closure.
    created: list[Actor] = []

    class IdleActor(Actor):
        def __init__(self):
            super().__init__()
            created.append(self)

        async def run(self, state):
            # Don't consume messages in the actor loop; we want the test helper
            # (which calls actor.receive()) to consume from the mailbox.
            await anyio.sleep(10)
            return state

    async with anyio.create_task_group() as tg:
        pid = await IdleActor.start(task_group=tg)
        actor = created[0]

        async def delayed_send():
            await anyio.sleep(0.02)
            await send(pid, ("ping", 123))

        tg.start_soon(delayed_send)

        res = await assert_receives(
            actor,
            (("ping", int), lambda n: n),
            timeout=1.0,
        )
        assert res == 123

        tg.cancel_scope.cancel()


async def test_assert_receives_times_out_when_no_message_matches():
    created: list[Actor] = []

    class IdleActor(Actor):
        def __init__(self):
            super().__init__()
            created.append(self)

        async def run(self, state):
            await anyio.sleep(10)
            return state

    async with anyio.create_task_group() as tg:
        _pid = await IdleActor.start(task_group=tg)
        actor = created[0]

        # assert_receives uses the same timeout for fail_after and mailbox.receive,
        # so depending on scheduling it can surface either TimeoutError or ReceiveTimeout.
        with pytest.raises((TimeoutError, ReceiveTimeout)):
            await assert_receives(actor, (("never",), lambda: None), timeout=0.05)

        tg.cancel_scope.cancel()


async def test_test_actor_collects_messages_deterministically():
    created: list[TestActor] = []

    class CapturingTestActor(TestActor):
        def __init__(self):
            super().__init__()
            created.append(self)

    async with anyio.create_task_group() as tg:
        pid = await CapturingTestActor.start(task_group=tg)
        actor = created[0]

        await send(pid, "message1")
        await send(pid, "message2")

        await wait_for(lambda: actor.get_messages() == ["message1", "message2"], timeout=1.0)

        actor.clear_messages()
        assert actor.get_messages() == []

        tg.cancel_scope.cancel()