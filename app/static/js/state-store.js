/**
 * Lanvan Unidirectional Architecture: Central Store & Action Queue
 * Implements Action Queue, Upload State Machine, Pure Reducers, and DevTools.
 */

(function (window) {
    'use strict';

    // 1. Upload State Machine: Defines valid status transitions
    var UPLOAD_STATE_TRANSITIONS = {
        'NEW': ['QUEUED', 'CANCELLED'],
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

    function isValidUploadTransition(currentStatus, nextStatus) {
        if (!currentStatus) return true; // Initial creation
        if (currentStatus === nextStatus) return true; // Idempotent
        var allowed = UPLOAD_STATE_TRANSITIONS[currentStatus] || [];
        return allowed.indexOf(nextStatus) !== -1;
    }

    // 2. Action Queue: Priority-sorted queue (HIGH vs LOW) with transaction tracing
    function ActionQueue(store) {
        this.store = store;
        this.queue = [];
        this.isProcessing = false;
        this.actionCounter = 0;
    }

    ActionQueue.prototype.dispatch = function (type, payload, priority) {
        var isHighPriority = priority === 'HIGH' || type === 'NAVIGATION' || type === 'DELETE_FILE' || type === 'CANCEL_UPLOAD' || type === 'RENAME_FILE';
        var action = {
            id: 'act_' + Date.now() + '_' + (++this.actionCounter),
            timestamp: Date.now(),
            type: type,
            payload: payload || {},
            priority: isHighPriority ? 'HIGH' : 'LOW'
        };

        if (isHighPriority) {
            // High priority actions jump ahead of low-priority progress ticks
            var insertIdx = this.queue.length;
            for (var i = 0; i < this.queue.length; i++) {
                if (this.queue[i].priority === 'LOW') {
                    insertIdx = i;
                    break;
                }
            }
            this.queue.splice(insertIdx, 0, action);
        } else {
            this.queue.push(action);
        }

        this.processNext();
        return action.id;
    };

    ActionQueue.prototype.processNext = function () {
        if (this.isProcessing || this.queue.length === 0) return;
        this.isProcessing = true;

        while (this.queue.length > 0) {
            var action = this.queue.shift();
            try {
                this.store._reduce(action);
            } catch (err) {
                console.error("  [ACTION ERROR] Reducer failed for action '" + action.type + "':", err);
            }
        }

        this.isProcessing = false;
    };

    // 3. Central Store & Pure Domain Reducers
    function LanvanStore() {
        this.state = {
            currentFolder: "",
            uploadQueue: [],
            selection: [],
            pendingOps: {},
            lastActionId: null
        };
        this.actionHistory = [];
        this.maxHistory = 100;
        this.listeners = [];
        this.actionQueue = new ActionQueue(this);
    }

    LanvanStore.prototype.dispatch = function (type, payload, priority) {
        return this.actionQueue.dispatch(type, payload, priority);
    };

    LanvanStore.prototype.getState = function () {
        return this.state;
    };

    LanvanStore.prototype.subscribe = function (listener) {
        if (typeof listener === 'function') {
            this.listeners.push(listener);
        }
    };

    LanvanStore.prototype._reduce = function (action) {
        // Record action history for DevTools tracing
        this.actionHistory.push(action);
        if (this.actionHistory.length > this.maxHistory) {
            this.actionHistory.shift();
        }

        var nextState = {
            currentFolder: this.state.currentFolder,
            uploadQueue: this.state.uploadQueue.slice(),
            selection: this.state.selection.slice(),
            pendingOps: Object.assign({}, this.state.pendingOps),
            lastActionId: action.id
        };

        // Delegate to Domain Reducers
        nextState.currentFolder = FolderReducer(nextState.currentFolder, action);
        nextState.uploadQueue = UploadReducer(nextState.uploadQueue, action);
        nextState.selection = SelectionReducer(nextState.selection, action);
        nextState.pendingOps = PendingOpsReducer(nextState.pendingOps, action);

        this.state = nextState;

        // Notify subscribers (Render Scheduler / Projection)
        for (var i = 0; i < this.listeners.length; i++) {
            try {
                this.listeners[i](this.state, action);
            } catch (err) {
                console.error("  [STORE LISTENER ERROR]:", err);
            }
        }
    };

    // Domain Reducer: Folder Navigation
    function FolderReducer(currentFolder, action) {
        if (action.type === 'NAVIGATION' || action.type === 'NAVIGATE_FOLDER') {
            var raw = action.payload.folderPath || "";
            return raw.replace(/^Home\/?/, "").replace(/^Home$/, "");
        }
        return currentFolder;
    }

    // Domain Reducer: Upload Queue
    function UploadReducer(queue, action) {
        if (action.type === 'ADD_UPLOAD') {
            var item = action.payload.item;
            if (!item || !item.id) return queue;
            var targetDir = item.targetDir !== undefined ? item.targetDir : "";
            var existingIdx = queue.findIndex(function(i){ return i.id === item.id; });
            var newItem = Object.assign({}, item, {
                targetDir: targetDir,
                status: item.status || 'QUEUED'
            });
            if (existingIdx >= 0) {
                queue[existingIdx] = newItem;
            } else {
                queue.push(newItem);
            }
        } else if (action.type === 'UPDATE_UPLOAD_STATUS') {
            var id = action.payload.id;
            var nextStatus = action.payload.status;
            var target = queue.find(function(i){ return String(i.id) === String(id); });
            if (target && isValidUploadTransition(target.status, nextStatus)) {
                target.status = nextStatus;
                if (action.payload.progress !== undefined) target.progress = action.payload.progress;
                if (action.payload.error !== undefined) target.error = action.payload.error;
            }
        } else if (action.type === 'CANCEL_UPLOAD') {
            var cancelId = action.payload.id;
            var cancelItem = queue.find(function(i){ return String(i.id) === String(cancelId); });
            if (cancelItem && isValidUploadTransition(cancelItem.status, 'CANCELLED')) {
                cancelItem.status = 'CANCELLED';
                cancelItem.error = 'Cancelled by user';
            }
        } else if (action.type === 'SYNC_QUEUE') {
            return (action.payload.queue || []).slice();
        }
        return queue;
    }

    // Domain Reducer: Selection State
    function SelectionReducer(selection, action) {
        if (action.type === 'SET_SELECTION') {
            return (action.payload.selection || []).slice();
        } else if (action.type === 'CLEAR_SELECTION') {
            return [];
        }
        return selection;
    }

    // Domain Reducer: Pending Operations (Optimistic UI)
    function PendingOpsReducer(pendingOps, action) {
        if (action.type === 'START_PENDING_OP') {
            var opId = action.payload.id;
            if (opId) {
                pendingOps[opId] = action.payload;
            }
        } else if (action.type === 'CLEAR_PENDING_OP') {
            delete pendingOps[action.payload.id];
        }
        return pendingOps;
    }

    // Instantiate Store
    var storeInstance = new LanvanStore();

    // 4. Lanvan DevTools Inspector Commands
    window.__LANVAN_DEVTOOLS__ = {
        dumpStore: function () {
            console.log("=== LANVAN STORE SNAPSHOT ===", storeInstance.state);
            return storeInstance.state;
        },
        dumpUploads: function () {
            console.table(storeInstance.state.uploadQueue);
            return storeInstance.state.uploadQueue;
        },
        dumpHistory: function () {
            console.table(storeInstance.actionHistory);
            return storeInstance.actionHistory;
        },
        verifyInvariants: function () {
            var curr = storeInstance.state.currentFolder;
            var violations = 0;
            storeInstance.state.uploadQueue.forEach(function (i) {
                if (i.status === 'UPLOADING' && i.targetDir !== curr) {
                    console.warn("  [INVARIANT WARNING] Upload running for targetDir '" + i.targetDir + "' while viewing '" + curr + "'");
                }
            });
            console.log("Invariant Check Complete: " + violations + " errors found.");
            return violations === 0;
        },
        traceAction: function (actionId) {
            var found = storeInstance.actionHistory.find(function (a) { return a.id === actionId; });
            console.log("Trace Action [" + actionId + "]:", found);
            return found;
        }
    };

    window.LanvanStore = storeInstance;

})(window);
