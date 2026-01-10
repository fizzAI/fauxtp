"""
HTTP Server Example (delightfully cursed)

Runs a tiny HTTP/1.1 server implemented on top of fauxtp actors.

- Each TCP connection is handled in the server actor's TaskGroup.
- Each request is turned into a message and routed through a GenServer router.
- One request per connection (Connection: close).

Run:
  uv run python examples/05_http_server.py

Then try:
  curl -i http://127.0.0.1:8080/
  curl -i http://127.0.0.1:8080/health
  curl -i -X POST http://127.0.0.1:8080/echo -d 'hello there'
"""

from __future__ import annotations

import anyio

from fauxtp import HttpRequest, HttpResponse, HttpRouter, HttpServer


async def handle_root(_req: HttpRequest) -> HttpResponse:
    return HttpResponse.text("hello from fauxtp-http\n")


async def handle_health(_req: HttpRequest) -> HttpResponse:
    return HttpResponse.json({"ok": True})


async def handle_echo(req: HttpRequest) -> HttpResponse:
    # Echo the raw body bytes back.
    return HttpResponse(
        status=200,
        headers={"content-type": req.headers.get("content-type", "application/octet-stream")},
        body=req.body,
    )


async def main() -> None:
    routes = {
        ("GET", "/"): handle_root,
        ("GET", "/health"): handle_health,
        ("POST", "/echo"): handle_echo,
    }

    async with anyio.create_task_group() as tg:
        router_pid = await HttpRouter.start(task_group=tg, routes=routes)
        _server_pid = await HttpServer.start(task_group=tg, router=router_pid, host="127.0.0.1", port=8080)

        print("Listening on http://127.0.0.1:8080")
        print("Press Ctrl-C to stop.")

        # Keep the app alive.
        await anyio.sleep_forever()


if __name__ == "__main__":
    anyio.run(main)