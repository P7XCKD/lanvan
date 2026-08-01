/**
 * @file utils.js
 * @description Centralized pure utility helpers for Lanvan application.
 * @module Utils
 */

(function (window) {
    'use strict';

    if (window.Utils) {
        return;
    }

    function escapeHtml(text) {
        if (text === null || text === undefined) return '';
        var map = {
            '&': '&amp;',
            '<': '&lt;',
            '>': '&gt;',
            '"': '&quot;',
            "'": '&#039;'
        };
        return String(text).replace(/[&<>"']/g, function (m) { return map[m]; });
    }

    function formatBytes(bytes, decimals) {
        if (bytes === 0 || !bytes) return '0 Bytes';
        var k = 1024;
        var dm = decimals < 0 ? 0 : (decimals || 2);
        var sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB', 'PB'];
        var i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + ' ' + sizes[i];
    }

    function formatSize(bytes) {
        return formatBytes(bytes, 1);
    }

    function cleanFolderPath(path) {
        if (!path) return "";
        var cleaned = String(path).replace(/\\/g, "/").replace(/^Home \(Root\)\/?/, "").replace(/^Home\/?/, "");
        cleaned = cleaned.replace(/^\/+|\/+$/g, "");
        return (cleaned === "Home (Root)" || cleaned === "Home" || cleaned === "Home/") ? "" : cleaned;
    }

    function formatSpeed(bytesPerSecond) {
        if (bytesPerSecond === 0 || !bytesPerSecond) return '0 B/s';
        var k = 1024;
        var sizes = ['B/s', 'KB/s', 'MB/s', 'GB/s'];
        var i = Math.floor(Math.log(bytesPerSecond) / Math.log(k));
        return parseFloat((bytesPerSecond / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
    }

    var Utils = Object.freeze({
        escapeHtml: escapeHtml,
        formatBytes: formatBytes,
        formatSize: formatSize,
        cleanFolderPath: cleanFolderPath,
        formatSpeed: formatSpeed
    });

    window.Utils = Utils;

    // Backward compatibility aliases
    window.escapeHtml = window.escapeHtml || escapeHtml;
    window.formatSize = window.formatSize || formatSize;
    window.cleanFolderPath = window.cleanFolderPath || cleanFolderPath;
    window.formatSpeed = window.formatSpeed || formatSpeed;

})(window);
