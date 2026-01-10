# Examples

The `examples/` directory is the “how this is meant to be used” companion to the API docs.

All examples are intended to be run under `uv`:

```bash
uv run python examples/01_concurrent_kvstore.py
uv run python examples/02_pipeline_processing.py
uv run python examples/03_task_queue.py
uv run python examples/04_pubsub_system.py
```

Implementation note: examples rely on actors being started inside an AnyIO TaskGroup via [`python.Actor.start()`](src/fauxtp/actor/base.py:137).

## Example 01: Concurrent KV Store

File: [`examples/01_concurrent_kvstore.py`](examples/01_concurrent_kvstore.py)

### What it demonstrates

- A shared mutable state owner implemented as a [`python.GenServer`](src/fauxtp/actor/genserver.py:15) (`KVStore`)
- Multiple client actors doing concurrent reads/writes (`Writer`, `Reader`)
- Discovery using the registry:
  - registration via [`python.register()`](src/fauxtp/registry/local.py:62)
  - lookup via [`python.whereis()`](src/fauxtp/registry/local.py:72)
- Using [`python.call()`](src/fauxtp/messaging.py:25) for request/reply operations (get/put/stats)
- Using [`python.cast()`](src/fauxtp/messaging.py:18) for “trigger this action” messages to clients

### How it works

- `KVStore` registers its PID as `"kvstore"` during `init`.
- `Writer` and `Reader` register their own PIDs as `"writer:<name>"` and `"reader:<name>"`.
- `main()` spawns the supervisor and then looks up all required PIDs.
- `main()` starts concurrent loops that:
  - cast work to writers/readers
  - writers perform `call(store, ("put", ...))`
  - readers perform `call(store, ("get", ...))`
- Finally, the demo calls `call(store, "stats")` and prints the totals.

### What to look for

- The store is single-threaded by design (one mailbox), so state updates are serialized without locks.
- Reads/writes are concurrent from the perspective of clients, but the store processes them deterministically in message order.

## Example 02: Pipeline Processing

File: [`examples/02_pipeline_processing.py`](examples/02_pipeline_processing.py)

### What it demonstrates

- A pipeline with:
  - a producer (`Producer`)
  - multiple processors (`Processor`)
  - a consumer (`Consumer`)
  - a coordinator (`PipelineCoordinator`) that orchestrates the flow
- A common concurrency pattern: use multiple workers (processors) to parallelize transformation work.
- Structured concurrency discipline: the coordinator starts its pipeline loop using its actor TaskGroup (no unstructured `asyncio.create_task`).

### How it works

- Components register themselves in `init()` under names like:
  - `"pipeline:producer"`
  - `"pipeline:processor:1"`
  - `"pipeline:consumer"`
  - `"pipeline:coordinator"`
- `main()` starts the supervisor, then discovers PIDs via [`python.whereis()`](src/fauxtp/registry/local.py:72).
- `main()` wires the coordinator with `call(coordinator, ("setup", producer, processors, consumer))`.
- `main()` triggers pipeline execution with `call(coordinator, "run")`.
- The coordinator:
  - calls the producer for events (`call(producer, "produce")`)
  - round-robins across processors (`call(processor, ("process", event))`)
  - casts results to consumer (`cast(consumer, ("store", result))`)

### What to look for

- The coordinator is the control plane. It holds PIDs for the pipeline and decides the flow.
- The processor pool shows a simple load distribution strategy.
- The consumer periodically prints progress (every 10 items) and returns stats when called.

## Example 03: Task Queue

File: [`examples/03_task_queue.py`](examples/03_task_queue.py)

### What it demonstrates

- A queue process that owns pending work state (GenServer as queue)
- A set of workers that request/claim tasks and process them
- A producer that adds tasks into the system

If you’re building “OTP-ish job processing” in Python, this is the reference example.

## Example 04: Pub/Sub System

File: [`examples/04_pubsub_system.py`](examples/04_pubsub_system.py)

### What it demonstrates

- A broker process managing:
  - topic subscriptions
  - message fan-out to subscribers
- Multiple subscriber processes with different topic lists
- Multiple publisher processes emitting events

This is a useful model for event buses and decoupled services.

## Running examples safely

All examples run under AnyIO structured concurrency and cancel their TaskGroups at the end. If you adapt an example into an application:

- Keep the root TaskGroup alive for the duration of the app (don’t immediately cancel it).
- Prefer supervisors for long-lived process trees.
- Use timeouts on calls in the presence of failure (see [`docs/messaging.md`](docs/messaging.md)).
