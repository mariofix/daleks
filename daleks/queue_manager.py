"""In-memory queue manager and background worker pool for Daleks.

Each configured SMTP account gets its own :class:`asyncio.Queue` and a pool
of worker coroutines.  Incoming email submissions are either routed to a
named account's queue or distributed round-robin across all accounts.

The :class:`QueueManager` is instantiated per application and stored in
``app.state.queue_manager`` so that multiple apps (e.g. in tests) can coexist
without sharing global state.
"""

from __future__ import annotations

import asyncio
import logging

from .config import Settings, SmtpAccount
from .models import EmailMessage

logger = logging.getLogger(__name__)


class QueueManager:
    """Owns the per-SMTP queues and the pool of delivery workers."""

    def __init__(self, cfg: Settings) -> None:
        self._cfg = cfg
        self.queues: dict[str, asyncio.Queue[EmailMessage]] = {}
        self._worker_tasks: list[asyncio.Task[None]] = []
        self._counter: int = 0

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    async def start(self) -> None:
        """Initialise queues and spawn worker tasks for every SMTP account."""
        self._counter = 0
        for account in self._cfg.smtp_accounts:
            max_size = self._cfg.queue_max_size if self._cfg.queue_max_size > 0 else 0
            self.queues[account.name] = asyncio.Queue(maxsize=max_size)
            for i in range(account.workers):
                task = asyncio.create_task(
                    self._worker(account, self.queues[account.name]),
                    name=f"daleks-worker-{account.name}-{i}",
                )
                self._worker_tasks.append(task)
            logger.info(
                "Started %d worker(s) for SMTP account %r",
                account.workers,
                account.name,
            )
        if not self._cfg.smtp_accounts:
            logger.warning("No SMTP accounts configured — emails cannot be sent")

    async def stop(self) -> None:
        """Cancel all worker tasks and clear internal state."""
        for task in self._worker_tasks:
            task.cancel()
        await asyncio.gather(*self._worker_tasks, return_exceptions=True)
        self._worker_tasks.clear()
        self.queues.clear()
        logger.info("All email workers stopped")

    # ── Public API ────────────────────────────────────────────────────────────

    def enqueue(self, email: EmailMessage, account_name: str | None = None) -> str:
        """Add *email* to the appropriate queue without blocking.

        Returns the name of the target SMTP account.

        Raises
        ------
        asyncio.QueueFull
            If the target queue has reached its maximum capacity.
        ValueError
            If *account_name* names an unknown SMTP account.
        RuntimeError
            If no SMTP accounts have been configured.
        """
        name, queue = self._pick_account(account_name)
        queue.put_nowait(email)
        logger.debug("Queued email for %s (qsize=%d)", name, queue.qsize())
        return name

    # ── Internals ─────────────────────────────────────────────────────────────

    def _pick_account(
        self, account_name: str | None
    ) -> tuple[str, asyncio.Queue[EmailMessage]]:
        if not self.queues:
            raise RuntimeError("No SMTP accounts are configured")
        if account_name is not None:
            if account_name not in self.queues:
                raise ValueError(f"Unknown SMTP account: {account_name!r}")
            return account_name, self.queues[account_name]
        names = list(self.queues)
        name = names[self._counter % len(names)]
        self._counter += 1
        return name, self.queues[name]

    @staticmethod
    async def _worker(
        account: SmtpAccount, queue: asyncio.Queue[EmailMessage]
    ) -> None:
        """Consume emails from *queue* and dispatch them via *account*."""
        from .smtp_client import send_email  # local import to avoid circular deps

        while True:
            email = await queue.get()
            try:
                await send_email(account, email)
            except Exception:
                logger.exception(
                    "Failed to send email via %s to %s",
                    account.name,
                    email.to,
                )
            finally:
                queue.task_done()
