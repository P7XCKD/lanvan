# Lanvan JavaScript Assets

This directory contains the client-side JavaScript assets used to manage upload queues, progressive resources loading, direct download strategies, clipboard synchronization, and responsive browser helpers.

## Modular Scripts Architecture

The JavaScript layer is organized into decoupled modules, separating loader mechanisms, utilities, and UI render controllers:

```
            ┌──────────────────────┐
            │  resource-loader.js  │ (Progressive loader, iOS Safari optimizations)
            └──────────┬───────────┘
                       │
         ┌─────────────┼──────────────┐
         ▼             ▼              ▼
 ┌──────────────┐┌────────────┐┌──────────────┐
 │file-utils.js ││ui-modules.js││ main-app.js  │
 │ (Utilities)  ││(UI Helpers)││(Orchestrator)│
 └──────────────┘└────────────┘└──────────────┘
```

---

## Detailed Component Map

### 1. `resource-loader.js` (Loader Layer)
* **Progressive Load System:** Declares `progressiveLoader` with `critical` and `enhanced` resource buckets to defer non-blocking assets.
* **Compatibility Signatures:** Runs instant detection flags (`window.isSafari`, `window.isiOS`, `window.isiOSSafari`).
* **Dynamic CDN Fallbacks:** Automatically lazy-loads external resources like `JSZip` from CDNs with automatic connection timeouts.

### 2. `file-utils.js` (Utilities Layer)
* **Standard Math Helpers:** Converts speed rates, timestamps, and sizes (`formatTime`, `formatFileSize`, `formatSpeed`, `formatClipboardSize`).
* **Security & XSS Prevents:** Escapes raw HTML formatting strings via `escapeHtml()`.
* **Diagnostics:** Detects device memory limits (`getDeviceMemory`) and incognito browsing sessions (`checkIncognitoMode`).

---

### 3. `ui-modules.js` (UI Controller Layer - ~1,300 Lines)
This script acts as the layout control system. It organizes interactive widgets and feeds real-time modifications to DOM elements.

* **DOM Cache Engine:** Maintains a local memory cache wrapper `DOM_CACHE` (`window.DOM_CACHE`) to avoid repeated, expensive document queries.
* **Toasts & Feedback:** Coordinates the `#toast` progress animations, styling overrides, colors (`setProgressColor`), and timers.
* **Download Controllers:** Sets up high-performance downloading logic (`setupDownloadHandlers`):
  * Decides between direct downloads and stream assembly.
  * Measures network throughput latency.
* **Folder Render Layout:** Fetches available subdirectory hierarchies from endpoints and populates the folder grid.
* **Page Navigation State:** Implements `switchToPage(viewName)` to toggle section visibility smoothly between file sharing and clipboard modes.

---

### 4. `main-app.js` (Core Application Layer - ~6,600 Lines)
This is the central execution runtime for the application. It coordinates asynchronous streaming operations, networking sockets, and upload tasks.

* **Logging Framework:** Instantiates a production logging module (`window.log`) exposing `.info()`, `.warn()`, `.error()`, and `.debug()` methods mapped to environment flags.
* **WebSocket Sockets:** Resolves real-time notifications for clipboard edits and coordinates connectivity fallbacks to polling intervals if network bounds fail.
* **Chunked Upload Manager:** Manages file splitting and assembly pipelines:
  * Splits files into chunk sizes optimized dynamically based on connection speeds.
  * Implements an asynchronous upload worker queue supporting pause, resume, and cancellation.
  * Integrates retry logic with exponential backoffs for chunks that fail during transfer.
  * Builds multi-chunk files on the server once uploads complete.
* **AES Cryptography Module:** Handles in-browser encryption and decryption using the Web Crypto API, securing payloads before transferring them over the network.
* **Drag & Drop Listeners:** Hooks drop zone overlays and resolves relative folder paths for uploading directories without browser dialog locks.

---

### 5. Third-Party Dependencies
* **`lucide.min.js`**: Vector icon library used for layout alignment.
