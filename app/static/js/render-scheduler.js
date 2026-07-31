/**
 * Lanvan Unidirectional Architecture: Render Scheduler & Fast-Path Engine
 * Manages single-flight rAF DOM render coalescing and Fast-Path in-place progress updates.
 * Implements fallback error protection (lastValidViewModel) so UI never crashes.
 * Includes self-healing DOM-vs-ViewModel verification (DEBUG_MODE only).
 */

(function (window) {
    'use strict';

    /**
     * Build a fast, deterministic hash of the ViewModel.
     * Does NOT use JSON.stringify — uses structural fields only.
     */
    function buildViewModelHashFast(viewModel, currentFolder) {
        var parts = [currentFolder || ''];
        for (var i = 0; i < viewModel.length; i++) {
            var f = viewModel[i];
            if (!f) continue;
            parts.push(
                f.name || '',
                f.isFolder ? 'd' : 'f',
                f.uploading ? 'u' : '-',
                f.uploadStatus || '',
                Math.round((f.uploadProgress || 0) * 10) / 10
            );
        }
        return parts.join('|');
    }

    /**
     * Self-Healing: Verify DOM consistency after every render.
     * DEBUG_MODE only — zero overhead in production.
     */
    function verifyDOMConsistency(viewModel, currentFolder) {
        var container = document.getElementById('nasFileList');
        if (!container) return;

        var vmNames = {};
        for (var i = 0; i < viewModel.length; i++) {
            var vf = viewModel[i];
            if (!vf || !vf.name) continue;
            var vid = vf.identity || (currentFolder || '') + '/' + vf.name;
            if (vmNames[vid]) {
                console.error('[SELF-HEAL] ViewModel has duplicate identity: ' + vid);
            }
            vmNames[vid] = vf;
        }

        var rows = container.querySelectorAll('.m3-list-item');
        var domNames = {};
        for (var j = 0; j < rows.length; j++) {
            var fn = rows[j].getAttribute('data-filename');
            if (!fn) continue;
            if (domNames[fn]) {
                console.error('[SELF-HEAL] DOM has duplicate data-filename: ' + fn);
            }
            domNames[fn] = true;

            // Check: does this DOM row have a corresponding ViewModel entry?
            var found = false;
            for (var k = 0; k < viewModel.length; k++) {
                if (viewModel[k] && viewModel[k].name === fn) {
                    found = true;
                    break;
                }
            }
            if (!found) {
                console.warn('[SELF-HEAL] DOM row without ViewModel entry: ' + fn);
            }
        }
    }

    function RenderScheduler(store, projection, repo) {
        this.store = store;
        this.projection = projection;
        this.repo = repo;
        
        this.renderRequested = false;
        this.isRendering = false;
        this.lastValidViewModel = null;
        this._lastViewModelHash = '';
        this._lastNavGeneration = 0;
        this._lastUpGeneration = 0;
        this.rendererFn = null;

        var self = this;

        if (this.store) {
            this.store.subscribe(function (state, action) {
                if (action.type === 'PROGRESS_TICK') {
                    self.fastPathUpdate(action.payload);
                    return;
                }
                var navGen = state.navigationGeneration || 0;
                var upGen = state.uploadGeneration || 0;
                if (navGen !== self._lastNavGeneration || upGen !== self._lastUpGeneration) {
                    self._lastNavGeneration = navGen;
                    self._lastUpGeneration = upGen;
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
        if (window.__lanvanTimelineTracker) {
            window.__lanvanTimelineTracker.recordEvent("schedulerRequest", "alreadyRequested: " + this.renderRequested);
        }
        if (this.renderRequested) return;
        this.renderRequested = true;

        var self = this;
        requestAnimationFrame(function () {
            self.renderRequested = false;
            self.executeRender();
        });
    };

    RenderScheduler.prototype.executeRender = function () {
        if (window.__lanvanTimelineTracker) {
            window.__lanvanTimelineTracker.recordEvent("schedulerExecute", "isRendering: " + this.isRendering + ", hasRenderer: " + (!!this.rendererFn));
        }
        if (this.isRendering || !this.rendererFn) return;
        this.isRendering = true;

        var viewModel = null;
        var state = this.store ? this.store.state : {};
        try {
            var diskFiles = this.repo ? this.repo.getFolderCache(state.currentFolder) : [];
            console.log("%c[FLICKER-TRACE] 🖼️ Scheduler.executeRender | Timestamp: " + performance.now().toFixed(1) + "ms | Repo cache: " + (Array.isArray(diskFiles) ? diskFiles.length : 0) + " items | Store uploadQueue: " + (state.uploadQueue ? state.uploadQueue.length : 0) + " items | uploadGen: " + (state.uploadGeneration || 0) + " | navGen: " + (state.navigationGeneration || 0));
            viewModel = this.projection.buildCurrentFolderViewModel(state, diskFiles);

            var newHash = buildViewModelHashFast(viewModel, state.currentFolder);
            if (newHash === this._lastViewModelHash && this.lastValidViewModel) {
                this.isRendering = false;
                return;
            }
            this._lastViewModelHash = newHash;
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

        if (typeof window.__logF5Trace === "function") {
            window.__logF5Trace("4. After RenderScheduler.executeRender()");
        }

        // SELF-HEALING (DEBUG only): DOM ↔ ViewModel reconciliation
        if (window.DEBUG_MODE && viewModel) {
            verifyDOMConsistency(viewModel, state.currentFolder);
        }
    };

    RenderScheduler.prototype.fastPathUpdate = function (payload) {
        if (!payload || !payload.id) return;
        
        var uploadId = payload.id;
        var progress = payload.progress !== undefined ? payload.progress : 0;
        var speedText = payload.speedText || "";
        var etaText = payload.etaText || "";

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
        window.ProjectionLayer,
        window.FileRepository
    );
    window.RenderScheduler = schedulerInstance;

})(window);