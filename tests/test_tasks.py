import anyio
import pytest

from src.fauxtp import Actor, ANY
from src.fauxtp.actor.task import Task


async def work_ok():
    await anyio.sleep(0.05)
    return "OK_RESULT"


async def work_fail():
    await anyio.sleep(0.05)
    raise RuntimeError("boom")


async def work_slow():
    await anyio.sleep(10)
    return "NOPE"


class ParentForwarder(Actor):
    def __init__(self, send_stream: anyio.abc.ObjectSendStream):
        super().__init__()
        self._send_stream = send_stream

    async def run(self, state):
        event = await self.receive(
            (("$$success", ANY, ANY), lambda child_pid, res: ("success", child_pid, res)),
            (("$$failure", ANY, ANY), lambda child_pid, reason: ("failure", child_pid, reason)),
            timeout=2,
        )
        await self._send_stream.send(event)
        return state


@pytest.mark.anyio
async def test_task_join_success():
    async with anyio.create_task_group() as tg:
        t = await Task.spawn(work_ok, tg)
        res = await t.join()
        assert res == "OK_RESULT"
        tg.cancel_scope.cancel()


@pytest.mark.anyio
async def test_task_join_failure_raises():
    async with anyio.create_task_group() as tg:
        t = await Task.spawn(work_fail, tg)
        with pytest.raises(RuntimeError):
            await t.join()
        tg.cancel_scope.cancel()


@pytest.mark.anyio
async def test_task_join_cancelled_does_not_hang():
    async with anyio.create_task_group() as tg:
        t = await Task.spawn(work_slow, tg)

        # cancel and ensure join returns promptly (raises)
        t._handle.cancel_scope.cancel()

        with anyio.fail_after(1):
            with pytest.raises(RuntimeError):
                await t.join()

        tg.cancel_scope.cancel()


@pytest.mark.anyio
async def test_task_spawn_and_notify_parent_gets_success_and_failure_and_cancel():
    events_send, events_recv = anyio.create_memory_object_stream(50)

    async with anyio.create_task_group() as tg:
        parent_pid = await ParentForwarder.start(events_send, task_group=tg)

        t_ok = await Task.spawn_and_notify(work_ok, tg, parent_pid)
        t_fail = await Task.spawn_and_notify(work_fail, tg, parent_pid)
        t_slow = await Task.spawn_and_notify(work_slow, tg, parent_pid)

        ok_pid = t_ok._handle.pid
        fail_pid = t_fail._handle.pid
        slow_pid = t_slow._handle.pid

        t_slow._handle.cancel_scope.cancel()

        # also ensure joins complete (so we're not just testing parent path)
        assert await t_ok.join() == "OK_RESULT"
        with pytest.raises(RuntimeError):
            await t_fail.join()
        with pytest.raises(RuntimeError):
            await t_slow.join()

        # Collect until we have what we need (tolerate duplicates)
        seen_ok = False
        seen_fail = False
        seen_cancel = False

        with anyio.fail_after(2):
            while not (seen_ok and seen_fail and seen_cancel):
                kind, child_pid, payload = await events_recv.receive()

                if kind == "success" and child_pid == ok_pid:
                    seen_ok = True
                    assert payload == "OK_RESULT"

                if kind == "failure" and child_pid == fail_pid:
                    seen_fail = True
                    assert "boom" in str(payload)

                if kind == "failure" and child_pid == slow_pid:
                    seen_cancel = True
                    assert "cancel" in str(payload).lower()

        tg.cancel_scope.cancel()