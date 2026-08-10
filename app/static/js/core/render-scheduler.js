/**
 * Render Scheduler & Fast-Path Engine
 *
 * Coordinates requestAnimationFrame DOM render coalescing, fast-path in-place progress mutations,
 * and fallback ViewModel error protection.
 */

(function (window) {
    'use strict';

    /**
     * Builds a deterministic structural hash of a ViewModel array.
     *
     * @param {Array} viewModel Collection of rendered item views.
     * @param {string} currentFolder Active folder scope.
     * @returns {string} Hash string for render change detection.
     */
    function buildViewModelHashFast(viewModel, currentFolder) {
        var vmMode = "grid";
        try { vmMode = localStorage.getItem("lanvan_view_mode") || "grid"; } catch (e) { }
        var parts = [
            currentFolder || '',
            window.typeFilter || 'all',
            window.sortBy || 'name',
            window.sortDirection || 'asc',
            window.sortFolders || 'top',
            vmMode
        ];
        for (var i = 0; i < viewModel.length; i++) {
            var item = viewModel[i];
            if (!item) continue;
            parts.push(
                item.name || '',
                item.isFolder ? 'd' : 'f',
                item.uploading ? 'u' : '-',
                item.uploadStatus || ''
            );
        }
        return parts.join('|');
    }

    /**
     * Verifies DOM elements against ViewModel records in debug environments.
     *
     * @param {Array} viewModel Target view model array.
     * @param {string} currentFolder Active folder path.
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

            // Verify existence of matching entry in ViewModel snapshot
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
        if (this.isRendering || !this.rendererFn || !window._initialized) return;
        var activeTab = document.documentElement.dataset.activeTab || (window.activeTab || 'file');
        if (activeTab !== 'file') return;
        this.isRendering = true;

        var viewModel = null;
        var state = this.store ? this.store.state : {};
        try {
            var diskFiles = this.repo ? this.repo.getFolderCache(state.currentFolder) : [];
            if (Array.isArray(diskFiles) && typeof window.__lanvanForensicTraceV2List === 'function') {
                window.__lanvanForensicTraceV2List('projection_input', state.currentFolder || '', diskFiles, 'repository_cache');
            }
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
            if (typeof window.__lanvanForensicEmit === 'function') {
                window.__lanvanForensicEmit('render_scheduler', 'render_requested', {
                    folder: state.currentFolder || '',
                    details: {
                        hasViewModel: !!viewModel,
                        itemCount: Array.isArray(viewModel) ? viewModel.length : ((viewModel && viewModel.visibleFiles) ? viewModel.visibleFiles.length : 0)
                    }
                });
            }
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

    RenderScheduler.prototype.triggerInstantUIUpdate = function () {
        var self = this;
        if (this._instantUIUpdateScheduled) return;
        this._instantUIUpdateScheduled = true;
        requestAnimationFrame(function () { self._instantUIUpdateScheduled = false; });

        if (typeof this.requestRender === 'function') {
            this.requestRender('instant_update');
        }
        if (typeof window.scheduleUploadTrayRender === "function") {
            window.scheduleUploadTrayRender();
        } else if (typeof window.renderUploadTray === "function") {
            window.renderUploadTray();
        }
    };

    RenderScheduler.prototype.doInstantUIUpdate = function () {
        if (typeof window.scheduleUploadTrayRender === "function") {
            window.scheduleUploadTrayRender();
        } else if (typeof window.renderUploadTray === "function") {
            window.renderUploadTray();
        }
        var container = document.getElementById("nasFileList");
        if (container && window.uploadQueue) {
            var activeFolder = window.LanvanStore ? window.LanvanStore.state.currentFolder : "";
            var normCurrentDir = typeof window.cleanFolderPath === "function" ? window.cleanFolderPath(activeFolder) : activeFolder;
            var missingRow = false;

            window.uploadQueue.forEach(function (item) {
                if (item && (item.status === 'QUEUED' || item.status === 'UPLOADING' || item.status === 'PROCESSING' || item.status === 'PAUSED')) {
                    var itemName = item.fileName || (item.file && item.file.name) || item.name;
                    var rawDir = item.targetDir || item.parent_path || item.folder || "";
                    var relDir = typeof window.getRelativeItemDir === "function" ? window.getRelativeItemDir(rawDir, normCurrentDir) : rawDir;
                    if (relDir === null) return;
                    var checkName = relDir === "" ? itemName : relDir.split("/")[0];
                    if (checkName) {
                        var targetKey = checkName.trim().toLowerCase();
                        var allRows = container.querySelectorAll('.m3-list-item');
                        var foundRow = false;
                        for (var r = 0; r < allRows.length; r++) {
                            var rowFn = allRows[r].getAttribute('data-filename');
                            if (rowFn && rowFn.trim().toLowerCase() === targetKey) {
                                foundRow = true;
                                break;
                            }
                        }
                        if (!foundRow) missingRow = true;
                    }
                }
            });

            var hasCancelled = window.uploadQueue.some(function (i) { return i && i.status === 'CANCELLED'; });
            var hasTimedOut = window.uploadQueue.some(function (i) { return i && i.status === 'COMPLETED' && i._dismissTimer; });

            if (missingRow && hasCancelled && !hasTimedOut) {
                missingRow = false;
            }

            if (missingRow && typeof window.lastRenderedFiles !== "undefined" && !window._instantRenderInProgress) {
                window._instantRenderInProgress = true;
                if (typeof window.renderFileList === "function") window.renderFileList(window.lastRenderedFiles);
                setTimeout(function () { window._instantRenderInProgress = false; }, 200);
            } else {
                var rowDataMap = {};

                window.uploadQueue.forEach(function (item) {
                    if (!item) return;
                    var itemName = item.fileName || (item.file && item.file.name) || item.name;
                    if (!itemName) return;
                    var rawDir = item.targetDir || item.parent_path || item.folder || "";
                    var relDir = typeof window.getRelativeItemDir === "function" ? window.getRelativeItemDir(rawDir, normCurrentDir) : rawDir;
                    if (relDir === null) return;
                    var checkName = relDir === "" ? itemName : relDir.split("/")[0];
                    var isFolder = relDir !== "";

                    if (!rowDataMap[checkName]) {
                        rowDataMap[checkName] = {
                            isFolder: isFolder,
                            totalBytes: 0,
                            uploadedBytes: 0,
                            status: 'QUEUED',
                            hasCancelled: false,
                            hasUploading: false,
                            hasPaused: false,
                            itemCount: 0
                        };
                    }

                    var rd = rowDataMap[checkName];
                    rd.itemCount++;

                    if (item.status === 'CANCELLED') {
                        rd.hasCancelled = true;
                        return;
                    }

                    var fileSize = item.fileSize || (item.file && item.file.size) || 0;
                    var bytesDone = 0;
                    if (item.status === 'COMPLETED') {
                        bytesDone = fileSize;
                    } else {
                        bytesDone = item.bytesUploaded || 0;
                        if (!bytesDone && item.progress && fileSize) {
                            bytesDone = (fileSize * item.progress) / 100;
                        }
                    }
                    rd.totalBytes += fileSize;
                    rd.uploadedBytes += bytesDone;

                    if (item.status === 'UPLOADING' || item.status === 'PROCESSING') rd.hasUploading = true;
                    if (item.status === 'PAUSED') rd.hasPaused = true;
                    if (item.status === 'CANCELLED') rd.hasCancelled = true;
                });

                Object.keys(rowDataMap).forEach(function (checkName) {
                    var rd = rowDataMap[checkName];
                    var escName = typeof window.escapeHtml === "function" ? window.escapeHtml(checkName) : checkName;
                    var row = container.querySelector('.m3-list-item[data-filename="' + escName + '"]');
                    if (!row) return;

                    var isRowFolder = row.getAttribute('data-is-folder') === '1';
                    var progress = 0;
                    if (rd.totalBytes > 0) {
                        progress = Math.min(100, Math.round((rd.uploadedBytes / rd.totalBytes) * 100));
                    }

                    var statusKey = rd.hasPaused ? 'PAUSED' : (rd.hasUploading ? 'UPLOADING' : 'QUEUED');

                    var subtitleCell = row.querySelector('.item-subtitle');
                    if (subtitleCell) {
                        var statusTxt = statusKey === 'PAUSED' ? 'Paused' : (statusKey === 'UPLOADING' ? 'Uploading' : 'Queued');
                        subtitleCell.textContent = progress + "% • " + statusTxt;
                    }
                    var dateCell = row.querySelector('.item-date');
                    if (dateCell) {
                        dateCell.textContent = statusKey === 'PAUSED' ? 'Paused' : (statusKey === 'UPLOADING' ? 'Uploading' : 'Queued');
                    }
                    var bar = row.querySelector('.row-progress-bar');
                    if (bar) {
                        bar.style.transform = "scaleX(" + (progress / 100) + ")";
                    }

                    var b4Num = row.querySelector('.b4-num');
                    if (b4Num) {
                        b4Num.textContent = progress + "%";
                    }
                    var b4Sub = row.querySelector('.b4-sub');
                    if (b4Sub) {
                        b4Sub.textContent = statusKey;
                    }
                    var b4Strip = row.querySelector('.b4-bottom-strip > div');
                    if (b4Strip) {
                        b4Strip.style.width = progress + "%";
                    }

                    var waterBar = row.querySelector('.grid-water-progress-bar');
                    if (waterBar) {
                        waterBar.style.height = progress + "%";
                    }

                    var playPauseBtn = row.querySelector('[data-action="pause-upload"], [data-action="resume-upload"]');
                    if (playPauseBtn) {
                        var currentAction = playPauseBtn.getAttribute("data-action");
                        var svgPlay = '<svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor" stroke="none"><polygon points="5 3 19 12 5 21 5 3"></polygon></svg>';
                        var svgPause = '<svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor" stroke="none"><rect x="6" y="4" width="4" height="16"></rect><rect x="14" y="4" width="4" height="16"></rect></svg>';

                        if (statusKey === 'PAUSED' && currentAction === 'pause-upload') {
                            playPauseBtn.setAttribute("data-action", "resume-upload");
                            playPauseBtn.setAttribute("title", "Resume upload");
                            playPauseBtn.innerHTML = svgPlay;
                        } else if (statusKey !== 'PAUSED' && currentAction === 'resume-upload') {
                            playPauseBtn.setAttribute("data-action", "pause-upload");
                            playPauseBtn.setAttribute("title", "Pause upload");
                            playPauseBtn.innerHTML = svgPause;
                        }
                    }
                });
            }
        }
    };

    RenderScheduler.prototype.updateRowProgress = function (item) {
        if (!item || !item.fileName) return;

        if (item.status === 'COMPLETED') {
            var hasOtherActiveUploads = Array.isArray(window.uploadQueue) && window.uploadQueue.some(function (qi) {
                return qi && qi.id !== item.id && (qi.status === 'UPLOADING' || qi.status === 'QUEUED' || qi.status === 'PROCESSING' || qi.status === 'PAUSED');
            });

            if (!hasOtherActiveUploads) {
                setTimeout(function () {
                    if (typeof window.triggerInstantRefresh === 'function') {
                        window.triggerInstantRefresh();
                    } else if (typeof window.refreshFileList === 'function') {
                        window.refreshFileList();
                    }
                }, 150);
            }
            return;
        }

        var container = document.getElementById("nasFileList");
        if (!container) return;

        var activeFolder = window.LanvanStore ? window.LanvanStore.state.currentFolder : "";
        var normCurrentDir = typeof window.cleanFolderPath === "function" ? window.cleanFolderPath(activeFolder) : activeFolder;
        var itemDir = typeof window.cleanFolderPath === "function" ? window.cleanFolderPath(item.targetDir || item.parent_path || item.folder || "") : "";

        if (itemDir === normCurrentDir) {
            var progress = Math.round(item.progress || 0);
            var escName = typeof window.escapeHtml === "function" ? window.escapeHtml(item.fileName) : item.fileName;
            var row = container.querySelector('.m3-list-item[data-filename="' + escName + '"]');
            if (row && row.getAttribute('data-is-folder') !== '1') {
                var subtitleCell = row.querySelector('.item-subtitle');
                if (subtitleCell) {
                    var statusTxt = item.status === 'PAUSED' ? 'Paused' : (item.status === 'PROCESSING' ? 'Processing' : 'Uploading');
                    var rowSub = progress + "% • " + statusTxt;
                    if (item.status === 'UPLOADING' && window.UploadETA) {
                        var etaStr = window.UploadETA.format(item);
                        if (etaStr) rowSub += " • ETA " + etaStr;
                    }
                    subtitleCell.textContent = rowSub;
                }
                var dateCell = row.querySelector('.item-date');
                if (dateCell) {
                    dateCell.textContent = item.status === 'PAUSED' ? 'Paused' : (item.status === 'PROCESSING' ? 'Processing' : 'Uploading');
                }
                var bar = row.querySelector('.row-progress-bar');
                if (bar) {
                    bar.style.transform = "scaleX(" + (progress / 100) + ")";
                }

                var b4Num = row.querySelector('.b4-num');
                if (b4Num) {
                    b4Num.textContent = progress + "%";
                }
                var b4Sub = row.querySelector('.b4-sub');
                if (b4Sub) {
                    b4Sub.textContent = item.status === 'PAUSED' ? 'PAUSED' : (item.status === 'QUEUED' ? 'QUEUED' : 'UPLOADING');
                }
                var b4Strip = row.querySelector('.b4-bottom-strip > div');
                if (b4Strip) {
                    b4Strip.style.width = progress + "%";
                }

                var playPauseBtn = row.querySelector('[data-action="pause-upload"], [data-action="resume-upload"]');
                if (playPauseBtn) {
                    var currentAction = playPauseBtn.getAttribute("data-action");
                    if (item.status === 'PAUSED' && currentAction === 'pause-upload') {
                        playPauseBtn.setAttribute("data-action", "resume-upload");
                        playPauseBtn.setAttribute("title", "Resume upload");
                        playPauseBtn.innerHTML = '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="currentColor" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="lucide lucide-play"><polygon points="6 3 20 12 6 21 6 3"/></svg>';
                    } else if (item.status !== 'PAUSED' && currentAction === 'resume-upload') {
                        playPauseBtn.setAttribute("data-action", "pause-upload");
                        playPauseBtn.setAttribute("title", "Pause upload");
                        playPauseBtn.innerHTML = '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="lucide lucide-pause"><rect width="4" height="16" x="6" y="4"/><rect width="4" height="16" x="14" y="4"/></svg>';
                    }
                }
            } else {
                if (typeof window.triggerInstantUIUpdate === 'function') {
                    window.triggerInstantUIUpdate();
                } else if (typeof window.lastRenderedFiles !== 'undefined' && typeof window.renderFileList === 'function') {
                    window.renderFileList(window.lastRenderedFiles);
                }
            }
        }
    };

    RenderScheduler.prototype.onUploadQueueAdded = function (files) {
        console.log("[RenderScheduler] onUploadQueueAdded hook fired!", files);
        window.uploadTrayDocked = false;
        if (typeof window.renderUploadTray === "function") {
            window.renderUploadTray();
        }
        if (typeof window.lastRenderedFiles !== "undefined" && typeof window.renderFileList === "function") {
            window.renderFileList(window.lastRenderedFiles);
        }
        if (typeof window.startUploadTrayPolling === "function") {
            window.startUploadTrayPolling();
        }
    };

    RenderScheduler.prototype.pauseAllUploads = function () {
        var queue = window.uploadQueue || [];
        queue.forEach(function (item) {
            if (item && (item.status === "UPLOADING" || item.status === "QUEUED" || item.status === "PROCESSING")) {
                if (typeof window.pauseUpload === "function") {
                    window.pauseUpload(item.id);
                } else if (typeof window.pauseUploadItem === "function") {
                    window.pauseUploadItem(item.id);
                } else {
                    item.status = "PAUSED";
                    if (item.xhr) { try { item.xhr.abort(); } catch (e) { } }
                }
            }
        });
        window.uploadManagerExpanded = true;
        this.triggerInstantUIUpdate();
    };

    RenderScheduler.prototype.resumeAllUploads = function () {
        var queue = window.uploadQueue || [];
        queue.forEach(function (item) {
            if (item && item.status === "PAUSED") {
                if (typeof window.resumeUpload === "function") {
                    window.resumeUpload(item.id);
                } else if (typeof window.resumeUploadItem === "function") {
                    window.resumeUploadItem(item.id);
                } else {
                    item.status = "UPLOADING";
                }
            }
        });
        window.uploadManagerExpanded = false;
        this.triggerInstantUIUpdate();
    };

    var schedulerInstance = new RenderScheduler(
        window.LanvanStore,
        window.ProjectionLayer,
        window.FileRepository
    );
    window.RenderScheduler = schedulerInstance;

    // Window backward compatibility exports
    window.triggerInstantUIUpdate = function() { return schedulerInstance.triggerInstantUIUpdate.apply(schedulerInstance, arguments); };
    window._doInstantUIUpdate = function() { return schedulerInstance.doInstantUIUpdate.apply(schedulerInstance, arguments); };
    window.updateRowProgress = function(item) { return schedulerInstance.updateRowProgress(item); };
    window.onUploadQueueAdded = function(files) { return schedulerInstance.onUploadQueueAdded(files); };
    window.pauseAllUploads = function() { return schedulerInstance.pauseAllUploads(); };
    window.resumeAllUploads = function() { return schedulerInstance.resumeAllUploads(); };

})(window);