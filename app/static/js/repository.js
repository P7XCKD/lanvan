/**
 * Lanvan Unidirectional Architecture: File Repository Layer
 * Manages HTTP fetches, WebSockets, AbortController request cancellation, and disk caching.
 * Communicates exclusively by dispatching actions to ActionQueue. NEVER touches DOM directly.
 */

(function (window) {
    'use strict';

    function FileRepository(store) {
        this.store = store;
        this.activeAbortController = null;
        this.cache = {}; // Keyed by cleanFolderPath
    }

    function cleanRepositoryFolderPath(path) {
        if (!path) return "";
        return String(path).replace(/\\/g, "/").replace(/^Home \(Root\)\/?/, "").replace(/^Home\/?/, "").replace(/^\/+|\/+$/g, "");
    }

    function tagRepositoryFiles(files, folderPath) {
        var list = Array.isArray(files) ? files : [];
        try {
            Object.defineProperty(list, "__folderPath", {
                value: cleanRepositoryFolderPath(folderPath),
                enumerable: false,
                configurable: true
            });
        } catch (e) {
            list.__folderPath = cleanRepositoryFolderPath(folderPath);
        }
        return list;
    }

    FileRepository.prototype.fetchFolderContents = function (folderPath) {
        var cleanPath = cleanRepositoryFolderPath(folderPath);
        
        // 1. Abort stale in-flight fetch request if user navigated
        if (this.activeAbortController) {
            try {
                this.activeAbortController.abort();
            } catch (e) {}
        }

        this.activeAbortController = new AbortController();
        var signal = this.activeAbortController.signal;

        var url = cleanPath 
            ? "/api/folders/" + encodeURIComponent(cleanPath) + "/files"
            : "/api/files";

        var self = this;

        return fetch(url, { signal: signal })
            .then(function (res) {
                if (!res.ok) throw new Error("HTTP error " + res.status);
                return res.json();
            })
            .then(function (data) {
                var filesData = tagRepositoryFiles((data && (data.files_data || data.files)) ? (data.files_data || data.files) : [], cleanPath);
                self.cache[cleanPath] = filesData;

                // Dispatch action to Store (Never touch DOM or trigger render directly!)
                if (window.LanvanStore) {
                    window.LanvanStore.dispatch("DISK_FILES_LOADED", {
                        folderPath: cleanPath,
                        files: filesData
                    }, "HIGH");
                }
                return filesData;
            })
            .catch(function (err) {
                if (err.name === 'AbortError') {
                    console.log("[REPOSITORY] Stale fetch request aborted for path: '" + cleanPath + "'");
                } else {
                    console.error("[REPOSITORY ERROR] Failed to fetch folder contents for '" + cleanPath + "':", err);
                }
                return [];
            });
    };

    FileRepository.prototype.getFolderCache = function (folderPath) {
        var cleanPath = cleanRepositoryFolderPath(folderPath);
        return this.cache[cleanPath] || tagRepositoryFiles([], cleanPath);
    };

    FileRepository.prototype.invalidateCache = function (folderPath) {
        if (folderPath === undefined) {
            this.cache = {};
        } else {
            var cleanPath = cleanRepositoryFolderPath(folderPath);
            delete this.cache[cleanPath];
        }
    };

    // Instantiate FileRepository
    var repoInstance = new FileRepository(window.LanvanStore);
    window.FileRepository = repoInstance;

    // Register with DevTools
    if (window.__LANVAN_DEVTOOLS__) {
        window.__LANVAN_DEVTOOLS__.dumpRepository = function () {
            console.log("=== LANVAN REPOSITORY CACHE ===", repoInstance.cache);
            return repoInstance.cache;
        };
    }

})(window);
