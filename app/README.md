# Lanvan Application Core Architecture

Welcome to the root `app` folder! This directory constitutes the runtime core of the Lanvan file-sharing application. It brings together the server lifecycle hooks, middleware setups, WebSocket modules, routing hierarchies, and core platform adapters.

---

## Directory Architecture

```
app/
  ├── __init__.py           # Package namespace initialization
  ├── main.py               # FastAPI application setup & server lifespan context manager
  ├── routes.py             # Router aggregator exposing and mapping sub-routers
  │
  ├── core/                 # Cryptography, validation, streaming merge, and atomic locks
  ├── routers/              # Controller routes for HTTP endpoints (files, pages, system, clipboard)
  ├── ws_manager/           # Real-time WebSocket state managers (clipboard, progress updates)
  ├── utils/                # Platform checks, memory limiters, thread pools, and mDNS discovery
  │
  ├── static/               # CSS styles, client JavaScript logic, images, and visual assets
  └── templates/            # Jinja2 HTML layout components and responsive design pages
```

---

## Root Core Modules

### 1. Application Namespace (`__init__.py`)
Initializes the `app` Python package namespace and declares the boundaries of the main framework hierarchy.

### 2. Main Entry Point (`main.py`)
Sets up the FastAPI framework instance, registers custom exceptions, filters logging output, and manages lifespan cycles.
* **CORS Security**: Implements `SecureCORSMiddleware` which limits origins dynamically using regex pattern matching specifically designed for LAN ranges (`127.0.0.1`, `192.168.0.0/16`, `10.0.0.0/8`, `.local` domains).
* **Logging Filters**: Applies `ClientDisconnectFilter` to silence starlette socket disconnect errors and prevent log inflation.
* **Lifespan Context Manager**:
  * **Startup Phase**: Spawns responsiveness monitors, launches background mDNS discovery, and runs clipboard persistence handlers.
  * **Shutdown Phase**: Awaits clean WebSocket manager shutdowns, stops thread pools, terminates streaming workers, and releases Zeroconf sockets.

### 3. Route Aggregator (`routes.py`)
Bundles separate endpoints into a single unified router structure.
* Wildcard exports (`from app.routers.pages import *`) are utilized specifically to retain full backward compatibility with diagnostic utilities like `qt.py`.
* Maps all sub-routers to the principal APIRouter context.

---

## Subfolder Explanations

For detailed descriptions of the components inside each folder, see their respective documentation files:

* **[app/core/](./core/README.md)**: Details the streaming chunk assembler (`streaming_assembly.py`), cryptography controllers (`aes_utils.py`), validation rules (`validation.py`), and atomic cross-platform file locking mechanisms.
* **[app/ws_manager/](./ws_manager/README.md)**: Documents WebSocket management, client subscriptions tracking, weak-reference sets preservation, and progress status broadcasts.
* **[app/utils/](./utils/README.md)**: Documents platform compatibility engines (`termux_compat.py`), memory limits monitors, thread manager pools, certificate validators, and local mDNS host name resolutions.
