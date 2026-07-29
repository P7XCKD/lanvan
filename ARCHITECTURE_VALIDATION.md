# Lanvan Architecture Validation

## State Ownership Map

| State          | Owner(s)                      | Readers                                      | Violation |
|----------------|-------------------------------|----------------------------------------------|-----------|
| uploadQueue    | main-app.js (_rawUploadQueue) | app-init.js, upload-engine.js, upload-tray-renderer.js, state-store.js, projection-layer.js | 5 writers |
| currentFolderPath | CONFLICT: app-init.js + state-store.js | app-init.js, main-app.js, breadcrumb-nav.js, repository.js | Both define `window.currentFolderPath` |
| disk cache     | repository.js                 | app-init.js (also has own `folderFilesCache`) | 2 caches |
| visibleFiles   | NONE (ephemeral)              | projection-layer.js, app-init.js             | No persistent owner |
| selection      | app-init.js (prototypeSelectedItems) | app-init.js, state-store.js               | Dual definition |

## Event Flow (Chaos)

```
WebSocket upload-status ──┐
WebSocket file-events  ──┤
Upload callbacks       ──┤
Progress safety net    ──┤──→ refreshFileList() → renderPrototypeFileList()
Auto-refresh poll      ──┤
Manual refresh btn     ──┤
Navigation             ──┘
Store subscriber       ──→ renderPrototypeFileList() directly
```

**No coordinator.** At least 8 independent triggers. Max 1 render per frame enforced by rAF in `triggerInstantUIUpdate`, but no dedup for full re-renders.

## Upload Queue Divergence

```js
// main-app.js line 1657:
uploadItem.status = 'cancelled';  // lowercase

// state-store.js line 22:
UPLOAD_TRANSITIONS['cancelled'] =  // undefined
// isValidTransition('cancelled', 'CANCELLED') returns 'cancelled' === 'CANCELLED' → false
// allowed.indexOf('CANCELLED') in undefined → TypeError
// Transition REJECTED
// Store and live queue diverge silently
```

## Navigation Double-Dispatch

```js
// app-init.js line 60-75:
Object.defineProperty(window, 'currentFolderPath', {
  set: function(val) {
    currentFolderPath = val;
    if (window.LanvanStore) window.LanvanStore.dispatch("NAVIGATE_FOLDER", ...);
  }
});

// state-store.js line 159-164:
Object.defineProperty(window, 'currentFolderPath', {
  set: function(val) { storeInstance.dispatch('SET_CURRENT_FOLDER', ...); }
});
```

**Both define the same property.** Last one wins. If app-init loads after state-store, its setter may or may not call store. This is non-deterministic.

## Invariants (Zero Satisfied)

| # | Invariant | Status |
|---|-----------|--------|
| 1 | Repository owns disk state | ❌ app-init.js also caches |
| 2 | UploadManager owns upload state | ❌ 5 files write to uploadQueue |
| 3 | Renderer never mutates state | ❌ renderPrototypeFileList modifies queue items |
| 4 | Projection never mutates input | ❌ projection-layer.js mutates items in-place |
| 5 | Navigation owns generations | ❌ No generation system |
| 6 | Repository never knows UI state | ✅ |
| 7 | Every visible file originates from Projection | ❌ Some render paths bypass projection |
| 8 | Exactly one source owns every mutable value | ❌ |
| 9 | Upload status transitions are validated | ❌ Lowercase strings bypass FSM |
| 10 | All timers/intervals have cleanup | ❌ Not audited |

## Required Upload Lifecycle

```
Created → QUEUED → UPLOADING → PROCESSING → COMPLETED
                     ↓  ↑         ↓
                  PAUSED  RETRYING FAILED
                     ↓              ↓
                  CANCELLED      CANCELLED
```

## Implementation Plan (8 Phases)

### Phase 0: Invariants as assertions only
Add UploadStatus enum, runtime assertions that detect violations without changing behavior.

### Phase 1: Single source for currentFolderPath
Remove app-init.js duplicate. state-store.js is sole owner.

### Phase 2: Single source for uploadQueue
Remove _rawUploadQueue. All code reads from store. UploadStatus enum.

### Phase 3: Single cache
Deprecate and remove folderFilesCache from app-init.js. Repository is sole cache.

### Phase 4: Navigation generations
Navigation gets generation counter. Stale renders rejected.

### Phase 5: Projection purity
No input mutation. Stable sort. Cancelled items tagged but not filtered.

### Phase 6: Event coordinator
Single RefreshCoordinator class deduplicates all refresh triggers.

### Phase 7: Memory leak audit
Every timer, listener, observer verified to have cleanup.