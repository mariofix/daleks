"""Tests for the in-memory queue manager."""

from __future__ import annotations

import asyncio

import pytest

from daleks.config import Settings, SmtpAccount
from daleks.models import EmailMessage
from daleks.queue_manager import QueueManager


def _make_email(**kwargs) -> EmailMessage:
    defaults = dict(
        from_address="a@b.com",
        to=["c@d.com"],
        subject="Test",
        text_body="hello",
    )
    defaults.update(kwargs)
    return EmailMessage(**defaults)


def _make_manager(*names: str, max_size: int = 5) -> QueueManager:
    accounts = [
        SmtpAccount(
            name=n,
            host="localhost",
            port=1025,
            use_tls=False,
            use_ssl=False,
            workers=1,
        )
        for n in names
    ]
    cfg = Settings(smtp_accounts=accounts, queue_max_size=max_size)
    return QueueManager(cfg)


async def test_start_and_stop():
    mgr = _make_manager("alpha", "beta")
    await mgr.start()
    assert "alpha" in mgr.queues
    assert "beta" in mgr.queues
    await mgr.stop()
    assert mgr.queues == {}


async def test_enqueue_round_robin():
    mgr = _make_manager("a", "b")
    await mgr.start()
    try:
        name1 = mgr.enqueue(_make_email())
        name2 = mgr.enqueue(_make_email())
        # Should alternate between 'a' and 'b'
        assert {name1, name2} == {"a", "b"}
    finally:
        await mgr.stop()


async def test_enqueue_targeted_account():
    mgr = _make_manager("x", "y")
    await mgr.start()
    try:
        name = mgr.enqueue(_make_email(), account_name="y")
        assert name == "y"
        assert mgr.queues["y"].qsize() == 1
        assert mgr.queues["x"].qsize() == 0
    finally:
        await mgr.stop()


async def test_enqueue_unknown_account_raises():
    mgr = _make_manager("only")
    await mgr.start()
    try:
        with pytest.raises(ValueError, match="Unknown SMTP account"):
            mgr.enqueue(_make_email(), account_name="missing")
    finally:
        await mgr.stop()


async def test_enqueue_no_accounts_raises():
    mgr = QueueManager(Settings(smtp_accounts=[]))
    # Don't start — queues dict is empty
    with pytest.raises(RuntimeError, match="No SMTP accounts"):
        mgr.enqueue(_make_email())


async def test_queue_full_raises():
    mgr = _make_manager("full", max_size=3)
    await mgr.start()
    try:
        for _ in range(3):
            mgr.enqueue(_make_email())
        with pytest.raises(asyncio.QueueFull):
            mgr.enqueue(_make_email())
    finally:
        await mgr.stop()
