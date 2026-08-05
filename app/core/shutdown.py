"""
Central Shutdown Coordinator

Provides a singleton ShutdownManager that serves as the single source of truth
for server lifecycle state. All entry points (uploads, downloads, WebSocket
upgrades, media streams, clipboard operations) gate on is_stopping() before
accepting new work.

Five-state lifecycle:
  STARTING → RUNNING → STOPPING → STOPPED
                        STOPPING → FAILED

Graceful shutdown is always attempted first. If cleanup hooks exceed the
configured timeout, os._exit(0) fires as an emergency fallback.
"""

import asyncio
import os
import sys
import time
import threading
from enum import Enum
from typing import Callable, Optional


class ShutdownState(Enum):
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    STOPPED = "stopped"
    FAILED = "failed"


class ShutdownManager:
    """
    Singleton coordinator for server shutdown lifecycle.

    Usage:
        from app.core.shutdown import shutdown_manager

        # Gate new work
        if shutdown_manager.is_stopping():
            return JSONResponse(status_code=503, ...)

        # Register cleanup
        shutdown_manager.register_cleanup("mDNS", mdns_manager.stop_service)

        # Begin shutdown
        await shutdown_manager.begin_shutdown()
    """

    _instance: Optional["ShutdownManager"] = None

    def __init__(self):
        self._state: ShutdownState = ShutdownState.STARTING
        self._cleanup_hooks: list[tuple[str, Callable]] = []
        self._completion_event = asyncio.Event()
        self._lock = threading.Lock()
        self._failure_reason: Optional[str] = None
        self._shutdown_timeout: float = 5.0  # seconds before emergency fallback

    # ── Singleton access ──────────────────────────────────────────────

    @classmethod
    def instance(cls) -> "ShutdownManager":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    # ── State management ──────────────────────────────────────────────

    @property
    def state(self) -> ShutdownState:
        return self._state

    def set_running(self) -> None:
        """Transition from STARTING → RUNNING after server is ready."""
        with self._lock:
            if self._state == ShutdownState.STARTING:
                self._state = ShutdownState.RUNNING

    def is_stopping(self) -> bool:
        """Returns True if the server is in STOPPING, STOPPED, or FAILED state."""
        return self._state in (
            ShutdownState.STOPPING,
            ShutdownState.STOPPED,
            ShutdownState.FAILED,
        )

    def is_running(self) -> bool:
        """Returns True if the server is accepting work."""
        return self._state == ShutdownState.RUNNING

    def mark_failed(self, reason: str) -> None:
        """
        Transition to FAILED state with a diagnostic reason.
        Only valid from STOPPING state.
        """
        with self._lock:
            if self._state == ShutdownState.STOPPING:
                self._state = ShutdownState.FAILED
                self._failure_reason = reason

    @property
    def failure_reason(self) -> Optional[str]:
        return self._failure_reason

    # ── Cleanup hook registration ─────────────────────────────────────

    def register_cleanup(self, name: str, hook: Callable) -> None:
        """
        Register a cleanup hook to execute during shutdown.

        Hooks execute in registration order. Each hook may be sync or async.
        """
        self._cleanup_hooks.append((name, hook))

    # ── Shutdown orchestration ────────────────────────────────────────

    async def begin_shutdown(self) -> None:
        """
        Initiate the shutdown sequence.

        1. Transition to STOPPING (rejects all new work)
        2. Execute all registered cleanup hooks in order
        3. If all hooks complete → STOPPED
        4. If any hook fails → FAILED
        5. If timeout exceeded → emergency os._exit(0)
        """
        with self._lock:
            if self._state != ShutdownState.RUNNING:
                return  # Already shutting down or not yet running
            self._state = ShutdownState.STOPPING

        try:
            await asyncio.wait_for(
                self._execute_cleanup_hooks(),
                timeout=self._shutdown_timeout,
            )
            with self._lock:
                if self._state == ShutdownState.STOPPING:
                    self._state = ShutdownState.STOPPED
        except asyncio.TimeoutError:
            # Cleanup exceeded timeout — emergency fallback
            print("[SHUTDOWN] Cleanup timeout exceeded — forcing emergency exit")
            os._exit(0)
        except Exception as exc:
            with self._lock:
                if self._state == ShutdownState.STOPPING:
                    self._state = ShutdownState.FAILED
                    self._failure_reason = str(exc)
            print(f"[SHUTDOWN] Cleanup failed: {exc}")
            # Still attempt emergency exit if cleanup was unrecoverable
            os._exit(1)

    async def _execute_cleanup_hooks(self) -> None:
        """Execute all registered cleanup hooks in registration order."""
        for name, hook in self._cleanup_hooks:
            try:
                result = hook()
                if asyncio.iscoroutine(result):
                    await result
                print(f"[SHUTDOWN] ✓ {name}")
            except Exception as exc:
                print(f"[SHUTDOWN] ✗ {name} failed: {exc}")
                raise  # Propagate to mark FAILED

    async def wait_until_complete(self, timeout: float = 5.0) -> bool:
        """
        Wait for shutdown to reach STOPPED or FAILED state.

        Returns True if shutdown completed, False on timeout.
        """
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self._state in (ShutdownState.STOPPED, ShutdownState.FAILED):
                return True
            await asyncio.sleep(0.1)
        return False


# Singleton instance
shutdown_manager = ShutdownManager.instance()