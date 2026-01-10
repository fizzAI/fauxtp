"""Tiny HTTP/1.1 server built on fauxtp + AnyIO.

This is intentionally minimal and "funny": it turns incoming HTTP requests into
messages sent to a GenServer-based router.

Features:
- HTTP/1.1 request line + headers parsing
- Optional Content-Length body (no chunked encoding)
- One request per connection (Connection: close)
- Fully AnyIO (no asyncio.create_task), uses the actor's TaskGroup for concurrency
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Mapping

import anyio
from anyio.abc import SocketStream

from ..actor.genserver import GenServer
from ..messaging import call
from ..primitives.pid import PID


HeaderMap = dict[str, str]
Handler = Callable[["HttpRequest"], Awaitable["HttpResponse"]]


@dataclass(frozen=True, slots=True)
class HttpRequest:
    method: str
    path: str
    version: str
    headers: HeaderMap
    body: bytes


@dataclass(frozen=True, slots=True)
class HttpResponse:
    status: int = 200
    headers: Mapping[str, str] | None = None
    body: bytes = b""

    @staticmethod
    def text(
        text: str,
        *,
        status: int = 200,
        headers: Mapping[str, str] | None = None,
        encoding: str = "utf-8",
    ) -> "HttpResponse":
        body = text.encode(encoding)
        merged: dict[str, str] = {"content-type": f"text/plain; charset={encoding}"}
        if headers:
            merged.update({k.lower(): v for k, v in headers.items()})
        return HttpResponse(status=status, headers=merged, body=body)

    @staticmethod
    def json(
        obj: Any,
        *,
        status: int = 200,
        headers: Mapping[str, str] | None = None,
    ) -> "HttpResponse":
        import json

        body = json.dumps(obj, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        merged: dict[str, str] = {"content-type": "application/json; charset=utf-8"}
        if headers:
            merged.update({k.lower(): v for k, v in headers.items()})
        return HttpResponse(status=status, headers=merged, body=body)


_STATUS_TEXT: dict[int, str] = {
    200: "OK",
    204: "No Content",
    400: "Bad Request",
    404: "Not Found",
    405: "Method Not Allowed",
    413: "Payload Too Large",
    500: "Internal Server Error",
}


def _status_line(status: int) -> str:
    text = _STATUS_TEXT.get(status, "OK")
    return f"HTTP/1.1 {status} {text}\r\n"


def _normalize_headers(headers: Mapping[str, str] | None) -> dict[str, str]:
    if not headers:
        return {}
    return {k.lower(): v for k, v in headers.items()}


async def _read_until(stream: SocketStream, marker: bytes, max_bytes: int) -> bytes:
    buf = bytearray()
    while True:
        if len(buf) > max_bytes:
            raise ValueError("request too large")
        idx = buf.find(marker)
        if idx != -1:
            return bytes(buf[: idx + len(marker)])
        try:
            chunk = await stream.receive(4096)
        except anyio.EndOfStream:
            return bytes(buf)
        if not chunk:
            return bytes(buf)
        buf.extend(chunk)


def _parse_headers(block: bytes) -> tuple[str, str, str, HeaderMap]:
    # block contains request line + headers ending with \r\n\r\n
    try:
        head = block.decode("iso-8859-1")
    except Exception as e:  # pragma: no cover
        raise ValueError(f"invalid header encoding: {e!r}") from e

    lines = head.split("\r\n")
    if not lines or not lines[0]:
        raise ValueError("missing request line")

    parts = lines[0].split(" ")
    if len(parts) != 3:
        raise ValueError("invalid request line")
    method, path, version = parts

    headers: HeaderMap = {}
    for line in lines[1:]:
        if line == "":
            break
        if ":" not in line:
            continue
        k, v = line.split(":", 1)
        headers[k.strip().lower()] = v.strip()
    return method, path, version, headers


async def _read_exact(stream: SocketStream, n: int) -> bytes:
    buf = bytearray()
    while len(buf) < n:
        try:
            chunk = await stream.receive(n - len(buf))
        except anyio.EndOfStream:
            break
        if not chunk:
            break
        buf.extend(chunk)
    return bytes(buf)


async def _write_response(stream: SocketStream, response: HttpResponse) -> None:
    headers = _normalize_headers(response.headers)
    body = response.body or b""

    # Default headers
    headers.setdefault("content-length", str(len(body)))
    headers.setdefault("connection", "close")

    # Write response
    start = _status_line(response.status).encode("ascii")
    head = b"".join(f"{k}: {v}\r\n".encode("ascii") for k, v in headers.items())

    # anyio SocketStream uses send()/receive() (not send_all()).
    await stream.send(start + head + b"\r\n" + body)


class HttpRouter(GenServer):
    """A very small router that dispatches (method, path) to async handlers.

    Messages:
      call(("route", HttpRequest)) -> HttpResponse
    """

    def __init__(self, routes: Mapping[tuple[str, str], Handler] | None = None):
        super().__init__()
        self._routes: dict[tuple[str, str], Handler] = dict(routes or {})

    async def init(self):
        return {"routes": self._routes}

    async def handle_call(self, request, from_ref, state):
        match request:
            case ("route", HttpRequest() as req):
                routes: dict[tuple[str, str], Handler] = state["routes"]
                handler = routes.get((req.method.upper(), req.path))
                if handler is None:
                    return (HttpResponse.text("not found", status=404), state)
                try:
                    resp = await handler(req)
                except Exception as e:
                    return (HttpResponse.text(f"handler error: {e!r}", status=500), state)
                return (resp, state)
            case _:
                return (HttpResponse.text("bad request", status=400), state)


class HttpServer(GenServer):
    """HTTP server actor.

    - Starts a TCP listener in init()
    - Accepts connections and handles them in background tasks in the same TaskGroup
    - Routes each request by calling a router PID (a GenServer)

    Messages:
      call("addr") -> {"host": str, "port": int}
    """

    def __init__(
        self,
        *,
        router: PID,
        host: str = "127.0.0.1",
        port: int = 0,
        max_header_bytes: int = 64 * 1024,
        max_body_bytes: int = 1 * 1024 * 1024,
    ):
        super().__init__()
        self._router = router
        self._host = host
        self._port = port
        self._max_header_bytes = max_header_bytes
        self._max_body_bytes = max_body_bytes
        # anyio.create_tcp_listener() may return a MultiListener depending on options;
        # we keep this loosely typed to avoid fighting the type checker.
        self._listener: Any = None

    async def init(self):
        if self._task_group is None:
            raise RuntimeError("HttpServer requires a task_group (structured concurrency)")

        self._listener = await anyio.create_tcp_listener(local_host=self._host, local_port=self._port)
        # `listeners[0]` address is available through the listener itself in anyio; we store desired host/port.
        # AnyIO doesn't give a direct "getsockname" on the abstract listener, so for now we treat port=0 as unknown.
        # If you need the bound port, pass an explicit port.
        self._task_group.start_soon(self._serve_loop)

        return {
            "host": self._host,
            "port": self._port,
        }

    async def _serve_loop(self) -> None:
        """
        Serve incoming connections.

        anyio.create_tcp_listener() may return a Listener or a MultiListener.
        The portable API is listener.serve(handler, ...), not accept().
        """
        assert self._listener is not None
        assert self._task_group is not None

        async with self._listener:
            # Use the actor's task group for per-connection tasks.
            await self._listener.serve(self._handle_client, task_group=self._task_group)

    async def _handle_client(self, stream: SocketStream) -> None:
        async with stream:
            try:
                header_block = await _read_until(stream, b"\r\n\r\n", self._max_header_bytes)
                if not header_block:
                    return

                method, path, version, headers = _parse_headers(header_block)
                content_length = int(headers.get("content-length", "0") or "0")
                if content_length > self._max_body_bytes:
                    await _write_response(stream, HttpResponse.text("payload too large", status=413))
                    return

                body = b""
                if content_length:
                    body = await _read_exact(stream, content_length)

                req = HttpRequest(
                    method=method,
                    path=path,
                    version=version,
                    headers=headers,
                    body=body,
                )
                resp: HttpResponse = await call(self._router, ("route", req), timeout=5.0)
                await _write_response(stream, resp)
            except ValueError as e:
                await _write_response(stream, HttpResponse.text(f"bad request: {e}", status=400))
            except Exception as e:  # pragma: no cover
                await _write_response(stream, HttpResponse.text(f"server error: {e!r}", status=500))

    async def handle_call(self, request, from_ref, state):
        match request:
            case "addr":
                return ({"host": state["host"], "port": state["port"]}, state)
            case _:
                return (None, state)