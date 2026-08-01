/**
 * @file upload-eta.js
 * @description Dedicated ETA (Estimated Time of Arrival) calculator for active uploads.
 *
 * Rules:
 *  - ETA is computed ONLY for items with status === 'UPLOADING' and speed > 0.
 *  - ETA is shown ONLY in list-view row subtitles (not in the notification tray, not in grid badges).
 *  - All calculation lives here — no ETA logic is scattered elsewhere.
 *
 * Public API (exposed as window.UploadETA):
 *  - format(item)   → string like "1m 23s" | "45s" | "" (empty when unavailable)
 */
(function (window) {
    'use strict';

    /**
     * Converts a number of seconds into a human-readable ETA string.
     * @param {number} seconds
     * @returns {string}
     */
    function secondsToEtaString(seconds) {
        var s = Math.round(seconds);
        if (s <= 0) return '';
        if (s < 60) return s + 's';
        var m = Math.floor(s / 60);
        var rem = s % 60;
        return rem > 0 ? m + 'm ' + rem + 's' : m + 'm';
    }

    /**
     * Calculates and formats the ETA for a single uploading item.
     *
     * Returns an empty string when:
     *  - The item status is anything other than 'UPLOADING'
     *  - Speed is missing or zero
     *  - File size or bytes-uploaded data is unavailable
     *  - Remaining bytes is zero or negative
     *
     * @param {Object} item  - Upload queue item (must have: status, speed, fileSize, bytesUploaded)
     * @returns {string}     - Formatted ETA string (e.g. "2m 15s") or "" if not applicable
     */
    function format(item) {
        if (!item) return '';

        // Only compute ETA when the item is actively transferring bytes
        if (item.status !== 'UPLOADING') return '';

        var speed = item.speed || 0;
        if (speed <= 0) return '';

        var fileSize = item.fileSize || (item.file && item.file.size) || 0;
        if (fileSize <= 0) return '';

        var uploaded = item.bytesUploaded || item.uploadedBytes || 0;
        if (!uploaded && item.progress && fileSize) {
            // Derive bytes from percentage as fallback
            uploaded = Math.round((fileSize * Math.min(100, item.progress)) / 100);
        }

        var remaining = fileSize - uploaded;
        if (remaining <= 0) return '';

        return secondsToEtaString(remaining / speed);
    }

    // Expose as singleton on window
    window.UploadETA = {
        format: format
    };

})(window);
