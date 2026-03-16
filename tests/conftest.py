"""Shared pytest fixtures for Daleks tests."""

from __future__ import annotations

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from daleks.app import create_app
from daleks.config import Settings, SmtpAccount


@pytest.fixture
def smtp_account() -> SmtpAccount:
    return SmtpAccount(
        name="test",
        host="localhost",
        port=1025,
        username="",
        password="",
        use_tls=False,
        use_ssl=False,
        workers=1,
    )


@pytest.fixture
def settings(smtp_account: SmtpAccount) -> Settings:
    return Settings(
        allowed_networks=["127.0.0.1/32", "::1/128"],
        queue_max_size=10,
        smtp_accounts=[smtp_account],
        log_level="DEBUG",
    )


@pytest_asyncio.fixture
async def client(settings: Settings):
    """An AsyncClient wired to a fresh app instance.

    Workers are started/stopped manually so the fixture does not depend on
    the ASGI lifespan being invoked by the test transport.
    """
    app = create_app(cfg=settings)
    qm = app.state.queue_manager
    await qm.start()
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://127.0.0.1"
        ) as ac:
            yield ac
    finally:
        await qm.stop()
