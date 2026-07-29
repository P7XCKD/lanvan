/**
 * Lanvan Render Coordinator (render-coordinator.js)
 * Single gate for all DOM rendering. Guarantees:
 *   - Maximum 1 render per animation frame
 *   - Identical ViewModel → skip render
 *   - All render triggers consolidated into one entry point
 */

(function(window) {
    'use strict';

    function RenderCoordinator() {
        this._pending = false;
        this._lastViewModelHash = '';
        this._renderCount = 0;
    }

    /**
     * Request a render. Multiple calls within the same animation frame
     * are collapsed into a single render on the next frame.
     *
     * @param {string} reason - Diagnostic label for the trigger source
     */
    RenderCoordinator.prototype.requestRender = function(reason) {
        var self = this;
        if (this._pending) {
            // Already scheduled for this frame — coalesce
            return;
        }
        this._pending = true;

        requestAnimationFrame(function() {
            self._pending = false;
            self._executeRender(reason || 'coordinator');
        });
    };

    RenderCoordinator.prototype._executeRender = function(reason) {
        // 1. Read current store state
        var store = window.LanvanStore;
        if (!store) return;
        var storeState = store.getState();
        var currentFolder = storeState.currentFolder || '';

        // 2. Read repository snapshot for current folder
        var repo = window.FileRepository;
        var diskFiles = repo ? repo.getFolderCache(currentFolder) : [];

        // 3. Run projection
        var projection = window.ProjectionLayer;
        if (!projection) return;
        var viewModel = projection.buildCurrentFolderViewModel(storeState, diskFiles);

        // 4. Incremental hash check — skip render if ViewModel unchanged
        var hash = buildViewModelHash(viewModel, currentFolder);
        if (hash === this._lastViewModelHash) {
            return;
        }
        this._lastViewModelHash = hash;
        this._renderCount++;

        // 5. Dispatch to renderer
        if (typeof window.renderPrototypeFileList === 'function') {
            window.renderPrototypeFileList(viewModel, reason);
        }

        // 6. Also update upload tray (lightweight, in-place DOM updates)
        if (typeof window.renderUploadTray === 'function') {
            window.renderUploadTray();
        }
    };

    /**
     * Build a lightweight, deterministic hash of the ViewModel.
     * Does NOT use JSON.stringify — uses a fast path with name+status+progress.
     */
    function buildViewModelHash(viewModel, currentFolder) {
        var parts = [currentFolder];
        for (var i = 0; i < viewModel.length; i++) {
            var f = viewModel[i];
            if (!f) continue;
            // Only hash fields that affect rendering
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

    // Singleton instance
    var instance = new RenderCoordinator();
    window.RenderCoordinator = instance;

})(window);