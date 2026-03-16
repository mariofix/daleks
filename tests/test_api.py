"""Integration tests for the FastAPI routes."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from daleks.app import create_app
from daleks.config import Settings, SmtpAccount


class TestHealth:
    async def test_health_ok(self, client):
        resp = await client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "test" in data["queues"]


class TestSubmitEmail:
    async def test_submit_text_email(self, client):
        with patch("daleks.smtp_client.aiosmtplib.send", new_callable=AsyncMock):
            resp = await client.post(
                "/api/v1/email",
                json={
                    "from_address": "sender@example.com",
                    "to": ["recipient@example.com"],
                    "subject": "Hello",
                    "text_body": "World",
                },
            )
        assert resp.status_code == 202
        data = resp.json()
        assert data["queued"] is True
        assert data["smtp_account"] == "test"

    async def test_submit_html_email(self, client):
        with patch("daleks.smtp_client.aiosmtplib.send", new_callable=AsyncMock):
            resp = await client.post(
                "/api/v1/email",
                json={
                    "from_address": "sender@example.com",
                    "to": "recipient@example.com",
                    "subject": "HTML",
                    "html_body": "<b>hi</b>",
                },
            )
        assert resp.status_code == 202

    async def test_submit_html_email_content_reaches_smtp(self, client):
        """HTML body submitted via the API is delivered to the SMTP client intact."""
        import asyncio

        html_body = "<h1>Password Reset</h1><p>Click <a href='https://example.com'>here</a>.</p>"
        captured: list = []

        async def _capture(msg, **kwargs):
            captured.append(msg)

        with patch("daleks.smtp_client.aiosmtplib.send", side_effect=_capture):
            resp = await client.post(
                "/api/v1/email",
                json={
                    "from_address": "noreply@example.com",
                    "to": ["user@example.com"],
                    "subject": "Password Reset",
                    "html_body": html_body,
                },
            )
        assert resp.status_code == 202
        # Allow the background queue worker to drain
        for _ in range(20):
            if captured:
                break
            await asyncio.sleep(0.05)
        assert captured, "aiosmtplib.send was never called — queue did not drain"
        msg = captured[0]
        content_types = [p.get_content_type() for p in msg.walk()]
        assert "text/html" in content_types
        html_part = next(p for p in msg.walk() if p.get_content_type() == "text/html")
        assert html_body in html_part.get_content()

    async def test_submit_email_no_body_returns_422(self, client):
        resp = await client.post(
            "/api/v1/email",
            json={
                "from_address": "sender@example.com",
                "to": ["recipient@example.com"],
                "subject": "No body",
            },
        )
        assert resp.status_code == 422

    async def test_submit_email_unknown_smtp_account_returns_400(self, client):
        resp = await client.post(
            "/api/v1/email",
            json={
                "from_address": "sender@example.com",
                "to": ["recipient@example.com"],
                "subject": "Test",
                "text_body": "Hi",
                "smtp_account": "nonexistent",
            },
        )
        assert resp.status_code == 400
        assert "nonexistent" in resp.json()["detail"]

    async def test_queue_full_returns_429(self):
        """When the queue is full, the endpoint returns 429."""
        from httpx import ASGITransport, AsyncClient

        # workers=0 → queue never drains so we can deterministically fill it
        cfg = Settings(
            allowed_networks=["127.0.0.1/32"],
            queue_max_size=2,
            smtp_accounts=[
                SmtpAccount(
                    name="full_test",
                    host="localhost",
                    port=1025,
                    use_tls=False,
                    use_ssl=False,
                    workers=0,
                )
            ],
        )
        app = create_app(cfg=cfg)
        qm = app.state.queue_manager
        await qm.start()
        try:
            payload = {
                "from_address": "a@b.com",
                "to": ["c@d.com"],
                "subject": "Flood",
                "text_body": "hi",
            }
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://127.0.0.1"
            ) as client:
                # Fill the queue to max_size
                for _ in range(2):
                    r = await client.post("/api/v1/email", json=payload)
                    assert r.status_code == 202
                # Next request must be rejected
                r = await client.post("/api/v1/email", json=payload)
                assert r.status_code == 429
        finally:
            await qm.stop()

    async def test_missing_from_address_returns_422(self, client):
        resp = await client.post(
            "/api/v1/email",
            json={
                "to": ["recipient@example.com"],
                "subject": "Test",
                "text_body": "Hi",
            },
        )
        assert resp.status_code == 422
