"""Django email backend for Daleks.

Drop-in replacement for Django's default SMTP email backend that routes all
outgoing emails through the Daleks HTTP API instead of connecting directly to
an SMTP server.

Installation
------------
Install Daleks with the ``contrib`` extra so that ``requests`` is available::

    pip install "daleks[contrib]"

Django settings keys
--------------------
``DALEKS_URL`` (required)
    Base URL of the running Daleks server, e.g. ``http://localhost:8000``.

``DALEKS_TIMEOUT`` (optional, default: 10)
    HTTP request timeout in seconds.

``DALEKS_SMTP_ACCOUNT`` (optional)
    SMTP account name to target on the Daleks server.  Omit to let the server
    pick via round-robin.

Usage
-----
Add the backend to your Django settings::

    # settings.py
    EMAIL_BACKEND = "daleks.contrib.django_backend.DaleksEmailBackend"
    DALEKS_URL = "http://localhost:8000"
    # DALEKS_TIMEOUT = 10          # optional, default 10 s
    # DALEKS_SMTP_ACCOUNT = None   # optional, uses round-robin

Then use Django's standard email API as usual::

    from django.core.mail import send_mail

    send_mail(
        subject="Hello",
        message="Plain text body",
        from_email="noreply@example.com",
        recipient_list=["user@example.com"],
    )
"""

from __future__ import annotations

import logging

from django.conf import settings
from django.core.mail.backends.base import BaseEmailBackend

from .client import DaleksClient

logger = logging.getLogger(__name__)


class DaleksEmailBackend(BaseEmailBackend):
    """Django email backend that sends via the Daleks queue API.

    Inherits from :class:`django.core.mail.backends.base.BaseEmailBackend`
    so that it is a fully compatible drop-in replacement.  Each call to
    :meth:`send_messages` submits every message to the Daleks HTTP endpoint
    using :class:`~daleks.contrib.client.DaleksClient`.

    Parameters
    ----------
    fail_silently:
        If ``True``, exceptions raised while sending are swallowed and
        ``send_messages`` returns ``0`` instead of re-raising.
    **kwargs:
        Additional keyword arguments accepted by the base class (ignored).
    """

    def __init__(self, fail_silently: bool = False, **kwargs: object) -> None:
        super().__init__(fail_silently=fail_silently, **kwargs)

        base_url: str = getattr(settings, "DALEKS_URL", "")
        if not base_url:
            raise RuntimeError(
                "DALEKS_URL is not set in Django settings. "
                "Set it to the base URL of your running Daleks server, "
                "e.g. DALEKS_URL = 'http://localhost:8000'."
            )

        timeout: int = int(getattr(settings, "DALEKS_TIMEOUT", 10))
        smtp_account: str | None = getattr(settings, "DALEKS_SMTP_ACCOUNT", None) or None

        self._client = DaleksClient(
            base_url=base_url,
            timeout=timeout,
            smtp_account=smtp_account,
        )

    # ── Django email backend interface ─────────────────────────────────────────

    def send_messages(self, email_messages: list) -> int:
        """Send each message in *email_messages* via the Daleks API.

        Parameters
        ----------
        email_messages:
            A list of :class:`django.core.mail.EmailMessage` instances.

        Returns
        -------
        int
            The number of messages that were successfully submitted.
        """
        if not email_messages:
            return 0

        sent = 0
        for message in email_messages:
            try:
                self._client.send_email(
                    from_address=message.from_email,
                    to=list(message.to),
                    subject=message.subject,
                    text_body=message.body or None,
                    html_body=_extract_html(message),
                    cc=list(message.cc) or None,
                    # Daleks accepts a single reply-to address; use the first
                    # one when Django provides multiple.
                    reply_to=list(message.reply_to)[0] if message.reply_to else None,
                )
                logger.debug(
                    "Sent email %r to %s via Daleks",
                    message.subject,
                    message.to,
                )
                sent += 1
            except Exception:
                if not self.fail_silently:
                    raise
        return sent

    def close(self) -> None:
        """Close the underlying HTTP session."""
        self._client.close()

    def __enter__(self) -> "DaleksEmailBackend":
        return self

    def __exit__(self, *args: object) -> None:
        self.close()


# ── Helpers ───────────────────────────────────────────────────────────────────


def _extract_html(message: object) -> str | None:
    """Return the HTML alternative body from a Django EmailMessage, or ``None``.

    Django stores HTML alternatives as ``(content, mimetype)`` tuples in the
    ``alternatives`` attribute of :class:`~django.core.mail.EmailMultiAlternatives`.
    Plain :class:`~django.core.mail.EmailMessage` instances have no such
    attribute.
    """
    for content, mimetype in getattr(message, "alternatives", []):
        if mimetype == "text/html":
            return content
    return None
