"""Simple synchronous HTTP client for the Daleks email-queue API.

This module requires the ``requests`` library.  Install it either via the
``contrib`` optional extra::

    pip install "daleks[contrib]"

or standalone::

    pip install requests

Example usage::

    from contrib.client import DaleksClient

    client = DaleksClient("http://localhost:8000")
    client.send_email(
        from_address="noreply@example.com",
        to=["user@example.com"],
        subject="Hello",
        text_body="World",
    )
"""

from __future__ import annotations

try:
    import requests as _requests
except ImportError as _exc:  # pragma: no cover
    raise ImportError(
        "The 'requests' package is required to use contrib.client. "
        "Install it with: pip install requests  "
        "or: pip install 'daleks[contrib]'"
    ) from _exc


class DaleksClient:
    """Synchronous client for the Daleks ``POST /api/v1/email`` endpoint.

    Parameters
    ----------
    base_url:
        Root URL of the running Daleks server, e.g. ``http://localhost:8000``.
    timeout:
        HTTP request timeout in seconds (default: 10).
    smtp_account:
        Default SMTP account name to target.  Can be overridden per call.
        Omit (or pass ``None``) to let the server pick via round-robin.
    """

    _EMAIL_PATH = "/api/v1/email"

    def __init__(
        self,
        base_url: str,
        timeout: int = 10,
        smtp_account: str | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.default_smtp_account = smtp_account
        self._session = _requests.Session()

    # ── Public API ────────────────────────────────────────────────────────────

    def send_email(
        self,
        from_address: str,
        to: str | list[str],
        subject: str,
        text_body: str | None = None,
        html_body: str | None = None,
        cc: list[str] | None = None,
        reply_to: str | None = None,
        smtp_account: str | None = None,
    ) -> dict:
        """Submit an email to the Daleks queue.

        Parameters
        ----------
        from_address:
            Sender address.
        to:
            Recipient address or list of addresses.
        subject:
            Email subject.
        text_body:
            Plain-text body (at least one of *text_body* / *html_body* required).
        html_body:
            HTML body (at least one of *text_body* / *html_body* required).
        cc:
            Optional list of CC addresses.
        reply_to:
            Optional Reply-To address.
        smtp_account:
            SMTP account name to use.  Overrides the instance-level default.

        Returns
        -------
        dict
            Parsed JSON response from the server.

        Raises
        ------
        requests.HTTPError
            If the server returns a non-2xx HTTP status code.
        requests.RequestException
            On any network-level error.
        """
        payload: dict = {
            "from_address": from_address,
            "to": [to] if isinstance(to, str) else to,
            "subject": subject,
        }
        if text_body is not None:
            payload["text_body"] = text_body
        if html_body is not None:
            payload["html_body"] = html_body
        if cc is not None:
            payload["cc"] = cc
        if reply_to is not None:
            payload["reply_to"] = reply_to

        effective_account = smtp_account if smtp_account is not None else self.default_smtp_account
        if effective_account is not None:
            payload["smtp_account"] = effective_account

        response = self._session.post(
            self.base_url + self._EMAIL_PATH,
            json=payload,
            timeout=self.timeout,
        )
        response.raise_for_status()
        return response.json()

    def close(self) -> None:
        """Close the underlying :class:`requests.Session`."""
        self._session.close()

    def __enter__(self) -> "DaleksClient":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()
