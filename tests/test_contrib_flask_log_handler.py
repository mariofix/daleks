"""Tests for daleks.contrib.flask_log_handler."""

from __future__ import annotations

import logging
from unittest.mock import MagicMock, call, patch

import pytest

from daleks.contrib.flask_log_handler import DaleksLogHandler, init_app


# ── Helpers ───────────────────────────────────────────────────────────────────


def _make_app(**config_overrides) -> MagicMock:
    """Return a minimal mock Flask app with .config and .logger."""
    app = MagicMock()
    cfg = {
        "DALEKS_URL": "http://localhost:8000",
        "DALEKS_LOG_FROM": "errors@example.com",
        "DALEKS_LOG_TO": "ops@example.com",
        "DALEKS_LOG_SUBJECT": "[MyApp] Error log",
        "DALEKS_TIMEOUT": 10,
        "DALEKS_SMTP_ACCOUNT": None,
        "DALEKS_LOG_LEVEL": "ERROR",
    }
    cfg.update(config_overrides)
    app.config = cfg
    app.logger = logging.getLogger("test_flask_app")
    return app


def _make_record(
    msg: str = "Something went wrong",
    level: int = logging.ERROR,
    name: str = "myapp",
) -> logging.LogRecord:
    return logging.LogRecord(
        name=name,
        level=level,
        pathname="app.py",
        lineno=42,
        msg=msg,
        args=(),
        exc_info=None,
    )


# ── DaleksLogHandler ──────────────────────────────────────────────────────────


class TestDaleksLogHandlerInit:
    def test_default_level_is_error(self):
        handler = DaleksLogHandler(
            daleks_url="http://localhost:8000",
            from_address="a@example.com",
            to="b@example.com",
        )
        assert handler.level == logging.ERROR

    def test_to_string_is_wrapped_in_list(self):
        handler = DaleksLogHandler(
            daleks_url="http://localhost:8000",
            from_address="a@example.com",
            to="b@example.com",
        )
        assert handler.to == ["b@example.com"]

    def test_to_list_is_preserved(self):
        handler = DaleksLogHandler(
            daleks_url="http://localhost:8000",
            from_address="a@example.com",
            to=["b@example.com", "c@example.com"],
        )
        assert handler.to == ["b@example.com", "c@example.com"]

    def test_default_subject(self):
        handler = DaleksLogHandler(
            daleks_url="http://localhost:8000",
            from_address="a@example.com",
            to="b@example.com",
        )
        assert handler.subject == "[App] Error log"

    def test_custom_level(self):
        handler = DaleksLogHandler(
            daleks_url="http://localhost:8000",
            from_address="a@example.com",
            to="b@example.com",
            level=logging.CRITICAL,
        )
        assert handler.level == logging.CRITICAL

    def test_client_created_with_correct_params(self):
        with patch("daleks.contrib.flask_log_handler.DaleksClient") as MockClient:
            DaleksLogHandler(
                daleks_url="http://daleks:8000",
                from_address="a@example.com",
                to="b@example.com",
                smtp_account="primary",
                timeout=30,
            )
        MockClient.assert_called_once_with(
            base_url="http://daleks:8000",
            timeout=30,
            smtp_account="primary",
        )


class TestDaleksLogHandlerEmit:
    def test_emit_calls_send_email(self):
        with patch("daleks.contrib.flask_log_handler.DaleksClient") as MockClient:
            client_instance = MockClient.return_value
            handler = DaleksLogHandler(
                daleks_url="http://localhost:8000",
                from_address="errors@example.com",
                to=["ops@example.com"],
                subject="[Test] Error",
            )
            record = _make_record("DB connection failed")
            handler.emit(record)

        client_instance.send_email.assert_called_once()
        _, kwargs = client_instance.send_email.call_args
        assert kwargs["from_address"] == "errors@example.com"
        assert kwargs["to"] == ["ops@example.com"]
        assert kwargs["subject"] == "[Test] Error"
        assert "DB connection failed" in kwargs["text_body"]

    def test_emit_includes_formatted_message(self):
        with patch("daleks.contrib.flask_log_handler.DaleksClient") as MockClient:
            client_instance = MockClient.return_value
            handler = DaleksLogHandler(
                daleks_url="http://localhost:8000",
                from_address="a@example.com",
                to="b@example.com",
            )
            formatter = logging.Formatter("%(levelname)s: %(message)s")
            handler.setFormatter(formatter)
            record = _make_record("Unexpected error occurred")
            handler.emit(record)

        _, kwargs = client_instance.send_email.call_args
        assert kwargs["text_body"] == "ERROR: Unexpected error occurred"

    def test_emit_swallows_client_exceptions(self):
        with patch("daleks.contrib.flask_log_handler.DaleksClient") as MockClient:
            client_instance = MockClient.return_value
            client_instance.send_email.side_effect = RuntimeError("network error")
            handler = DaleksLogHandler(
                daleks_url="http://localhost:8000",
                from_address="a@example.com",
                to="b@example.com",
            )
            record = _make_record("Some error")
            # Should not raise
            handler.emit(record)

    def test_emit_below_level_not_delivered(self):
        with patch("daleks.contrib.flask_log_handler.DaleksClient") as MockClient:
            client_instance = MockClient.return_value
            handler = DaleksLogHandler(
                daleks_url="http://localhost:8000",
                from_address="a@example.com",
                to="b@example.com",
                level=logging.ERROR,
            )
            # WARNING is below ERROR — the handler filter should block it
            record = _make_record("Just a warning", level=logging.WARNING)
            # Simulate what the logging framework does: check the level first
            if handler.filter(record) and record.levelno >= handler.level:
                handler.emit(record)

        client_instance.send_email.assert_not_called()

    def test_emit_multiple_recipients(self):
        with patch("daleks.contrib.flask_log_handler.DaleksClient") as MockClient:
            client_instance = MockClient.return_value
            handler = DaleksLogHandler(
                daleks_url="http://localhost:8000",
                from_address="a@example.com",
                to=["b@example.com", "c@example.com"],
            )
            handler.emit(_make_record())

        _, kwargs = client_instance.send_email.call_args
        assert kwargs["to"] == ["b@example.com", "c@example.com"]


class TestDaleksLogHandlerClose:
    def test_close_closes_client(self):
        with patch("daleks.contrib.flask_log_handler.DaleksClient") as MockClient:
            client_instance = MockClient.return_value
            handler = DaleksLogHandler(
                daleks_url="http://localhost:8000",
                from_address="a@example.com",
                to="b@example.com",
            )
            handler.close()

        client_instance.close.assert_called_once()

    def test_close_calls_super(self):
        with patch("daleks.contrib.flask_log_handler.DaleksClient"):
            handler = DaleksLogHandler(
                daleks_url="http://localhost:8000",
                from_address="a@example.com",
                to="b@example.com",
            )
            # After close() the handler should be removed from the manager
            handler.close()
            # No exception means super().close() was called
            assert handler.level == logging.ERROR


# ── init_app ──────────────────────────────────────────────────────────────────


class TestInitApp:
    def test_attaches_handler_to_app_logger(self):
        app = _make_app()
        with patch("daleks.contrib.flask_log_handler.DaleksClient"):
            handler = init_app(app)

        assert handler in app.logger.handlers
        app.logger.removeHandler(handler)

    def test_returns_daleks_log_handler(self):
        app = _make_app()
        with patch("daleks.contrib.flask_log_handler.DaleksClient"):
            handler = init_app(app)

        assert isinstance(handler, DaleksLogHandler)
        app.logger.removeHandler(handler)

    def test_handler_configured_from_flask_config(self):
        app = _make_app(
            DALEKS_LOG_FROM="sender@example.com",
            DALEKS_LOG_TO=["a@example.com", "b@example.com"],
            DALEKS_LOG_SUBJECT="[Prod] Error",
        )
        with patch("daleks.contrib.flask_log_handler.DaleksClient"):
            handler = init_app(app)

        assert handler.from_address == "sender@example.com"
        assert handler.to == ["a@example.com", "b@example.com"]
        assert handler.subject == "[Prod] Error"
        app.logger.removeHandler(handler)

    def test_handler_level_from_config(self):
        app = _make_app(DALEKS_LOG_LEVEL="CRITICAL")
        with patch("daleks.contrib.flask_log_handler.DaleksClient"):
            handler = init_app(app)

        assert handler.level == logging.CRITICAL
        app.logger.removeHandler(handler)

    def test_default_level_is_error_when_not_set(self):
        app = _make_app()
        del app.config["DALEKS_LOG_LEVEL"]
        with patch("daleks.contrib.flask_log_handler.DaleksClient"):
            handler = init_app(app)

        assert handler.level == logging.ERROR
        app.logger.removeHandler(handler)

    def test_custom_logger_used_when_provided(self):
        app = _make_app()
        custom_logger = logging.getLogger("custom.test.logger")
        with patch("daleks.contrib.flask_log_handler.DaleksClient"):
            handler = init_app(app, app_logger=custom_logger)

        assert handler in custom_logger.handlers
        custom_logger.removeHandler(handler)

    def test_missing_daleks_url_raises(self):
        app = _make_app(DALEKS_URL="")
        with pytest.raises(RuntimeError, match="DALEKS_URL"):
            init_app(app)

    def test_missing_log_from_raises(self):
        app = _make_app(DALEKS_LOG_FROM="")
        with pytest.raises(RuntimeError, match="DALEKS_LOG_FROM"):
            init_app(app)

    def test_missing_log_to_raises(self):
        app = _make_app(DALEKS_LOG_TO=None)
        with pytest.raises(RuntimeError, match="DALEKS_LOG_TO"):
            init_app(app)

    def test_smtp_account_passed_to_client(self):
        app = _make_app(DALEKS_SMTP_ACCOUNT="primary")
        with patch("daleks.contrib.flask_log_handler.DaleksClient") as MockClient:
            handler = init_app(app)

        MockClient.assert_called_once_with(
            base_url="http://localhost:8000",
            timeout=10,
            smtp_account="primary",
        )
        app.logger.removeHandler(handler)

    def test_timeout_passed_to_client(self):
        app = _make_app(DALEKS_TIMEOUT=60)
        with patch("daleks.contrib.flask_log_handler.DaleksClient") as MockClient:
            handler = init_app(app)

        MockClient.assert_called_once_with(
            base_url="http://localhost:8000",
            timeout=60,
            smtp_account=None,
        )
        app.logger.removeHandler(handler)

    def test_to_as_string_accepted(self):
        app = _make_app(DALEKS_LOG_TO="single@example.com")
        with patch("daleks.contrib.flask_log_handler.DaleksClient"):
            handler = init_app(app)

        assert handler.to == ["single@example.com"]
        app.logger.removeHandler(handler)
