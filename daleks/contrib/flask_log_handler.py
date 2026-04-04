"""Flask logging handler for Daleks.

Provides a :class:`logging.Handler` subclass that forwards every
``ERROR``-or-higher log record to the Daleks HTTP API as an email, plus a
convenience :func:`init_app` helper that wires everything up from standard
Flask configuration keys.

Installation
------------
Install Daleks with the ``contrib`` extra so that ``requests`` is available::

    pip install "daleks[contrib]"

Flask configuration keys
------------------------
``DALEKS_URL`` (required)
    Base URL of the running Daleks server, e.g. ``http://localhost:8000``.

``DALEKS_LOG_FROM`` (required)
    Sender address for error-notification emails.

``DALEKS_LOG_TO`` (required)
    Recipient address string **or** list of address strings.

``DALEKS_LOG_SUBJECT`` (optional, default: ``"[App] Error log"``)
    Subject line prefix for error-notification emails.

``DALEKS_TIMEOUT`` (optional, default: 10)
    HTTP request timeout in seconds.

``DALEKS_SMTP_ACCOUNT`` (optional)
    SMTP account name to target on the Daleks server.  Omit to let the
    server pick via round-robin.

``DALEKS_LOG_LEVEL`` (optional, default: ``"ERROR"``)
    Minimum log level that triggers an email.  Accepts any standard level
    name (``"WARNING"``, ``"ERROR"``, ``"CRITICAL"``, …).

Usage
-----
Using ``init_app`` (recommended for Flask apps)::

    from flask import Flask
    from daleks.contrib.flask_log_handler import init_app

    app = Flask(__name__)
    app.config["DALEKS_URL"]      = "http://localhost:8000"
    app.config["DALEKS_LOG_FROM"] = "errors@example.com"
    app.config["DALEKS_LOG_TO"]   = "ops@example.com"

    init_app(app)  # attaches DaleksLogHandler to app.logger

Instantiating the handler directly::

    import logging
    from daleks.contrib.flask_log_handler import DaleksLogHandler

    handler = DaleksLogHandler(
        daleks_url="http://localhost:8000",
        from_address="errors@example.com",
        to=["ops@example.com"],
    )
    logging.getLogger().addHandler(handler)
"""

from __future__ import annotations

import logging

from .client import DaleksClient

logger = logging.getLogger(__name__)


class DaleksLogHandler(logging.Handler):
    """Logging handler that sends each log record as an email via the Daleks API.

    Every :meth:`emit` call submits the formatted log record to the Daleks
    ``POST /api/v1/email`` endpoint using a :class:`~daleks.contrib.client.DaleksClient`.
    Network or API errors are swallowed via :meth:`logging.Handler.handleError`
    so that logging failures never break the application.

    Parameters
    ----------
    daleks_url:
        Base URL of the running Daleks server, e.g. ``http://localhost:8000``.
    from_address:
        Sender address for error-notification emails.
    to:
        Recipient address string or list of address strings.
    subject:
        Email subject line.
    smtp_account:
        SMTP account name to target on the Daleks server.  Omit to let the
        server pick via round-robin.
    timeout:
        HTTP request timeout in seconds (default: 10).
    level:
        Minimum log level (default: :data:`logging.ERROR`).
    """

    def __init__(
        self,
        daleks_url: str,
        from_address: str,
        to: str | list[str],
        subject: str = "[App] Error log",
        smtp_account: str | None = None,
        timeout: int = 10,
        level: int = logging.ERROR,
    ) -> None:
        super().__init__(level=level)
        self.from_address = from_address
        self.to = [to] if isinstance(to, str) else list(to)
        self.subject = subject
        self._client = DaleksClient(
            base_url=daleks_url,
            timeout=timeout,
            smtp_account=smtp_account,
        )

    # ── logging.Handler interface ─────────────────────────────────────────────

    def emit(self, record: logging.LogRecord) -> None:
        """Format *record* and deliver it as an email via Daleks.

        Any exception raised during formatting or delivery is handled by
        :meth:`~logging.Handler.handleError` (writes to ``sys.stderr``) so
        that logging never crashes the application.
        """
        try:
            text = self.format(record)
            self._client.send_email(
                from_address=self.from_address,
                to=self.to,
                subject=self.subject,
                text_body=text,
            )
        except Exception:
            self.handleError(record)

    def close(self) -> None:
        """Close the underlying HTTP session and deactivate the handler."""
        try:
            self._client.close()
        finally:
            super().close()


# ── Flask helper ──────────────────────────────────────────────────────────────


def init_app(app: object, app_logger: logging.Logger | None = None) -> DaleksLogHandler:
    """Attach a :class:`DaleksLogHandler` to a Flask application's logger.

    Reads all configuration from the Flask application's ``config`` dict
    (see module-level documentation for the full list of keys).  The handler
    is attached to *app_logger* when provided, otherwise to ``app.logger``.

    Parameters
    ----------
    app:
        Flask application instance.
    app_logger:
        Logger to attach the handler to.  Defaults to ``app.logger``.

    Returns
    -------
    DaleksLogHandler
        The newly created and attached handler (useful for later removal or
        reconfiguration).

    Raises
    ------
    RuntimeError
        If ``DALEKS_URL``, ``DALEKS_LOG_FROM``, or ``DALEKS_LOG_TO`` are
        missing from the Flask configuration.
    """
    cfg = app.config  # type: ignore[union-attr]

    base_url: str = cfg.get("DALEKS_URL", "")
    if not base_url:
        raise RuntimeError(
            "DALEKS_URL is not set in the Flask application configuration. "
            "Set it to the base URL of your running Daleks server, "
            "e.g. app.config['DALEKS_URL'] = 'http://localhost:8000'."
        )

    from_address: str = cfg.get("DALEKS_LOG_FROM", "")
    if not from_address:
        raise RuntimeError(
            "DALEKS_LOG_FROM is not set in the Flask application configuration. "
            "Set it to the sender address for error-notification emails, "
            "e.g. app.config['DALEKS_LOG_FROM'] = 'errors@example.com'."
        )

    to_cfg = cfg.get("DALEKS_LOG_TO")
    if not to_cfg:
        raise RuntimeError(
            "DALEKS_LOG_TO is not set in the Flask application configuration. "
            "Set it to the recipient address (or list of addresses) for "
            "error-notification emails, "
            "e.g. app.config['DALEKS_LOG_TO'] = 'ops@example.com'."
        )

    subject: str = cfg.get("DALEKS_LOG_SUBJECT", "[App] Error log")
    timeout: int = int(cfg.get("DALEKS_TIMEOUT", 10))
    smtp_account: str | None = cfg.get("DALEKS_SMTP_ACCOUNT") or None
    level_name: str = str(cfg.get("DALEKS_LOG_LEVEL", "ERROR")).upper()
    level: int = getattr(logging, level_name, logging.ERROR)

    handler = DaleksLogHandler(
        daleks_url=base_url,
        from_address=from_address,
        to=to_cfg,
        subject=subject,
        smtp_account=smtp_account,
        timeout=timeout,
        level=level,
    )

    target_logger: logging.Logger = app_logger or app.logger  # type: ignore[union-attr]
    target_logger.addHandler(handler)

    logger.debug(
        "DaleksLogHandler attached to %r (level=%s, to=%s) via %s",
        target_logger.name,
        level_name,
        to_cfg,
        base_url,
    )

    return handler
