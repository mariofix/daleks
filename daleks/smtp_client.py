"""Async SMTP client for Daleks.

Builds a :class:`email.message.EmailMessage` from a
:class:`~daleks.models.EmailMessage` payload and dispatches it via
``aiosmtplib``.
"""

from __future__ import annotations

import logging
from email.message import EmailMessage as StdEmailMessage

import aiosmtplib

from .config import SmtpAccount
from .models import EmailMessage

logger = logging.getLogger(__name__)


def _build_message(email: EmailMessage) -> StdEmailMessage:
    """Construct a stdlib :class:`email.message.EmailMessage`."""
    msg = StdEmailMessage()
    msg["Subject"] = email.subject
    msg["From"] = email.from_address
    msg["To"] = ", ".join(email.to)
    if email.cc:
        msg["Cc"] = ", ".join(email.cc)
    if email.reply_to:
        msg["Reply-To"] = email.reply_to

    if email.html_body and email.text_body:
        msg.set_content(email.text_body)
        msg.add_alternative(email.html_body, subtype="html")
    elif email.html_body:
        msg.set_content(email.html_body, subtype="html")
    else:
        msg.set_content(email.text_body or "")

    return msg


async def send_email(account: SmtpAccount, email: EmailMessage) -> None:
    """Send *email* via *account*.

    All connection setup and teardown is handled by ``aiosmtplib.send``.
    """
    msg = _build_message(email)
    recipients = email.to + (email.cc or [])
    await aiosmtplib.send(
        msg,
        sender=email.from_address,
        recipients=recipients,
        hostname=account.host,
        port=account.port,
        username=account.username or None,
        password=account.password or None,
        use_tls=account.use_ssl,
        start_tls=account.use_tls,
        timeout=account.timeout,
    )
    logger.info(
        "Email sent via %s to %s subject=%r",
        account.name,
        email.to,
        email.subject,
    )
