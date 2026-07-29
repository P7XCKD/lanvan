/**
 * Lanvan Clean Single-Store Architecture: Central State Store (state-store.js)
 * Implements authoritative state repository for currentFolder, uploadQueue, selection, and subscribers.
 */

(function (window) {
    'use strict';

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

    function isValidTransition(curr, next) {
        if (!curr) return true;
        if (curr === next) return true;
        var allowed = UPLOAD_TRANSITIONS[curr] || [];
        return allowed.indexOf(next) !== -1;
    }

    // 2. Central Store Definition
    function LanvanStore() {
        this.state = {
            currentFolder: "",
            uploadQueue: [],
            selection: [],
            pendingOps: {},
            lastAction: null
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
        var action = { type: type, payload: payload || {}, timestamp: Date.now() };
        var nextState = {
            currentFolder: this.state.currentFolder,
            uploadQueue: this.state.uploadQueue.slice(),
            selection: this.state.selection.slice(),
            pendingOps: Object.assign({}, this.state.pendingOps),
            lastAction: action
        };

        // Reducer Transformations
        switch (type) {
            case 'SET_CURRENT_FOLDER':
            case 'NAVIGATE_FOLDER':
            case 'NAVIGATION':
                var rawFolder = payload.folderPath !== undefined ? payload.folderPath : (payload.folder || "");
                nextState.currentFolder = String(rawFolder).replace(/^Home\/?/, "").replace(/^Home$/, "").replace(/^\/+|\/+$/g, "");
                break;

            case 'ADD_UPLOAD_ITEM':
            case 'ADD_UPLOAD':
                var item = payload.item;
                if (item && item.id) {
                    var existingIdx = nextState.uploadQueue.findIndex(function (i) { return String(i.id) === String(item.id); });
                    var newItem = Object.assign({}, item, {
                        targetDir: item.targetDir !== undefined ? item.targetDir : "",
                        status: item.status || 'QUEUED',
                        progress: typeof item.progress === 'number' ? item.progress : 0
                    });
                    if (existingIdx >= 0) {
                        nextState.uploadQueue[existingIdx] = newItem;
                    } else {
                        nextState.uploadQueue.push(newItem);
                    }
                }
                break;

            case 'UPDATE_UPLOAD_STATUS':
                var id = payload.id;
                var nextStatus = payload.status;
                var target = nextState.uploadQueue.find(function (i) { return String(i.id) === String(id); });
                if (target && isValidTransition(target.status, nextStatus)) {
                    target.status = nextStatus;
                    if (typeof payload.progress === 'number') target.progress = payload.progress;
                    if (payload.error !== undefined) target.error = payload.error;
                }
                break;

            case 'CANCEL_UPLOAD':
                var cancelId = payload.id;
                var cancelItemIndex = nextState.uploadQueue.findIndex(function (i) { return String(i.id) === String(cancelId); });
                var cancelItem = cancelItemIndex >= 0 ? nextState.uploadQueue[cancelItemIndex] : null;
                if (cancelItem && isValidTransition(cancelItem.status, 'CANCELLED')) {
                    cancelItem.status = 'CANCELLED';
                    cancelItem.error = 'Cancelled by user';
                    nextState.uploadQueue.splice(cancelItemIndex, 1);
                }
                break;

            case 'CLEAR_COMPLETED_UPLOADS':
                nextState.uploadQueue = nextState.uploadQueue.filter(function (item) {
                    return item && item.status !== 'completed' && item.status !== 'deleted';
                });
                break;

            case 'SYNC_QUEUE':
                if (Array.isArray(payload.queue)) {
                    nextState.uploadQueue = payload.queue.slice();
                }
                break;

            case 'SET_SELECTION':
                nextState.selection = Array.isArray(payload.selection) ? payload.selection.slice() : [];
                break;

            case 'CLEAR_SELECTION':
                nextState.selection = [];
                break;
        }

        this.state = nextState;

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
