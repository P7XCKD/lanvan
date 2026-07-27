# Architectural Standards & Mandatory Rules: Lanvan Unidirectional Pipeline

This document defines the strict, non-negotiable architectural contracts governing all frontend code in Lanvan.

---

## 1. The Golden Invariant
> **There shall be exactly one code path that produces `VisibleFiles[]`. No component, reducer, repository, WebSocket handler, upload manager, or renderer may create, modify, append to, or filter visible file lists outside the Projection Layer.**

---

## 2. Unidirectional Data Flow Pipeline

```
User / WS / Upload / Nav / API Events
                 │
                 ▼
          Action Queue (Priority Sorted: HIGH vs LOW)
                 │  (Action: { id, timestamp, type, payload })
                 ▼
    Domain Reducers (Pure: Upload, Folder, Nav, WS, Selection)
                 │
                 ▼
          Central Store & State Machine
        (NEW -> QUEUED -> UPLOADING -> PROCESSING -> COMPLETED)
                 │
  ┌──────────────┴──────────────┐
  │ [Structural Changes]        │ [High-Frequency Progress]
  ▼                             ▼
Projection Layer (Pure)     Fast-Path Row Update (In-Place)
  │                             │ (Updates Progress Bar, Speed, ETA)
  ▼                             │
Render Scheduler (rAF)          │
(Single Render Lock)            │
  │                             │
  ▼                             │
Stateless Renderer (No Globals) │
  │                             │
  └──────────────┬──────────────┘
                 ▼
                DOM
```

---

## 3. Mandatory Architectural Contracts

### ❌ NEVER
- Touch the DOM outside the Stateless Renderer or Fast-Path engine.
- Build or filter `VisibleFiles[]` outside `ProjectionLayer`.
- Fetch network requests or call APIs inside Reducers.
- Read global variables (`window.currentFolder`, `window.uploadQueue`, `window.lastFilesData`) inside the Renderer.
- Dispatch actions from inside the Renderer.
- Mutate Store state outside Domain Reducers.

### ✅ ALWAYS
- Dispatch actions via `ActionQueue.dispatch(type, payload, priority)`.
- Keep Reducers pure: `(oldState, action) => newState`.
- Pass all state into `ProjectionLayer` explicitly.
- Render strictly from `ViewModel` (`render(viewModel)`).
- Enforce the `UploadStateMachine` legal transitions.
