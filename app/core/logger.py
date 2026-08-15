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

import os
import time
import datetime
import threading
import logging
import warnings
import sys
from typing import List, Dict, Any, Optional

# Valid Categories
CATEGORIES = {
    "SERVER", "NETWORK", "MDNS", "UPLOAD", "DOWNLOAD",
    "STORAGE", "CLIPBOARD", "WEBSOCKET", "SECURITY", "DIAGNOSTIC", "ANDROID"
}

# Valid Levels
LEVELS = {"INFO", "WARN", "ERROR", "DEBUG"}

class QuietAccessFilter(logging.Filter):
    """
    Filter out access logs in production mode.
    In Android/production mode, completely suppresses individual HTTP/HTTPS request logs
    to protect user privacy (no URLs, parameters, filenames, or client IPs in access logs).
    In development mode, filters out static assets and polling noise.
    """
    NOISE_EXTENSIONS = ('.js', '.css', '.png', '.jpg', '.jpeg', '.gif', '.ico', '.svg', '.woff2', '.ttf', '.map', '.html')
    NOISE_ENDPOINTS = ('/api/clipboard/list', '/api/upload-history', '/favicon.ico', '/apple-touch-icon.png')

    def filter(self, record: logging.LogRecord) -> bool:
        # In production mode (or on Android), suppress all per-request access log lines
        is_prod = os.environ.get("LANVAN_ENV") == "production" or os.environ.get("PRODUCTION") == "true" or os.path.exists("/data/data/com.probz.lanvan")
        if is_prod:
            return False

        msg = record.getMessage()
        if "GET " in msg and (" 200" in msg or " 304" in msg):
            for ep in self.NOISE_ENDPOINTS:
                if ep in msg:
                    return False
            for ext in self.NOISE_EXTENSIONS:
                if f"{ext} " in msg or f"{ext}?" in msg or f"{ext} HTTP" in msg:
                    return False
        return True

class StructuredLogger:
    """Thread-safe structured logger with diagnostic event ring buffer"""
    
    def __init__(self, max_history: int = 200):
        self._max_history = max_history
        self._history: List[Dict[str, Any]] = []
        self._lock = threading.Lock()
        self._last_line: Optional[str] = None

    def _format_timestamp(self) -> str:
        return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    @staticmethod
    def extract_safe_ext(filename: str) -> str:
        """Extract upper-case file extension without exposing filename"""
        if not filename or "." not in filename:
            return "BIN"
        ext = filename.rsplit(".", 1)[-1].strip().upper()
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
        
        op_suffix = f"[{op_id}]" if op_id else ""
        header = f"{timestamp} [{lvl}] [{cat}]{op_suffix} {message}"
        
        detail_str = ""
        if details:
            kv_pairs = []
            for k, v in details.items():
                if v is not None:
                    kv_pairs.append(f"{k}: {v}")
            if kv_pairs:
                detail_str = " | " + " | ".join(kv_pairs)
        
        full_line = header + detail_str
        
        with self._lock:
            if self._last_line != full_line:
                print(full_line, flush=True)
                self._last_line = full_line

            entry = {
                "timestamp": timestamp,
                "category": cat,
                "level": lvl,
                "message": message,
                "op_id": op_id,
                "details": details or {},
                "full_line": full_line
            }
            self._history.append(entry)
            if len(self._history) > self._max_history:
                self._history.pop(0)

    def info(self, category: str, message: str, op_id: Optional[str] = None, details: Optional[Dict[str, Any]] = None):
        self.log(category, "INFO", message, op_id, details)

    def warn(self, category: str, message: str, op_id: Optional[str] = None, details: Optional[Dict[str, Any]] = None):
        self.log(category, "WARN", message, op_id, details)

    def error(self, category: str, message: str, op_id: Optional[str] = None, details: Optional[Dict[str, Any]] = None):
        self.log(category, "ERROR", message, op_id, details)

    def debug(self, category: str, message: str, op_id: Optional[str] = None, details: Optional[Dict[str, Any]] = None):
        self.log(category, "DEBUG", message, op_id, details)

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

# Apply Uvicorn Access Filter
uvicorn_access_logger = logging.getLogger("uvicorn.access")
uvicorn_access_logger.addFilter(QuietAccessFilter())

# Structured Warning Interceptor
_original_showwarning = warnings.showwarning

def _structured_warning_handler(message, category, filename, lineno, file=None, line=None):
    warning_str = str(message)
    category_name = category.__name__ if category else "Warning"
    
    if "python-multipart" in warning_str.lower():
        logger.warn("DIAGNOSTIC", "Dependency deprecation", details={"Component": "python-multipart"})
    elif "socket" in warning_str.lower() or "transport" in warning_str.lower() or "zeroconf" in warning_str.lower():
        logger.error("MDNS", "Resource cleanup incomplete", details={"Resource": "UDP transport"})
    else:
        logger.warn("DIAGNOSTIC", f"{category_name}: {warning_str}")

warnings.showwarning = _structured_warning_handler
