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

## 6. Self-Documenting Code & Clear Comments
- Write clean, modular, self-documenting code with descriptive function and variable names.
- Include clear, concise comments explaining key technical decisions (e.g., `// Retain completed queue items in list until backend disk scan updates to prevent UI flickers`) without adding redundant boilerplate text.
