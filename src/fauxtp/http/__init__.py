"""HTTP utilities built on top of fauxtp.

This module intentionally provides a tiny "cursed but educational" HTTP server
implemented with AnyIO sockets and routed through GenServer messaging.
"""

from .server import HttpRequest, HttpResponse, HttpRouter, HttpServer

__all__ = [
    "HttpRequest",
    "HttpResponse",
    "HttpRouter",
    "HttpServer",
]