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

    function getCanonicalIdentity(parentPath, fileName) {
        if (!fileName) return "";
        var cleanParent = cleanFolderPath(parentPath);
        var cleanName = String(fileName).trim().replace(/\\/g, "/").replace(/^\/+|\/+$/g, "");
        return cleanParent ? (cleanParent + "/" + cleanName) : cleanName;
    }

    function formatSpeed(bytesPerSecond) {
        if (bytesPerSecond === 0 || !bytesPerSecond) return '0 B/s';
        var k = 1024;
        var sizes = ['B/s', 'KB/s', 'MB/s', 'GB/s'];
        var i = Math.floor(Math.log(bytesPerSecond) / Math.log(k));
        return parseFloat((bytesPerSecond / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
    }

    var _cachedFormatters = null;

    function getFormatters() {
        if (!_cachedFormatters) {
            try {
                _cachedFormatters = {
                    time: new Intl.DateTimeFormat(undefined, { hour: 'numeric', minute: '2-digit' }),
                    weekday: new Intl.DateTimeFormat(undefined, { weekday: 'long' }),
                    monthDay: new Intl.DateTimeFormat(undefined, { month: 'short', day: 'numeric' }),
                    fullDate: new Intl.DateTimeFormat(undefined, { month: 'short', day: 'numeric', year: 'numeric' }),
                    tooltip: new Intl.DateTimeFormat(undefined, {
                        weekday: 'long',
                        year: 'numeric',
                        month: 'long',
                        day: 'numeric',
                        hour: 'numeric',
                        minute: '2-digit',
                        second: '2-digit'
                    })
                };
            } catch (e) {
                _cachedFormatters = null;
            }
        }
        return _cachedFormatters;
    }

    function formatLastModified(dateInput) {
        if (dateInput === null || dateInput === undefined || dateInput === "" || dateInput === "--") {
            return { display: "--", tooltip: "", toString: function () { return "--"; } };
        }

        var d = null;
        if (dateInput instanceof Date) {
            d = dateInput;
        } else if (typeof dateInput === 'number') {
            d = new Date(dateInput < 1e11 ? dateInput * 1000 : dateInput);
        } else if (typeof dateInput === 'string') {
            var trimmed = dateInput.trim();
            if (/^\d+(\.\d+)?$/.test(trimmed)) {
                var num = parseFloat(trimmed);
                d = new Date(num < 1e11 ? num * 1000 : num);
            } else {
                d = new Date(trimmed);
            }
        }

        if (!d || isNaN(d.getTime())) {
            var fallback = String(dateInput);
            return { display: fallback, tooltip: fallback, toString: function () { return fallback; } };
        }

        var now = new Date();
        var diffMs = now.getTime() - d.getTime();
        var diffSec = Math.floor(diffMs / 1000);

        var formatters = getFormatters();

        var tooltipStr = "";
        if (formatters && formatters.tooltip) {
            tooltipStr = formatters.tooltip.format(d);
        } else {
            tooltipStr = d.toLocaleString();
        }

        var displayStr = "";

        if (diffSec < 0) {
            displayStr = formatters && formatters.fullDate ? formatters.fullDate.format(d) : d.toLocaleDateString();
        } else if (diffSec < 60) {
            displayStr = "Just now";
        } else if (diffSec < 3600) {
            var mins = Math.floor(diffSec / 60);
            displayStr = mins + " min ago";
        } else {
            var startOfToday = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();
            var startOfYesterday = new Date(now.getFullYear(), now.getMonth(), now.getDate() - 1).getTime();
            var startOf7DaysAgo = new Date(now.getFullYear(), now.getMonth(), now.getDate() - 6).getTime();

            var dateTime = d.getTime();

            if (dateTime >= startOfToday) {
                displayStr = formatters && formatters.time ? formatters.time.format(d) : d.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' });
            } else if (dateTime >= startOfYesterday) {
                displayStr = "Yesterday";
            } else if (dateTime >= startOf7DaysAgo) {
                displayStr = formatters && formatters.weekday ? formatters.weekday.format(d) : d.toLocaleDateString([], { weekday: 'long' });
            } else if (d.getFullYear() === now.getFullYear()) {
                displayStr = formatters && formatters.monthDay ? formatters.monthDay.format(d) : d.toLocaleDateString([], { month: 'short', day: 'numeric' });
            } else {
                displayStr = formatters && formatters.fullDate ? formatters.fullDate.format(d) : d.toLocaleDateString([], { month: 'short', day: 'numeric', year: 'numeric' });
            }
        }

        return {
            display: displayStr,
            tooltip: tooltipStr,
            toString: function () { return displayStr; }
        };
    }

    var Utils = Object.freeze({
        escapeHtml: escapeHtml,
        formatBytes: formatBytes,
        formatSize: formatSize,
        cleanFolderPath: cleanFolderPath,
        getCanonicalIdentity: getCanonicalIdentity,
        formatSpeed: formatSpeed,
        formatLastModified: formatLastModified
    });

    window.Utils = Utils;

    // Backward compatibility aliases
    window.escapeHtml = window.escapeHtml || escapeHtml;
    window.formatSize = window.formatSize || formatSize;
    window.cleanFolderPath = window.cleanFolderPath || cleanFolderPath;
    window.getCanonicalIdentity = window.getCanonicalIdentity || getCanonicalIdentity;
    window.formatSpeed = window.formatSpeed || formatSpeed;
    window.formatLastModified = window.formatLastModified || formatLastModified;

})(window);
