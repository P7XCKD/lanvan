/**
 * @file sorting-manager.js
 * @description File list comparator & sorting manager.
 * @module SortingManager
 */

(function (window) {
    'use strict';

    function parseSizeToBytes(sizeStr, isFolder) {
        if (isFolder) return -1;
        if (sizeStr === null || sizeStr === undefined) return 0;
        if (typeof sizeStr === "number") return sizeStr;
        var str = String(sizeStr).toUpperCase().trim();
        if (!str || str === "--" || str === "-") return 0;

        if (/^\d+(\.\d+)?$/.test(str)) {
            return parseFloat(str);
        }

        var match = str.match(/^([\d.]+)\s*([KMGTP]?B)?$/i);
        if (!match) return 0;
        var val = parseFloat(match[1]);
        var unit = match[2] ? match[2].toUpperCase() : "B";
        if (unit === "KB") return val * 1024;
        if (unit === "MB") return val * 1024 * 1024;
        if (unit === "GB") return val * 1024 * 1024 * 1024;
        if (unit === "TB") return val * 1024 * 1024 * 1024 * 1024;
        return val;
    }

    function parseDateToTimestamp(dateVal) {
        if (!dateVal) return 0;
        if (typeof dateVal === "number") {
            return dateVal < 1e11 ? dateVal * 1000 : dateVal;
        }
        var str = String(dateVal).trim();
        if (!str || str === "--" || str === "-") return 0;

        if (/^\d+(\.\d+)?$/.test(str)) {
            var num = parseFloat(str);
            return num < 1e11 ? num * 1000 : num;
        }

        var lower = str.toLowerCase();
        if (lower === "just now" || lower === "today") {
            return Date.now();
        }
        var minMatch = lower.match(/^(\d+)\s*(min|minute)s?\s*ago$/);
        if (minMatch) {
            return Date.now() - parseInt(minMatch[1], 10) * 60 * 1000;
        }
        var hrMatch = lower.match(/^(\d+)\s*(hour|hr)s?\s*ago$/);
        if (hrMatch) {
            return Date.now() - parseInt(hrMatch[1], 10) * 3600 * 1000;
        }
        var dayMatch = lower.match(/^(\d+)\s*days?\s*ago$/);
        if (dayMatch) {
            return Date.now() - parseInt(dayMatch[1], 10) * 86400 * 1000;
        }

        var parsed = Date.parse(str);
        return isNaN(parsed) ? 0 : parsed;
    }

    function compareFiles(a, b, field, direction) {
        var dir = direction === "desc" ? -1 : 1;
        var isFolderA = !!a.isFolder;
        var isFolderB = !!b.isFolder;

        // Folders always sorted first
        if (isFolderA && !isFolderB) return -1;
        if (!isFolderA && isFolderB) return 1;

        if (field === "size") {
            var sizeA = parseSizeToBytes(a.size || a.fileSize, isFolderA);
            var sizeB = parseSizeToBytes(b.size || b.fileSize, isFolderB);
            return (sizeA - sizeB) * dir;
        } else if (field === "date") {
            var timeA = parseDateToTimestamp(a.mtime || a.date || a.modified);
            var timeB = parseDateToTimestamp(b.mtime || b.date || b.modified);
            return (timeA - timeB) * dir;
        } else if (field === "type") {
            var extA = (a.name || "").split(".").pop().toLowerCase();
            var extB = (b.name || "").split(".").pop().toLowerCase();
            return extA.localeCompare(extB) * dir;
        } else {
            // Default: name
            var nameA = (a.name || "").toLowerCase();
            var nameB = (b.name || "").toLowerCase();
            return nameA.localeCompare(nameB, undefined, { numeric: true, sensitivity: 'base' }) * dir;
        }
    }

    window.SortingManager = {
        parseSizeToBytes: parseSizeToBytes,
        parseDateToTimestamp: parseDateToTimestamp,
        compareFiles: compareFiles
    };

    window.parseSizeToBytes = parseSizeToBytes;
    window.parseDateToTimestamp = parseDateToTimestamp;
    window.compareFiles = compareFiles;

})(window);
