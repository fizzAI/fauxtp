"""
Pub/Sub System

Demonstrates publisher-subscriber pattern with topic-based routing.
Publishers send to topics, subscribers receive relevant messages.
"""

import anyio
from fauxtp import GenServer, Supervisor, ChildSpec, call, cast, send


class PubSubBroker(GenServer):
    """Central message broker managing topics and subscriptions."""
    
    async def init(self):
        print("[Broker] Starting pub/sub broker")
        return {
            "topics": {},  # topic -> set of subscriber PIDs
            "messages_routed": 0
        }
    
    async def handle_call(self, request, from_ref, state):
        match request:
            case ("subscribe", topic, subscriber_pid):
                if topic not in state["topics"]:
                    state["topics"][topic] = set()
                state["topics"][topic].add(subscriber_pid)
                print(f"[Broker] Subscribed {subscriber_pid._id} to '{topic}'")
                return ("ok", state)
            
            case ("unsubscribe", topic, subscriber_pid):
                if topic in state["topics"]:
                    state["topics"][topic].discard(subscriber_pid)
                return ("ok", state)
            
            case "stats":
                return ({
                    "topics": list(state["topics"].keys()),
                    "subscribers": {t: len(subs) for t, subs in state["topics"].items()},
                    "messages_routed": state["messages_routed"]
                }, state)
        
        return (None, state)
    
    async def handle_cast(self, request, state):
        match request:
            case ("publish", topic, message):
                if topic in state["topics"]:
                    for subscriber in state["topics"][topic]:
                        await send(subscriber, ("message", topic, message))
                        state["messages_routed"] += 1
                    print(f"[Broker] Published to '{topic}': {message}")
        
        return state


class Publisher(GenServer):
    """Publishes messages to topics."""
    
    def __init__(self, name: str, broker_pid):
        super().__init__()
        self.name = name
        self.broker_pid = broker_pid
    
    async def init(self):
        print(f"[Publisher:{self.name}] Starting")
        return {"name": self.name, "broker": self.broker_pid, "published": 0}
    
    async def handle_cast(self, request, state):
        match request:
            case ("publish", topic, message):
                await cast(state["broker"], ("publish", topic, message))
                state["published"] += 1
                print(f"[Publisher:{state['name']}] Published to '{topic}'")
        
        return state


class Subscriber(GenServer):
    """Subscribes to topics and processes messages."""
    
    def __init__(self, name: str, broker_pid, topics: list[str]):
        super().__init__()
        self.name = name
        self.broker_pid = broker_pid
        self.topics = topics
    
    async def init(self):
        print(f"[Subscriber:{self.name}] Starting, subscribing to {self.topics}")
        
        # Subscribe to topics
        for topic in self.topics:
            await call(self.broker_pid, ("subscribe", topic, self.pid))
        
        return {
            "name": self.name,
            "broker": self.broker_pid,
            "topics": self.topics,
            "received": 0,
            "messages": []
        }
    
    async def handle_info(self, message, state):
        match message:
            case ("message", topic, content):
                state["received"] += 1
                state["messages"].append({"topic": topic, "content": content})
                print(f"[Subscriber:{state['name']}] Received from '{topic}': {content}")
        
        return state
    
    async def handle_call(self, request, from_ref, state):
        match request:
            case "get_messages":
                return (state["messages"], state)
            case "stats":
                return ({"received": state["received"]}, state)
        
        return (None, state)


async def main():
    """Run pub/sub demo."""
    print("=== Pub/Sub System Example ===\n")
    
    async with anyio.create_task_group() as tg:
        # Start broker
        broker = await PubSubBroker.start(task_group=tg)
        await anyio.sleep(0.1)
        
        # Start subscribers
        sub1 = await Subscriber.start(task_group=tg, name="Analytics", broker_pid=broker, topics=["events", "metrics"])
        sub2 = await Subscriber.start(task_group=tg, name="Logger", broker_pid=broker, topics=["events", "errors"])
        sub3 = await Subscriber.start(task_group=tg, name="Monitor", broker_pid=broker, topics=["metrics"])
        
        await anyio.sleep(0.2)
        
        # Start publishers
        pub1 = await Publisher.start(task_group=tg, name="App", broker_pid=broker)
        pub2 = await Publisher.start(task_group=tg, name="Worker", broker_pid=broker)
        
        await anyio.sleep(0.1)
        
        print("\n→ Publishing messages...\n")
        
        # Publish messages
        await cast(pub1, ("publish", "events", "User logged in"))
        await anyio.sleep(0.1)
        
        await cast(pub1, ("publish", "metrics", {"cpu": 45, "memory": 2048}))
        await anyio.sleep(0.1)
        
        await cast(pub2, ("publish", "events", "Job completed"))
        await anyio.sleep(0.1)
        
        await cast(pub2, ("publish", "errors", "Connection timeout"))
        await anyio.sleep(0.1)
        
        await cast(pub1, ("publish", "metrics", {"cpu": 52, "memory": 2100}))
        await anyio.sleep(0.2)
        
        # Get stats
        print("\n→ System Stats:")
        broker_stats = await call(broker, "stats")
        print(f"  Broker: {broker_stats}")
        
        sub1_stats = await call(sub1, "stats")
        print(f"  Analytics subscriber: {sub1_stats}")
        
        sub2_stats = await call(sub2, "stats")
        print(f"  Logger subscriber: {sub2_stats}")
        
        sub3_stats = await call(sub3, "stats")
        print(f"  Monitor subscriber: {sub3_stats}")
        
        print("\n→ Demo complete")
        tg.cancel_scope.cancel()


if __name__ == "__main__":
    anyio.run(main)