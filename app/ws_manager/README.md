# Lanvan WebSocket Manager Layer Developer Documentation

Welcome to the `app/ws_manager` folder! This directory hosts the WebSocket controllers and managers responsible for handling real-time, low-latency client-server synchronization across devices.

---

## Directory Map & Module Responsibilities

```
app/ws_manager/
  ├── __init__.py         # Exports connection managers and routers
  ├── clipboard.py        # Real-time clipboard synchronization websocket endpoint & manager
  └── upload_status.py    # Multi-client/session upload progress tracking websocket endpoint & manager
```

---

## Module Specifications

### 1. Clipboard Syncer (`clipboard.py`)
Facilitates seamless, instant text and data exchange between devices.

#### Key Classes & Methods
* **`ClipboardConnectionManager`**:
  * **`_start_cleanup_task()`**: Starts the background task loop to clean up expired/stale sockets.
  * **`_background_cleanup()`**: Async loop that triggers stale connection cleanups at configured intervals.
  * **`connect(websocket: WebSocket) -> str`**: Establishes connections, tracks activity states, limits connection counts to prevent DoS, and returns a unique hexadecimal ID identifying the socket.
  * **`disconnect(websocket: Optional[WebSocket], connection_id: Optional[str])`**: Helper that maps closures to `force_disconnect`.
  * **`force_disconnect(connection_id: str)`**: Closes the socket frame gracefully (or falls back to force-close if graceful fails) and deletes all active registries.
  * **`cleanup_stale_connections()`**: Scans for connections exceeding the timeout threshold and identifies orphaned weak references.
  * **`update_activity(connection_id: str)`**: Refreshes last-activity timestamps and extends timeouts.
  * **`broadcast(message: str)`**: Dispatches payload data to all active connections in parallel, automatically pruning non-responsive connections.
  * **`get_stats() -> Dict`**: Gathers metrics on total connections, active memory references, and session ages.
  * **`shutdown()`**: Lifespan hooks execution to close connections and cancel loop routines.

#### WebSocket Router Entry Points
* **`GET /ws/clipboard`**: Websocket endpoint mapping client connections directly to the `ClipboardConnectionManager` workflow.

---

### 2. Upload Progress Tracker (`upload_status.py`)
Keeps clients informed of multi-part upload states and chunk merger actions.

#### Key Classes & Methods
* **`UploadStatusConnectionManager`**:
  * **`_start_cleanup_task()`**: Initializes the progress monitoring loop.
  * **`_background_cleanup()`**: Periodically cleans up completed upload registries and stale tracking sockets.
  * **`connect(websocket: WebSocket, upload_id: Optional[str] = None) -> str`**: Registers connection sockets, optionally subscribing them to a target upload tracker session.
  * **`subscribe_to_upload(connection_id: str, upload_id: str)`**: Links a connection ID to an upload session ID, creating a new session state record if needed.
  * **`update_upload_progress(upload_id: str, progress_data: Dict[str, Any])`**: Updates progress values and broadcasts state changes to all subscribers.
  * **`complete_upload(upload_id: str, final_data: Optional[Dict[str, Any]] = None)`**: Dispatches complete status signals and updates final session metrics.
  * **`disconnect(websocket: Optional[WebSocket] = None, connection_id: Optional[str] = None)`**: Gracefully disconnects client tracking references.
  * **`_force_disconnect(connection_id: str)`**: Forces socket closure and removes subscription references.
  * **`cleanup_stale_connections()`**: Disconnects tracking sockets that have exceeded timeout limits.
  * **`cleanup_completed_uploads()`**: Purges completed upload session records older than 1 hour to free memory.
  * **`get_stats() -> Dict[str, Any]`**: Gathers statistics on active connections, pending uploads, and weak reference counts.
  * **`shutdown()`**: Safely cancels background task loops and closes all sockets.

#### WebSocket Router Entry Points
* **`GET /ws/upload-status`**: Connects status listeners to broad progress updates.
* **`GET /ws/upload-status/{upload_id}`**: Direct connection tunnel mapping listeners to progress events for a specific `upload_id`.

---

## Resource Disposal Lifecycle

To prevent memory leaks and orphaned sockets, the WebSocket managers are hooked directly into the FastAPI application lifespan:

```
  [FastAPI Shutdown Event]
             │
             ▼
   [app.main Lifespan Yield]
             │
             ▼
   [Stop WebSocket Managers]
    (Awaits clipboard_ws_manager.shutdown())
    (Awaits upload_status_manager.shutdown())
             │
             ├───────► Disconnects all active WebSocket clients gracefully
             ├───────► Cancels background timeout/cleanup loops
             ▼
   [Stop mDNS & Cleanup Resources]
```
