"""Pydantic models for the Daleks API."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, field_validator, model_validator


class EmailMessage(BaseModel):
    """Inbound email submission payload."""

    from_address: str
    to: list[str]
    subject: str
    text_body: str | None = None
    html_body: str | None = None
    cc: list[str] | None = None
    reply_to: str | None = None
    # Optional: target a specific configured SMTP account by name.
    smtp_account: str | None = None
    # Importance / priority hint for the receiving MUA.
    importance: Literal["low", "normal", "high"] = "normal"

    @field_validator("to", mode="before")
    @classmethod
    def _coerce_to_list(cls, v: object) -> list[str]:
        if isinstance(v, str):
            return [v]
        return v  # type: ignore[return-value]

    @model_validator(mode="after")
    def _require_body(self) -> "EmailMessage":
        if not self.text_body and not self.html_body:
            raise ValueError("At least one of text_body or html_body must be provided")
        return self


class EmailResponse(BaseModel):
    """Response returned after a successful submission."""

    queued: bool = True
    smtp_account: str
    message: str = "Email queued for delivery"


class HealthResponse(BaseModel):
    """Health-check response."""

    status: str
    queues: dict[str, int]
