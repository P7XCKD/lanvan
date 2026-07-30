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
        var count = Array.isArray(cached) ? cached.length : 0;
        console.log("[FLICKER-TRACE] 📂 Repository.getFolderCache | Folder: '" + (target || "(root)") + "' | Count: " + count + " | Timestamp: " + performance.now().toFixed(1) + "ms");
        return Array.isArray(cached) ? cached.slice() : [];
    };

    FileRepository.prototype.setFolderCache = function (folderPath, files) {
        var target = cleanPath(folderPath);
        var tagged = tagFiles(files, target);
        var prevCount = this.cache[target] ? (Array.isArray(this.cache[target]) ? this.cache[target].length : -1) : -1;
        var newCount = Array.isArray(tagged) ? tagged.length : 0;
        var caller = ((new Error()).stack || "").split("\n")[2] || "";
        console.log("%c[FLICKER-TRACE] 📝 Repository.setFolderCache | Folder: '" + (target || "(root)") + "' | Old: " + prevCount + " → New: " + newCount + " | Timestamp: " + performance.now().toFixed(1) + "ms | Caller: " + caller);
        this.cache[target] = tagged;
        return tagged.slice();
    };

    FileRepository.prototype.invalidateCache = function (folderPath) {
        var caller = ((new Error()).stack || "").split("\n")[2] || "";
        if (folderPath === undefined) {
            console.log("%c[FLICKER-TRACE] 🗑️ Repository.invalidateCache(ALL) | Cleared entire cache | Timestamp: " + performance.now().toFixed(1) + "ms | Caller: " + caller);
            this.cache = {};
        } else {
            console.log("%c[FLICKER-TRACE] 🗑️ Repository.invalidateCache | Folder: '" + cleanPath(folderPath) + "' | Timestamp: " + performance.now().toFixed(1) + "ms | Caller: " + caller);
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

        console.log("[FLICKER-TRACE] 🌐 Repository.fetchFolderContents START | Folder: '" + (target || "(root)") + "' | URL: " + url + " | Timestamp: " + performance.now().toFixed(1) + "ms");
        var self = this;
        return fetch(url, { signal: signal })
            .then(function (res) {
                if (!res.ok) throw new Error("HTTP error " + res.status);
                return res.json();
            })
            .then(function (data) {
                var rawFiles = (data && (data.files_data || data.files)) ? (data.files_data || data.files) : [];
                var prevCount = self.cache[target] ? (Array.isArray(self.cache[target]) ? self.cache[target].length : -1) : -1;
                var newCount = Array.isArray(rawFiles) ? rawFiles.length : 0;
                console.log("%c[FLICKER-TRACE] 🌐 Repository.fetchFolderContents RESULT | Folder: '" + (target || "(root)") + "' | API returned: " + newCount + " items | Old cache: " + prevCount + " → New: " + newCount + " | Timestamp: " + performance.now().toFixed(1) + "ms");
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
