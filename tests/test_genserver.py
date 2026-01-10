"""Tests for GenServer."""

import pytest
import anyio
from src.fauxtp import GenServer, call, cast, send


class TestGenServer(GenServer):
    """Test GenServer implementation."""
    
    async def init(self):
        return {"count": 0, "data": {}}
    
    async def handle_call(self, request, from_ref, state):
        match request:
            case "get":
                return (state["count"], state)
            case ("add", n):
                new_count = state["count"] + n
                return (new_count, {**state, "count": new_count})
            case ("get_data", key):
                return (state["data"].get(key), state)
            case _:
                return (None, state)
    
    async def handle_cast(self, request, state):
        match request:
            case "reset":
                return {**state, "count": 0}
            case ("set", n):
                return {**state, "count": n}
            case ("put_data", key, value):
                new_data = {**state["data"], key: value}
                return {**state, "data": new_data}
            case _:
                return state
    
    async def handle_info(self, message, state):
        return {**state, "last_info": message}


class TestGenServerFunctionality:
    """Test GenServer functionality."""
    
    async def test_genserver_call(self):
        """Test synchronous call."""
        async with anyio.create_task_group() as tg:
            pid = await TestGenServer.start(task_group=tg)
            await anyio.sleep(0.1)
            
            # Test get
            result = await call(pid, "get", timeout=1.0)
            assert result == 0
            
            # Test add
            result = await call(pid, ("add", 5), timeout=1.0)
            assert result == 5
            
            result = await call(pid, ("add", 3), timeout=1.0)
            assert result == 8
            
            tg.cancel_scope.cancel()
    
    async def test_genserver_cast(self):
        """Test asynchronous cast."""
        async with anyio.create_task_group() as tg:
            pid = await TestGenServer.start(task_group=tg)
            await anyio.sleep(0.1)
            
            # Cast operations
            await cast(pid, ("set", 100))
            await anyio.sleep(0.2)
            
            result = await call(pid, "get", timeout=1.0)
            assert result == 100
            
            await cast(pid, "reset")
            await anyio.sleep(0.2)
            
            result = await call(pid, "get", timeout=1.0)
            assert result == 0
            
            tg.cancel_scope.cancel()
    
    async def test_genserver_info(self):
        """Test info message handling."""
        async with anyio.create_task_group() as tg:
            pid = await TestGenServer.start(task_group=tg)
            await anyio.sleep(0.1)
            
            # Send info message
            await send(pid, ("custom", "info", "message"))
            await anyio.sleep(0.2)
            
            tg.cancel_scope.cancel()
    
    async def test_genserver_call_timeout(self):
        """Test call timeout."""
        class SlowGenServer(GenServer):
            async def init(self):
                return {}
            
            async def handle_call(self, request, from_ref, state):
                await anyio.sleep(5.0)  # Will timeout
                return ("done", state)
        
        async with anyio.create_task_group() as tg:
            pid = await SlowGenServer.start(task_group=tg)
            await anyio.sleep(0.1)
            
            with pytest.raises(Exception):  # Will timeout
                await call(pid, "slow", timeout=0.1)
            
            tg.cancel_scope.cancel()
    
    async def test_genserver_multiple_calls(self):
        """Test multiple concurrent calls."""
        async with anyio.create_task_group() as tg:
            pid = await TestGenServer.start(task_group=tg)
            await anyio.sleep(0.1)
            
            # Sequential calls
            await call(pid, ("add", 1), timeout=1.0)
            await call(pid, ("add", 2), timeout=1.0)
            await call(pid, ("add", 3), timeout=1.0)
            
            result = await call(pid, "get", timeout=1.0)
            assert result == 6
            
            tg.cancel_scope.cancel()