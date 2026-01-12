"""
Task Queue with Worker Pool

Demonstrates a job queue with multiple workers processing tasks concurrently.
Workers pull tasks from queue, process them, and report results.
"""

import anyio
import random
from fauxtp import GenServer, Supervisor, ChildSpec, call, cast, RestartStrategy, RestartType


class TaskQueue(GenServer):
    """Central task queue."""
    
    async def init(self):
        print("[Queue] Starting task queue")
        return {
            "pending": [],
            "in_progress": {},
            "completed": [],
            "failed": []
        }
    
    async def handle_call(self, request, from_ref, state):
        match request:
            case ("dequeue",):
                if state["pending"]:
                    task = state["pending"].pop(0)
                    return (task, state)
                return (None, state)
            
            case "stats":
                return ({
                    "pending": len(state["pending"]),
                    "in_progress": len(state["in_progress"]),
                    "completed": len(state["completed"]),
                    "failed": len(state["failed"])
                }, state)
        
        return (None, state)
    
    async def handle_cast(self, request, state):
        match request:
            case ("enqueue", task):
                state["pending"].append(task)
                print(f"[Queue] Enqueued task {task['id']}")
            
            case ("complete", task_id, result):
                if task_id in state["in_progress"]:
                    del state["in_progress"][task_id]
                state["completed"].append({"id": task_id, "result": result})
                print(f"[Queue] Task {task_id} completed")
            
            case ("fail", task_id, error):
                if task_id in state["in_progress"]:
                    del state["in_progress"][task_id]
                state["failed"].append({"id": task_id, "error": error})
                print(f"[Queue] Task {task_id} failed: {error}")
        
        return state


class Worker(GenServer):
    """Worker that processes tasks from queue."""
    
    def __init__(self, worker_id: int, queue_pid):
        super().__init__()
        self.worker_id = worker_id
        self.queue_pid = queue_pid
        # Limit to 2 concurrent tasks per worker
        self.set_max_tasks(2)
    
    async def init(self):
        print(f"[Worker-{self.worker_id}] Starting")
        return {
            "id": self.worker_id,
            "queue": self.queue_pid,
            "processed": 0,
            "running": True,
            "active_tasks": {} # task_id -> pid
        }
    
    async def handle_cast(self, request, state):
        match request:
            case "work":
                if not state["running"]:
                    return state

                # Get task from queue
                task = await call(state["queue"], ("dequeue",), timeout=1.0)
                
                if task:
                    # Process task in background using the new Task system
                    print(f"[Worker-{state['id']}] Spawning task {task['id']}")
                    pid = await self.spawn_task(self._process_task, task)
                    if pid:
                        state["active_tasks"][pid] = task["id"]
                    else:
                        # Re-enqueue if we hit the limit (simplified)
                        await cast(state["queue"], ("enqueue", task))
                
                # Schedule next check
                await cast(self.pid, "work")
                await anyio.sleep(0.1)
            
            case "stop":
                state["running"] = False
        
        return state

    async def handle_task_end(self, pid, result, state):
        task_id = state["active_tasks"].pop(pid, "unknown")
        
        if result["status"] == "ok":
            print(f"[Worker-{state['id']}] Task {task_id} finished successfully")
            await cast(state["queue"], ("complete", task_id, result["value"]))
            state["processed"] += 1
        else:
            print(f"[Worker-{state['id']}] Task {task_id} failed: {result['value']}")
            await cast(state["queue"], ("fail", task_id, result["value"]))
            
        return state
    
    async def _process_task(self, task):
        """Simulate task processing."""
        # Random processing time
        await anyio.sleep(random.uniform(0.1, 0.5))
        
        # Random failure (10% chance)
        if random.random() < 0.1:
            raise Exception("Random task failure")


class TaskProducer(GenServer):
    """Produces tasks for the queue."""
    
    def __init__(self, queue_pid, num_tasks: int = 20):
        super().__init__()
        self.queue_pid = queue_pid
        self.num_tasks = num_tasks
    
    async def init(self):
        print(f"[Producer] Will generate {self.num_tasks} tasks")
        return {"queue": self.queue_pid, "generated": 0, "target": self.num_tasks}
    
    async def handle_cast(self, request, state):
        match request:
            case "start":
                # Generate tasks
                for i in range(state["target"]):
                    task = {
                        "id": f"task_{i}",
                        "type": random.choice(["compute", "io", "network"]),
                        "data": f"data_{i}"
                    }
                    await cast(state["queue"], ("enqueue", task))
                    state["generated"] += 1
                    await anyio.sleep(0.05)
                
                print(f"[Producer] Generated {state['generated']} tasks")
        
        return state


class TaskQueueApp(Supervisor):
    """Supervisor for task queue system."""
    
    strategy = RestartStrategy.ONE_FOR_ONE
    
    def __init__(self, num_workers: int = 3):
        super().__init__()
        self.num_workers = num_workers
    
    def child_specs(self):
        specs = [ChildSpec(id="queue", actor_class=TaskQueue, restart=RestartType.PERMANENT)]
        
        # Add workers (will need queue PID - simplified for example)
        for i in range(self.num_workers):
            specs.append(
                ChildSpec(
                    id=f"worker{i}",
                    actor_class=Worker,
                    args=(i, None),  # Queue PID would be injected
                    restart=RestartType.PERMANENT
                )
            )
        
        return specs


async def main():
    """Run task queue demo."""
    print("=== Task Queue with Worker Pool ===\n")
    
    async with anyio.create_task_group() as tg:
        # Start queue
        queue_pid = await TaskQueue.start(task_group=tg)
        await anyio.sleep(0.1)
        
        # Start workers
        workers = []
        for i in range(3):
            worker_pid = await Worker.start(task_group=tg, worker_id=i, queue_pid=queue_pid)
            workers.append(worker_pid)
            await cast(worker_pid, "work")  # Start working
        
        await anyio.sleep(0.2)
        
        # Start producer
        producer_pid = await TaskProducer.start(task_group=tg, queue_pid=queue_pid, num_tasks=15)
        await cast(producer_pid, "start")
        
        # Let system run
        await anyio.sleep(5)
        
        # Get final stats
        stats = await call(queue_pid, "stats", timeout=1.0)
        print(f"\n→ Final Stats: {stats}")
        
        tg.cancel_scope.cancel()


if __name__ == "__main__":
    anyio.run(main)