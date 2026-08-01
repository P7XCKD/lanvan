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
        if (window.__lanvanTimelineTracker) {
            window.__lanvanTimelineTracker.recordEvent("repoGetCache", "folder: '" + target + "', count: " + count);
        }
        return Array.isArray(cached) ? cached.slice() : [];
    };

    FileRepository.prototype.getAllCachedFiles = function () {
        var all = [];
        var keys = Object.keys(this.cache);
        var seenMap = {};
        for (var i = 0; i < keys.length; i++) {
            var folderKey = keys[i];
            var folderFiles = this.cache[folderKey];
            if (Array.isArray(folderFiles)) {
                for (var j = 0; j < folderFiles.length; j++) {
                    var item = folderFiles[j];
                    if (!item) continue;
                    var itemObj = (typeof item === 'string') ? { name: item } : Object.assign({}, item);
                    var nameStr = itemObj.name;
                    if (!nameStr) continue;
                    itemObj.location = folderKey ? folderKey : "Home";
                    var fullPath = itemObj.path ? itemObj.path : (folderKey ? folderKey + "/" + nameStr : nameStr);
                    var key = fullPath + "::" + (itemObj.isFolder ? "folder" : "file");
                    if (!seenMap[key]) {
                        seenMap[key] = true;
                        all.push(itemObj);
                    }
                }
            }
        }
        return all;
    };

    FileRepository.prototype.setFolderCache = function (folderPath, files) {
        var target = cleanPath(folderPath);
        var oldFiles = this.cache[target] || [];
        var oldNames = oldFiles.map(function(f) { return typeof f === 'string' ? f : f.name; });
        if (window.DEBUG_MODE) {
            console.log("[TRACE STEP 5] Repository.setFolderCache BEFORE update | folder: '" + target + "' | old: " + JSON.stringify(oldNames));
        }
        var tagged = tagFiles(files, target);
        var newNames = tagged.map(function(f) { return typeof f === 'string' ? f : f.name; });
        if (window.DEBUG_MODE) {
            console.log("[TRACE STEP 5] Repository.setFolderCache AFTER update | folder: '" + target + "' | new: " + JSON.stringify(newNames));
        }
        
        this.cache[target] = tagged;

        if (window.__lanvanTimelineTracker) {
            window.__lanvanTimelineTracker.recordEvent("repoSetCache", "folder: '" + target + "', count: " + tagged.length);
            if (typeof window.__lanvanTimelineTracker.checkMutation === "function") {
                window.__lanvanTimelineTracker.checkMutation("FileRepository", "setFolderCache", "repository.js", 58, "manual_or_refresh", "Repository.cache['" + target + "']", oldNames, newNames);
            }
        }
        return tagged.slice();
    };

    FileRepository.prototype.invalidateCache = function (folderPath) {
        var caller = ((new Error()).stack || "").split("\n")[2] || "";
        if (folderPath === undefined) {
            if (window.__lanvanTimelineTracker) {
                window.__lanvanTimelineTracker.recordEvent("repoSetCache", "invalidate ALL");
            }
            this.cache = {};
        } else {
            if (window.__lanvanTimelineTracker) {
                window.__lanvanTimelineTracker.recordEvent("repoSetCache", "invalidate '" + cleanPath(folderPath) + "'");
            }
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
                var oldFiles = self.cache[target] || [];
                var oldNames = oldFiles.map(function(f) { return typeof f === 'string' ? f : f.name; });
                var tagged = tagFiles(rawFiles, target);
                var newNames = tagged.map(function(f) { return typeof f === 'string' ? f : f.name; });

                self.cache[target] = tagged;

                if (window.__lanvanTimelineTracker) {
                    window.__lanvanTimelineTracker.recordEvent("repoSetCache", "fetchFolderContents result: '" + target + "', count: " + tagged.length);
                    if (typeof window.__lanvanTimelineTracker.checkMutation === "function") {
                        window.__lanvanTimelineTracker.checkMutation("FileRepository", "fetchFolderContents", "repository.js", 104, "API_fetch_response", "Repository.cache['" + target + "']", oldNames, newNames);
                    }
                }
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

    FileRepository.prototype.renameItem = function (oldName, newName, isFolder, parentPath) {
        var formData = new FormData();
        formData.append("filename", oldName);
        formData.append("new_name", newName);
        var targetPath = cleanPath(parentPath);
        if (targetPath) {
            formData.append("parent_path", targetPath);
        }
        var self = this;
        return fetch("/api/files/rename", { method: "POST", body: formData })
            .then(function (r) { return r.json(); })
            .then(function (data) {
                if (data && data.status === "success") {
                    self.invalidateCache(targetPath);
                }
                return data;
            });
    };

    var repoInstance = new FileRepository();
    window.FileRepository = repoInstance;

})(window);
