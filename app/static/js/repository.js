/**
 * Lanvan Data & Repository Layer (repository.js)
 * Manages HTTP fetches, WebSockets, in-flight AbortController cancellation, and disk caching.
 * Sole owner of server file cache.
 */

(function (window) {
    'use strict';

    function cleanPath(path) {
        if (!path) return "";
        var cleaned = String(path).replace(/\\/g, "/").replace(/^Home \(Root\)\/?/, "").replace(/^Home\/?/, "");
        cleaned = cleaned.replace(/^\/+|\/+$/g, "");
        return (cleaned === "Home (Root)" || cleaned === "Home" || cleaned === "Home/") ? "" : cleaned;
    }

    function tagFiles(files, folderPath) {
        var list = Array.isArray(files) ? files : [];
        var targetPath = cleanPath(folderPath);
        for (var i = 0; i < list.length; i++) {
            var item = list[i];
            if (item && typeof item === 'object') {
                item.isFolder = !!(item.isFolder || item.is_dir || item.is_folder);
            }
        }
        try {
            Object.defineProperty(list, "__folderPath", {
                value: targetPath,
                enumerable: false,
                configurable: true
            });
        } catch (e) {
            list.__folderPath = targetPath;
        }
        return list;
    }

    function FileRepository() {
        this.cache = {};
        this.activeAbortController = null;
    }

    FileRepository.prototype.getFolderCache = function (folderPath) {
        var target = cleanPath(folderPath);
        var cached = this.cache[target] || tagFiles([], target);
        return Array.isArray(cached) ? cached.slice() : [];
    };

    FileRepository.prototype.setFolderCache = function (folderPath, files) {
        var target = cleanPath(folderPath);
        var tagged = tagFiles(files, target);
        this.cache[target] = tagged;
        return tagged.slice();
    };

    FileRepository.prototype.invalidateCache = function (folderPath) {
        if (folderPath === undefined) {
            this.cache = {};
        } else {
            delete this.cache[cleanPath(folderPath)];
        }
    };

    FileRepository.prototype.fetchFolderContents = function (folderPath) {
        var target = cleanPath(folderPath);

        // Abort stale fetch if user navigated
        if (this.activeAbortController) {
            try { this.activeAbortController.abort(); } catch (e) {}
        }

        this.activeAbortController = new AbortController();
        var signal = this.activeAbortController.signal;

        var url = target
            ? "/api/folders/" + encodeURIComponent(target) + "/files"
            : "/api/files";

        var self = this;
        return fetch(url, { signal: signal })
            .then(function (res) {
                if (!res.ok) throw new Error("HTTP error " + res.status);
                return res.json();
            })
            .then(function (data) {
                var rawFiles = (data && (data.files_data || data.files)) ? (data.files_data || data.files) : [];
                var tagged = tagFiles(rawFiles, target);
                self.cache[target] = tagged;
                return tagged;
            })
            .catch(function (err) {
                if (err.name === 'AbortError') {
                    console.log("[REPOSITORY] Fetch request aborted for path: '" + target + "'");
                } else {
                    console.error("[REPOSITORY ERROR] Failed to fetch folder contents for '" + target + "':", err);
                }
                return self.getFolderCache(target);
            });
    };

    var repoInstance = new FileRepository();
    window.FileRepository = repoInstance;

})(window);
