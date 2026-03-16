"""Daleks entry point."""

from __future__ import annotations

import uvicorn

from .config import load_settings


def main() -> None:
    cfg = load_settings()
    uvicorn.run(
        "daleks.app:app",
        host="0.0.0.0",
        port=8000,
        log_level=cfg.log_level.lower(),
    )


if __name__ == "__main__":
    main()
