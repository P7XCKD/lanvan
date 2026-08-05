/**
 * @file logger.js
 * @description Centralized, safe, toggleable production logging system for Lanvan application.
 *              Suppresses dev debug console outputs in production while preserving console.warn,
 *              console.error, uncaught exceptions, promise rejections, and network/browser errors.
 * @module Logger
 */

(function (window) {
    'use strict';

    if (window.__loggerInstalled) {
        return;
    }
    window.__loggerInstalled = true;

    // 1. Store original console methods once to prevent double-wrapping or recursion
    var OriginalConsole = {
        log: console.log.bind(console),
        info: (console.info || console.log).bind(console),
        debug: (console.debug || console.log).bind(console),
        trace: (console.trace || console.log).bind(console),
        table: (console.table || console.log).bind(console),
        group: (console.group || console.log).bind(console),
        groupCollapsed: (console.groupCollapsed || console.log).bind(console),
        groupEnd: (console.groupEnd || console.log).bind(console),
        time: (console.time || console.log).bind(console),
        timeEnd: (console.timeEnd || console.log).bind(console),
        warn: console.warn.bind(console),
        error: console.error.bind(console)
    };

    var noop = function () {};

    function restoreConsole() {
        console.log = OriginalConsole.log;
        console.info = OriginalConsole.info;
        console.debug = OriginalConsole.debug;
        console.trace = OriginalConsole.trace;
        console.table = OriginalConsole.table;
        console.group = OriginalConsole.group;
        console.groupCollapsed = OriginalConsole.groupCollapsed;
        console.groupEnd = OriginalConsole.groupEnd;
        console.time = OriginalConsole.time;
        console.timeEnd = OriginalConsole.timeEnd;
    }

    function suppressConsole() {
        console.log = noop;
        console.info = noop;
        console.debug = noop;
        console.trace = noop;
        if (typeof console.table === 'function') console.table = noop;
        if (typeof console.group === 'function') console.group = noop;
        if (typeof console.groupCollapsed === 'function') console.groupCollapsed = noop;
        if (typeof console.groupEnd === 'function') console.groupEnd = noop;
        if (typeof console.time === 'function') console.time = noop;
        if (typeof console.timeEnd === 'function') console.timeEnd = noop;
    }

    // 2. Debug Detection Priority Logic:
    // Priority 1: localStorage.debug == "true"
    // Priority 2: Explicit window.DEBUG_MODE if already defined
    // Priority 3: Default = false
    function detectDebugMode() {
        try {
            var localSetting = localStorage.getItem('debug');
            if (localSetting !== null) {
                return localSetting === 'true';
            }
        } catch (e) {}

        if (typeof window.DEBUG_MODE === 'boolean') {
            return window.DEBUG_MODE;
        }

        return false;
    }

    var isDebug = detectDebugMode();
    window.DEBUG_MODE = isDebug;

    function enableDebugMode() {
        try { localStorage.setItem('debug', 'true'); } catch (e) {}
        window.DEBUG_MODE = true;
        restoreConsole();
        OriginalConsole.log('%c[LOGGER] 🐞 Debug mode ENABLED. Full logging active.', 'color: #3b82f6; font-weight: bold;');
        return 'Debug mode ENABLED. Console logs are now unsuppressed.';
    }

    function disableDebugMode() {
        try { localStorage.removeItem('debug'); } catch (e) {}
        window.DEBUG_MODE = false;
        suppressConsole();
        OriginalConsole.log('%c[LOGGER] 🔇 Debug mode DISABLED. Console logs suppressed.', 'color: #6b7280; font-style: italic;');
        return 'Debug mode DISABLED. Console logs are now suppressed.';
    }

    // 3. Central Logger API
    var Logger = Object.freeze({
        OriginalConsole: OriginalConsole,
        isDebugMode: function () {
            return window.DEBUG_MODE;
        },
        enableDebug: enableDebugMode,
        disableDebug: disableDebugMode,
        log: function () {
            if (window.DEBUG_MODE) OriginalConsole.log.apply(console, arguments);
        },
        info: function () {
            if (window.DEBUG_MODE) OriginalConsole.info.apply(console, arguments);
        },
        debug: function () {
            if (window.DEBUG_MODE) OriginalConsole.debug.apply(console, arguments);
        },
        trace: function () {
            if (window.DEBUG_MODE) OriginalConsole.trace.apply(console, arguments);
        },
        warn: function () {
            OriginalConsole.warn.apply(console, arguments);
        },
        error: function () {
            OriginalConsole.error.apply(console, arguments);
        }
    });

    window.Logger = Logger;
    window.enableDebug = enableDebugMode;
    window.disableDebug = disableDebugMode;

    // 4. Global Error Handlers: Ensure Uncaught ReferenceErrors & Rejections are ALWAYS printed to console
    window.addEventListener('error', function (event) {
        if (event && event.error) {
            OriginalConsole.error('[UNCAUGHT ERROR]', event.error);
        } else if (event && event.message) {
            OriginalConsole.error('[UNCAUGHT ERROR]', event.message);
        }
    });

    window.addEventListener('unhandledrejection', function (event) {
        if (event && event.reason) {
            OriginalConsole.error('[UNHANDLED REJECTION]', event.reason);
        }
    });

    // 5. Install Compatibility Layer if DEBUG_MODE is false
    if (!window.DEBUG_MODE) {
        suppressConsole();
    }

})(window);
