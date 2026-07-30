# Lanvan Rendering Architecture Consolidation — Migration Log

## Phase 0 — Dependency Audit ✓

### Dependency Graph

```
API Response
    │
    ├── data.files (string[]) ──► auto-refresh ──► updateFileDisplay() ──► renderPrototypeFileList()
    │                                                                    (BYPASS - string input)
    │
    ├── data.files_data (object[]) ──► refreshFileList() ──► Repository.setFolderCache()
    │                                                         │
    │                                                         └──► RenderScheduler.requestRender()
    │                                                              │
    │                                                              └──► Projection ──► renderPrototypeFileList(viewModel, 'scheduler')
    │
    └── Via WebSocket ──► refreshFileList() ──► (same canonical path)


Direct renderPrototypeFileList() callers (ALL BYPASS):

    app-init.js:
    ├── updateFileDisplay wrapper:41          ── tagFilesWithFolder(files)
    ├── setSortOption:1900                    ── fetchFilesData().then(render)
    ├── setTypeFilter:1973                    ── fetchFilesData().then(render)
    ├── setViewMode:2058                      ── lastRenderedFiles
    ├── handleHeaderSortClick:2028            ── fetchFilesData().then(render)
    ├── submitNewFolder completion:~2160      ── fetchFilesData().then(render)
    ├── renameItem completion:~2250           ── fetchFilesData().then(render)
    ├── deleteSelectedItems:~2480             ── fetchFilesData().then(render)
    ├── moveSelectedItems:~2620               ── fetchFilesData().then(render)
    ├── navigateIntoFolder:~2900              ── fetchFolderContents().then(render)
    ├── applySearchQuery:~3100                ── lastRenderedFiles
    ├── initial bootstrap:~3780               ── fetchFilesData().then(render)
    ├── onUploadQueueAdded fallback:~4680     ── lastRenderedFiles
    ├── pauseAllUploads:~4710                  ── lastRenderedFiles
    ├── resumeAllUploads:~4720                ── lastRenderedFiles
    ├── triggerInstantUIUpdate fallback:~4340 ── lastRenderedFiles
    ├── triggerInstantRefresh:~4314           ── fetchFilesData().then(render)
    ├── requestSafeVisibleFilesRefresh:~4330  ── triggerInstantRefresh()
    ├── Store navigation subscriber:~3300     ── fetchFolderContents().then(render)
    └── clearSelection:~2700                 ── lastRenderedFiles or fetch

    ui-modules.js:
    ├── folderUpload completion:~1290         ── requestSafeVisibleFilesRefresh(120)
    └── folderUpload httpSafe:~1340           ── requestSafeVisibleFilesRefresh(120)

    main-app.js:
    ├── auto-refresh:2836                     ── updateFileDisplay(files) [string[]]
    ├── auto-refresh:2853 (count match)       ── updateFileDisplay(files)
    ├── clearAllFiles:3260                    ── updateFileDisplay([])
    ├── uploadLargeFileChunked completion:~2212 ── refreshFileList() [canonical]
    └── single upload completion:~4209         ── refreshFileList() [canonical]

    upload-engine.js:
    ├── resumeUploadItem:79                   ── triggerInstantUIUpdate()
    └── cancelUploadItem:105                  ── triggerInstantUIUpdate()

    upload-tray-renderer.js:
    └── renderUploadTray:~140                 ── triggerInstantUIUpdate()
```

### Reference Count Summary

| Symbol | References | Files |
|---|---|---|
| `renderPrototypeFileList` | 42 | app-init.js, ui-modules.js, main-app.js |
| `updateFileDisplay` | 11 | main-app.js, app-init.js |
| `triggerInstantUIUpdate` | 24 | app-init.js, main-app.js, upload-engine.js, upload-tray-renderer.js |
| `triggerInstantRefresh` | 12 | app-init.js |
| `requestSafeVisibleFilesRefresh` | 24 | app-init.js, main-app.js, ui-modules.js |
| `fetchFilesData` | 22 | app-init.js, ui-modules.js, main-app.js |
| `lastRenderedFiles` | 28 | app-init.js, main-app.js |
| `RenderScheduler.requestRender` | 4 | main-app.js, app-init.js |

### Direct renderPrototypeFileList() Call Sites (BYPASS Scheduler)

1. **app-init.js:41** — `updateFileDisplay` wrapper
2. **app-init.js:1900** — `setSortOption`
3. **app-init.js:1973** — `setTypeFilter`
4. **app-init.js:2028** — `handleHeaderSortClick`
5. **app-init.js:2058** — `setViewMode`
6. **app-init.js:~2160** — `submitNewFolder` completion
7. **app-init.js:~2250** — rename completion
8. **app-init.js:~2480** — `deleteSelectedItems`
9. **app-init.js:~2620** — `moveSelectedItems`
10. **app-init.js:~2900** — `navigateIntoFolder`
11. **app-init.js:~3100** — `applySearchQuery`
12. **app-init.js:~3780** — initial bootstrap
13. **app-init.js:~4680** — `onUploadQueueAdded` fallback
14. **app-init.js:~4710** — `pauseAllUploads`
15. **app-init.js:~4720** — `resumeAllUploads`
16. **app-init.js:~4340** — `triggerInstantUIUpdate` fallback
17. **app-init.js:4314** — `triggerInstantRefresh`
18. **app-init.js:~3300** — Store navigation subscriber
19. **app-init.js:~2700** — `clearSelection`

## Phase 1 — Define Ownership

### Repository (repository.js)
- **Owns**: filesystem snapshot — tagged object arrays with `__folderPath`, `isFolder`, `name`, `size`, `mtime`
- **Does NOT own**: rendering, ViewModel generation, DOM, API fetching logic (fetchFolderContents is a convenience, not ownership)
- **Single cache per folder**: Guaranteed by `this.cache[key]` keyed on cleaned folder path

### Store (state-store.js)
- **Owns**: `currentFolder`, `uploadQueue`, `selection`, `pendingOps`, generation counters
- **Does NOT own**: rendering, DOM, Repository, file data
- **State immutable**: Guaranteed by `dispatch()` creating new object references via `.slice()` and `Object.assign({}, ...)`
- **Single owner**: Only `dispatch()` writes to `this.state`

### Projection Layer (projection-layer.js)
- **Owns**: Pure ViewModel generation — `(storeState, diskFiles) => ViewModel[]`
- **Does NOT own**: rendering, DOM, API calls, cache management
- **Pure**: Same inputs always produce same output (modulo the line 225 vs 192 identity bug identified earlier)

### Render Scheduler (render-scheduler.js)
- **Owns**: Render scheduling — rAF coalescing, single-flight, hash-based skip
- **Does NOT own**: data fetching, Projection, DOM mutations, Store mutations
- **Single render**: `isRendering` guard + `renderRequested` flag

### Renderer (app-init.js:renderPrototypeFileList)
- **Owns**: DOM mutation — `container.innerHTML = ...`
- **Does NOT own**: data fetching, Repository, Projection, scheduling
- **Problem**: Currently also runs its own Projection pass (app-init.js:361-362) — this is a VIOLATION. Projection belongs in Projection Layer only.

## Phase 2 — Eliminate Parallel Pipelines (PLAN)

### Migration Order (by risk, lowest first)

**Phase 2a**: Fix auto-refresh to use canonical pipeline ✅ DONE
- File: `main-app.js:2830-2836`
- Change: `updateFileDisplay(files)` → `refreshFileList('auto_refresh')`
- Risk: None. Both paths fetch API data. Canonical path writes Repository + triggers Scheduler.
- Test: Auto-refresh on new files from another device
- Status: **COMPLETE**
- Behavior preserved: Auto-refresh still detects count changes and triggers a refresh. Now goes through `refreshFileList()` → Repository → RenderScheduler → Projection → Renderer instead of bypassing to `updateFileDisplay()` with string array.
- Bugs eliminated: Duplicate "Lot of files(dir) + Lot of files(file)" on auto-refresh, string-vs-object type mismatch in Projection

**Phase 2b**: Simplify `triggerInstantUIUpdate` — remove fallback
- File: `app-init.js:~4338-4350`
- Change: Remove `renderPrototypeFileList(lastRenderedFiles)` fallback path. Always delegate to `RenderScheduler.requestRender()`.
- Risk: Very low. Scheduler always available.
- Test: Upload progress UI updates
- Status: NOT STARTED

**Phase 2c**: Remove `triggerInstantRefresh` — delegate to `refreshFileList`
- File: `app-init.js:4302-4319`
- Change: Replace body with `refreshFileList('instant_refresh')`. Remove `fetchFilesData().then(render)` AND the second `refreshFileList()` call.
- Risk: Low. Eliminates double-fetch/double-render.
- Test: Upload completion, delete, move, rename
- Status: NOT STARTED

**Phase 2d**: Redirect `requestSafeVisibleFilesRefresh` to `refreshFileList` directly
- File: `app-init.js:4322-4336`
- Change: Remove call to `triggerInstantRefresh()`. Call `refreshFileList()` directly (already debounced via `requestFileListRefresh`).
- Risk: Low. Same debounce behavior, canonical pipeline.
- Test: File operations, WebSocket refreshes
- Status: NOT STARTED

**Phase 2e**: Redirect direct `renderPrototypeFileList()` calls from event handlers
- File: `app-init.js` — all call sites in sort, filter, view mode, file operations
- Change: Replace `renderPrototypeFileList(fd)` with `refreshFileList()` + remove `fetchFilesData()` prefix (refreshFileList already fetches)
- Risk: Medium. Ensure all callers that need immediate feedback (sort, filter) still work correctly.
- Test: Sort, filter, view mode toggle, create/delete/rename/move folder
- Status: NOT STARTED

**Phase 2f**: Remove WebSocket file_events direct DOM mutation
- File: `main-app.js:287-305`
- Change: Remove manual DOM row removal and `lastRenderedFiles` mutation. Keep `invalidateCache()` + `refreshFileList()`.
- Risk: Medium. Ensure deleted files disappear through Scheduler render.
- Test: File deletion from another device
- Status: NOT STARTED

**Phase 2g**: Consolidate navigation to Scheduler-only
- File: `app-init.js` Store navigation subscriber
- Change: Keep `fetchFolderContents()` but remove `.then(renderPrototypeFileList)`. Scheduler handles the render.
- Risk: Medium. Navigation must still update breadcrumbs and clear selection.
- Test: Navigate into/out of folders
- Status: NOT STARTED

**Phase 2h**: Remove duplicate Projection pass from `renderPrototypeFileList`
- File: `app-init.js:361-362`
- Change: When `reason === 'scheduler'`, accept ViewModel directly (already projected). Internal Projection only for legacy callers (until they're all migrated).
- Risk: Medium. Must ensure ViewModel format is compatible.
- Test: All rendering scenarios
- Status: NOT STARTED

**Phase 2i**: Remove dead wrapper code
- File: `app-init.js:31-52` — `updateFileDisplay` wrapper
- Change: Remove (no callers remain after Phase 2a)
- Risk: Low. Verify no remaining references.
- Status: NOT STARTED