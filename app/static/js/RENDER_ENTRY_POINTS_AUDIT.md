# Render Entry Points Audit

## All Code Paths That Trigger a DOM Render

### 1. RenderScheduler.requestRender() — THE AUTHORITATIVE PATH
| Attribute | Value |
|---|---|
| **Entry function** | `RenderScheduler.prototype.requestRender()` (render-scheduler.js:112) |
| **Why it exists** | Centralized rAF-coalesced, single-flight render pipeline |
| **Bypasses scheduler** | No — IS the scheduler |
| **Reads Repository directly** | Yes — `executeRender()` (line 130): `this.repo.getFolderCache(state.currentFolder)` |
| **Reads Store directly** | Yes — `executeRender()` (line 128): `this.store.state` |
| **Concurrent render possible** | No — `isRendering` guard + `renderRequested` coalescing via rAF |
| **Redundant** | No — this is the intended single pipeline |
| **Subscribers** | Store listener (line 90): fires on any `navigationGeneration` or `uploadGeneration` change |
| **Callers** | `refreshFileList()` (main-app.js:2765), `triggerInstantUIUpdate()` (app-init.js) |

---

### 2. RenderScheduler.fastPathUpdate() — DOM PATCH (NOT FULL RENDER)
| Attribute | Value |
|---|---|
| **Entry function** | `RenderScheduler.prototype.fastPathUpdate()` (render-scheduler.js:159) |
| **Why it exists** | Ultra-fast progress bar update without full Projection/render cycle |
| **Bypasses scheduler** | No — IS the scheduler, but bypasses Projection |
| **Reads Repository directly** | No |
| **Reads Store directly** | No (reads payload directly) |
| **Concurrent render possible** | Yes — does NOT check `isRendering` flag |
| **Redundant** | No — intentional optimization to avoid full re-render on every progress tick |
| **Subscribers** | Store listener (line 91): fires on `PROGRESS_TICK` action |

---

### 3. renderPrototypeFileList() via Scheduler setRenderer — AUTHORITATIVE CALLBACK
| Attribute | Value |
|---|---|
| **Entry function** | `renderPrototypeFileList()` — registered via `RenderScheduler.setRenderer()` (app-init.js line ~4330) |
| **Why it exists** | The RenderScheduler's output target — renders the PROJECTED ViewModel (already merged) |
| **Bypasses scheduler** | No — called BY the scheduler |
| **Reads Repository directly** | No — receives already-merged ViewModel from Projection |
| **Reads Store directly** | No |
| **Concurrent render possible** | No — inside scheduler's `isRendering` guard |
| **Redundant** | No — this is the correct final render stage |
| **Signature** | `renderPrototypeFileList(viewModel, 'scheduler')` |

---

### 4. renderPrototypeFileList() — DIRECT CALLS (BYPASSING SCHEDULER)
| Attribute | Value |
|---|---|
| **Entry function** | `renderPrototypeFileList(files, reason)` (app-init.js) |
| **Why it exists** | Prototype UI adapter — called from dozens of event handlers |
| **Bypasses scheduler** | **YES** — does not go through RenderScheduler.requestRender() |
| **Reads Repository directly** | Yes — falls back to Repository cache when `files` is null/empty (app-init.js:279) |
| **Reads Store directly** | Yes — reads `window.LanvanStore.state` and `window.uploadQueue` (app-init.js:349-354) |
| **Runs its own internal Projection** | **YES** — lines 361-362: `projectionEngine.buildCurrentFolderViewModel(storeState, files)` |
| **Concurrent render possible** | **YES** — no guard against concurrent direct calls from multiple event sources |
| **Redundant** | **YES** — this is a DUPLICATE rendering pipeline that competes with the scheduler |
| **Renders differently than scheduler** | Partially — reads `files` from cache/fallback instead of Repository, but also calls its own Projection pass |

#### DIRECT callers of renderPrototypeFileList() (ALL bypass scheduler):

| Caller | Location in app-init.js | Data Source | Concurrent Risk |
|---|---|---|---|
| `updateFileDisplay()` wrapper | line 41 | Cached files or fresh fetch | Yes |
| `triggerInstantUIUpdate()` fallback | ~line 4340 | `lastRenderedFiles` | Yes |
| `triggerInstantRefresh()` | ~line 4370 | Fresh `fetchFilesData()` | Yes |
| `setViewMode()` | line 2058 | `lastRenderedFiles` | Yes |
| `setSortOption()` | line 1900 | Fresh `fetchFilesData()` | Yes |
| `setTypeFilter()` | line 1973 | Fresh `fetchFilesData()` | Yes |
| `handleHeaderSortClick()` | line 2028 | Fresh `fetchFilesData()` | Yes |
| `submitNewFolder()` completion | ~line 2160 | Fresh `fetchFilesData()` | Yes |
| `createRenameDialog()` completion | ~line 2250 | Fresh `fetchFilesData()` | Yes |
| `deleteSelectedItems()` | ~line 2480 | Fresh `fetchFilesData()` | Yes |
| `moveSelectedItems()` | ~line 2620 | Fresh `fetchFilesData()` | Yes |
| `clearSelection()` | ~line 2700 | `lastRenderedFiles` or fresh fetch | Yes |
| `navigateIntoFolder()` | ~line 2900 | Fresh `fetchFilesData()` | Yes |
| `applySearchQuery()` | ~line 3100 | `lastRenderedFiles` | Yes |
| Navigation via Store dispatch | ~line 3300 | `FileRepository.fetchFolderContents()` | Yes |
| Initial load / bootstrap | ~line 3780 | `fetchFilesData()` | Yes |
| `onUploadQueueAdded` fallback | ~line 4680 | `lastRenderedFiles` | Yes |
| `resumeAllUploads` | ~line 4710 | `lastRenderedFiles` | Yes |
| `pauseAllUploads` | ~line 4720 | `lastRenderedFiles` | Yes |

---

### 5. updateFileDisplay() — LEGACY RENDER PATH
| Attribute | Value |
|---|---|
| **Entry function** | `updateFileDisplay(files)` (main-app.js:2957, wrapped in app-init.js:31-52) |
| **Why it exists** | Legacy pre-scheduler render function, now wrapped as fallback |
| **Bypasses scheduler** | **YES** — directly calls `renderPrototypeFileList()` |
| **Reads Repository directly** | No (reads `files` parameter or fetches fresh) |
| **Reads Store directly** | No |
| **Concurrent render possible** | **YES** |
| **Redundant** | **YES** — fallback when RenderScheduler unavailable |
| **Callers** | `refreshFileList()` fallback (line 2767), auto-refresh count change (line 2853) |

---

### 6. refreshFileList() — API FETCH + CACHE + TRIGGER
| Attribute | Value |
|---|---|
| **Entry function** | `refreshFileList(reason)` (main-app.js:2744) |
| **Why it exists** | Fetch latest files from server, cache in Repository, trigger render |
| **Bypasses scheduler** | No — calls `RenderScheduler.requestRender()` |
| **Reads Repository directly** | No — writes to it (`setFolderCache`) |
| **Reads Store directly** | Yes — `getCurrentFolderPath()` for current folder |
| **Concurrent render possible** | Partially — debounced via `requestFileListRefresh()` wrapper |
| **Redundant** | No — this is the primary data ingress path |
| **Callers** | WebSocket events (file_events, upload_status), auto-refresh, manual refresh, upload completion, cancel-upload, clear files, visibility change, `requestFileListRefresh()`, `requestSafeVisibleFilesRefresh()`, `triggerInstantRefresh()` |

---

### 7. triggerInstantUIUpdate() — FAST-PATH RENDER
| Attribute | Value |
|---|---|
| **Entry function** | `triggerInstantUIUpdate()` (app-init.js) |
| **Why it exists** | Immediate UI refresh after upload state changes |
| **Bypasses scheduler** | **Conditional** — uses `RenderScheduler.requestRender()` when available; falls back to direct `renderPrototypeFileList(lastRenderedFiles)` |
| **Reads Repository directly** | No (uses lastRenderedFiles) |
| **Reads Store directly** | No |
| **Concurrent render possible** | Yes — debounced by `_instantUIUpdateScheduled` flag |
| **Redundant** | **YES when scheduler exists** — the scheduler already subscribes to Store changes |
| **Called from** | `onUploadQueueAdded` hook, `pauseUpload`, `resumeUpload`, `pauseAllUploads`, `resumeAllUploads`, `cancelUpload`, `updateUploadItem` (on completion), upload-engine.js progress events, upload-tray-renderer.js |

---

### 8. triggerInstantRefresh() — FORCE FRESH RENDER
| Attribute | Value |
|---|---|
| **Entry function** | `triggerInstantRefresh()` (app-init.js) |
| **Why it exists** | Force-fetch + render after operations |
| **Bypasses scheduler** | **YES** — `fetchFilesData().then(renderPrototypeFileList)` + also calls `refreshFileList()` |
| **Reads Repository directly** | No (fetches fresh) |
| **Reads Store directly** | No |
| **Concurrent render possible** | **YES** — no guard |
| **Redundant** | **YES** — fetches data AND calls `refreshFileList()` which ALSO fetches data |
| **Called from** | `requestSafeVisibleFilesRefresh()`, upload completion in app-init.js, delete operations |

---

### 9. requestSafeVisibleFilesRefresh() — DEBOUNCED REFRESH
| Attribute | Value |
|---|---|
| **Entry function** | `requestSafeVisibleFilesRefresh(delayMs)` (app-init.js) |
| **Why it exists** | Debounced safe refresh with timeout |
| **Bypasses scheduler** | **YES** — calls `triggerInstantRefresh()` which bypasses scheduler |
| **Reads Repository directly** | No |
| **Reads Store directly** | No |
| **Concurrent render possible** | Yes — debounced but no render guard |
| **Redundant** | **YES** — just a debounced wrapper around paths that are already redundant |
| **Called from** | WebSocket upload_status events, main-app.js upload completion, file operations (delete, move, mkdir, rename), cancel-upload cleanup, ui-modules.js folder upload completion |

---

### 10. requestFileListRefresh() — DEBOUNCED API REFRESH
| Attribute | Value |
|---|---|
| **Entry function** | `requestFileListRefresh(delayMs)` (main-app.js:2710) |
| **Why it exists** | Debounced API fetch to avoid thundering herd |
| **Bypasses scheduler** | No — calls `refreshFileList()` which calls scheduler |
| **Reads Repository directly** | No |
| **Reads Store directly** | No |
| **Concurrent render possible** | No — debounced + single-flight promise |
| **Redundant** | No — legitimate debounce wrapper |

---

### 11. Auto-Refresh (setInterval) — POLLING RENDER
| Attribute | Value |
|---|---|
| **Entry function** | `autoRefreshInterval` callback (main-app.js:2809) |
| **Why it exists** | Cross-device file sync polling |
| **Bypasses scheduler** | **Conditional** — calls `refreshFileList()` (which uses scheduler) on count mismatch, but calls `updateFileDisplay()` (which bypasses) |
| **Reads Repository directly** | No |
| **Reads Store directly** | No |
| **Concurrent render possible** | Yes — fires every 5s independent of other renders |
| **Redundant** | Partially — server-side WebSocket events already trigger real-time refresh |

---

### 12. WebSocket Event Handlers — NETWORK TRIGGERS
| Attribute | Value |
|---|---|
| **Entry functions** | `uploadWs.onmessage` (main-app.js:223), `fileEventsWs.onmessage` (main-app.js:279) |
| **Why it exists** | Real-time cross-device sync |
| **Bypasses scheduler** | **PARTIALLY** — `fileEventsWs` directly mutates DOM (line 299-304: removes stale rows), then calls `refreshFileList()` |
| **Reads Repository directly** | `fileEventsWs` calls `FileRepository.invalidateCache()` (line 285) |
| **Reads Store directly** | No |
| **Concurrent render possible** | **YES** — WebSocket events are asynchronous and can interleave with any render |
| **Redundant** | No — but multiple WebSocket types (upload_status, file_events) can fire simultaneously |

---

## Concurrent Render Risk Analysis

The following code paths can fire **simultaneously** and each will independently call `renderPrototypeFileList()`, the Projection, or mutate DOM:

| Path 1 | Path 2 | Concurrency Mechanism |
|---|---|---|
| Scheduler rAF render | `triggerInstantUIUpdate()` direct call | rAF vs synchronous/microtask |
| Auto-refresh `updateFileDisplay()` | WebSocket `refreshFileList()` | setInterval vs WebSocket message |
| Upload completion `triggerInstantUIUpdate()` | Auto-refresh count check | setTimeout vs setInterval |
| `fileEventsWs` DOM mutation (line 299-304) | Any render path | Synchronous DOM write during render |
| `fastPathUpdate()` DOM mutation | `executeRender()` full render | PROGRESS_TICK Store event during scheduled render |
| `setSortOption()` → `fetchFilesData().then(render)` | `refreshFileList()` → scheduler render | Two independent fetch chains |
| `submitNewFolder()` → render | WebSocket file_change → render | POST response vs WebSocket event |
| `navigateIntoFolder()` → `fetchFolderContents().then(render)` | Store subscriber → scheduler render | Two independent async chains |

---

## Render Pipeline Architecture Assessment

```
                        ┌─────────────────────────────────────┐
                        │        DATA INGRESS (CORRECT)        │
                        │                                     │
                        │  refreshFileList() ──► Repository   │
                        │  WebSocket events ──► invalidation  │
                        │  Upload completion ──► Store        │
                        └──────────┬──────────────────────────┘
                                   │
                    ┌──────────────┼───────────────┬──────────────────┐
                    ▼              ▼               ▼                  ▼
            ┌───────────┐  ┌─────────────┐  ┌───────────┐  ┌──────────────────┐
            │ SCHEDULER │  │triggerInstant│  │ trigger   │  │ DIRECT           │
            │ pipeline  │  │UIUpdate()    │  │ Instant   │  │ renderPrototype  │
            │ (correct) │  │(duplicate)   │  │ Refresh() │  │ FileList() calls │
            │           │  │              │  │(duplicate)│  │ (duplicate)      │
            │ Store→    │  │ lastFiles→   │  │ fetch→    │  │ fetch/cache→     │
            │ Repo→     │  │ render       │  │ render    │  │ render           │
            │ Proj→     │  │              │  │ +refresh  │  │ +internal Proj   │
            │ render    │  │              │  │ FileList  │  │                  │
            └─────┬─────┘  └──────┬──────┘  └─────┬─────┘  └────────┬─────────┘
                  │               │               │                 │
                  ▼               ▼               ▼                 ▼
            ┌─────────────────────────────────────────────────────────────────┐
            │              renderPrototypeFileList(files, reason)             │
            │                                                                 │
            │  • Normalizes files (isFolder detection)                        │
            │  • Falls back to Repository cache when files is null/empty      │
            │  • Runs ITS OWN PROJECTION PASS (line 361-362)                  │
            │  • Applies type filter, search filter, sort                     │
            │  • Generates render signature, skips if identical to last       │
            │  • Mutates DOM (container.innerHTML = ...)                      │
            └─────────────────────────────────────────────────────────────────┘
```

## Invariant Violations

| Invariant | Current State |
|---|---|
| **Single render pipeline** | **VIOLATED** — 4+ independent pipelines converge on the same DOM |
| **Projection runs once** | **VIOLATED** — `renderPrototypeFileList()` runs its own Projection pass (line 361) INDEPENDENTLY of the scheduler's Projection pass (render-scheduler.js:131) |
| **Read-only renderer** | **VIOLATED** — `fastPathUpdate()` mutates DOM; `fileEventsWs` (main-app.js:299-304) mutates DOM |
| **Scheduler is sole render gate** | **VIOLATED** — 12+ code paths call `renderPrototypeFileList()` directly |

## Root Cause of the Duplicate Bug

The transient duplicate occurs because:

1. **Upload queue adds items** → `triggerInstantUIUpdate()` fires → reads `lastRenderedFiles` (stale, no new folder) + live uploadQueue → Projection creates synthetic folder with identity `"/Lot of files"`

2. **`refreshFileList()` returns** → `setFolderCache()` with correct folder data → `RenderScheduler.requestRender()` fires → Projection reads fresh Repository cache (folder with `identity: "Lot of files"`, `isFolder: true`) + upload queue → Section 3 matching succeeds (line 192 ternary produces `"Lot of files"`) BUT the synthetic folder from step 1 is NOT in `normalizedDiskFiles` anymore because the scheduler starts from scratch

3. **HOWEVER**, if another `triggerInstantUIUpdate()` or direct `renderPrototypeFileList()` call interleaves between step 1 and step 2, it reads `lastRenderedFiles` (containing the synthetic folder from step 1) + uploadQueue + possibly new Repository data → **two Projection passes with different snapshots** → identity mismatch at line 225 vs line 192 → dedup fails → duplicate appears

4. **Next `refreshFileList()`** → everything consistent → duplicate disappears

## Recommended Consolidation

The system needs **exactly one rendering pipeline**:

1. All data mutation goes through Store
2. Store subscribers trigger `RenderScheduler.requestRender()`
3. `RenderScheduler.executeRender()` reads Store + Repository, runs Projection ONCE, and calls the registered renderer ONCE
4. Remove `triggerInstantUIUpdate()`, `triggerInstantRefresh()`, and all direct `renderPrototypeFileList()` calls from event handlers
5. `fastPathUpdate()` should be the ONLY exception for progress-only DOM patches
6. `fileEventsWs` DOM mutation (main-app.js:299-304) should be removed — let the scheduler handle removal via Projection