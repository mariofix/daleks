"""Configuration loading for Daleks.

Settings are read from a TOML file whose path is determined by, in order:
1. The ``DALEKS_CONFIG`` environment variable.
2. A ``config.toml`` file in the current working directory.
3. Built-in defaults (no SMTP accounts, loopback-only network).
"""

from __future__ import annotations

import logging
import os
import tomllib
from pathlib import Path

from pydantic import BaseModel, model_validator

logger = logging.getLogger(__name__)


class SmtpAccount(BaseModel):
    """A single outbound SMTP relay."""

    name: str
    host: str
    port: int = 587
    username: str = ""
    password: str = ""
    use_tls: bool = True
    use_ssl: bool = False
    timeout: int = 30
    workers: int = 2

    @model_validator(mode="after")
    def _validate_tls_ssl(self) -> "SmtpAccount":
        if self.use_tls and self.use_ssl:
            raise ValueError(
                f"SMTP account '{self.name}': use_tls and use_ssl are mutually exclusive"
            )
        return self


class Settings(BaseModel):
    """Application-wide settings."""

    allowed_networks: list[str] = ["127.0.0.1/32", "::1/128"]
    queue_max_size: int = 1000
    smtp_accounts: list[SmtpAccount] = []
    log_level: str = "INFO"


def load_settings(config_path: str | None = None) -> Settings:
    """Load and validate settings from a TOML file.

    Parameters
    ----------
    config_path:
        Explicit path to a TOML config file.  Falls back to the
        ``DALEKS_CONFIG`` environment variable and then ``config.toml``.
    """
    path = Path(config_path or os.environ.get("DALEKS_CONFIG", "config.toml"))
    if path.exists():
        with open(path, "rb") as fh:
            data = tomllib.load(fh)
        logger.debug("Loaded config from %s", path)
        return Settings(**data)
    logger.debug("No config file found at %s; using defaults", path)
    return Settings()


# Module-level singleton — overridable in tests via ``daleks.config.settings``.
settings: Settings = load_settings()
