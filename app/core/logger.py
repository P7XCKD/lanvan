"""
Lanvan Structured & Privacy-Safe Logger Module
Provides high-performance, thread-safe logging with standardized categories,
safe metadata extraction, and in-memory ring buffer for diagnostic reporting.

Categories:
- SERVER, NETWORK, MDNS, UPLOAD, DOWNLOAD, STORAGE, CLIPBOARD, WEBSOCKET, SECURITY, DIAGNOSTIC, ANDROID

Levels:
- INFO, WARN, ERROR, DEBUG

PRIVACY INVARIANT:
Raw filenames, filesystem paths, directory listings, clipboard text, passwords, and user feedback
MUST NEVER reach log outputs or diagnostic buffers.
"""

import time
import datetime
import threading
from typing import List, Dict, Any, Optional

# Valid Categories
CATEGORIES = {
    "SERVER", "NETWORK", "MDNS", "UPLOAD", "DOWNLOAD",
    "STORAGE", "CLIPBOARD", "WEBSOCKET", "SECURITY", "DIAGNOSTIC", "ANDROID"
}

# Valid Levels
LEVELS = {"INFO", "WARN", "ERROR", "DEBUG"}

class StructuredLogger:
    """Thread-safe structured logger with diagnostic event ring buffer"""
    
    def __init__(self, max_history: int = 200):
        self._max_history = max_history
        self._history: List[Dict[str, Any]] = []
        self._lock = threading.Lock()

    def _format_timestamp(self) -> str:
        return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    @staticmethod
    def extract_safe_ext(filename: str) -> str:
        """Extract upper-case file extension without exposing filename"""
        if not filename or "." not in filename:
            return "BIN"
        ext = filename.rsplit(".", 1)[-1].strip().upper()
        # Sanitize extension string (max 10 alphanumeric chars)
        safe_ext = "".join(c for c in ext if c.isalnum())[:10]
        return safe_ext if safe_ext else "BIN"

    @staticmethod
    def format_size(size_bytes: int) -> str:
        """Format byte counts into human readable strings"""
        if size_bytes < 0:
            return "0 B"
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f} KB"
        elif size_bytes < 1024 * 1024 * 1024:
            return f"{size_bytes / (1024 * 1024):.2f} MB"
        else:
            return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"

    def log(
        self,
        category: str,
        level: str,
        message: str,
        op_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        """Record a structured log event"""
        cat = category.upper() if category.upper() in CATEGORIES else "SERVER"
        lvl = level.upper() if level.upper() in LEVELS else "INFO"
        timestamp = self._format_timestamp()
        
        # Build formatted header: YYYY-MM-DD HH:MM:SS [LEVEL] [CATEGORY][OP_ID]
        op_suffix = f"[{op_id}]" if op_id else ""
        header = f"{timestamp} [{lvl}] [{cat}]{op_suffix} {message}"
        
        # Append safe key-value details if provided
        detail_str = ""
        if details:
            kv_pairs = []
            for k, v in details.items():
                if v is not None:
                    kv_pairs.append(f"{k}: {v}")
            if kv_pairs:
                detail_str = " | " + " | ".join(kv_pairs)
        
        full_line = header + detail_str
        
        # Print to stdout/console safely
        print(full_line, flush=True)

        # Store in ring buffer for diagnostic report generation
        entry = {
            "timestamp": timestamp,
            "category": cat,
            "level": lvl,
            "message": message,
            "op_id": op_id,
            "details": details or {},
            "full_line": full_line
        }
        
        with self._lock:
            self._history.append(entry)
            if len(self._history) > self._max_history:
                self._history.pop(0)

    # Convenience Log Helpers
    def info(self, category: str, message: str, op_id: Optional[str] = None, details: Optional[Dict[str, Any]] = None):
        self.log(category, "INFO", message, op_id, details)

    def warn(self, category: str, message: str, op_id: Optional[str] = None, details: Optional[Dict[str, Any]] = None):
        self.log(category, "WARN", message, op_id, details)

    def error(self, category: str, message: str, op_id: Optional[str] = None, details: Optional[Dict[str, Any]] = None):
        self.log(category, "ERROR", message, op_id, details)

    def debug(self, category: str, message: str, op_id: Optional[str] = None, details: Optional[Dict[str, Any]] = None):
        self.log(category, "DEBUG", message, op_id, details)

    # Specialized Safe Handlers
    def log_upload(
        self,
        event: str,
        op_id: Optional[str] = None,
        file_ext: Optional[str] = None,
        size_bytes: Optional[int] = None,
        duration: Optional[float] = None,
        status: str = "SUCCESS",
        reason: Optional[str] = None,
        batch_info: Optional[Dict[str, Any]] = None
    ):
        """Log upload lifecycle safely without raw filenames or paths"""
        details = {}
        if batch_info:
            if "files" in batch_info:
                details["Files"] = batch_info["files"]
            if "total_size" in batch_info:
                details["Total size"] = self.format_size(batch_info["total_size"])
            if "succeeded" in batch_info:
                details["Succeeded"] = batch_info["succeeded"]
            if "failed" in batch_info:
                details["Failed"] = batch_info["failed"]

        if file_ext:
            details["Type"] = file_ext.upper()
        if size_bytes is not None:
            details["Size"] = self.format_size(size_bytes)
        if duration is not None:
            details["Duration"] = f"{duration:.2f}s"
        
        details["Status"] = status
        if reason:
            details["Reason"] = reason

        level = "ERROR" if status in ("FAILED", "ERROR") else "INFO"
        self.log("UPLOAD", level, event, op_id=op_id, details=details)

    def log_clipboard(
        self,
        action: str,
        item_type: str = "TEXT",
        size_bytes: Optional[int] = None,
        status: str = "SUCCESS",
        reason: Optional[str] = None
    ):
        """Log clipboard actions safely without ever logging clipboard values"""
        details = {
            "Type": item_type.upper(),
            "Size": f"{size_bytes} bytes" if size_bytes is not None else None,
            "Status": status
        }
        if reason:
            details["Reason"] = reason
        level = "ERROR" if status in ("FAILED", "ERROR") else "INFO"
        self.log("CLIPBOARD", level, action, details=details)

    def get_recent_history(self, count: int = 50) -> List[str]:
        """Return the recent activity formatted lines for diagnostic reports"""
        with self._lock:
            recent = self._history[-count:]
            return [item["full_line"] for item in recent]


# Global Logger Instance
logger = StructuredLogger()
