"""Tests for the Pydantic email models."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from daleks.models import EmailMessage, EmailResponse, HealthResponse


class TestEmailMessage:
    def test_minimal_text(self):
        msg = EmailMessage(
            from_address="sender@example.com",
            to=["recipient@example.com"],
            subject="Hello",
            text_body="World",
        )
        assert msg.to == ["recipient@example.com"]

    def test_to_coercion_from_string(self):
        msg = EmailMessage(
            from_address="a@b.com",
            to="single@example.com",  # type: ignore[arg-type]
            subject="Hi",
            text_body="Hi",
        )
        assert msg.to == ["single@example.com"]

    def test_html_body_only(self):
        msg = EmailMessage(
            from_address="a@b.com",
            to=["b@c.com"],
            subject="Hi",
            html_body="<b>Hi</b>",
        )
        assert msg.html_body == "<b>Hi</b>"
        assert msg.text_body is None

    def test_missing_body_raises(self):
        with pytest.raises(ValidationError, match="text_body or html_body"):
            EmailMessage(
                from_address="a@b.com",
                to=["b@c.com"],
                subject="Hi",
            )

    def test_optional_fields(self):
        msg = EmailMessage(
            from_address="a@b.com",
            to=["b@c.com"],
            subject="Hi",
            text_body="Hi",
            cc=["cc@c.com"],
            reply_to="reply@b.com",
            smtp_account="primary",
        )
        assert msg.cc == ["cc@c.com"]
        assert msg.reply_to == "reply@b.com"
        assert msg.smtp_account == "primary"


class TestEmailResponse:
    def test_defaults(self):
        resp = EmailResponse(smtp_account="primary")
        assert resp.queued is True
        assert resp.message == "Email queued for delivery"
        assert resp.smtp_account == "primary"


class TestHealthResponse:
    def test_structure(self):
        resp = HealthResponse(status="ok", queues={"primary": 3, "secondary": 0})
        assert resp.status == "ok"
        assert resp.queues["primary"] == 3
