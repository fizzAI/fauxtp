"""
Pipeline Processing Example (GenStage-inspired)

Demonstrates producer-consumer pattern with backpressure.
Producer generates data → Processor transforms it → Consumer stores results.
"""

import anyio
from fauxtp import GenServer, Supervisor, ChildSpec, PID, call, cast, register, whereis


class Producer(GenServer):
    """Generates events at a controlled rate."""
    
    async def init(self):
        print("[Producer] Starting")
        register("pipeline:producer", self.pid)
        return {"count": 0, "running": True}
    
    async def handle_call(self, request, from_ref, state):
        match request:
            case "produce":
                if state["running"] and state["count"] < 100:
                    event = {"id": state["count"], "data": f"item_{state['count']}"}
                    state["count"] += 1
                    return (event, state)
                return (None, state)
            
            case "stop":
                return ("ok", {**state, "running": False})
        
        return (None, state)


class Processor(GenServer):
    """Transforms events from producer."""
    
    def __init__(self, worker_id: int):
        super().__init__()
        self.worker_id = worker_id
    
    async def init(self):
        print(f"[Processor:{self.worker_id}] Starting")
        register(f"pipeline:processor:{self.worker_id}", self.pid)
        return {"id": self.worker_id, "processed": 0}
    
    async def handle_call(self, request, from_ref, state):
        match request:
            case ("process", event):
                # Simulate processing
                await anyio.sleep(0.01)
                processed = {
                    **event,
                    "processed_by": self.worker_id,
                    "transformed": event["data"].upper()
                }
                state["processed"] += 1
                return (processed, state)
            
            case "stats":
                return ({"worker": state["id"], "processed": state["processed"]}, state)
        
        return (None, state)


class Consumer(GenServer):
    """Stores processed results."""
    
    async def init(self):
        print("[Consumer] Starting")
        register("pipeline:consumer", self.pid)
        return {"results": [], "count": 0}
    
    async def handle_cast(self, request, state):
        match request:
            case ("store", result):
                state["results"].append(result)
                state["count"] += 1
                if state["count"] % 10 == 0:
                    print(f"[Consumer] Stored {state['count']} items")
        return state
    
    async def handle_call(self, request, from_ref, state):
        match request:
            case "get_results":
                return (state["results"], state)
            case "stats":
                return ({"total": state["count"]}, state)
        return (None, state)


class PipelineCoordinator(GenServer):
    """Coordinates the pipeline flow."""
    
    async def init(self):
        print("[Coordinator] Starting pipeline")
        register("pipeline:coordinator", self.pid)
        return {
            "producer": None,
            "processors": [],
            "consumer": None,
            "active": False,
        }
    
    async def handle_call(self, request, from_ref, state):
        match request:
            case ("setup", producer, processors, consumer):
                return (
                    "ok",
                    {
                        **state,
                        "producer": producer,
                        "processors": processors,
                        "consumer": consumer,
                    },
                )

            case "run":
                # Start pipeline in structured concurrency (same TaskGroup as the actor).
                if self._task_group is None:
                    return ("error:no_task_group", state)

                new_state = {**state, "active": True}
                self._task_group.start_soon(self._run_pipeline, new_state)
                return ("started", new_state)

        return (None, state)
    
    async def _run_pipeline(self, state):
        """Run the data pipeline."""
        producer: PID | None = state.get("producer")
        processors: list[PID] = state.get("processors", [])
        consumer: PID | None = state.get("consumer")

        if producer is None or consumer is None or not processors:
            print("[Coordinator] Pipeline not configured; run setup first")
            return

        processor_idx = 0

        for _ in range(50):  # Process 50 items
            if not state.get("active", False):
                break

            # Get item from producer
            event = await call(producer, "produce")
            if not event:
                break

            # Round-robin to processors
            processor = processors[processor_idx]
            processor_idx = (processor_idx + 1) % len(processors)

            # Process item
            result = await call(processor, ("process", event))

            # Store in consumer
            await cast(consumer, ("store", result))

            await anyio.sleep(0.05)

        print("\n[Coordinator] Pipeline complete")


class PipelineApp(Supervisor):
    """Supervisor for pipeline components."""
    
    def child_specs(self):
        return [
            ChildSpec(id="producer", actor_class=Producer),
            ChildSpec(id="processor1", actor_class=Processor, args=(1,)),
            ChildSpec(id="processor2", actor_class=Processor, args=(2,)),
            ChildSpec(id="processor3", actor_class=Processor, args=(3,)),
            ChildSpec(id="consumer", actor_class=Consumer),
            ChildSpec(id="coordinator", actor_class=PipelineCoordinator),
        ]


async def main():
    """Run pipeline processing demo."""
    print("=== Pipeline Processing Example ===\n")
    
    async with anyio.create_task_group() as tg:
        _app_pid = await PipelineApp.start(task_group=tg)
        await anyio.sleep(0.5)

        producer = whereis("pipeline:producer")
        consumer = whereis("pipeline:consumer")
        coordinator = whereis("pipeline:coordinator")
        processors = [
            whereis("pipeline:processor:1"),
            whereis("pipeline:processor:2"),
            whereis("pipeline:processor:3"),
        ]

        if producer is None or consumer is None or coordinator is None or any(p is None for p in processors):
            raise RuntimeError("Example failed to start/register all pipeline actors")

        # Narrow types for type checkers
        assert producer is not None
        assert consumer is not None
        assert coordinator is not None
        processor_pids: list[PID] = [p for p in processors if p is not None]

        await call(coordinator, ("setup", producer, processor_pids, consumer))
        await call(coordinator, "run")

        print("→ Pipeline started, processing data...\n")

        # Let pipeline run
        await anyio.sleep(3)

        stats = await call(consumer, "stats")
        print(f"\n→ Consumer stats: {stats}")
        print("\n→ Pipeline demo complete")

        tg.cancel_scope.cancel()


if __name__ == "__main__":
    anyio.run(main)