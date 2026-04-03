"""FastAPI application factory for Daleks."""

from __future__ import annotations

import asyncio
import logging
import logging.handlers
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI, HTTPException, Request, status

from . import __version__
from .config import Settings, load_settings
from .middleware import IPRestrictionMiddleware
from .models import EmailMessage, EmailResponse, HealthResponse
from .queue_manager import QueueManager


def create_app(cfg: Settings | None = None) -> FastAPI:
    """Create and return the configured :class:`~fastapi.FastAPI` instance.

    Parameters
    ----------
    cfg:
        Optional :class:`~daleks.config.Settings` override — useful in tests.
        Defaults to the module-level singleton loaded from disk.
    """
    if cfg is None:
        cfg = load_settings()

    logging.basicConfig(
        level=cfg.log_level.upper(),
        format="%(asctime)s %(levelname)-8s %(name)s %(message)s",
    )

    if cfg.error_notify is not None:
        en = cfg.error_notify
        credentials = (en.username, en.password) if en.username else None
        secure = () if en.use_tls else None
        smtp_handler = logging.handlers.SMTPHandler(
            mailhost=(en.host, en.port),
            fromaddr=en.from_address,
            toaddrs=en.to,
            subject=en.subject,
            credentials=credentials,
            secure=secure,
        )
        smtp_handler.setLevel(logging.ERROR)
        logging.getLogger().addHandler(smtp_handler)

    queue_manager = QueueManager(cfg)

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        await queue_manager.start()
        try:
            yield
        finally:
            await queue_manager.stop()

    app = FastAPI(
        title="Daleks",
        description="Private mailer — exterminate your email queues.",
        version=__version__,
        lifespan=lifespan,
        # Disable the auto-generated docs in production if desired.
        # docs_url=None,
        # redoc_url=None,
    )

    # Store the queue manager on app state so routes can access it.
    app.state.queue_manager = queue_manager

    app.add_middleware(IPRestrictionMiddleware, cfg=cfg)

    # ── Routes ────────────────────────────────────────────────────────────────

    @app.post(
        "/api/v1/email",
        response_model=EmailResponse,
        status_code=status.HTTP_202_ACCEPTED,
        summary="Submit an email for delivery",
    )
    async def submit_email(request: Request, email: EmailMessage) -> EmailResponse:
        """Accept an email payload, place it in the outbound queue and return
        immediately — actual delivery happens in the background."""
        qm: QueueManager = request.app.state.queue_manager
        try:
            account_name = qm.enqueue(email, email.smtp_account)
        except asyncio.QueueFull:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Queue is full — try again later",
            )
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
        except RuntimeError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
            )
        return EmailResponse(smtp_account=account_name)

    @app.get(
        "/health",
        response_model=HealthResponse,
        summary="Health check and queue depth",
    )
    async def health(request: Request) -> HealthResponse:
        """Return service status and the current depth of every outbound queue."""
        qm: QueueManager = request.app.state.queue_manager
        return HealthResponse(
            status="ok",
            queues={name: q.qsize() for name, q in qm.queues.items()},
        )

    return app


# Module-level app instance used by ``uvicorn daleks.app:app`` and the
# ``daleks`` CLI entry-point.
app = create_app()
