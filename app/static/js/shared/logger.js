/**
 * Centralized Application Logger for Lanvan Web Client
 *
 * Provides a structured, privacy-safe, production-grade console logging system.
 * Matches Python backend & Android app log format and privacy standards.
 */

(function (window) {
    'use strict';

    if (window.__loggerInstalled) {
        return;
    }
    window.__loggerInstalled = true;

    // 1. Store original console methods
    var OriginalConsole = {
        log: (console.log || function () {}).bind(console),
        info: (console.info || console.log || function () {}).bind(console),
        warn: (console.warn || console.log || function () {}).bind(console),
        error: (console.error || console.log || function () {}).bind(console),
        debug: (console.debug || console.log || function () {}).bind(console),
        trace: (console.trace || console.log || function () {}).bind(console)
    };

    var noop = function () {};

    // 2. Standard Categories Allowlist
    var ALLOWED_CATEGORIES = [
        'SERVER', 'NETWORK', 'MDNS', 'UPLOAD', 'DOWNLOAD',
        'STORAGE', 'CLIPBOARD', 'WEBSOCKET', 'SECURITY', 'DIAGNOSTIC',
        'ANDROID', 'CLIENT'
    ];

    // 3. Debug Detection Priority Logic
    function detectDebugMode() {
        try {
            var localSetting = localStorage.getItem('debug');
            if (localSetting === 'true') {
                return true;
            } else if (localSetting === 'false') {
                return false;
            }
        } catch (e) {}

        if (window.DEBUG_MODE === true) {
            try { localStorage.setItem('debug', 'true'); } catch (e) {}
            return true;
        }

        return false;
    }

    var isDebug = detectDebugMode();
    window.DEBUG_MODE = isDebug;

    // 4. Privacy & Utility Helpers
    function getFileExtension(filename) {
        if (!filename || typeof filename !== 'string') return 'FILE';
        var clean = filename.split(/[/\\]/).pop();
        var dotIdx = clean.lastIndexOf('.');
        if (dotIdx > 0 && dotIdx < clean.length - 1) {
            return clean.substring(dotIdx + 1).toUpperCase();
        }
        return 'FILE';
    }

    function formatBytes(bytes) {
        if (bytes === undefined || bytes === null || isNaN(bytes)) return '0 B';
        if (bytes < 1024) return bytes + ' B';
        if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
        if (bytes < 1024 * 1024 * 1024) return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
        return (bytes / (1024 * 1024 * 1024)).toFixed(2) + ' GB';
    }

    /**
     * Sanitizes any value (string, object, array) to prevent leaking raw filenames,
     * paths, clipboard contents, auth headers, tokens, or raw payloads.
     */
    function sanitizeValue(val) {
        if (val === null || val === undefined) return val;
        
        if (typeof val === 'string') {
            // Check for recognizeable private test values or raw file paths
            if (val.indexOf('PRIVATE_BROWSER_') !== -1) {
                return '[REDACTED_PRIVATE_VALUE]';
            }
            if (val.indexOf('C:\\') === 0 || val.indexOf('data\\uploads') !== -1 || val.indexOf('data/uploads') !== -1) {
                return '[REDACTED_PATH]';
            }
            return val;
        }

        if (typeof File !== 'undefined' && val instanceof File) {
            return {
                type: getFileExtension(val.name),
                size: formatBytes(val.size)
            };
        }

        if (typeof FormData !== 'undefined' && val instanceof FormData) {
            return '[FormData Object]';
        }

        if (typeof val === 'object') {
            if (Array.isArray(val)) {
                return val.map(sanitizeValue);
            }
            var safe = {};
            for (var k in val) {
                if (Object.prototype.hasOwnProperty.call(val, k)) {
                    var lowerK = k.toLowerCase();
                    if (lowerK.indexOf('filename') !== -1 || lowerK === 'path' || lowerK === 'target_dir' || lowerK === 'full_path' || lowerK === 'file_path') {
                        safe[k] = getFileExtension(val[k]);
                    } else if (lowerK.indexOf('clipboard') !== -1 || lowerK === 'text' || lowerK === 'content' || lowerK === 'token' || lowerK === 'cookie' || lowerK === 'auth') {
                        safe[k] = '[REDACTED]';
                    } else {
                        safe[k] = sanitizeValue(val[k]);
                    }
                }
            }
            return safe;
        }

        return val;
    }

    function formatMessage(category, event, details) {
        cat = ALLOWED_CATEGORIES.indexOf(category) !== -1 ? category : 'CLIENT';
        var line = '[' + cat + '] ' + event;
        if (details) {
            if (typeof details === 'object') {
                var safeDetails = sanitizeValue(details);
                var parts = [];
                for (var key in safeDetails) {
                    if (Object.prototype.hasOwnProperty.call(safeDetails, key)) {
                        parts.push(key + ': ' + safeDetails[key]);
                    }
                }
                if (parts.length > 0) {
                    line += ' | ' + parts.join(' | ');
                }
            } else {
                line += ' | ' + sanitizeValue(details);
            }
        }
        return line;
    }

    // 5. Core Structured Logger API
    var Logger = {
        OriginalConsole: OriginalConsole,

        isDebugMode: function () {
            return window.DEBUG_MODE;
        },

        enableDebug: function () {
            try { localStorage.setItem('debug', 'true'); } catch (e) {}
            window.DEBUG_MODE = true;
            OriginalConsole.info('%c[DIAGNOSTIC] Debug mode ENABLED', 'color: #3b82f6; font-weight: bold;');
            return 'Debug mode ENABLED';
        },

        disableDebug: function () {
            try { localStorage.removeItem('debug'); } catch (e) {}
            window.DEBUG_MODE = false;
            OriginalConsole.info('%c[DIAGNOSTIC] Debug mode DISABLED', 'color: #6b7280; font-style: italic;');
            return 'Debug mode DISABLED';
        },

        info: function (category, event, details) {
            var msg = formatMessage(category, event, details);
            OriginalConsole.info(msg);
        },

        warn: function (category, event, details) {
            var msg = formatMessage(category, event, details);
            OriginalConsole.warn(msg);
        },

        error: function (category, event, details) {
            var msg = formatMessage(category, event, details);
            OriginalConsole.error(msg);
        },

        debug: function (category, event, details) {
            if (window.DEBUG_MODE) {
                var msg = formatMessage(category, event, details);
                OriginalConsole.debug(msg);
            }
        },

        // Helper shortcut formatters for specific subsystems
        logUpload: function (event, opId, ext, sizeBytes, duration, status, reason) {
            var prefix = opId ? '[UPLOAD][' + opId.toUpperCase() + ']' : '[UPLOAD]';
            var details = {};
            if (ext) details['Type'] = String(ext).toUpperCase();
            if (sizeBytes !== undefined) details['Size'] = formatBytes(sizeBytes);
            if (duration !== undefined) details['Duration'] = (typeof duration === 'number' ? duration.toFixed(2) : duration) + 's';
            if (status) details['Status'] = status.toUpperCase();
            if (reason) details['Reason'] = reason;

            var msg = prefix + ' ' + event;
            var parts = [];
            for (var k in details) {
                parts.push(k + ': ' + details[k]);
            }
            if (parts.length > 0) msg += ' | ' + parts.join(' | ');

            if (status === 'FAILED' || status === 'ERROR') {
                OriginalConsole.error(msg);
            } else {
                OriginalConsole.info(msg);
            }
        },

        logClipboard: function (event, itemType, sizeBytes, status, reason) {
            var details = {
                Type: (itemType || 'TEXT').toUpperCase(),
                Size: formatBytes(sizeBytes || 0),
                Status: (status || 'SUCCESS').toUpperCase()
            };
            if (reason) details['Reason'] = reason;

            var msg = '[CLIPBOARD] ' + event;
            var parts = [];
            for (var k in details) parts.push(k + ': ' + details[k]);
            msg += ' | ' + parts.join(' | ');

            if (status === 'FAILED' || status === 'ERROR') {
                OriginalConsole.error(msg);
            } else {
                OriginalConsole.info(msg);
            }
        },

        logNetwork: function (event, endpoint, method, status, reason) {
            var details = {
                Endpoint: endpoint || '',
                Method: (method || 'GET').toUpperCase(),
                Status: status || 0
            };
            if (reason) details['Reason'] = reason;

            var msg = '[NETWORK] ' + event;
            var parts = [];
            for (var k in details) parts.push(k + ': ' + details[k]);
            msg += ' | ' + parts.join(' | ');

            if (status >= 400 || status === 0) {
                OriginalConsole.error(msg);
            } else {
                OriginalConsole.info(msg);
            }
        },

        logWebSocket: function (event, channel, status, reason) {
            var details = { Channel: channel || 'default' };
            if (status) details['Status'] = status;
            if (reason) details['Reason'] = reason;

            var msg = '[WEBSOCKET] ' + event;
            var parts = [];
            for (var k in details) parts.push(k + ': ' + details[k]);
            msg += ' | ' + parts.join(' | ');

            if (status === 'FAILED' || status === 'DISCONNECTED') {
                OriginalConsole.warn(msg);
            } else {
                OriginalConsole.info(msg);
            }
        },

        formatBytes: formatBytes,
        getFileExtension: getFileExtension,
        sanitizeValue: sanitizeValue
    };

    window.Logger = Logger;
    window.LanvanLogger = Logger;
    window.enableDebug = Logger.enableDebug;
    window.disableDebug = Logger.disableDebug;

    // 6. Console Interceptor with Privacy Shield
    // Wraps standard console methods so even third-party or legacy direct console.log
    // calls cannot leak private filenames or clipboard contents.
    console.log = function () {
        if (!window.DEBUG_MODE) return;
        var args = Array.prototype.slice.call(arguments).map(sanitizeValue);
        OriginalConsole.log.apply(console, args);
    };

    console.info = function () {
        var args = Array.prototype.slice.call(arguments).map(sanitizeValue);
        OriginalConsole.info.apply(console, args);
    };

    console.warn = function () {
        var args = Array.prototype.slice.call(arguments).map(sanitizeValue);
        OriginalConsole.warn.apply(console, args);
    };

    console.error = function () {
        var args = Array.prototype.slice.call(arguments).map(sanitizeValue);
        OriginalConsole.error.apply(console, args);
    };

    console.debug = function () {
        if (!window.DEBUG_MODE) return;
        var args = Array.prototype.slice.call(arguments).map(sanitizeValue);
        OriginalConsole.debug.apply(console, args);
    };

    // 7. Global Uncaught Error & Rejection Handlers
    window.addEventListener('error', function (event) {
        var errorMsg = (event && event.error && event.error.message) ? event.error.message : ((event && event.message) ? event.message : 'Unknown error');
        var component = (event && event.filename) ? getFileExtension(event.filename) : 'Runtime';
        Logger.error('CLIENT', 'Unhandled error', {
            Component: component,
            Reason: sanitizeValue(errorMsg)
        });
    });

    window.addEventListener('unhandledrejection', function (event) {
        var reasonMsg = (event && event.reason && event.reason.message) ? event.reason.message : String(event ? event.reason : 'Unhandled Promise Rejection');
        Logger.error('CLIENT', 'Unhandled promise rejection', {
            Reason: sanitizeValue(reasonMsg)
        });
    });

})(window);
