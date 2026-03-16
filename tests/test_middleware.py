"""Tests for the IP restriction middleware."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from daleks.app import create_app
from daleks.config import Settings, SmtpAccount


def _app(allowed_networks: list[str]):
    cfg = Settings(
        allowed_networks=allowed_networks,
        smtp_accounts=[
            SmtpAccount(
                name="test",
                host="localhost",
                port=1025,
                use_tls=False,
                use_ssl=False,
                workers=1,
            )
        ],
    )
    return create_app(cfg=cfg)


async def test_allowed_ip():
    """127.0.0.1 should be allowed when it is in the allow-list."""
    app = _app(["127.0.0.1/32"])
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://127.0.0.1"
    ) as client:
        resp = await client.get("/health")
    assert resp.status_code == 200


async def test_blocked_ip():
    """127.0.0.1 should be blocked when it is NOT in the allow-list."""
    app = _app(["10.0.0.0/8"])
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://127.0.0.1"
    ) as client:
        resp = await client.get("/health")
    assert resp.status_code == 403


async def test_cidr_range():
    """127.0.0.1 should be allowed when it falls inside the CIDR range."""
    app = _app(["127.0.0.0/24"])
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://127.0.0.1"
    ) as client:
        resp = await client.get("/health")
    assert resp.status_code == 200


async def test_invalid_network_in_config_does_not_crash():
    """A bad CIDR entry should be skipped, not crash the server."""
    app = _app(["not-a-valid-cidr", "127.0.0.1/32"])
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://127.0.0.1"
    ) as client:
        resp = await client.get("/health")
    assert resp.status_code == 200
