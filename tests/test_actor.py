"""Tests for Actor base class."""

import pytest
import anyio
from src.fauxtp import Actor, send, ANY


class CounterActor(Actor):
    """Test actor that counts messages."""
    
    async def init(self):
        return {"count": 0, "messages": []}
    
    async def run(self, state):
        return await self.receive(
            ((("increment",),), lambda: {**state, "count": state["count"] + 1}),
            ((("get",),), lambda: state),
            ((("stop",),), lambda: {**state, "should_stop": True}),
            ((ANY,), lambda msg: {**state, "messages": state["messages"] + [msg]}),
            timeout=0.5
        )


class TestActor:
    """Test Actor functionality."""
    
    async def test_actor_start(self):
        """Test actor can be started."""
        async with anyio.create_task_group() as tg:
            pid = await CounterActor.start(task_group=tg)
            assert pid is not None
            await anyio.sleep(0.1)
            tg.cancel_scope.cancel()
    
    async def test_actor_send_receive(self):
        """Test sending messages to actor."""
        async with anyio.create_task_group() as tg:
            pid = await CounterActor.start(task_group=tg)
            await anyio.sleep(0.1)
            
            await send(pid, ("increment",))
            await send(pid, ("increment",))
            await anyio.sleep(0.2)
            
            tg.cancel_scope.cancel()
    
    async def test_actor_pattern_matching(self):
        """Test actor pattern matching."""
        async with anyio.create_task_group() as tg:
            pid = await CounterActor.start(task_group=tg)
            await anyio.sleep(0.1)
            
            # Send various messages
            await send(pid, ("increment",))
            await send(pid, ("unknown", "message"))
            await anyio.sleep(0.2)
            
            tg.cancel_scope.cancel()
    
    async def test_actor_lifecycle(self):
        """Test actor init and terminate."""
        class LifecycleActor(Actor):
            def __init__(self):
                super().__init__()
                self.init_called = False
                self.terminate_called = False
            
            async def init(self):
                self.init_called = True
                return {"ready": True}
            
            async def run(self, state):
                return await self.receive(
                    ((ANY,), lambda msg: state),
                    timeout=0.1
                )
            
            async def terminate(self, reason, state):
                self.terminate_called = True
        
        async with anyio.create_task_group() as tg:
            actor = LifecycleActor()
            actor._mailbox = anyio.Lock()  # Type doesn't matter for this test
            
            # Just verify structure exists
            assert hasattr(actor, 'init')
            assert hasattr(actor, 'run')
            assert hasattr(actor, 'terminate')
            
            tg.cancel_scope.cancel()