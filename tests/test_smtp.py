"""Tests for the SMTP client (send_email + _build_message)."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from daleks.config import SmtpAccount
from daleks.models import EmailMessage
from daleks.smtp_client import _build_message, send_email


def _account(**kwargs) -> SmtpAccount:
    defaults = dict(
        name="test",
        host="localhost",
        port=1025,
        username="",
        password="",
        use_tls=False,
        use_ssl=False,
        timeout=10,
        workers=1,
    )
    defaults.update(kwargs)
    return SmtpAccount(**defaults)


def _email(**kwargs) -> EmailMessage:
    defaults = dict(
        from_address="sender@example.com",
        to=["recipient@example.com"],
        subject="Hello",
        text_body="World",
    )
    defaults.update(kwargs)
    return EmailMessage(**defaults)


class TestBuildMessage:
    def test_message_id_is_set(self):
        """Every built message must have a non-empty Message-ID header."""
        msg = _build_message(_email())
        assert msg["Message-ID"]
        assert msg["Message-ID"].strip("<>") != ""

    def test_date_is_set(self):
        """Every built message must have a non-empty Date header (required by RFC 5322)."""
        msg = _build_message(_email())
        assert msg["Date"]
        assert msg["Date"].strip() != ""

    def test_x_mailer_is_set(self):
        """Every built message must include an X-Mailer header identifying daleks."""
        from daleks import __version__

        msg = _build_message(_email())
        assert msg["X-Mailer"] == f"daleks/{__version__}"

    def test_auto_submitted_is_set(self):
        """Every built message must include Auto-Submitted: auto-generated."""
        msg = _build_message(_email())
        assert msg["Auto-Submitted"] == "auto-generated"

    def test_precedence_is_bulk(self):
        """Every built message must include Precedence: bulk."""
        msg = _build_message(_email())
        assert msg["Precedence"] == "bulk"

    def test_importance_defaults_to_normal(self):
        """Default importance must yield Importance: normal and X-Priority: 3."""
        msg = _build_message(_email())
        assert msg["Importance"] == "normal"
        assert msg["X-Priority"] == "3"

    def test_importance_high(self):
        """importance='high' must set Importance: high and X-Priority: 1."""
        msg = _build_message(_email(importance="high"))
        assert msg["Importance"] == "high"
        assert msg["X-Priority"] == "1"

    def test_importance_low(self):
        """importance='low' must set Importance: low and X-Priority: 5."""
        msg = _build_message(_email(importance="low"))
        assert msg["Importance"] == "low"
        assert msg["X-Priority"] == "5"

    def test_plain_text(self):
        msg = _build_message(_email())
        assert msg["Subject"] == "Hello"
        assert msg["From"] == "sender@example.com"
        assert msg["To"] == "recipient@example.com"
        assert "World" in msg.get_body().get_content()  # type: ignore[union-attr]

    def test_multiple_recipients(self):
        msg = _build_message(_email(to=["a@b.com", "c@d.com"]))
        assert msg["To"] == "a@b.com, c@d.com"

    def test_cc_and_reply_to(self):
        msg = _build_message(_email(cc=["cc@example.com"], reply_to="r@example.com"))
        assert msg["Cc"] == "cc@example.com"
        assert msg["Reply-To"] == "r@example.com"

    def test_html_only(self):
        msg = _build_message(_email(text_body=None, html_body="<b>hi</b>"))
        content_types = [p.get_content_type() for p in msg.walk()]
        assert "text/html" in content_types

    def test_html_only_content(self):
        """The exact HTML string must appear in the message body."""
        html = "<h1>Welcome</h1><p>Click <a href='https://example.com'>here</a> to confirm.</p>"
        msg = _build_message(_email(text_body=None, html_body=html))
        content_types = [p.get_content_type() for p in msg.walk()]
        assert "text/html" in content_types
        html_part = next(p for p in msg.walk() if p.get_content_type() == "text/html")
        assert html in html_part.get_content()

    def test_html_and_text(self):
        msg = _build_message(_email(text_body="plain", html_body="<b>html</b>"))
        content_types = [p.get_content_type() for p in msg.walk()]
        assert "text/plain" in content_types
        assert "text/html" in content_types

    def test_html_and_text_content(self):
        """Both the plain-text and HTML strings must appear in their respective parts."""
        text = "Please confirm your account."
        html = "<p>Please <strong>confirm</strong> your account.</p>"
        msg = _build_message(_email(text_body=text, html_body=html))
        text_part = next(p for p in msg.walk() if p.get_content_type() == "text/plain")
        html_part = next(p for p in msg.walk() if p.get_content_type() == "text/html")
        assert text in text_part.get_content()
        assert html in html_part.get_content()

    def test_html_special_characters(self):
        """HTML entities and special characters survive the round-trip."""
        html = '<p>Reset link: <a href="https://example.com/reset?token=abc&amp;id=1">click</a></p>'
        msg = _build_message(_email(text_body=None, html_body=html))
        html_part = next(p for p in msg.walk() if p.get_content_type() == "text/html")
        assert html in html_part.get_content()


class TestSendEmail:
    async def test_send_calls_aiosmtplib(self):
        account = _account(use_tls=True)
        email = _email()
        with patch("daleks.smtp_client.aiosmtplib.send", new_callable=AsyncMock) as mock_send:
            await send_email(account, email)
        mock_send.assert_awaited_once()
        _, kwargs = mock_send.call_args
        assert kwargs["hostname"] == "localhost"
        assert kwargs["port"] == 1025
        assert kwargs["start_tls"] is True
        assert kwargs["sender"] == "sender@example.com"
        assert kwargs["recipients"] == ["recipient@example.com"]

    async def test_send_ssl_account(self):
        account = _account(use_tls=False, use_ssl=True, port=465)
        email = _email()
        with patch("daleks.smtp_client.aiosmtplib.send", new_callable=AsyncMock) as mock_send:
            await send_email(account, email)
        _, kwargs = mock_send.call_args
        assert kwargs["use_tls"] is True
        assert kwargs["start_tls"] is False

    async def test_credentials_passed(self):
        account = _account(username="user", password="pass")
        email = _email()
        with patch("daleks.smtp_client.aiosmtplib.send", new_callable=AsyncMock) as mock_send:
            await send_email(account, email)
        _, kwargs = mock_send.call_args
        assert kwargs["username"] == "user"
        assert kwargs["password"] == "pass"

    async def test_empty_credentials_become_none(self):
        account = _account(username="", password="")
        email = _email()
        with patch("daleks.smtp_client.aiosmtplib.send", new_callable=AsyncMock) as mock_send:
            await send_email(account, email)
        _, kwargs = mock_send.call_args
        assert kwargs["username"] is None
        assert kwargs["password"] is None

    async def test_cc_recipients_included_in_envelope(self):
        account = _account()
        email = _email(cc=["cc@example.com", "cc2@example.com"])
        with patch("daleks.smtp_client.aiosmtplib.send", new_callable=AsyncMock) as mock_send:
            await send_email(account, email)
        _, kwargs = mock_send.call_args
        assert "recipient@example.com" in kwargs["recipients"]
        assert "cc@example.com" in kwargs["recipients"]
        assert "cc2@example.com" in kwargs["recipients"]

    async def test_no_cc_recipients_only_to(self):
        account = _account()
        email = _email()
        with patch("daleks.smtp_client.aiosmtplib.send", new_callable=AsyncMock) as mock_send:
            await send_email(account, email)
        _, kwargs = mock_send.call_args
        assert kwargs["recipients"] == ["recipient@example.com"]
