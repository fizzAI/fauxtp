"""Tests for GenServer."""

from __future__ import annotations

import anyio
import pytest

from src.fauxtp import GenServer, call, cast, send
from src.fauxtp.primitives.mailbox import ReceiveTimeout


class CountingGenServer(GenServer):
    """Test GenServer implementation with observable state."""

    async def init(self):
        return {"count": 0, "data": {}, "last_info": None}

    async def handle_call(self, request, from_ref, state):
        match request:
            case "get":
                return (state["count"], state)
            case ("add", int() as n):
                new_count = state["count"] + n
                return (new_count, {**state, "count": new_count})
            case ("get_data", str() as key):
                return (state["data"].get(key), state)
            case "get_last_info":
                return (state.get("last_info"), state)
            case _:
                return (None, state)

    async def handle_cast(self, request, state):
        match request:
            case "reset":
                return {**state, "count": 0}
            case ("set", int() as n):
                return {**state, "count": n}
            case ("put_data", str() as key, value):
                new_data = {**state["data"], key: value}
                return {**state, "data": new_data}
            case _:
                return state

    async def handle_info(self, message, state):
        return {**state, "last_info": message}


@pytest.mark.anyio
async def test_genserver_call_updates_state_and_replies():
    async with anyio.create_task_group() as tg:
        pid = await CountingGenServer.start(task_group=tg)

        assert await call(pid, "get", timeout=1.0) == 0
        assert await call(pid, ("add", 5), timeout=1.0) == 5
        assert await call(pid, ("add", 3), timeout=1.0) == 8

        tg.cancel_scope.cancel()


@pytest.mark.anyio
async def test_genserver_cast_is_observable_via_followup_call_without_sleep():
    async with anyio.create_task_group() as tg:
        pid = await CountingGenServer.start(task_group=tg)

        # Cast then call: message ordering ensures cast is processed before the call.
        await cast(pid, ("set", 100))
        assert await call(pid, "get", timeout=1.0) == 100

        await cast(pid, "reset")
        assert await call(pid, "get", timeout=1.0) == 0

        await cast(pid, ("put_data", "k", {"v": 1}))
        assert await call(pid, ("get_data", "k"), timeout=1.0) == {"v": 1}

        tg.cancel_scope.cancel()


@pytest.mark.anyio
async def test_genserver_info_is_observable_via_call():
    async with anyio.create_task_group() as tg:
        pid = await CountingGenServer.start(task_group=tg)

        msg = ("custom", "info", "message")
        await send(pid, msg)

        # Info messages are processed before later calls (mailbox ordering).
        assert await call(pid, "get_last_info", timeout=1.0) == msg

        tg.cancel_scope.cancel()


@pytest.mark.anyio
async def test_genserver_call_timeout_raises_receive_timeout():
    class SlowGenServer(GenServer):
        async def init(self):
            return {}

        async def handle_call(self, request, from_ref, state):
            await anyio.sleep(5.0)
            return ("done", state)

    async with anyio.create_task_group() as tg:
        pid = await SlowGenServer.start(task_group=tg)

        with pytest.raises(ReceiveTimeout, match=r"No matching message within 0\.1s"):
            await call(pid, "slow", timeout=0.1)

        tg.cancel_scope.cancel()


@pytest.mark.anyio
async def test_genserver_multiple_concurrent_calls_all_reply_and_state_is_consistent():
    async with anyio.create_task_group() as tg:
        pid = await CountingGenServer.start(task_group=tg)

        results: list[int] = []
        lock = anyio.Lock()

        async def do_add_one():
            r = await call(pid, ("add", 1), timeout=2.0)
            async with lock:
                results.append(r)

        async with anyio.create_task_group() as callers:
            for _ in range(10):
                callers.start_soon(do_add_one)

        assert sorted(results) == list(range(1, 11))
        assert await call(pid, "get", timeout=1.0) == 10

        tg.cancel_scope.cancel()


@pytest.mark.anyio
async def test_genserver_can_start_background_task_and_receive_success_message():
    class BackgroundTaskGenServer(GenServer):
        def __init__(self):
            super().__init__()
            self._last_task = None

        async def init(self):
            return {"done": None, "failed": None}

        async def handle_call(self, request, from_ref, state):
            match request:
                case "start_ok":
                    async def work_ok():
                        await anyio.sleep(0.05)
                        return "OK"

                    ref, task = await self.start_background_task(work_ok)
                    self._last_task = task
                    return (ref, state)

                case "get_done":
                    return (state["done"], state)

                case "get_failed":
                    return (state["failed"], state)

                case _:
                    return (None, state)

        async def handle_task_success(self, task_ref, task_pid, result, state):
            return {**state, "done": (task_ref, task_pid, result)}

        async def handle_task_failure(self, task_ref, task_pid, reason, state):
            return {**state, "failed": (task_ref, task_pid, reason)}

    async with anyio.create_task_group() as tg:
        pid = await BackgroundTaskGenServer.start(task_group=tg)

        ref = await call(pid, "start_ok", timeout=1.0)

        with anyio.fail_after(2):
            while True:
                done = await call(pid, "get_done", timeout=1.0)
                if done is not None:
                    break
                await anyio.sleep(0.01)

        done_ref, _task_pid, result = done
        assert done_ref == ref
        assert result == "OK"

        tg.cancel_scope.cancel()


@pytest.mark.anyio
async def test_genserver_can_start_background_task_and_receive_failure_message_and_cancel():
    class BackgroundTaskGenServer(GenServer):
        def __init__(self):
            super().__init__()
            self._last_task = None

        async def init(self):
            return {"failed": None}

        async def handle_call(self, request, from_ref, state):
            match request:
                case "start_fail":
                    async def work_fail():
                        await anyio.sleep(0.05)
                        raise RuntimeError("boom")

                    ref, _task = await self.start_background_task(work_fail)
                    return (ref, state)

                case "start_slow":
                    async def work_slow():
                        await anyio.sleep(10)
                        return "NOPE"

                    ref, task = await self.start_background_task(work_slow)
                    self._last_task = task
                    return (ref, state)

                case "cancel_last":
                    assert self._last_task is not None
                    self._last_task.cancel()
                    return (True, state)

                case "get_failed":
                    return (state["failed"], state)

                case _:
                    return (None, state)

        async def handle_task_failure(self, task_ref, task_pid, reason, state):
            return {**state, "failed": (task_ref, task_pid, reason)}

    async with anyio.create_task_group() as tg:
        pid = await BackgroundTaskGenServer.start(task_group=tg)

        fail_ref = await call(pid, "start_fail", timeout=1.0)

        with anyio.fail_after(2):
            while True:
                failed = await call(pid, "get_failed", timeout=1.0)
                if failed is not None:
                    break
                await anyio.sleep(0.01)

        failed_ref, _task_pid, reason = failed
        assert failed_ref == fail_ref
        assert "boom" in str(reason)

        # cancellation also routes through handle_task_failure
        slow_ref = await call(pid, "start_slow", timeout=1.0)
        assert await call(pid, "cancel_last", timeout=1.0) is True

        with anyio.fail_after(2):
            while True:
                failed2 = await call(pid, "get_failed", timeout=1.0)
                if failed2 is not None and failed2[0] == slow_ref:
                    break
                await anyio.sleep(0.01)

        tg.cancel_scope.cancel()
