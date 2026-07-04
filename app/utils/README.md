# Lanvan Utilities Layer Developer Documentation

Welcome to the `app/utils` folder! This directory houses the platform compatibility layers, network discovery services, background task managers, SSL certificate validators, and resource monitors that ensure Lanvan operates smoothly across Windows, Linux, MacOS, and Android/Termux environments.

---

## Directory Map & Module Responsibilities

```
app/utils/
  ├── termux_compat.py          # Centralized OS platform flags & Android/Termux detection
  ├── termux_memory_monitor.py   # Background memory threshold monitor & GC trigger
  ├── universal_optimizer.py    # Platform-adaptive chunk size selector & background keepalives
  ├── responsiveness_manager.py # Thread yields & event-loop pause coordinator
  ├── simple_mdns.py            # Multicast DNS (Zeroconf) network discovery & collision manager
  ├── certificate_validator.py  # SSL Certificate validation checks & security indicators
  ├── thread_manager.py         # Prioritized system thread tracking & zombie cleanup
  └── task_manager.py           # Asynchronous task registry using garbage collection-safe weak refs
```

---

## Module Specifications

### 1. Platform Detection (`termux_compat.py`)
Provides centralized utilities to determine operating system environments and configure settings dynamically.

#### Key Functions
* **`is_android_environment() -> bool`**:
  Checks environment keys (like `ANDROID_ROOT`) to identify Android environments.
* **`is_termux_environment() -> bool`**:
  Checks for Termux installation files (e.g. `/data/data/com.termux`).
* **`detect_platform() -> str`**:
  Returns OS labels (`windows`, `linux`, `darwin`, `android`, `termux`, `unknown`).
* **`get_safe_memory_info() -> Dict[str, Any]`**:
  Queries system RAM status using `psutil` or falls back to system info files on Android/Termux.
* **`get_safe_cpu_usage() -> float`**:
  Gets current CPU usage percentage safely, avoiding platform-specific blocks.

---

### 2. Memory Throttling (`termux_memory_monitor.py`)
Tracks system RAM usage, firing garbage collection cycles to prevent Termux processes from being terminated by the Android Low Memory Killer (LMK).

#### Key Classes & Methods
* **`TermuxMemoryMonitor`**:
  * **`start_monitoring()`**: Spawns a background thread checking memory constraints every 2 seconds.
  * **`stop_monitoring()`**: Terminates the monitoring loop thread safely.
  * **`enforce_memory_limit(operation_name: str) -> bool`**: Evaluates system state; returns `False` if free memory is below critical thresholds (less than 50MB free).
  * **`get_adaptive_chunk_size(file_size: int) -> int`**: Calculates dynamic block sizes based on current RAM pressure.

---

### 3. Service Optimization (`universal_optimizer.py`)
Regulates file chunk configurations and maintains server keepalives.

#### Key Classes & Methods
* **`UniversalOptimizer`**:
  * **`get_adaptive_chunk_size(file_size: int) -> int`**: Adjusts chunk boundaries (from 512KB to 4MB) to balance performance and RAM.
  * **`start_background_keepalive()`**: Runs a daemon loop writing updates to a temporary keepalive file, preventing the OS from suspending the server process in background states.
  * **`stop_background_keepalive()`**: Terminates the keepalive worker thread.
  * **`memory_cleanup(force: bool = False)`**: Invokes Python garbage collection (`gc.collect`) when size thresholds are breached.

---

### 4. Responsiveness Management (`responsiveness_manager.py`)
Prevents CPU-heavy transfers from blocking FastAPI's async event loop.

#### Key Classes & Methods
* **`UnifiedResponsivenessManager`**:
  * **`register_operation(operation_id: str, operation_type: str, estimated_size: int)`**: Adds an active transfer task to the tracker.
  * **`should_yield(operation_id: str, processed_amount: int) -> bool`**: Evaluates if the task has run long enough to warrant a thread yield.
  * **`yield_control(operation_id: str, async_context: bool)`**: Pauses execution temporarily (`time.sleep` or `asyncio.sleep`) to allow other connections to be processed.

---

### 5. Local Network Discovery (`simple_mdns.py`)
Enables Zero-Configuration networking so users can connect via friendly local domain hostnames.

#### Key Classes & Methods
* **`SimpleMDNSManager`**:
  * **`get_lan_ip() -> str`**: Gets the LAN IP address (works offline by scanning local interfaces).
  * **`start_service() -> bool`**: Registers the server domain on the network.
  * **`stop_service() -> bool`**: Unregisters domain info and closes Zeroconf sockets.
  * **`get_hybrid_url() -> str`**: Returns the best hostname for QR code generation (prioritizes IP-based URLs on Android/Termux).

#### Dynamic Collision Resolution Sequence
When starting the mDNS service, it checks for existing hostnames to prevent conflicts:

```
  [Server Startup]
         │
         ▼
  [Browse mDNS Network]
   (Scan for "Lanvan")
         │
         ├───────► [Conflict Found?] ───Yes───► [Append Device ID]
         │                                       (e.g., "Lanvan-90b")
         │                                                │
         ▼                                                ▼
  [Register "Lanvan.local"]                [Register "Lanvan-[ID].local"]
```

---

### 6. SSL Certificate Validation (`certificate_validator.py`)
Ensures secure HTTPS servers launch only with valid configuration certificates.

#### Key Classes & Methods
* **`SafeCertificateValidator`**:
  * **`validate_certificate_safe(cert_path: Path, key_path: Path) -> CertValidationResult`**: Central method that validates PEM certificate formatting, expiry, and key compatibility.
  * **`check_network_security(local_ip: str) -> Dict[str, Any]`**: Checks the SSL configuration security for the given local network interface.

---

### 7. Thread Pooling (`thread_manager.py`)
Prevents resource leaks and system exhaustion from unmanaged background threads.

#### Key Classes & Methods
* **`ThreadManager`**:
  * **`create_thread(target: Callable, name: str, priority: ThreadPriority)`**: Spawns a daemon thread registered inside the system tracker.
  * **`stop_thread(name: str, timeout: float)`**: Signals a target thread to exit and joins it.
  * **`shutdown_all(timeout: float)`**: Triggers prioritized shutdown (Critical -> High -> Normal -> Low) during server stop.

---

### 8. Asynchronous Task Registry (`task_manager.py`)
Registers and tracks asynchronous background coroutines safely.

#### Key Classes & Methods
* **`LightweightTaskManager`**:
  * **`submit_task(coro, name: Optional[str]) -> Optional[asyncio.Task]`**: Submits and registers a coroutine in the tracker using `weakref` to prevent memory leaks.
  * **`_cleanup_completed_tasks()`**: Sweeps the task registry internally to prune finished references.

---

## System Coordination Flow

The following diagram illustrates how the utility modules cooperate with the FastAPI event loop during a file transfer:

```
  [Client Upload Request]
             │
             ▼
   [responsiveness_manager] ───► Register active operation
             │
             ▼
   [universal_optimizer] ─────► Retrieve adaptive chunk size (e.g. 1MB)
             │
             ▼
   [termux_memory_monitor] ───► Check RAM. If <50MB free, trigger gc.collect()
             │
             ▼
   [task_manager] ────────────► Spawns background worker task (tracked via weakref)
             │
             ▼
   [thread_manager] ──────────► Executes file block operations on safe pool threads
```

---

## Developer Guidelines

1. **Platform Fallbacks**: Never assume a platform-specific binary or library (such as `psutil` or `ctypes`) is installed. Always wrap import statements in try-except blocks and provide functional fallbacks.
2. **Standard Error Handlers**: Avoid using bare `except:` statements. Conforming to PEP 8 standards, always specify the target exception or use `except Exception:` to prevent capturing system shutdown events.
