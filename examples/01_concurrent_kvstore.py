"""
Concurrent Key-Value Store Example

Multiple actors reading and writing to a shared KV store GenServer.
Demonstrates concurrent access patterns and state management.
"""

import anyio
from fauxtp import GenServer, Supervisor, ChildSpec, PID, call, cast, register, whereis


class KVStore(GenServer):
    """Thread-safe key-value store."""
    
    async def init(self):
        print("[KVStore] Starting")
        register("kvstore", self.pid)
        return {"data": {}, "reads": 0, "writes": 0}
    
    async def handle_call(self, request, from_ref, state):
        match request:
            case ("get", key):
                state["reads"] += 1
                return (state["data"].get(key), state)
            
            case ("put", key, value):
                new_data = {**state["data"], key: value}
                state["writes"] += 1
                return ("ok", {**state, "data": new_data})
            
            case "stats":
                return ({
                    "keys": len(state["data"]),
                    "reads": state["reads"],
                    "writes": state["writes"]
                }, state)
            
            case _:
                return (None, state)


class Writer(GenServer):
    """Actor that writes to KV store."""
    
    def __init__(self, name: str, store_name: str):
        super().__init__()
        self.name = name
        self.store_name = store_name
    
    async def init(self):
        print(f"[Writer:{self.name}] Starting")
        register(f"writer:{self.name}", self.pid)
        return {"name": self.name, "writes": 0}
    
    async def handle_cast(self, request, state):
        match request:
            case ("write", key, value):
                store = whereis(self.store_name)
                if store:
                    await call(store, ("put", key, value))
                    state["writes"] += 1
                    print(f"[Writer:{state['name']}] Wrote {key}={value}")
        return state


class Reader(GenServer):
    """Actor that reads from KV store."""
    
    def __init__(self, name: str, store_name: str):
        super().__init__()
        self.name = name
        self.store_name = store_name
    
    async def init(self):
        print(f"[Reader:{self.name}] Starting")
        register(f"reader:{self.name}", self.pid)
        return {"name": self.name, "reads": 0}
    
    async def handle_cast(self, request, state):
        match request:
            case ("read", key):
                store = whereis(self.store_name)
                if store:
                    value = await call(store, ("get", key))
                    state["reads"] += 1
                    print(f"[Reader:{state['name']}] Read {key}={value}")
        return state


class KVStoreApp(Supervisor):
    """Supervisor managing KV store and clients."""
    
    def child_specs(self):
        return [
            ChildSpec(id="store", actor_class=KVStore),
            ChildSpec(id="writer1", actor_class=Writer, args=("W1", "kvstore")),
            ChildSpec(id="writer2", actor_class=Writer, args=("W2", "kvstore")),
            ChildSpec(id="reader1", actor_class=Reader, args=("R1", "kvstore")),
            ChildSpec(id="reader2", actor_class=Reader, args=("R2", "kvstore")),
        ]


async def main():
    """Run concurrent KV store demo."""
    print("=== Concurrent KV Store Example ===\n")
    
    async with anyio.create_task_group() as tg:
        _app_pid = await KVStoreApp.start(task_group=tg)
        await anyio.sleep(0.3)

        store = whereis("kvstore")
        w1 = whereis("writer:W1")
        w2 = whereis("writer:W2")
        r1 = whereis("reader:R1")
        r2 = whereis("reader:R2")

        if not all([store, w1, w2, r1, r2]):
            raise RuntimeError("Example failed to start/register all actors")

        assert store is not None
        assert w1 is not None
        assert w2 is not None
        assert r1 is not None
        assert r2 is not None

        print("\n→ Performing concurrent operations...\n")

        async def writer_loop(pid: PID, prefix: str) -> None:
            for i in range(10):
                await cast(pid, ("write", f"{prefix}{i}", i))
                await anyio.sleep(0.02)

        async def reader_loop(pid: PID, keys: list[str]) -> None:
            for k in keys:
                await cast(pid, ("read", k))
                await anyio.sleep(0.03)

        keys1 = [f"a{i}" for i in range(10)]
        keys2 = [f"b{i}" for i in range(10)]

        async with anyio.create_task_group() as ops:
            ops.start_soon(writer_loop, w1, "a")
            ops.start_soon(writer_loop, w2, "b")
            ops.start_soon(reader_loop, r1, keys1)
            ops.start_soon(reader_loop, r2, keys2)

        # Let any remaining casts flush through
        await anyio.sleep(0.5)

        stats = await call(store, "stats")
        print(f"\n→ KVStore stats: {stats}")
        print("\n→ Demo complete")

        tg.cancel_scope.cancel()


if __name__ == "__main__":
    anyio.run(main)