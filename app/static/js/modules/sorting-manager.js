/**
 * @file sorting-manager.js
 * @description File list comparator & sorting manager.
 * @module SortingManager
 */

(function (window) {
    'use strict';

    function parseSizeToBytes(sizeStr, isFolder) {
        if (isFolder) return -1;
        if (!sizeStr) return 0;
        var str = String(sizeStr).toUpperCase().trim();
        var match = str.match(/^([\d.]+)\s*([KMG]?B)$/);
        if (!match) return 0;
        var val = parseFloat(match[1]);
        var unit = match[2];
        if (unit === "KB") return val * 1024;
        if (unit === "MB") return val * 1024 * 1024;
        if (unit === "GB") return val * 1024 * 1024 * 1024;
        return val;
    }

    function compareFiles(a, b, field, direction) {
        var dir = direction === "desc" ? -1 : 1;
        var isFolderA = !!a.isFolder;
        var isFolderB = !!b.isFolder;

        // Folders always sorted first
        if (isFolderA && !isFolderB) return -1;
        if (!isFolderA && isFolderB) return 1;

        if (field === "size") {
            var sizeA = parseSizeToBytes(a.size, isFolderA);
            var sizeB = parseSizeToBytes(b.size, isFolderB);
            return (sizeA - sizeB) * dir;
        } else if (field === "date") {
            var dateA = a.date || "";
            var dateB = b.date || "";
            return dateA.localeCompare(dateB) * dir;
        } else if (field === "type") {
            var extA = (a.name || "").split(".").pop().toLowerCase();
            var extB = (b.name || "").split(".").pop().toLowerCase();
            return extA.localeCompare(extB) * dir;
        } else {
            // Default: name
            var nameA = (a.name || "").toLowerCase();
            var nameB = (b.name || "").toLowerCase();
            return nameA.localeCompare(nameB) * dir;
        }
    }

    window.SortingManager = {
        parseSizeToBytes: parseSizeToBytes,
        compareFiles: compareFiles
    };

    window.parseSizeToBytes = parseSizeToBytes;
    window.compareFiles = compareFiles;

})(window);
