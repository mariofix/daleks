"""Tests for daleks.contrib.flask_security_mail.DaleksMailUtil."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from flask_security import MailUtil

from daleks.contrib.flask_security_mail import DaleksMailUtil, _normalise_sender


# ── Helper ────────────────────────────────────────────────────────────────────


def _make_app(**config_overrides) -> MagicMock:
    """Return a minimal mock Flask app with a .config dict."""
    app = MagicMock()
    cfg = {
        "DALEKS_URL": "http://localhost:8000",
        "DALEKS_TIMEOUT": 10,
        "DALEKS_SMTP_ACCOUNT": None,
    }
    cfg.update(config_overrides)
    app.config = cfg
    return app


# ── _normalise_sender ─────────────────────────────────────────────────────────


class TestNormaliseSender:
    def test_plain_string_unchanged(self):
        assert _normalise_sender("noreply@example.com") == "noreply@example.com"

    def test_tuple_returns_address(self):
        assert _normalise_sender(("My App", "noreply@example.com")) == "noreply@example.com"


# ── DaleksMailUtil ────────────────────────────────────────────────────────────


class TestDaleksMailUtil:
    def test_send_mail_calls_client(self):
        app = _make_app()
        util = DaleksMailUtil(app)

        with patch("daleks.contrib.flask_security_mail.DaleksClient") as MockClient:
            client_instance = MockClient.return_value
            util.send_mail(
                template="welcome",
                subject="Welcome",
                recipient="user@example.com",
                sender="noreply@example.com",
                body="Hello",
                html="<b>Hello</b>",
            )

        MockClient.assert_called_once_with(
            base_url="http://localhost:8000",
            timeout=10,
            smtp_account=None,
        )
        client_instance.send_email.assert_called_once_with(
            from_address="noreply@example.com",
            to="user@example.com",
            subject="Welcome",
            text_body="Hello",
            html_body="<b>Hello</b>",
        )

    def test_sender_tuple_normalised(self):
        app = _make_app()
        util = DaleksMailUtil(app)

        with patch("daleks.contrib.flask_security_mail.DaleksClient") as MockClient:
            client_instance = MockClient.return_value
            util.send_mail(
                template="reset",
                subject="Reset",
                recipient="user@example.com",
                sender=("My App", "noreply@example.com"),
                body="Reset link",
                html=None,
            )

        client_instance.send_email.assert_called_once_with(
            from_address="noreply@example.com",
            to="user@example.com",
            subject="Reset",
            text_body="Reset link",
            html_body=None,
        )

    def test_empty_body_becomes_none(self):
        """Flask-Security may pass an empty string for a missing body."""
        app = _make_app()
        util = DaleksMailUtil(app)

        with patch("daleks.contrib.flask_security_mail.DaleksClient") as MockClient:
            client_instance = MockClient.return_value
            util.send_mail(
                template="confirm",
                subject="Confirm",
                recipient="u@example.com",
                sender="a@example.com",
                body="",
                html="<b>confirm</b>",
            )

        client_instance.send_email.assert_called_once_with(
            from_address="a@example.com",
            to="u@example.com",
            subject="Confirm",
            text_body=None,  # empty string converted to None
            html_body="<b>confirm</b>",
        )

    def test_smtp_account_passed_to_client(self):
        app = _make_app(DALEKS_SMTP_ACCOUNT="primary")
        util = DaleksMailUtil(app)

        with patch("daleks.contrib.flask_security_mail.DaleksClient") as MockClient:
            util.send_mail(
                template="welcome",
                subject="Hi",
                recipient="u@example.com",
                sender="a@example.com",
                body="Hi",
                html=None,
            )

        MockClient.assert_called_once_with(
            base_url="http://localhost:8000",
            timeout=10,
            smtp_account="primary",
        )

    def test_custom_timeout_used(self):
        app = _make_app(DALEKS_TIMEOUT=30)
        util = DaleksMailUtil(app)

        with patch("daleks.contrib.flask_security_mail.DaleksClient") as MockClient:
            util.send_mail(
                template="welcome",
                subject="Hi",
                recipient="u@example.com",
                sender="a@example.com",
                body="Hi",
                html=None,
            )

        MockClient.assert_called_once_with(
            base_url="http://localhost:8000",
            timeout=30,
            smtp_account=None,
        )

    def test_missing_daleks_url_raises(self):
        app = _make_app(DALEKS_URL="")
        util = DaleksMailUtil(app)

        with pytest.raises(RuntimeError, match="DALEKS_URL"):
            util.send_mail(
                template="welcome",
                subject="Hi",
                recipient="u@example.com",
                sender="a@example.com",
                body="Hi",
                html=None,
            )

    def test_extra_kwargs_ignored(self):
        """Flask-Security may pass extra kwargs; they should be silently ignored."""
        app = _make_app()
        util = DaleksMailUtil(app)

        with patch("daleks.contrib.flask_security_mail.DaleksClient"):
            # Should not raise even with unknown kwargs
            util.send_mail(
                template="welcome",
                subject="Hi",
                recipient="u@example.com",
                sender="a@example.com",
                body="Hi",
                html=None,
                user=MagicMock(),
                extra_future_arg="value",
            )

    def test_is_subclass_of_mail_util(self):
        """DaleksMailUtil must be a subclass of MailUtil for the full interface."""
        assert issubclass(DaleksMailUtil, MailUtil)

    def test_has_validate_method(self):
        """DaleksMailUtil must expose the validate() method required by Flask-Security."""
        app = _make_app()
        util = DaleksMailUtil(app)
        assert callable(getattr(util, "validate", None))

    def test_has_normalize_method(self):
        """DaleksMailUtil must expose the normalize() method required by Flask-Security."""
        app = _make_app()
        util = DaleksMailUtil(app)
        assert callable(getattr(util, "normalize", None))
