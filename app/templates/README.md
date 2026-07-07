# Lanvan HTML Templates

This directory contains the Jinja2 HTML templates used to render Lanvan's web interface.

## Template Architecture

Lanvan uses **Jinja2 Template Inheritance** to keep frontend pages DRY (Don't Repeat Yourself) and modular:

```
                  ┌──────────────────────┐
                  │      base.html       │ (Shared Layout, head metadata, scripts, styles, Toast & Logs Modals)
                  └──────────┬───────────┘
                             │
            ┌────────────────┴────────────────┐
            ▼                                 ▼
   ┌─────────────────┐               ┌─────────────────┐
   │   index.html    │               │ clipboard.html  │
   │ (File Transfer) │               │   (Clipboard)   │
   └─────────────────┘               └─────────────────┘
```

### 1. `base.html`
The parent template defining the global page skeleton:
* Page `<head>` settings (viewport parameters, cache-busting stylesheets).
* Instant theme/dark-mode injector script to prevent light flash during loading.
* Universal components like the `#toast` banner and `#deviceLogsModal`.
* Global script includes (`main-app.js` and `ui-modules.js`).

### 2. `index.html`
Extends `base.html` to supply the main **Upload Files & Manager** panel along with the **Available Files & Folders** list grid.

### 3. `clipboard.html`
Extends `base.html` to supply the **Unified Clipboard System** including text inputs, pasted image preview targets, and historical text/logs downloaders.

---

## Standalone Templates

* **`loading.html`**: A lightweight standalone splash screen containing progressive loaders shown to users while initial server resources and connection states are prepared.
* **`ios-help.html`**: A standalone help guide outlining browser setting adjustments required to bypass local network protocol limits on iOS Safari.
