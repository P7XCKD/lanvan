# Project Rules & Architectural Standards: Lanvan Web Application

This document defines the mandatory architectural standards, defensive programming patterns, and UI state guidelines for the Lanvan codebase. All code modifications must strictly adhere to these rules.

---

## 1. Defensive Property Access & Data Contracts (Industry Standard)
Objects in `uploadQueue` originate from multiple sources (HTML5 file picker, drag & drop, localStorage recovery, API WebSocket sync). Never dereference nested object properties directly without defensive getters.

###  Forbidden (Anti-Pattern):
```javascript
// CRASH RISK: Throws Uncaught TypeError if item.file is undefined
const size = uploadItem.file.size;
const name = uploadItem.file.name;
```

###  Mandatory Standard:
Always use safe fallback accessors or defensive helper functions:
```javascript
function getItemSize(item) {
    if (!item) return 0;
    return item.fileSize || (item.file ? item.file.size : 0);
}

function getItemName(item) {
    if (!item) return "Unknown";
    return item.fileName || (item.file ? item.file.name : "Unknown");
}

function getItemProgress(item) {
    if (!item || typeof item.progress !== "number") return 0;
    return Math.min(100, Math.max(0, item.progress));
}
```
*Rule*: Ensure all stats loggers, toast notifications, progress calculators, and network payloads use non-throwing defensive getters so state transitions never crash JavaScript execution.

---

## 2. Single Source of Truth & Declarative UI Rendering
`window.uploadQueue` is the single authoritative state repository for all upload items (`uploading`, `queued`, `processing`, `paused`, `completed`, `cancelled`).

###  Forbidden (Anti-Pattern):
```javascript
// DESYNC RISK: Direct DOM removal causes UI flickering when auto-refresh triggers
row.remove();
document.getElementById('status-1').textContent = 'Cancelled';
```

###  Mandatory Standard (Declarative Action Pattern):
Action handlers (`pauseUpload`, `resumeUpload`, `cancelUpload`) MUST ONLY mutate state properties on `uploadQueue` items and trigger `triggerInstantUIUpdate()`:
```javascript
function cancelUpload(uploadId) {
    const uploadItem = uploadQueue.find(item => item.id === uploadId);
    if (!uploadItem) return;

    // 1. Safe network cleanup
    if (uploadItem.xhr) {
        try { uploadItem.xhr.abort(); } catch (err) {}
    }

    // 2. Mutate state on single source of truth
    uploadItem.status = 'cancelled';
    uploadItem.error = 'Cancelled by user';

    // 3. Declarative UI re-render
    if (typeof window.triggerInstantUIUpdate === 'function') {
        window.triggerInstantUIUpdate();
    }
}
```
*Rule*: The UI must be rendered declaratively from `uploadQueue` state (`UI = f(State)`) to prevent DOM desynchronization between `main-app.js` (production view) and `app-init.js` (prototype list view).

---

## 3. Upload State & Notification Tray Integrity
- `isAllCompleted` MUST ONLY evaluate to `true` when 100% of items in `uploadQueue` have status `'completed'` or `'deleted'` AND `pausedCount === 0` and `activePendingCount === 0`.
- **Header Actions**: If any items are `paused` (`pausedCount > 0`), header action controls MUST render the **Play (Resume All)** button (`<i data-lucide="play"></i>`).
- **Tray Items**: Paused rows in the notification tray MUST render individual **Resume** and **Cancel** action controls.
- **Blink Prevention**: Completed upload items in `uploadQueue` MUST be retained in `normalizedFiles` until backend disk scan APIs update to eliminate temporary UI blinks or blank screen flickers.
- **Empty State Protection**: Active or paused upload queues MUST NOT be overridden by empty directory templates (`Drop files here`).

---

## 4. Subfolder Upload Synthesis Pattern
When rendering file lists (`renderPrototypeFileList`), subfolder uploads (e.g. `FolderA/file1.zip`) MUST be aggregated dynamically into synthetic root folder rows (`activeFolderMap`) for the current directory view.
- Synthetic folder rows calculate total size, uploaded bytes, and overall progress percentage.
- Toggling pause/resume on a synthetic folder row pauses or resumes all items inside that subfolder batch.

---

## 5. Non-Blocking Async & Error Shielding
- Wrap all network fetch requests, WebSocket message handlers, and stats loggers in non-throwing `try/catch` or `.catch()` handlers.
- Uncaught exceptions MUST NEVER escape to window event loops or break background uploads.

---

## 7. Zero-Flicker Icon & UI Element Stability (Mandatory Standard)
- **Inline SVGs over Dynamic Tag Parsing**: Never rely on asynchronous JS icon replacement loops (`lucide.createIcons()`) or raw placeholder tags (`<i data-lucide="...">`) during high-frequency update loops (e.g. progress ticks). Always use resilient, direct inline SVGs so control icons (Play, Pause, Chevron, Cancel X) render natively without showing broken characters (`00` / `ll`) or disappearing.
- **Strict In-Place DOM Property Updates**: High-frequency progress handlers (`_doInstantUIUpdate`) MUST strictly mutate existing DOM element properties (`textContent`, `style.width`) in-place. NEVER wipe or re-create parent DOM containers (`container.innerHTML = html`) during active transfers, as destroying elements under the user's cursor drops CSS `:hover` states and causes card flickering.
- **Loose ID Equality**: Event handlers and queue lookups MUST use loose type coercion (`item.id == uploadId` or `String(item.id) === String(uploadId)`). Never use strict number-to-string equality (`item.id === uploadId`), which fails when `uploadId` is read as a string from DOM attributes.
- **Scrollbar Layout Shift Prevention**: Scrollable containers with dynamic content (`.upload-toast-body`) MUST specify `scrollbar-gutter: stable;` and `overflow-x: hidden;` in CSS. Action controls (`.upload-toast-actions`, `.upload-toast-cancel-text`) MUST have `flex-shrink: 0; margin-left: auto;` so scrollbar toggle states never cause horizontal button shifting.
- **Guard DOM Element Re-ordering**: High-frequency list renderers (`renderUploadTray`) MUST verify if an element is already in position (`if (container.children[i] !== itemEl)`) before calling `appendChild(itemEl)`. Re-attaching existing DOM nodes continuously detaches them from the render tree, dropping CSS `:hover` states and causing button flickering on mouseover.

---

## 8. Mandatory Test Suite Expansion & Feature/Combination Coverage (`qt.py` & `ui_test.py`)
Whenever introducing new features, options, UI flows, API routes, or multi-item operation combinations, you MUST proactively update and expand `qt.py` (server API, static integrity, & feature assertion tests) and `ui_test.py` to cover all new features and operational combinations. Always run `python qt.py --fast` (and full suite) to ensure 100% pass rate before declaring completion.

---

## 9. Bug Report Stress Testing & Exploratory Combination Verification (Mandatory Standard)
Whenever the user reports a bug:
- You MUST create temporary scratch test scripts (in scratch directory or exploratory combination runs) to stress test all edge-case variations, nested combinations, and race conditions related to that bug before declaring completion.
- Test multiple combinations of operations (e.g. create same-name folders $\rightarrow$ upload files $\rightarrow$ move files $\rightarrow$ delete nested folders $\rightarrow$ verify 404 recovery) to discover any hidden side effects and guarantee the bug is 100% permanently eliminated.

---

## 10. Mandatory Server Restart Notification Pattern
The user runs `python run.py` continuously in a background terminal. Whenever modifying backend Python code (`.py` files), FastAPI routes, or server environment configurations, you MUST explicitly remind the user in your response summary to restart `python run.py` so the active background server process registers the backend changes.

---

## 11. Autonomous Protocol & AGENTS.md Rule Self-Evolution Pattern
Whenever encountering repetitive errors, circular loops, structural ambiguities, or discovering new architectural best practices, you ARE FULLY AUTHORIZED AND MANDATED to update `.agents/AGENTS.md` immediately. Document the new pattern, architectural standard, or preventive rule explicitly in `.agents/AGENTS.md` and strictly follow it going forward to guarantee zero regression and maximum code quality.

---

## 12. Strict Zero-Emoji & Native Lucide Icon Standard (Mandatory Standard)
- **Zero Emojis in Toast Notifications or UI Text**: NEVER use emoji characters (e.g. 📦, ✅, 📥, 📄, 🚀, ⚡, 🟢) in toast notification messages, dialog titles, alert strings, or user-facing UI text. Keep all toast notifications clean, professional, and plain text.
- **Lucide Icons Only**: Use native Lucide inline SVG icons whenever icons are needed in UI components, buttons, or context menus.
