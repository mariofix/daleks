"""Tests for contrib.client.DaleksClient."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from contrib.client import DaleksClient


def _mock_response(status_code: int = 202, json_data: dict | None = None) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data or {"queued": True, "smtp_account": "primary"}
    resp.raise_for_status = MagicMock()
    if status_code >= 400:
        import requests

        resp.raise_for_status.side_effect = requests.HTTPError(response=resp)
    return resp


def _patched_post(mock_resp: MagicMock):
    """Context manager that patches Session.post to return *mock_resp*."""
    return patch("requests.Session.post", return_value=mock_resp)


class TestDaleksClientInit:
    def test_default_timeout(self):
        client = DaleksClient("http://localhost:8000")
        assert client.timeout == 10
        assert client.default_smtp_account is None

    def test_trailing_slash_stripped(self):
        client = DaleksClient("http://localhost:8000/")
        assert client.base_url == "http://localhost:8000"

    def test_custom_smtp_account(self):
        client = DaleksClient("http://localhost:8000", smtp_account="relay")
        assert client.default_smtp_account == "relay"


class TestSendEmail:
    def test_posts_to_correct_endpoint(self):
        client = DaleksClient("http://localhost:8000")
        mock_resp = _mock_response()
        with _patched_post(mock_resp) as mock_post:
            client.send_email(
                from_address="a@b.com",
                to=["c@d.com"],
                subject="Hi",
                text_body="Hello",
            )
        url = mock_post.call_args[0][0]
        assert url == "http://localhost:8000/api/v1/email"

    def test_payload_text_body(self):
        client = DaleksClient("http://localhost:8000")
        mock_resp = _mock_response()
        with _patched_post(mock_resp) as mock_post:
            client.send_email(
                from_address="a@b.com",
                to=["c@d.com"],
                subject="Hi",
                text_body="Hello",
            )
        payload = mock_post.call_args[1]["json"]
        assert payload["from_address"] == "a@b.com"
        assert payload["to"] == ["c@d.com"]
        assert payload["text_body"] == "Hello"
        assert "html_body" not in payload

    def test_payload_html_body(self):
        client = DaleksClient("http://localhost:8000")
        mock_resp = _mock_response()
        with _patched_post(mock_resp) as mock_post:
            client.send_email(
                from_address="a@b.com",
                to="c@d.com",  # string → list conversion
                subject="Hi",
                html_body="<b>hi</b>",
            )
        payload = mock_post.call_args[1]["json"]
        assert payload["to"] == ["c@d.com"]
        assert payload["html_body"] == "<b>hi</b>"
        assert "text_body" not in payload

    def test_optional_fields_included_when_set(self):
        client = DaleksClient("http://localhost:8000")
        mock_resp = _mock_response()
        with _patched_post(mock_resp) as mock_post:
            client.send_email(
                from_address="a@b.com",
                to=["c@d.com"],
                subject="Hi",
                text_body="Hello",
                cc=["cc@d.com"],
                reply_to="reply@a.com",
            )
        payload = mock_post.call_args[1]["json"]
        assert payload["cc"] == ["cc@d.com"]
        assert payload["reply_to"] == "reply@a.com"

    def test_smtp_account_per_call_overrides_default(self):
        client = DaleksClient("http://localhost:8000", smtp_account="default")
        mock_resp = _mock_response()
        with _patched_post(mock_resp) as mock_post:
            client.send_email(
                from_address="a@b.com",
                to=["c@d.com"],
                subject="Hi",
                text_body="Hello",
                smtp_account="override",
            )
        payload = mock_post.call_args[1]["json"]
        assert payload["smtp_account"] == "override"

    def test_instance_default_smtp_account_used_when_not_overridden(self):
        client = DaleksClient("http://localhost:8000", smtp_account="default")
        mock_resp = _mock_response()
        with _patched_post(mock_resp) as mock_post:
            client.send_email(
                from_address="a@b.com",
                to=["c@d.com"],
                subject="Hi",
                text_body="Hello",
            )
        payload = mock_post.call_args[1]["json"]
        assert payload["smtp_account"] == "default"

    def test_no_smtp_account_omits_key(self):
        client = DaleksClient("http://localhost:8000")
        mock_resp = _mock_response()
        with _patched_post(mock_resp) as mock_post:
            client.send_email(
                from_address="a@b.com",
                to=["c@d.com"],
                subject="Hi",
                text_body="Hello",
            )
        payload = mock_post.call_args[1]["json"]
        assert "smtp_account" not in payload

    def test_returns_response_json(self):
        client = DaleksClient("http://localhost:8000")
        mock_resp = _mock_response(json_data={"queued": True, "smtp_account": "test"})
        with _patched_post(mock_resp):
            result = client.send_email(
                from_address="a@b.com",
                to=["c@d.com"],
                subject="Hi",
                text_body="Hello",
            )
        assert result == {"queued": True, "smtp_account": "test"}

    def test_http_error_propagated(self):
        import requests

        client = DaleksClient("http://localhost:8000")
        mock_resp = _mock_response(status_code=429)
        with _patched_post(mock_resp):
            with pytest.raises(requests.HTTPError):
                client.send_email(
                    from_address="a@b.com",
                    to=["c@d.com"],
                    subject="Hi",
                    text_body="Hello",
                )

    def test_timeout_passed_to_session(self):
        client = DaleksClient("http://localhost:8000", timeout=5)
        mock_resp = _mock_response()
        with _patched_post(mock_resp) as mock_post:
            client.send_email("a@b.com", ["c@d.com"], "Hi", text_body="Hello")
        assert mock_post.call_args[1]["timeout"] == 5


class TestContextManager:
    def test_context_manager_closes_session(self):
        with DaleksClient("http://localhost:8000") as client:
            mock_resp = _mock_response()
            with _patched_post(mock_resp):
                client.send_email("a@b.com", ["c@d.com"], "Hi", text_body="Hi")
        # If we got here the __exit__ ran without error
