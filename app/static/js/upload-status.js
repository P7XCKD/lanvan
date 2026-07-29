/**
 * @file upload-status.js
 * @description Upload Status Enum — Single source of truth for upload state transitions.
 * Every upload status assignment MUST use these constants, never raw strings.
 * @dependency None (Ultra-safe: must load before any other script)
 */

(function (window) {
    'use strict';

    // ── Defensive: prevent double-load ──────────────────────────────────
    if (window.UploadStatus) {
        console.log("[UploadStatus] Already loaded — skipping duplicate initialization");
        return;
    }

    // ── Allowed State Transitions ──────────────────────────────────────
    // Format: currentStatus -> [allowedNextStatuses]
    var TRANSITIONS = {
        'QUEUED':      ['UPLOADING', 'PAUSED', 'CANCELLED', 'FAILED'],
        'UPLOADING':   ['PROCESSING', 'PAUSED', 'FAILED', 'CANCELLED'],
        'PROCESSING':  ['COMPLETED', 'FAILED', 'CANCELLED'],
        'PAUSED':      ['UPLOADING', 'QUEUED', 'CANCELLED'],
        'FAILED':      ['RETRYING', 'CANCELLED'],
        'RETRYING':    ['UPLOADING', 'CANCELLED'],
        'COMPLETED':   ['DELETED'],
        'CANCELLED':   [],
        'DELETED':     []
    };

    // ── Enum Definition ────────────────────────────────────────────────
    var STATUS = {
        QUEUED:      'QUEUED',
        UPLOADING:   'UPLOADING',
        PROCESSING:  'PROCESSING',
        PAUSED:      'PAUSED',
        FAILED:      'FAILED',
        RETRYING:    'RETRYING',
        COMPLETED:   'COMPLETED',
        CANCELLED:   'CANCELLED',
        DELETED:     'DELETED'
    };

    // ── Assertion Helpers ──────────────────────────────────────────────
    var DEV_MODE = window.DEBUG_MODE === true || window.__LANVAN_DEV__ === true;

    /**
     * Normalize a status string to uppercase.
     * Returns null if the string doesn't match any valid status.
     */
    function normalize(raw) {
        if (!raw || typeof raw !== 'string') return null;
        var upper = raw.toUpperCase();
        return STATUS[upper] ? upper : null;
    }

    /**
     * Assert that a status value is a valid UploadStatus constant.
     * In dev mode, throws on invalid values.
     */
    function assertValid(status, label) {
        if (typeof status !== 'string') {
            console.error("[UploadStatus] ❌ INVALID: " + (label || 'status') + " is not a string, got:", typeof status);
            if (DEV_MODE) throw new Error("UploadStatus: " + (label || 'status') + " must be a string, got " + typeof status);
            return false;
        }
        var upper = status.toUpperCase();
        if (!STATUS[upper]) {
            console.error("[UploadStatus] ❌ INVALID: " + (label || 'status') + " = '" + status + "' is not a valid UploadStatus value. Use UploadStatus constants.");
            if (DEV_MODE) throw new Error("UploadStatus: '" + status + "' is not valid. Use UploadStatus constants like UploadStatus.QUEUED.");
            return false;
        }
        if (status !== upper) {
            console.warn("[UploadStatus] ⚠️ CASE MISMATCH: " + (label || 'status') + " = '" + status + "' should be uppercase '" + upper + "'. Auto-fixing.");
            return false;
        }
        return true;
    }

    /**
     * Assert that a transition from `current` to `next` is legal.
     * In dev mode, throws on illegal transitions.
     */
    function assertTransition(current, next, label) {
        var cur = current ? current.toUpperCase() : null;
        var nxt = next ? next.toUpperCase() : null;

        if (!nxt) {
            console.warn("[UploadStatus] ⚠️ " + (label || 'transition') + ": next status is empty/null");
            return false;
        }
        if (!cur) {
            // First status assignment — always allowed
            return true;
        }

        var allowed = TRANSITIONS[cur];
        if (!allowed) {
            console.error("[UploadStatus] ❌ UNKNOWN CURRENT: " + (label || 'transition') + " current status '" + cur + "' has no defined transitions.");
            if (DEV_MODE) throw new Error("UploadStatus: Unknown current status '" + cur + "'. Must be one of: " + Object.keys(STATUS).join(', '));
            return false;
        }

        if (allowed.indexOf(nxt) === -1) {
            console.error(
                "[UploadStatus] ❌ ILLEGAL TRANSITION: " + (label || 'upload item') +
                " cannot go from '" + cur + "' to '" + nxt + "'. " +
                "Allowed transitions from '" + cur + "': " + allowed.join(', ')
            );
            if (DEV_MODE) {
                throw new Error(
                    "UploadStatus: Illegal transition for " + (label || 'item') +
                    " — from '" + cur + "' to '" + nxt + "'. " +
                    "Allowed: " + allowed.join(', ')
                );
            }
            return false;
        }
        return true;
    }

    // ── Public API ─────────────────────────────────────────────────────
    window.UploadStatus = {
        // Enum values
        QUEUED:      STATUS.QUEUED,
        UPLOADING:   STATUS.UPLOADING,
        PROCESSING:  STATUS.PROCESSING,
        PAUSED:      STATUS.PAUSED,
        FAILED:      STATUS.FAILED,
        RETRYING:    STATUS.RETRYING,
        COMPLETED:   STATUS.COMPLETED,
        CANCELLED:   STATUS.CANCELLED,
        DELETED:     STATUS.DELETED,

        // Value checks
        isValid: function (status) { return !!normalize(status); },
        normalize: normalize,

        // Assertions (dev mode throws)
        assertValid: assertValid,
        assertTransition: assertTransition,

        // All valid status values
        all: Object.keys(STATUS).map(function (k) { return STATUS[k]; }),

        // Check if a status is active (not completed/cancelled/deleted)
        isActive: function (status) {
            var n = normalize(status);
            return n && n !== STATUS.COMPLETED && n !== STATUS.CANCELLED && n !== STATUS.DELETED && n !== STATUS.FAILED;
        },

        // Check if a status is terminal (no further transitions possible except DELETED)
        isTerminal: function (status) {
            var n = normalize(status);
            return n === STATUS.CANCELLED || n === STATUS.COMPLETED || n === STATUS.DELETED;
        }
    };

    console.log("[UploadStatus] ✅ Loaded. " + Object.keys(STATUS).length + " status values defined. Dev mode: " + DEV_MODE);

})(window);