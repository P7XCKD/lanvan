/**
 * Lanvan Unidirectional Architecture: Render Scheduler & Fast-Path Engine
 * Manages single-flight rAF DOM render coalescing and Fast-Path in-place progress updates.
 * Implements fallback error protection (lastValidViewModel) so UI never crashes.
 */

(function (window) {
    'use strict';

    function RenderScheduler(store, projection, repo) {
        this.store = store;
        this.projection = projection;
        this.repo = repo;
        
        this.renderRequested = false;
        this.isRendering = false;
        this.lastValidViewModel = null;
        this.rendererFn = null;

        var self = this;

        // Subscribe to Store updates
        if (this.store) {
            this.store.subscribe(function (state, action) {
                if (action.type === 'PROGRESS_TICK') {
                    // High-Frequency Progress: Execute Fast-Path In-Place Progress Update
                    self.fastPathUpdate(action.payload);
                } else {
                    // Structural Change: Schedule Full Projection & Render
                    self.requestRender();
                }
            });
        }
    }

    RenderScheduler.prototype.setRenderer = function (fn) {
        if (typeof fn === 'function') {
            this.rendererFn = fn;
        }
    };

    RenderScheduler.prototype.requestRender = function () {
        if (this.renderRequested) return;
        this.renderRequested = true;

        var self = this;
        requestAnimationFrame(function () {
            self.renderRequested = false;
            self.executeRender();
        });
    };

    RenderScheduler.prototype.executeRender = function () {
        if (this.isRendering || !this.rendererFn) return;
        this.isRendering = true;

        var viewModel = null;
        try {
            var state = this.store ? this.store.state : {};
            var diskFiles = this.repo ? this.repo.getFolderCache(state.currentFolder) : [];
            viewModel = this.projection.buildCurrentFolderViewModel(state, diskFiles);
            this.lastValidViewModel = viewModel;
        } catch (err) {
            console.error("  [PROJECTION ERROR] Render fallback activated:", err);
            viewModel = this.lastValidViewModel || { currentFolder: "", visibleFiles: [], selection: [], timestamp: Date.now() };
        }

        try {
            this.rendererFn(viewModel);
        } catch (renderErr) {
            console.error("  [RENDERER ERROR] Stateless renderer failed:", renderErr);
        } finally {
            this.isRendering = false;
        }
    };

    // Fast-Path Progress Update (STRICT IN-PLACE BOUNDARY RULES)
    // Permitted: Modifying progress bar style.width, speed text, and ETA text on existing DOM rows.
    // Strictly Banned: Creating rows, deleting rows, reordering rows, switching folders, or modifying VisibleFiles[].
    RenderScheduler.prototype.fastPathUpdate = function (payload) {
        if (!payload || !payload.id) return;
        
        var uploadId = payload.id;
        var progress = payload.progress !== undefined ? payload.progress : 0;
        var speedText = payload.speedText || "";
        var etaText = payload.etaText || "";

        // Locate existing DOM row by upload ID or data attribute
        var row = document.querySelector('[data-upload-id="' + uploadId + '"]') || document.getElementById('file-row-' + uploadId);
        if (row) {
            var progressBar = row.querySelector('.upload-progress-bar') || row.querySelector('.progress-fill');
            if (progressBar) {
                progressBar.style.width = Math.min(100, Math.max(0, progress)) + "%";
            }
            var speedEl = row.querySelector('.upload-speed');
            if (speedEl && speedText) {
                speedEl.textContent = speedText;
            }
            var etaEl = row.querySelector('.upload-eta');
            if (etaEl && etaText) {
                etaEl.textContent = etaText;
            }
        }
    };

    var schedulerInstance = new RenderScheduler(
        window.LanvanStore,
        window.projectionLayer,
        window.FileRepository
    );
    window.RenderScheduler = schedulerInstance;

})(window);
