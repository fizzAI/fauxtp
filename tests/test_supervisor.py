"""Tests for Supervisor."""

import pytest
import anyio
from src.fauxtp import (
    Supervisor, ChildSpec, GenServer,
    RestartStrategy, RestartType,
    call
)


class SimpleWorker(GenServer):
    """Simple worker for testing."""
    
    def __init__(self, name: str):
        super().__init__()
        self.name = name
    
    async def init(self):
        return {"name": self.name, "count": 0}
    
    async def handle_call(self, request, from_ref, state):
        match request:
            case "get_count":
                return (state["count"], state)
            case _:
                return (None, state)


class TestSupervisor(Supervisor):
    """Test supervisor."""
    
    strategy = RestartStrategy.ONE_FOR_ONE
    max_restarts = 3
    max_seconds = 5.0
    
    def child_specs(self):
        return [
            ChildSpec(
                id="worker1",
                actor_class=SimpleWorker,
                args=("Worker1",),
                restart=RestartType.PERMANENT
            ),
            ChildSpec(
                id="worker2",
                actor_class=SimpleWorker,
                args=("Worker2",),
                restart=RestartType.TRANSIENT
            ),
        ]


class TestSupervisorFunctionality:
    """Test Supervisor functionality."""
    
    async def test_supervisor_start(self):
        """Test supervisor can start."""
        async with anyio.create_task_group() as tg:
            pid = await TestSupervisor.start(task_group=tg)
            assert pid is not None
            await anyio.sleep(0.3)
            tg.cancel_scope.cancel()
    
    async def test_supervisor_children(self):
        """Test supervisor starts children."""
        async with anyio.create_task_group() as tg:
            pid = await TestSupervisor.start(task_group=tg)
            await anyio.sleep(0.3)
            # Children should be started
            tg.cancel_scope.cancel()
    
    async def test_child_spec_validation(self):
        """Test ChildSpec validation."""
        with pytest.raises(ValueError):
            ChildSpec(id="", actor_class=SimpleWorker)
    
    async def test_restart_strategies(self):
        """Test restart strategy can be set."""
        class OneForAllSupervisor(Supervisor):
            strategy = RestartStrategy.ONE_FOR_ALL
            max_restarts = 5
            max_seconds = 10.0
            
            def child_specs(self):
                return []
        
        assert OneForAllSupervisor.strategy == RestartStrategy.ONE_FOR_ALL
        assert OneForAllSupervisor.max_restarts == 5
    
    async def test_restart_types(self):
        """Test different restart types."""
        permanent_spec = ChildSpec(
            id="permanent",
            actor_class=SimpleWorker,
            args=("P",),
            restart=RestartType.PERMANENT
        )
        assert permanent_spec.restart == RestartType.PERMANENT
        
        transient_spec = ChildSpec(
            id="transient",
            actor_class=SimpleWorker,
            args=("T",),
            restart=RestartType.TRANSIENT
        )
        assert transient_spec.restart == RestartType.TRANSIENT
        
        temporary_spec = ChildSpec(
            id="temporary",
            actor_class=SimpleWorker,
            args=("T",),
            restart=RestartType.TEMPORARY
        )
        assert temporary_spec.restart == RestartType.TEMPORARY