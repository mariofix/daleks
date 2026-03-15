"""Tests for configuration loading."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from daleks.config import Settings, SmtpAccount, load_settings


def test_default_settings():
    cfg = Settings()
    assert cfg.allowed_networks == ["127.0.0.1/32", "::1/128"]
    assert cfg.queue_max_size == 1000
    assert cfg.smtp_accounts == []
    assert cfg.log_level == "INFO"


def test_load_settings_from_toml(tmp_path: Path):
    config_file = tmp_path / "config.toml"
    config_file.write_text(
        textwrap.dedent("""\
            allowed_networks = ["192.168.1.0/24"]
            queue_max_size = 500
            log_level = "DEBUG"

            [[smtp_accounts]]
            name = "relay"
            host = "mail.example.com"
            port = 587
            username = "user"
            password = "pass"
            use_tls = true
            use_ssl = false
            workers = 2
        """)
    )
    cfg = load_settings(str(config_file))
    assert cfg.allowed_networks == ["192.168.1.0/24"]
    assert cfg.queue_max_size == 500
    assert len(cfg.smtp_accounts) == 1
    account = cfg.smtp_accounts[0]
    assert account.name == "relay"
    assert account.host == "mail.example.com"
    assert account.workers == 2


def test_load_settings_missing_file(tmp_path: Path):
    cfg = load_settings(str(tmp_path / "nonexistent.toml"))
    assert cfg == Settings()


def test_smtp_account_tls_ssl_exclusive():
    with pytest.raises(Exception, match="mutually exclusive"):
        SmtpAccount(
            name="bad",
            host="smtp.example.com",
            use_tls=True,
            use_ssl=True,
        )


def test_smtp_account_defaults():
    account = SmtpAccount(name="test", host="smtp.example.com")
    assert account.port == 587
    assert account.use_tls is True
    assert account.use_ssl is False
    assert account.workers == 2
    assert account.timeout == 30
