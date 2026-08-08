/**
 * @file ui-events-ws.js
 * @description Dedicated, isolated WebSocket client for presentation-layer UI events (toasts, presence, notifications, themes, banners).
 * @module UIEventsWS
 * 
 * Rules:
 * - Single Responsibility: presentation-layer events ONLY.
 * - NEVER refreshes file lists, mutates Repository, or touches upload status.
 * - Standardized event envelope parsing.
 * - Map-based event dispatcher.
 * - Exponential backoff auto-reconnect with strict timer cleanup.
 * - Debug inspection panel (`UIEventsWS.debug()`).
 */

(function (window) {
    'use strict';

    if (window.UIEventsWS) {
        return;
    }

    var STATE = Object.freeze({
        DISCONNECTED: 'Disconnected',
        CONNECTING: 'Connecting',
        CONNECTED: 'Connected',
        RECONNECTING: 'Reconnecting'
    });

    var TYPES = Object.freeze({
        TOAST: 'ui.toast',
        PRESENCE: 'ui.presence',
        CONNECTION: 'ui.connection',
        BANNER: 'ui.banner',
        DIALOG: 'ui.dialog',
        NOTIFICATION: 'ui.notification',
        THEME: 'ui.theme',
        SETTINGS: 'ui.settings'
    });

    var socket = null;
    var currentState = STATE.DISCONNECTED;
    var reconnectAttempts = 0;
    var reconnectTimer = null;
    var pingIntervalTimer = null;
    var lastHeartbeatTime = null;

    // Diagnostic metrics
    var metrics = {
        messagesSent: 0,
        messagesReceived: 0,
        errorsObserved: 0
    };

    // Use Map for clean dynamic registration & removal
    var handlers = new Map();

    // Default UI presentation handlers
    function defaultToastHandler(payload) {
        if (!payload) return;
        var msg = payload.message || payload.title || payload.text;
        if (!msg) return;
        var type = payload.level || payload.type || 'info';
        if (typeof window.showToast === 'function') {
            window.showToast(msg, type);
        } else if (typeof console !== 'undefined' && console.log) {
            console.log('[UI EVENTS TOAST]', type.toUpperCase() + ':', msg);
        }
    }

    function defaultPresenceHandler(payload) {
        if (typeof console !== 'undefined' && console.log) {
            console.log('[UI EVENTS PRESENCE]', payload);
        }
    }

    function defaultConnectionHandler(payload) {
        if (typeof console !== 'undefined' && console.log) {
            console.log('[UI EVENTS CONNECTION]', payload);
        }
    }

    /**
     * Handles the server_shutdown event broadcast before the server stops.
     *
     * Clears all client-side state, cancels reconnect timers and polling
     * intervals, and updates the UI to reflect that the server is no longer
     * running. This prevents stale "Running" UI, orphaned intervals, and
     * infinite reconnect loops.
     */
    function shutdownHandler(payload) {
        if (typeof window.showToast === 'function') {
            window.showToast('Server stopped. You may restart it from the app.', 6000);
        }

        // 1. Cancel WebSocket reconnect timers so we don't keep trying
        //    to reach a server that intentionally shut down.
        clearReconnectTimer();
        stopHeartbeat();
        if (socket) {
            try { socket.close(); } catch (ignored) { }
            socket = null;
        }
        setState(STATE.DISCONNECTED);
        reconnectAttempts = 0;

        // 2. Clear upload tray polling interval
        if (window._uploadTrayInterval) {
            clearInterval(window._uploadTrayInterval);
            window._uploadTrayInterval = null;
        }

        // 3. Clear state store so the file list, upload queue, and
        //    selection don't show stale data when the app reopens.
        if (window.LanvanStore && typeof window.LanvanStore.dispatch === 'function') {
            window.LanvanStore.dispatch('SYNC_QUEUE', { queue: [] });
        }
        window.uploadQueue = [];

        // 4. Clear cached network info (QR code, LAN URL, mDNS data)
        window._currentNetworkInfo = null;

        // 5. Clear clipboard cache
        window.clipboardHistoryData = [];

        // 6. Update UI to stopped state if the helper is available
        if (typeof window.updateSelectionToolbar === 'function') {
            window.updateSelectionToolbar();
        }
    }

    // Initialize Map registry with default presentation handlers
    handlers.set(TYPES.TOAST, defaultToastHandler);
    handlers.set(TYPES.PRESENCE, defaultPresenceHandler);
    handlers.set(TYPES.CONNECTION, defaultConnectionHandler);
    handlers.set('server_shutdown', shutdownHandler);

    function registerHandler(type, fn) {
        if (typeof type === 'string' && typeof fn === 'function') {
            handlers.set(type, fn);
        }
    }

    function unregisterHandler(type) {
        if (typeof type === 'string') {
            handlers.delete(type);
        }
    }

    function setState(newState) {
        currentState = newState;
    }

    function getWebSocketUrl() {
        var loc = window.location;
        var protocol = loc.protocol === 'https:' ? 'wss:' : 'ws:';
        return protocol + '//' + loc.host + '/ws/ui-events';
    }

    function stopHeartbeat() {
        if (pingIntervalTimer) {
            clearInterval(pingIntervalTimer);
            pingIntervalTimer = null;
        }
    }

    function startHeartbeat() {
        stopHeartbeat();
        pingIntervalTimer = setInterval(function () {
            if (socket && socket.readyState === WebSocket.OPEN) {
                try {
                    socket.send(JSON.stringify({ type: 'ping', timestamp: Math.floor(Date.now() / 1000) }));
                    metrics.messagesSent++;
                } catch (e) {
                    metrics.errorsObserved++;
                    console.warn('[WS UI EVENTS] Heartbeat ping send failed:', e);
                }
            }
        }, 25000);
    }

    function clearReconnectTimer() {
        if (reconnectTimer) {
            clearTimeout(reconnectTimer);
            reconnectTimer = null;
        }
    }

    function scheduleReconnect() {
        clearReconnectTimer();
        setState(STATE.RECONNECTING);

        // Exponential backoff: 1s, 2s, 4s, 8s, 16s, max 30s
        var delay = Math.min(30000, Math.pow(2, reconnectAttempts) * 1000);
        reconnectAttempts++;

        reconnectTimer = setTimeout(function () {
            reconnectTimer = null;
            connect();
        }, delay);
    }

    function dispatchEnvelope(envelope) {
        if (!envelope || typeof envelope !== 'object') return;
        var type = envelope.type;
        if (!type) return;

        if (type === 'pong') {
            lastHeartbeatTime = new Date().toISOString();
            return;
        }

        var handler = handlers.get(type);
        if (typeof handler === 'function') {
            try {
                handler(envelope.payload || {}, envelope);
            } catch (err) {
                metrics.errorsObserved++;
                console.error('[WS UI EVENTS] Error executing handler for ' + type + ':', err);
            }
        }
    }

    function connect() {
        if (socket && (socket.readyState === WebSocket.CONNECTING || socket.readyState === WebSocket.OPEN)) {
            return;
        }

        // Clean up previous socket if existing in closed/closing state
        if (socket) {
            try { socket.close(); } catch (e) { }
            socket = null;
        }

        setState(reconnectAttempts > 0 ? STATE.RECONNECTING : STATE.CONNECTING);
        var wsUrl = getWebSocketUrl();

        try {
            socket = new WebSocket(wsUrl);
        } catch (e) {
            metrics.errorsObserved++;
            console.warn('[WS UI EVENTS] WebSocket initialization failed:', e);
            scheduleReconnect();
            return;
        }

        socket.onopen = function () {
            console.log('[WS UI EVENTS] 🟢 Connected to UI Events WebSocket');
            setState(STATE.CONNECTED);
            reconnectAttempts = 0;
            clearReconnectTimer();
            startHeartbeat();
        };

        socket.onmessage = function (event) {
            metrics.messagesReceived++;
            try {
                var envelope = JSON.parse(event.data);
                dispatchEnvelope(envelope);
            } catch (err) {
                metrics.errorsObserved++;
                console.warn('[WS UI EVENTS] Malformed packet received:', event.data);
            }
        };

        socket.onerror = function () {
            metrics.errorsObserved++;
            console.warn('[WS UI EVENTS] Socket error observed');
        };

        socket.onclose = function (event) {
            stopHeartbeat();
            socket = null;
            setState(STATE.DISCONNECTED);
            console.log('[WS UI EVENTS] 🔴 Disconnected from UI Events WebSocket (code: ' + event.code + ')');
            scheduleReconnect();
        };
    }

    function sendEvent(type, payload) {
        if (!socket || socket.readyState !== WebSocket.OPEN) {
            console.warn('[WS UI EVENTS] Cannot send event - socket not open');
            return false;
        }
        try {
            var envelope = {
                version: 1,
                type: type,
                timestamp: Math.floor(Date.now() / 1000),
                payload: payload || {}
            };
            socket.send(JSON.stringify(envelope));
            metrics.messagesSent++;
            return true;
        } catch (e) {
            metrics.errorsObserved++;
            console.warn('[WS UI EVENTS] Send failed:', e);
            return false;
        }
    }

    function disconnect() {
        stopHeartbeat();
        clearReconnectTimer();
        if (socket) {
            try {
                socket.close();
            } catch (e) { }
            socket = null;
        }
        setState(STATE.DISCONNECTED);
    }

    function debugInfo() {
        var handlerKeys = [];
        handlers.forEach(function (v, key) { handlerKeys.push(key); });
        return {
            state: currentState,
            reconnectAttempts: reconnectAttempts,
            lastHeartbeat: lastHeartbeatTime,
            metrics: Object.assign({}, metrics),
            registeredHandlers: handlerKeys
        };
    }

    // Auto-connect on page load
    if (document.readyState === 'complete' || document.readyState === 'interactive') {
        setTimeout(connect, 100);
    } else {
        window.addEventListener('DOMContentLoaded', function () {
            setTimeout(connect, 100);
        });
    }

    // Expose public API
    window.UIEventsWS = Object.freeze({
        connect: connect,
        disconnect: disconnect,
        sendEvent: sendEvent,
        registerHandler: registerHandler,
        unregisterHandler: unregisterHandler,
        getState: function () { return currentState; },
        debug: debugInfo,
        TYPES: TYPES,
        STATE: STATE
    });

})(window);
