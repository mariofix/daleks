"""IP / network restriction middleware for Daleks.

Requests whose client IP is **not** listed in ``allowed_networks`` receive an
immediate ``403 Forbidden`` response before any route handler is invoked.
"""

from __future__ import annotations

import ipaddress
import logging

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

from .config import Settings

logger = logging.getLogger(__name__)


class IPRestrictionMiddleware(BaseHTTPMiddleware):
    """Block requests whose source IP is not in the configured allow-list."""

    def __init__(self, app: ASGIApp, cfg: Settings) -> None:
        super().__init__(app)
        self._networks: list[ipaddress.IPv4Network | ipaddress.IPv6Network] = []
        for entry in cfg.allowed_networks:
            try:
                self._networks.append(ipaddress.ip_network(entry, strict=False))
            except ValueError:
                logger.warning("Ignoring invalid network entry in config: %r", entry)

    # ------------------------------------------------------------------
    # Middleware dispatch
    # ------------------------------------------------------------------

    async def dispatch(self, request: Request, call_next):  # type: ignore[override]
        client_ip = request.client.host if request.client else None
        if client_ip is None or not self._is_allowed(client_ip):
            logger.warning("Blocked request from %s %s", client_ip, request.url.path)
            return Response("Forbidden", status_code=403)
        return await call_next(request)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _is_allowed(self, ip: str) -> bool:
        try:
            addr = ipaddress.ip_address(ip)
            return any(addr in net for net in self._networks)
        except ValueError:
            return False
