"""Tests for daleks.contrib.django_backend.DaleksEmailBackend."""

from __future__ import annotations

from unittest.mock import MagicMock, call, patch

import pytest
import django
from django.conf import settings


# ── Django setup ──────────────────────────────────────────────────────────────


def _configure_django(**overrides) -> None:
    """Configure minimal Django settings for testing."""
    cfg = {
        "DALEKS_URL": "http://localhost:8000",
        "DALEKS_TIMEOUT": 10,
        "DALEKS_SMTP_ACCOUNT": None,
    }
    cfg.update(overrides)
    if not settings.configured:
        settings.configure(
            EMAIL_BACKEND="daleks.contrib.django_backend.DaleksEmailBackend",
            **cfg,
        )
    else:
        for key, value in cfg.items():
            setattr(settings, key, value)


_configure_django()


# ── Helpers ───────────────────────────────────────────────────────────────────


def _make_message(
    subject: str = "Test",
    body: str = "Hello",
    from_email: str = "noreply@example.com",
    to: list[str] | None = None,
    cc: list[str] | None = None,
    reply_to: list[str] | None = None,
    alternatives: list[tuple[str, str]] | None = None,
) -> MagicMock:
    """Return a minimal mock Django EmailMessage."""
    msg = MagicMock()
    msg.subject = subject
    msg.body = body
    msg.from_email = from_email
    msg.to = to or ["user@example.com"]
    msg.cc = cc or []
    msg.reply_to = reply_to or []
    msg.alternatives = alternatives or []
    return msg


def _make_backend(**setting_overrides):
    """Instantiate DaleksEmailBackend with patched settings."""
    from daleks.contrib.django_backend import DaleksEmailBackend

    for key, value in setting_overrides.items():
        setattr(settings, key, value)
    return DaleksEmailBackend()


# ── _extract_html ─────────────────────────────────────────────────────────────


class TestExtractHtml:
    def test_returns_html_alternative(self):
        from daleks.contrib.django_backend import _extract_html

        msg = _make_message(alternatives=[("<b>Hello</b>", "text/html")])
        assert _extract_html(msg) == "<b>Hello</b>"

    def test_returns_none_when_no_alternatives(self):
        from daleks.contrib.django_backend import _extract_html

        msg = _make_message()
        assert _extract_html(msg) is None

    def test_returns_none_for_non_html_alternatives(self):
        from daleks.contrib.django_backend import _extract_html

        msg = _make_message(alternatives=[("data", "text/plain")])
        assert _extract_html(msg) is None

    def test_returns_none_when_no_alternatives_attr(self):
        from daleks.contrib.django_backend import _extract_html

        msg = MagicMock(spec=[])  # no attributes at all
        assert _extract_html(msg) is None


# ── DaleksEmailBackend ────────────────────────────────────────────────────────


class TestDaleksEmailBackendInit:
    def test_raises_when_daleks_url_missing(self):
        from daleks.contrib.django_backend import DaleksEmailBackend

        original = settings.DALEKS_URL
        settings.DALEKS_URL = ""
        try:
            with pytest.raises(RuntimeError, match="DALEKS_URL"):
                DaleksEmailBackend()
        finally:
            settings.DALEKS_URL = original

    def test_client_created_with_correct_params(self):
        with patch("daleks.contrib.django_backend.DaleksClient") as MockClient:
            settings.DALEKS_URL = "http://daleks.local"
            settings.DALEKS_TIMEOUT = 15
            settings.DALEKS_SMTP_ACCOUNT = "primary"
            from daleks.contrib.django_backend import DaleksEmailBackend

            DaleksEmailBackend()

        MockClient.assert_called_once_with(
            base_url="http://daleks.local",
            timeout=15,
            smtp_account="primary",
        )

    def test_smtp_account_none_when_unset(self):
        with patch("daleks.contrib.django_backend.DaleksClient") as MockClient:
            settings.DALEKS_URL = "http://daleks.local"
            settings.DALEKS_TIMEOUT = 10
            settings.DALEKS_SMTP_ACCOUNT = None
            from daleks.contrib.django_backend import DaleksEmailBackend

            DaleksEmailBackend()

        MockClient.assert_called_once_with(
            base_url="http://daleks.local",
            timeout=10,
            smtp_account=None,
        )


class TestSendMessages:
    def _backend_with_mock_client(self) -> tuple:
        """Return (backend, mock_client_instance)."""
        settings.DALEKS_URL = "http://localhost:8000"
        settings.DALEKS_TIMEOUT = 10
        settings.DALEKS_SMTP_ACCOUNT = None
        with patch("daleks.contrib.django_backend.DaleksClient") as MockClient:
            client_instance = MockClient.return_value
            from daleks.contrib.django_backend import DaleksEmailBackend

            backend = DaleksEmailBackend()
        return backend, client_instance

    def test_returns_zero_for_empty_list(self):
        backend, _ = self._backend_with_mock_client()
        assert backend.send_messages([]) == 0

    def test_sends_single_message(self):
        backend, mock_client = self._backend_with_mock_client()
        msg = _make_message()

        result = backend.send_messages([msg])

        assert result == 1
        mock_client.send_email.assert_called_once_with(
            from_address="noreply@example.com",
            to=["user@example.com"],
            subject="Test",
            text_body="Hello",
            html_body=None,
            cc=None,
            reply_to=None,
        )

    def test_sends_multiple_messages(self):
        backend, mock_client = self._backend_with_mock_client()
        msgs = [_make_message(subject=f"Msg {i}") for i in range(3)]

        result = backend.send_messages(msgs)

        assert result == 3
        assert mock_client.send_email.call_count == 3

    def test_html_alternative_extracted(self):
        backend, mock_client = self._backend_with_mock_client()
        msg = _make_message(alternatives=[("<b>Hello</b>", "text/html")])

        backend.send_messages([msg])

        _, kwargs = mock_client.send_email.call_args
        assert kwargs["html_body"] == "<b>Hello</b>"

    def test_cc_passed_when_present(self):
        backend, mock_client = self._backend_with_mock_client()
        msg = _make_message(cc=["cc@example.com"])

        backend.send_messages([msg])

        _, kwargs = mock_client.send_email.call_args
        assert kwargs["cc"] == ["cc@example.com"]

    def test_cc_none_when_empty(self):
        backend, mock_client = self._backend_with_mock_client()
        msg = _make_message(cc=[])

        backend.send_messages([msg])

        _, kwargs = mock_client.send_email.call_args
        assert kwargs["cc"] is None

    def test_reply_to_passed_when_present(self):
        backend, mock_client = self._backend_with_mock_client()
        msg = _make_message(reply_to=["reply@example.com"])

        backend.send_messages([msg])

        _, kwargs = mock_client.send_email.call_args
        assert kwargs["reply_to"] == "reply@example.com"

    def test_reply_to_none_when_empty(self):
        backend, mock_client = self._backend_with_mock_client()
        msg = _make_message(reply_to=[])

        backend.send_messages([msg])

        _, kwargs = mock_client.send_email.call_args
        assert kwargs["reply_to"] is None

    def test_empty_body_becomes_none(self):
        backend, mock_client = self._backend_with_mock_client()
        msg = _make_message(body="", alternatives=[("<b>hi</b>", "text/html")])

        backend.send_messages([msg])

        _, kwargs = mock_client.send_email.call_args
        assert kwargs["text_body"] is None

    def test_fail_silently_swallows_error(self):
        settings.DALEKS_URL = "http://localhost:8000"
        settings.DALEKS_TIMEOUT = 10
        settings.DALEKS_SMTP_ACCOUNT = None
        with patch("daleks.contrib.django_backend.DaleksClient") as MockClient:
            client_instance = MockClient.return_value
            client_instance.send_email.side_effect = Exception("network error")
            from daleks.contrib.django_backend import DaleksEmailBackend

            backend = DaleksEmailBackend(fail_silently=True)

        result = backend.send_messages([_make_message()])
        assert result == 0

    def test_fail_silently_false_raises(self):
        settings.DALEKS_URL = "http://localhost:8000"
        settings.DALEKS_TIMEOUT = 10
        settings.DALEKS_SMTP_ACCOUNT = None
        with patch("daleks.contrib.django_backend.DaleksClient") as MockClient:
            client_instance = MockClient.return_value
            client_instance.send_email.side_effect = Exception("network error")
            from daleks.contrib.django_backend import DaleksEmailBackend

            backend = DaleksEmailBackend(fail_silently=False)

        with pytest.raises(Exception, match="network error"):
            backend.send_messages([_make_message()])

    def test_partial_failure_counted_correctly(self):
        """Only messages sent before an error count when fail_silently=False."""
        settings.DALEKS_URL = "http://localhost:8000"
        settings.DALEKS_TIMEOUT = 10
        settings.DALEKS_SMTP_ACCOUNT = None
        with patch("daleks.contrib.django_backend.DaleksClient") as MockClient:
            client_instance = MockClient.return_value
            client_instance.send_email.side_effect = [None, Exception("boom")]
            from daleks.contrib.django_backend import DaleksEmailBackend

            backend = DaleksEmailBackend(fail_silently=True)

        msgs = [_make_message(subject="First"), _make_message(subject="Second")]
        result = backend.send_messages(msgs)
        assert result == 1


class TestContextManager:
    def test_close_called_on_exit(self):
        settings.DALEKS_URL = "http://localhost:8000"
        settings.DALEKS_TIMEOUT = 10
        settings.DALEKS_SMTP_ACCOUNT = None
        with patch("daleks.contrib.django_backend.DaleksClient") as MockClient:
            client_instance = MockClient.return_value
            from daleks.contrib.django_backend import DaleksEmailBackend

            with DaleksEmailBackend() as backend:
                pass

        client_instance.close.assert_called_once()
