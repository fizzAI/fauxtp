"""Tests for testing utilities."""

import pytest
import anyio
from src.fauxtp import Actor, send, ANY
from src.fauxtp.testing.helpers import (
    with_timeout,
    assert_receives,
    wait_for,
    TestActor
)


class TestTestingHelpers:
    """Test the testing helper utilities."""
    
    async def test_with_timeout_success(self):
        """Test with_timeout succeeds within limit."""
        async def quick_task():
            await anyio.sleep(0.01)
            return "done"
        
        result = await with_timeout(quick_task(), timeout=1.0)
        assert result == "done"
    
    async def test_with_timeout_fails(self):
        """Test with_timeout raises on timeout."""
        async def slow_task():
            await anyio.sleep(5.0)
            return "done"
        
        with pytest.raises(TimeoutError):
            await with_timeout(slow_task(), timeout=0.1)
    
    async def test_wait_for_success(self):
        """Test wait_for succeeds when condition met."""
        flag = {"value": False}
        
        async def set_flag():
            await anyio.sleep(0.05)
            flag["value"] = True
        
        async with anyio.create_task_group() as tg:
            tg.start_soon(set_flag)
            await wait_for(lambda: flag["value"], timeout=1.0, interval=0.01)
    
    async def test_wait_for_timeout(self):
        """Test wait_for times out when condition not met."""
        with pytest.raises(TimeoutError):
            await wait_for(lambda: False, timeout=0.1, interval=0.01)
    
    async def test_test_actor(self):
        """Test TestActor collects messages."""
        async with anyio.create_task_group() as tg:
            actor = TestActor()
            pid = await TestActor.start(task_group=tg)
            await anyio.sleep(0.1)
            
            await send(pid, "message1")
            await send(pid, "message2")
            await anyio.sleep(0.2)
            
            tg.cancel_scope.cancel()