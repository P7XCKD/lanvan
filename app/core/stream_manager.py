"""
Lanvan Stream Manager Module
============================
Provides deterministic event-driven tracking and graceful cancellation of active
media stream sessions (HTTP 206 Range and full download streams).

Guarantees that filesystem operations (rename, move, delete) complete cleanly
without 409 Conflict or Windows WinError 32 file handle locks.
"""

import os
import sys
import uuid
import time
import asyncio
import threading
from typing import List, Dict, Set, Optional, Any
from dataclasses import dataclass
from pathlib import Path


@dataclass
class StreamSession:
    """Represents an active media streaming session."""
    session_id: str
    path: Path
    client_ip: str
    cancel_event: asyncio.Event
    finished_event: asyncio.Event
    created_at: float
    file_handle: Optional[Any] = None

    def close_file_handle(self):
        """Force-close the underlying OS file handle to release Windows locks immediately."""
        if self.file_handle:
            try:
                self.file_handle.close()
                print(f"[STREAM_MANAGER] Explicitly closed file handle for session {self.session_id}")
            except Exception as e:
                print(f"[STREAM_MANAGER] Exception closing file handle for {self.session_id}: {e}")


class StreamManager:
    """
    Authoritative repository for active media streaming sessions.
    Thread-safe and async-native.
    """

    def __init__(self):
        self._sessions: Dict[str, StreamSession] = {}
        self._lock = threading.Lock()

    def _canonical_path_str(self, path: Path) -> str:
        try:
            return str(path.resolve()).lower()
        except Exception:
            return str(path).lower()

    def register_stream(self, file_path: Path, client_ip: str = "unknown") -> StreamSession:
        """Register a new active stream session for a file."""
        session_id = uuid.uuid4().hex[:12]
        loop = None
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        cancel_evt = asyncio.Event() if loop else None
        finished_evt = asyncio.Event() if loop else None

        session = StreamSession(
            session_id=session_id,
            path=file_path,
            client_ip=client_ip,
            cancel_event=cancel_evt or asyncio.Event(),
            finished_event=finished_evt or asyncio.Event(),
            created_at=time.time()
        )

        with self._lock:
            self._sessions[session_id] = session

        print(f"[STREAM_MANAGER] Registered stream {session_id} for '{file_path.name}' (IP: {client_ip})")
        return session

    def unregister_stream(self, session: StreamSession):
        """Unregister an active stream session when streaming completes or cancels."""
        with self._lock:
            if session.session_id in self._sessions:
                del self._sessions[session.session_id]

        # Set finished_event to notify any awaiting file operation
        if session.finished_event:
            try:
                session.finished_event.set()
            except Exception:
                pass

        print(f"[STREAM_MANAGER] Unregistered stream {session.session_id} for '{session.path.name}'")

    def get_active_sessions_for_path(self, target_path: Path) -> List[StreamSession]:
        """
        Find all active stream sessions matching target_path (exact file, .enc variants, or inside a folder).
        """
        target_canonical = self._canonical_path_str(target_path)
        variants = {
            target_canonical,
            target_canonical + ".enc",
            target_canonical + ".enc.meta",
        }
        if target_canonical.endswith(".enc"):
            variants.add(target_canonical[:-4])
            variants.add(target_canonical + ".meta")
        elif target_canonical.endswith(".enc.meta"):
            variants.add(target_canonical[:-9])
            variants.add(target_canonical[:-5])

        matched: List[StreamSession] = []

        with self._lock:
            for session in self._sessions.values():
                sess_canonical = self._canonical_path_str(session.path)
                if sess_canonical in variants:
                    matched.append(session)
                    continue
                for var in list(variants):
                    if sess_canonical.startswith(var + os.sep) or sess_canonical.startswith(var + "/"):
                        matched.append(session)
                        break

        return matched

    async def cancel_and_await_cleanup(self, target_path: Path, timeout: float = 3.0) -> int:
        """
        Signal cancellation to all active streams for target_path, close file handles, and await finished_event.
        Returns the number of canceled stream sessions.
        """
        matched = self.get_active_sessions_for_path(target_path)
        if not matched:
            return 0

        print(f"[STREAM_MANAGER] Canceling {len(matched)} active stream session(s) for '{target_path.name}'...")

        finished_waiters = []
        for session in matched:
            # 1. Signal cancellation event
            if session.cancel_event:
                session.cancel_event.set()
            
            # 2. Force-close OS file handle immediately to release WinError 32 lock
            session.close_file_handle()

            # 3. Collect waiter
            if session.finished_event:
                finished_waiters.append(session.finished_event.wait())

        # 4. Deterministically await all finished_events with timeout
        if finished_waiters:
            try:
                await asyncio.wait_for(
                    asyncio.gather(*finished_waiters, return_exceptions=True),
                    timeout=timeout
                )
                print(f"[STREAM_MANAGER] All {len(matched)} stream session(s) finalized cleanup successfully.")
            except asyncio.TimeoutError:
                print(f"[STREAM_MANAGER] Timed out waiting for stream cleanup after {timeout}s")

        return len(matched)


# Global singleton instance
_stream_manager_instance: Optional[StreamManager] = None
_stream_manager_lock = threading.Lock()


def get_stream_manager() -> StreamManager:
    """Get global StreamManager singleton instance."""
    global _stream_manager_instance
    if _stream_manager_instance is None:
        with _stream_manager_lock:
            if _stream_manager_instance is None:
                _stream_manager_instance = StreamManager()
    return _stream_manager_instance
