"""Flask-Security ``mail_util_cls`` integration for Daleks.

Drop-in replacement for the default :class:`flask_security.MailUtil` that
routes outgoing emails through the Daleks HTTP API instead of connecting
directly to an SMTP server.

Installation
------------
Install Daleks with the ``contrib`` extra so that ``requests`` is available::

    pip install "daleks[contrib]"

Flask configuration keys
------------------------
``DALEKS_URL`` (required)
    Base URL of the running Daleks server, e.g. ``http://localhost:8000``.

``DALEKS_TIMEOUT`` (optional, default: 10)
    HTTP request timeout in seconds.

``DALEKS_SMTP_ACCOUNT`` (optional)
    SMTP account name to target on the Daleks server.  Omit to let the server
    pick via round-robin.

Usage
-----
::

    from flask import Flask
    from flask_security import Security, SQLAlchemyUserDatastore
    from contrib.flask_security_mail import DaleksMailUtil

    app = Flask(__name__)
    app.config["DALEKS_URL"] = "http://localhost:8000"
    # app.config["DALEKS_TIMEOUT"] = 10
    # app.config["DALEKS_SMTP_ACCOUNT"] = "primary"

    security = Security(
        app,
        user_datastore,
        mail_util_cls=DaleksMailUtil,
    )
"""

from __future__ import annotations

import logging

from .client import DaleksClient

logger = logging.getLogger(__name__)


class DaleksMailUtil:
    """Flask-Security ``mail_util_cls`` that sends via the Daleks API.

    This class matches the interface expected by Flask-Security's
    ``mail_util_cls`` configuration option (the same interface as
    :class:`flask_security.MailUtil`).

    Parameters
    ----------
    app:
        The Flask application instance.  Used to read configuration values
        and retrieve the sender address from ``SECURITY_EMAIL_SENDER``.
    """

    def __init__(self, app: object) -> None:
        self.app = app

    # ── Flask-Security interface ───────────────────────────────────────────────

    def send_mail(
        self,
        template: str,
        subject: str,
        recipient: str,
        sender: str | tuple,
        body: str,
        html: str | None,
        **kwargs: object,
    ) -> None:
        """Send a Flask-Security email via the Daleks queue API.

        Parameters
        ----------
        template:
            The template name (provided by Flask-Security; not used here
            because the rendered *body* / *html* are already passed in).
        subject:
            Email subject line.
        recipient:
            Recipient email address.
        sender:
            Sender address — either a plain string or a ``(name, address)``
            tuple as produced by Flask-Security.
        body:
            Plain-text email body.
        html:
            HTML email body (may be ``None``).
        **kwargs:
            Extra keyword arguments forwarded by Flask-Security (ignored).
        """
        cfg = self.app.config  # type: ignore[union-attr]

        base_url: str = cfg.get("DALEKS_URL", "")
        if not base_url:
            raise RuntimeError(
                "DALEKS_URL is not set in the Flask application configuration. "
                "Set it to the base URL of your running Daleks server, "
                "e.g. app.config['DALEKS_URL'] = 'http://localhost:8000'."
            )

        timeout: int = int(cfg.get("DALEKS_TIMEOUT", 10))
        smtp_account: str | None = cfg.get("DALEKS_SMTP_ACCOUNT") or None

        from_address = _normalise_sender(sender)

        client = DaleksClient(
            base_url=base_url,
            timeout=timeout,
            smtp_account=smtp_account,
        )
        with client:
            client.send_email(
                from_address=from_address,
                to=recipient,
                subject=subject,
                text_body=body or None,
                html_body=html or None,
            )

        logger.debug(
            "Sent Flask-Security email %r to %s via Daleks (%s)",
            template,
            recipient,
            base_url,
        )


# ── Helpers ───────────────────────────────────────────────────────────────────


def _normalise_sender(sender: str | tuple) -> str:
    """Return a plain ``address`` string from a sender value.

    Flask-Security may pass either a plain string ``"noreply@example.com"``
    or a ``(display_name, address)`` tuple.  We keep only the address portion
    because the Daleks ``from_address`` field is a plain string.
    """
    if isinstance(sender, tuple):
        return sender[1]
    return sender
