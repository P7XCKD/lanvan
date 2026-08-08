/**
 * Lanvan Clean Single-Store Architecture: Central State Store (state-store.js)
 * Implements authoritative state repository for currentFolder, uploadQueue, selection, and subscribers.
 */

(function (window) {
    'use strict';

    // =========================================================================
    // TIMELINE TRACKER ENGINE (FORENSIC AUDIT INSTRUMENTATION ONLY)
    // =========================================================================
    var tracker = {
        logs: [],
        lastEvents: {
            storeAction: null,
            storeDispatch: null,
            schedulerRequest: null,
            schedulerExecute: null,
            refreshFileList: null,
            repoSetCache: null,
            repoGetCache: null,
            projectionBuild: null,
            renderView: null,
            domUpdate: null,
            wsEvent: null,
            navEvent: null
        },
        stateHistory: {
            repoNames: [],
            projNames: [],
            domNames: [],
            currentFolder: "",
            uploadQueueCount: 0
        },
        recordEvent: function(type, detail) {
            var ts = performance.now().toFixed(1);
            var entry = { ts: ts, type: type, detail: detail };
            this.logs.push(entry);
            this.lastEvents[type] = ts + "ms (" + (typeof detail === 'string' ? detail : JSON.stringify(detail)) + ")";
        },
        checkMutation: function(who, fn, file, line, reason, fieldName, oldVal, newVal) {
            var ts = performance.now().toFixed(1);
            var sOld = JSON.stringify(oldVal);
            var sNew = JSON.stringify(newVal);
            if (sOld !== sNew) {
                console.log("[MUTATION TRACE] ⚡ " + ts + "ms | " + fieldName + " MUTATED\n" +
                    "   OLD VALUE: " + sOld + "\n" +
                    "   ↓\n" +
                    "   NEW VALUE: " + sNew + "\n" +
                    "   WHO: " + who + " | FUNCTION: " + fn + " | FILE: " + file + ":" + line + " | REASON: " + reason);
            }
        },
        printSnapshot: function(label) {
            try {
                var ts = performance.now().toFixed(1);
                var folder = typeof window.getCurrentFolderPath === 'function' ? window.getCurrentFolderPath() : (window.currentFolderPath || "");
                
                var repoItems = (window.FileRepository && typeof window.FileRepository.getFolderCache === 'function') 
                    ? (window.FileRepository.getFolderCache(folder) || []) : [];
                var repoNames = repoItems.map(function(f) { return typeof f === 'string' ? f : f.name; });

                var projNames = [];
                if (window.ProjectionLayer) {
                    try {
                        var storeState = window.LanvanStore ? Object.assign({}, window.LanvanStore.state) : { currentFolder: folder, uploadQueue: [] };
                        storeState.currentFolder = folder;
                        var engine = window.projectionLayer || (typeof window.ProjectionLayer === 'function' ? new window.ProjectionLayer() : window.ProjectionLayer);
                        if (engine && engine.buildCurrentFolderViewModel) {
                            var vm = engine.buildCurrentFolderViewModel(storeState, repoItems);
                            var list = Array.isArray(vm) ? vm : ((vm && vm.visibleFiles) ? vm.visibleFiles : []);
                            projNames = list.map(function(f) { return f.name; });
                        }
                    } catch(e) {}
                }

                var container = document.getElementById("nasFileList");
                var domItems = container ? Array.prototype.slice.call(container.querySelectorAll(".m3-list-item")) : [];
                var domNames = domItems.map(function(el) { return el.getAttribute("data-filename") || el.textContent.trim(); });

                console.log("\n==================================================");
                console.log("SNAPSHOT @ " + ts + "ms (" + label + ")");
                console.log("==================================================");
                console.log("Timestamp: " + ts + "ms");
                console.log("Current Folder: '" + folder + "'");
                console.log("Repository Count: " + repoNames.length);
                console.log("Repository Names: [" + repoNames.join(", ") + "]");
                console.log("Projection Count: " + projNames.length);
                console.log("Projection Names: [" + projNames.join(", ") + "]");
                console.log("DOM Count: " + domNames.length);
                console.log("DOM Names: [" + domNames.join(", ") + "]");
                console.log("Last Store Action: " + (this.lastEvents.storeAction || "None"));
                console.log("Last Store Dispatch: " + (this.lastEvents.storeDispatch || "None"));
                console.log("Last RenderScheduler.requestRender(): " + (this.lastEvents.schedulerRequest || "None"));
                console.log("Last RenderScheduler.executeRender(): " + (this.lastEvents.schedulerExecute || "None"));
                console.log("Last refreshFileList(): " + (this.lastEvents.refreshFileList || "None"));
                console.log("Last Repository.setFolderCache(): " + (this.lastEvents.repoSetCache || "None"));
                console.log("Last Repository.getFolderCache(): " + (this.lastEvents.repoGetCache || "None"));
                console.log("Last Projection.buildCurrentFolderViewModel(): " + (this.lastEvents.projectionBuild || "None"));
                console.log("Last renderFileList(): " + (this.lastEvents.renderView || "None"));
                console.log("Last DOM update: " + (this.lastEvents.domUpdate || "None"));
                console.log("Last WebSocket Event: " + (this.lastEvents.wsEvent || "None"));
                console.log("Last Navigation Event: " + (this.lastEvents.navEvent || "None"));
                console.log("==================================================\n");
            } catch (err) {
                console.error("[TIMELINE ERROR] Snapshot error:", err);
            }
        }
    };
    window.__lanvanTimelineTracker = tracker;

    function scheduleSnapshots() {
        [250, 300, 400, 500, 750, 1000, 1500, 2000, 2500].forEach(function(delay) {
            setTimeout(function() {
                tracker.printSnapshot("T=" + delay + "ms check");
            }, delay);
        });
    }

    if (window.DEBUG_MODE) {
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', scheduleSnapshots);
        } else {
            scheduleSnapshots();
        }
    }

    // 1. Upload State Machine Transitions
    var UPLOAD_TRANSITIONS = {
        'QUEUED': ['UPLOADING', 'PAUSED', 'CANCELLED'],
        'UPLOADING': ['PROCESSING', 'PAUSED', 'FAILED', 'CANCELLED'],
        'PROCESSING': ['COMPLETED', 'FAILED', 'CANCELLED'],
        'PAUSED': ['UPLOADING', 'QUEUED', 'CANCELLED'],
        'FAILED': ['RETRYING', 'CANCELLED'],
        'RETRYING': ['UPLOADING', 'CANCELLED'],
        'COMPLETED': ['DELETED'],
        'CANCELLED': [],
        'DELETED': []
    };

    /**
     * Normalize any status string to UPPERCASE. This is the single gate
     * that prevents the Store/queue divergence bug where main-app.js writes
     * lowercase statuses ('cancelled') that the FSM cannot validate.
     */
    function normalizeStatus(status) {
        if (!status) return 'QUEUED';
        var upper = String(status).toUpperCase();
        var LEGACY_MAP = {
            'QUEUED': 'QUEUED',
            'UPLOADING': 'UPLOADING',
            'PROCESSING': 'PROCESSING',
            'PAUSED': 'PAUSED',
            'FAILED': 'FAILED',
            'RETRYING': 'RETRYING',
            'COMPLETED': 'COMPLETED',
            'CANCELLED': 'CANCELLED',
            'DELETED': 'DELETED',
            'ERROR': 'FAILED'
        };
        return LEGACY_MAP[upper] || upper;
    }

    function isValidTransition(curr, next) {
        if (!curr) return true;
        var normCurr = normalizeStatus(curr);
        var normNext = normalizeStatus(next);
        if (normCurr === normNext) return true;
        var allowed = UPLOAD_TRANSITIONS[normCurr] || [];
        return allowed.indexOf(normNext) !== -1;
    }

    // 2. Central Store Definition
    function LanvanStore() {
        this.state = {
            currentFolder: "",
            uploadQueue: [],
            selection: [],
            pendingOps: {},
            lastAction: null,
            navigationGeneration: 0,
            repositoryGeneration: 0,
            uploadGeneration: 0
        };
        this.listeners = [];
    }

    LanvanStore.prototype.getState = function () {
        return this.state;
    };

    LanvanStore.prototype.subscribe = function (listener) {
        if (typeof listener === 'function') {
            this.listeners.push(listener);
        }
        var self = this;
        return function unsubscribe() {
            var idx = self.listeners.indexOf(listener);
            if (idx >= 0) self.listeners.splice(idx, 1);
        };
    };

    LanvanStore.prototype.dispatch = function (type, payload) {
        if (window.__lanvanTimelineTracker) {
            window.__lanvanTimelineTracker.recordEvent("storeDispatch", type + " " + JSON.stringify(payload || {}));
            window.__lanvanTimelineTracker.recordEvent("storeAction", type);
        }
        var action = { type: type, payload: payload || {}, timestamp: Date.now() };
        var oldFolder = this.state.currentFolder;
        var oldQueueCount = this.state.uploadQueue ? this.state.uploadQueue.length : 0;
        var nextState = {
            currentFolder: this.state.currentFolder,
            uploadQueue: this.state.uploadQueue.slice(),
            selection: this.state.selection.slice(),
            pendingOps: Object.assign({}, this.state.pendingOps),
            lastAction: action,
            navigationGeneration: this.state.navigationGeneration,
            repositoryGeneration: this.state.repositoryGeneration,
            uploadGeneration: this.state.uploadGeneration
        };

        // Reducer Transformations
        switch (type) {
            case 'SET_CURRENT_FOLDER':
            case 'NAVIGATE_FOLDER':
            case 'NAVIGATION':
                var rawFolder = payload.folderPath !== undefined ? payload.folderPath : (payload.folder || "");
                var newFolder = String(rawFolder).replace(/^Home\/?/, "").replace(/^Home$/, "").replace(/^\/+|\/+$/g, "");
                if (newFolder !== this.state.currentFolder) {
                    nextState.navigationGeneration = this.state.navigationGeneration + 1;
                }
                nextState.currentFolder = newFolder;
                break;

            case 'ADD_UPLOAD_ITEM':
            case 'ADD_UPLOAD':
                var item = payload.item;
                if (item && item.id) {
                    var existingIdx = nextState.uploadQueue.findIndex(function (i) { return String(i.id) === String(item.id); });
                    var newItem = Object.assign({}, item, {
                        targetDir: item.targetDir !== undefined ? item.targetDir : "",
                        status: normalizeStatus(item.status),
                        progress: typeof item.progress === 'number' ? item.progress : 0
                    });
                    if (existingIdx >= 0) {
                        nextState.uploadQueue[existingIdx] = newItem;
                    } else {
                        nextState.uploadQueue.push(newItem);
                    }
                    nextState.uploadGeneration = (this.state.uploadGeneration || 0) + 1;
                }
                break;

            case 'UPDATE_UPLOAD_STATUS':
                var updateId = payload.id;
                var rawStatus = payload.status;
                var normStatus = normalizeStatus(rawStatus);
                var targetItem = nextState.uploadQueue.find(function (i) { return String(i.id) === String(updateId); });
                if (targetItem && isValidTransition(targetItem.status, normStatus)) {
                    targetItem.status = normStatus;
                    if (typeof payload.progress === 'number') targetItem.progress = payload.progress;
                    if (payload.error !== undefined) targetItem.error = payload.error;
                    nextState.uploadGeneration = (this.state.uploadGeneration || 0) + 1;
                }
                break;

            case 'BATCH_UPDATE_UPLOADS':
                if (Array.isArray(payload.items)) {
                    var changed = false;
                    for (var bi = 0; bi < payload.items.length; bi++) {
                        var upd = payload.items[bi];
                        if (!upd || !upd.id) continue;
                        var bt = nextState.uploadQueue.find(function (i) { return String(i.id) === String(upd.id); });
                        if (bt) {
                            var ns = normalizeStatus(upd.status || bt.status);
                            if (isValidTransition(bt.status, ns)) {
                                bt.status = ns;
                                if (typeof upd.progress === 'number') bt.progress = upd.progress;
                                if (upd.error !== undefined) bt.error = upd.error;
                                changed = true;
                            }
                        }
                    }
                    if (changed) {
                        nextState.uploadGeneration = (this.state.uploadGeneration || 0) + 1;
                    }
                }
                break;

            case 'CANCEL_UPLOAD':
                var cancelId = payload.id;
                var cancelItemIndex = nextState.uploadQueue.findIndex(function (i) { return String(i.id) === String(cancelId); });
                var cancelItem = cancelItemIndex >= 0 ? nextState.uploadQueue[cancelItemIndex] : null;
                if (cancelItem && isValidTransition(cancelItem.status, 'CANCELLED')) {
                    cancelItem.status = 'CANCELLED';
                    nextState.uploadGeneration = (this.state.uploadGeneration || 0) + 1;
                }
                break;

            case 'CLEAR_COMPLETED_UPLOADS':
                nextState.uploadQueue = nextState.uploadQueue.filter(function (item) {
                    return item && item.status !== 'COMPLETED' && item.status !== 'DELETED';
                });
                nextState.uploadGeneration = (this.state.uploadGeneration || 0) + 1;
                break;

            case 'SYNC_QUEUE':
                if (Array.isArray(payload.queue)) {
                    nextState.uploadQueue = payload.queue.slice();
                    nextState.uploadGeneration = (this.state.uploadGeneration || 0) + 1;
                }
                break;

            case 'SET_SELECTION':
                var selectionList = Array.isArray(payload.selection) ? payload.selection : (Array.isArray(payload.files) ? payload.files : []);
                nextState.selection = selectionList.slice();
                break;

            case 'CLEAR_SELECTION':
                nextState.selection = [];
                break;
        }

        this.state = nextState;

        if (window.__lanvanTimelineTracker) {
            window.__lanvanTimelineTracker.checkMutation("LanvanStore", "dispatch", "state-store.js", 311, type, "currentFolder", oldFolder, nextState.currentFolder);
            window.__lanvanTimelineTracker.checkMutation("LanvanStore", "dispatch", "state-store.js", 311, type, "uploadQueue.length", oldQueueCount, nextState.uploadQueue.length);
        }

        // INVARIANT GUARD (DEBUG only): Verify upload state machine integrity.
        // Every upload item must have exactly one valid UPPERCASE status.
        if (window.DEBUG_MODE) {
            var seenIds = {};
            for (var vi = 0; vi < this.state.uploadQueue.length; vi++) {
                var vItem = this.state.uploadQueue[vi];
                if (!vItem || !vItem.id) continue;
                var vStatus = vItem.status;
                if (!vStatus || vStatus !== vStatus.toUpperCase()) {
                    console.error('[INVARIANT FAILED] Upload item has invalid status: ' + vStatus, vItem);
                }
                if (seenIds[vItem.id]) {
                    console.error('[INVARIANT FAILED] Duplicate upload ID in queue: ' + vItem.id);
                }
                seenIds[vItem.id] = true;
            }
        }

        // Synchronize legacy window properties safely for backward compatibility
        try {
            window.uploadQueue = this.state.uploadQueue;
        } catch (e) {}

        // Notify Subscribers
        for (var i = 0; i < this.listeners.length; i++) {
            try {
                this.listeners[i](this.state, action);
            } catch (err) {
                console.error("  [STORE LISTENER ERROR]:", err);
            }
        }

        return action;
    };

    // Instantiate Single Store Instance
    var storeInstance = new LanvanStore();
    window.LanvanStore = storeInstance;

    // Direct property bindings
    try {
        Object.defineProperty(window, 'currentFolderPath', {
            get: function () { return storeInstance.state.currentFolder; },
            set: function (val) { storeInstance.dispatch('SET_CURRENT_FOLDER', { folderPath: val }); },
            configurable: true
        });
    } catch (e) {}

    // DevTools API
    window.__LANVAN_DEVTOOLS__ = {
        dumpStore: function () { return storeInstance.state; },
        dumpQueue: function () { return storeInstance.state.uploadQueue; }
    };

})(window);