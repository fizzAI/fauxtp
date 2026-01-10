"""
Supervisor - manages child actor lifecycles.

Restart strategies:
  - one_for_one: Only restart the failed child
  - one_for_all: Restart all children if one fails
  - rest_for_one: Restart failed child and all children started after it
"""

from collections import deque
from typing import Any

import anyio

from ..actor.base import Actor, ActorHandle
from ..primitives.pid import PID
from ..primitives.pattern import ANY
from .child_spec import ChildSpec, RestartStrategy, RestartType


class MaxRestartsExceeded(Exception):
    """Raised when a child exceeds the max restart limit."""
    pass


class Supervisor(Actor):
    """
    Base supervisor. Subclass and define children + strategy.
    """
    strategy: RestartStrategy = RestartStrategy.ONE_FOR_ONE
    max_restarts: int = 3
    max_seconds: float = 5.0
    
    def child_specs(self) -> list[ChildSpec]:
        """Override to define children."""
        return []
    
    async def init(self) -> Any:
        """Initialize supervisor state."""
        # Start all children
        children: dict[str, dict[str, Any]] = {}
        
        for spec in self.child_specs():
            child_info = await self._start_child(spec)
            children[spec.id] = child_info
        
        return {
            "children": children,
            "restart_history": deque[float](),
        }
    
    async def run(self, state: Any) -> Any:
        """Main supervisor loop - handles child management."""
        children: dict[str, dict[str, Any]] = state["children"]
        restart_history: deque[float] = state["restart_history"]

        return await self.receive(
            # Child died notification: include pid so we can ignore stale exits after restarts
            ((("$child_down", str, PID, ANY),
              lambda child_id, pid, reason: self._handle_down(
                  child_id, pid, reason, children, restart_history))),

            # External commands
            ((("$terminate_child", str),
              lambda child_id: self._terminate_child(child_id, children, state))),

            ((("$restart_child", str),
              lambda child_id: self._restart_single_child(child_id, children, state))),

            ((("$which_children",),
              lambda: self._which_children(children, state))),

            ((("$count_children",),
              lambda: self._count_children(children, state))),
        )
    
    async def _start_child(self, spec: ChildSpec) -> dict[str, Any]:
        """Start a single child actor in the supervisor's TaskGroup."""
        if self._task_group is None:
            raise RuntimeError(
                "Supervisor has no task group; start it with Actor.start(task_group=...)"
            )

        async def _on_exit(pid: PID, reason: str) -> None:
            # Best-effort notification to supervisor mailbox.
            if self._mailbox is not None:
                await self._mailbox.put(("$child_down", spec.id, pid, reason))

        handle: ActorHandle = await spec.actor_class.start_link(
            *spec.args,
            task_group=self._task_group,
            on_exit=_on_exit,
            **spec.kwargs,
        )

        return {
            "spec": spec,
            "pid": handle.pid,
            "handle": handle,
        }
    
    async def _handle_down(
        self,
        child_id: str,
        pid: PID,
        reason: str,
        children: dict[str, dict[str, Any]],
        restart_history: deque[float]
    ) -> dict[str, Any]:
        """Handle child death according to strategy."""
        if child_id not in children:
            # Child already removed
            return {"children": children, "restart_history": restart_history}

        child_info = children[child_id]

        # Ignore stale exit notifications from an older instance (e.g. during restarts).
        if child_info.get("pid") != pid:
            return {"children": children, "restart_history": restart_history}

        spec: ChildSpec = child_info["spec"]
        
        # Check if we should restart based on restart type
        should_restart = False
        if spec.restart == RestartType.PERMANENT:
            should_restart = True
        elif spec.restart == RestartType.TRANSIENT:
            # Only restart on abnormal exit
            should_restart = "error" in reason.lower()
        # TEMPORARY never restarts
        
        if not should_restart:
            # Remove child and don't restart
            del children[child_id]
            return {"children": children, "restart_history": restart_history}
        
        # Track restart
        now = anyio.current_time()
        restart_history.append(now)
        
        # Prune old restart events
        cutoff = now - self.max_seconds
        while restart_history and restart_history[0] < cutoff:
            restart_history.popleft()
        
        # Check if we've exceeded max restarts
        if len(restart_history) > self.max_restarts:
            raise MaxRestartsExceeded(
                f"Child {child_id} exceeded restart limit "
                f"({self.max_restarts} restarts in {self.max_seconds}s)"
            )
        
        # Apply restart strategy
        match self.strategy:
            case RestartStrategy.ONE_FOR_ONE:
                await self._restart_child_internal(child_id, children)
            
            case RestartStrategy.ONE_FOR_ALL:
                # Restart all children
                for cid in list(children.keys()):
                    await self._restart_child_internal(cid, children)
            
            case RestartStrategy.REST_FOR_ONE:
                # Restart this child and all started after it
                child_ids = list(children.keys())
                start_restarting = False
                for cid in child_ids:
                    if cid == child_id:
                        start_restarting = True
                    if start_restarting:
                        await self._restart_child_internal(cid, children)
        
        return {"children": children, "restart_history": restart_history}
    
    async def _restart_child_internal(
        self,
        child_id: str,
        children: dict[str, dict[str, Any]]
    ) -> None:
        """Internal method to restart a specific child."""
        if child_id not in children:
            return

        child_info = children[child_id]
        spec: ChildSpec = child_info["spec"]

        # Cancel the old child task (structured, AnyIO cancellation).
        handle: ActorHandle | None = child_info.get("handle")
        if handle is not None:
            handle.cancel_scope.cancel()

        # Start a new instance
        new_child_info = await self._start_child(spec)
        children[child_id] = new_child_info
    
    async def _terminate_child(
        self,
        child_id: str,
        children: dict[str, dict[str, Any]],
        state: dict[str, Any]
    ) -> dict[str, Any]:
        """Terminate a specific child."""
        if child_id not in children:
            return state

        child_info = children[child_id]

        handle: ActorHandle | None = child_info.get("handle")
        if handle is not None:
            handle.cancel_scope.cancel()

        # Remove from children
        del children[child_id]

        return state
    
    async def _restart_single_child(
        self,
        child_id: str,
        children: dict[str, dict[str, Any]],
        state: dict[str, Any]
    ) -> dict[str, Any]:
        """Restart a specific child."""
        await self._restart_child_internal(child_id, children)
        return state
    
    async def _which_children(
        self,
        children: dict[str, dict[str, Any]],
        state: dict[str, Any]
    ) -> dict[str, Any]:
        """Return list of child info."""
        result = []
        for child_id, child_info in children.items():
            result.append({
                "id": child_id,
                "pid": child_info.get("pid"),
                "spec": child_info["spec"],
            })
        return {**state, "$reply": result}
    
    async def _count_children(
        self,
        children: dict[str, dict[str, Any]],
        state: dict[str, Any]
    ) -> dict[str, Any]:
        """Return count of children."""
        return {**state, "$reply": len(children)}
    
    def child(self, child_id: str) -> PID | None:
        """Get a child's PID by id."""
        if self._state is None:
            return None
        children = self._state.get("children", {})
        child_info = children.get(child_id)
        if child_info:
            return child_info.get("pid")
        return None