/**
 * app-init.js — Prototype UI to Production Logic Adapter
 *
 * This is a THIN TRANSLATION LAYER. It does not implement business logic,
 * networking, encryption, upload management, or clipboard sync.
 * It wraps production rendering functions and connects prototype UI events
 * to existing production functions.
 *
 * Rules:
 * - No duplicate state (single source of truth always in production)
 * - No production JS modifications
 * - Wrap, don't replace
 */

(function () {
    "use strict";

    // GUARD: Prevent double-wrapping if script loads multiple times
    if (window.__appInitLoaded) {
        console.log("[app-init] Already loaded — skipping duplicate initialization");
        return;
    }
    window.__appInitLoaded = true;

    // =========================================================================
    // 1. RENDERING WRAPPERS — Sync prototype containers with production data
    // =========================================================================

    // Wrap updateFileDisplay() — called by production refreshFileList() and auto-refresh
    // Guard: only wrap if not already wrapped by a previous partial load
    if (typeof updateFileDisplay === "function" && !updateFileDisplay.__prototypeWrapped) {
        const _originalUpdateFileDisplay = updateFileDisplay;
        updateFileDisplay = function (files) {
            var normCurrentDir = cleanFolderPath(currentFolderPath);
            if (Array.isArray(files)) {
                var taggedFolder = getTaggedFolderPath(files);
                if (taggedFolder !== null && taggedFolder !== normCurrentDir) {
                    console.warn("[UPDATE FILE DISPLAY] Ignoring stale payload for folder '" + taggedFolder + "' while active view is '" + normCurrentDir + "'.");
                    return;
                }
                renderPrototypeFileList(tagFilesWithFolder(files, normCurrentDir));
            } else {
                fetchFilesData().then(function (fd) {
                    renderPrototypeFileList(fd);
                }).catch(function (err) {
                    console.error("fetchFilesData error:", err);
                });
            }
        };
        updateFileDisplay.__prototypeWrapped = true;
        window.updateFileDisplay = updateFileDisplay;
    }

    // Wrap refreshClipboardHistory() — called by production WebSocket and manual refresh
    if (typeof refreshClipboardHistory === "function" && !refreshClipboardHistory.__prototypeWrapped) {
        const _originalRefreshClipboardHistory = refreshClipboardHistory;
        refreshClipboardHistory = async function () {
            await _originalRefreshClipboardHistory();
            // After production refreshes, also render prototype clipboard
            // Production stores data in #clipboardHistoryContent DOM
            setTimeout(() => syncPrototypeClipboard(), 100);
        };
        refreshClipboardHistory.__prototypeWrapped = true;
    }

    // =========================================================================
    // 2. PROTOTYPE RENDERERS — Consume production data, output prototype DOM
    // =========================================================================

    // currentFolderPath is owned exclusively by state-store.js via its Object.defineProperty setter.
    // This local variable mirrors the Store value for fast read access within this module.
    var currentFolderPath = "Home";
    window.getCurrentFolderPath = function () {
        var p = "";
        if (typeof window.LanvanStore !== 'undefined' && window.LanvanStore.getState) {
            p = window.LanvanStore.getState().currentFolder || "";
        }
        return (p === "Home" || p === "Home/") ? "" : p;
    };

    // Intercept network requests to log detailed error info to the console if requests fail.
    // IMPORTANT: Do NOT inject parent_path here! The upload handlers in main-app.js
    // already set parent_path from the queued uploadItem.targetDir. Injecting it here
    // using the live currentFolderPath would override the correct target directory
    // when a user navigates to a different folder during upload.
    (function () {
        const _originalOpen = XMLHttpRequest.prototype.open;
        XMLHttpRequest.prototype.open = function (method, url) {
            this._url = url;
            return _originalOpen.apply(this, arguments);
        };

        const _originalSend = XMLHttpRequest.prototype.send;
        XMLHttpRequest.prototype.send = function (body) {
            // No automatic parent_path injection — production handlers set it correctly.
            // Log response errors
            var self = this;
            var originalOnLoad = this.onload;
            this.onload = function () {
                if (self.status >= 400) {
                    console.error("[Network Error] XHR failed with status " + self.status + " for URL: " + self._url + "\nResponse: ", self.responseText);
                }
                if (originalOnLoad) {
                    originalOnLoad.apply(this, arguments);
                }
            };
            var originalOnError = this.onerror;
            this.onerror = function () {
                console.error("[Network Error] XHR connection failed for URL: " + self._url);
                if (originalOnError) {
                    originalOnError.apply(this, arguments);
                }
            };

            return _originalSend.apply(this, arguments);
        };

        const _originalFetch = window.fetch;
        window.fetch = function (url, options) {
            // No automatic parent_path injection — production handlers set it correctly.
            return _originalFetch.apply(this, arguments)
                .then(function (response) {
                    if (!response.ok) {
                        console.error("[Network Error] Fetch failed with status " + response.status + " for URL: " + url);
                    }
                    return response;
                })
                .catch(function (error) {
                    if (error && (error.name === 'AbortError' || error.message === 'signal is aborted without reason')) {
                        throw error;
                    }
                    console.error("[Network Error] Fetch connection failed for URL: " + url + ". Error: ", error);
                    throw error;
                });
        };
    })();

    // Client-side sort and filter state
    var typeFilter = "all";
    var sortBy = "name";
    var sortDirection = "asc";
    var sortFolders = "top";

    // Move dialog state
    var moveCurrentPath = ["Home"];
    var moveTargetFolder = "Home";
    var itemsToMove = [];
    var isCreatingFolderInMove = false;



    // renderBreadcrumbs is provided by breadcrumb-nav.js module

    /**
     * Render files in prototype #nasFileList from the same data production uses.
     * @param {string[]} files - Array of filenames from production API
     */
    function getDiskFileMetadata(filename, folderPath) {
        if (!filename) return null;
        var path = folderPath || (typeof window.lanvanStore !== 'undefined' && window.lanvanStore.getState ? window.lanvanStore.getState().currentFolder : (window.currentFolderPath || ""));
        var cache = (window.FileRepository && typeof window.FileRepository.getFolderCache === 'function')
            ? window.FileRepository.getFolderCache(path)
            : [];
        var match = (cache || []).find(function (f) {
            if (!f) return false;
            var fn = typeof f === 'string' ? f : f.name;
            return fn && fn.trim().toLowerCase() === String(filename).trim().toLowerCase();
        });
        if (match) {
            if (typeof match === 'object') {
                return Object.assign({}, match, {
                    isFolder: !!(match.isFolder || match.is_dir || match.is_folder || (window._recentlyCreatedFolders && window._recentlyCreatedFolders[filename]))
                });
            } else if (typeof match === 'string') {
                var isF = !!(window._recentlyCreatedFolders && window._recentlyCreatedFolders[match]);
                return { name: match, size: "--", mtime: 0, isFolder: isF };
            }
        }
        return match || null;
    }

    var lastRenderedFiles = [];
    window.activeTab = "file";

    function tagFilesWithFolder(files, folderPath) {
        var list = Array.isArray(files) ? files : [];
        try {
            Object.defineProperty(list, "__folderPath", {
                value: cleanFolderPath(folderPath),
                enumerable: false,
                configurable: true,
                writable: true
            });
        } catch (e) {
            list.__folderPath = cleanFolderPath(folderPath);
        }
        return list;
    }

    function getTaggedFolderPath(files) {
        return files && files.__folderPath !== undefined ? cleanFolderPath(files.__folderPath) : null;
    }

    window.tagFilesWithFolder = tagFilesWithFolder;
    window.getTaggedFolderPath = getTaggedFolderPath;

    function formatSize(bytes) {
        if (typeof formatFileSize === 'function') {
            return formatFileSize(bytes);
        }
        if (!bytes) return '--';
        if (bytes === 0) return '0 Bytes';
        var k = 1024;
        var sizes = ['Bytes', 'KB', 'MB', 'GB'];
        var i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }

    // Strips all Home-prefix variants so folder paths match across upload queue and browser navigation
    function cleanFolderPath(path) {
        if (!path) return "";
        var cleaned = String(path).replace(/\\/g, "/").replace(/^Home \(Root\)\/?/, "").replace(/^Home\/?/, "");
        cleaned = cleaned.replace(/^\/+|\/+$/g, "");
        if (cleaned === "Home (Root)" || cleaned === "Home" || cleaned === "Home/") return "";
        return cleaned;
    }

    // Calculates item directory relative to current folder view (normCurrentDir)
    // Returns null if the item belongs to a completely different folder tree
    function getRelativeItemDir(itemDir, normCurrentDir) {
        var cleanItem = cleanFolderPath(itemDir);
        var cleanCurrent = cleanFolderPath(normCurrentDir);
        if (!cleanCurrent) return cleanItem;
        if (cleanItem === cleanCurrent) return "";
        if (cleanItem.startsWith(cleanCurrent + "/")) {
            return cleanItem.substring(cleanCurrent.length + 1);
        }
        return null;
    }

    var folderFilesCache = {}; // Folder-scoped disk file cache keyed by cleanFolderPath

    function renderPrototypeFileList(files, renderReason) {
        if (window.__lanvanTimelineTracker) {
            var fCount = Array.isArray(files) ? files.length : (files ? 1 : 0);
            window.__lanvanTimelineTracker.recordEvent("renderPrototype", "reason: " + renderReason + ", filesArg: " + fCount);
        }
        if (typeof window.__logF5Trace === "function") {
            window.__logF5Trace("5. After renderPrototypeFileList() entry");
        }
        if (typeof window !== "undefined") window.renderPrototypeFileList = renderPrototypeFileList;
        var normCurrentDir = cleanFolderPath((typeof window.getCurrentFolderPath === "function")
            ? window.getCurrentFolderPath()
            : currentFolderPath);
        var reason = renderReason || "render_prototype";
        var container = document.getElementById("nasFileList");
        var filePanelMeta = document.getElementById("filePanelMeta");
        if (!container) return;

        // Repository writes belong exclusively to refreshFileList() (main-app.js:2757)
        // and fetchFolderContents() (repository.js:89). The renderer must only read.
        if (files) {
            var taggedFolderPath = getTaggedFolderPath(files);

            if (taggedFolderPath !== null) {
                if (taggedFolderPath !== normCurrentDir) {
                    console.warn("[CACHE GUARD] Incoming payload belongs to '" + taggedFolderPath + "' but active view is '" + normCurrentDir + "'. Rendering active folder cache instead.");
                    files = window.FileRepository ? window.FileRepository.getFolderCache(normCurrentDir) : tagFilesWithFolder([], normCurrentDir);
                }
            } else {
                // Untagged payload: assume active folder ONLY if current folder is root Home ("")
                if (normCurrentDir !== "") {
                    console.warn("[CACHE GUARD] Rejecting untagged payload while viewing subfolder '" + normCurrentDir + "'. Rendering active folder cache instead.");
                    files = window.FileRepository ? window.FileRepository.getFolderCache(normCurrentDir) : tagFilesWithFolder([], normCurrentDir);
                } else {
                    files = tagFilesWithFolder(files, "");
                }
            }
            lastRenderedFiles = files;
        }

        var fileSource = "explicit_arg";
        if (!files || (Array.isArray(files) && files.length === 0)) {
            var cachedRepoFiles = window.FileRepository ? window.FileRepository.getFolderCache(normCurrentDir) : [];
            if (cachedRepoFiles && cachedRepoFiles.length > 0) {
                files = cachedRepoFiles;
                fileSource = "folder_cache_" + (normCurrentDir || "root");
            } else if (!files) {
                files = tagFilesWithFolder([], normCurrentDir);
                fileSource = "empty_folder_init";
            }
        }
        if (files) {
            if (getTaggedFolderPath(files) === null) {
                files = tagFilesWithFolder(files, normCurrentDir);
            }
            lastRenderedFiles = files;
        }

        var container = document.getElementById("nasFileList");
        var filePanelMeta = document.getElementById("filePanelMeta");
        if (!container) return;

        // Hide Recents (Quick Access) if inside a subfolder
        var quickContainer = document.getElementById("quickAccessContainer");
        if (quickContainer) {
            if (normCurrentDir && normCurrentDir !== "") {
                quickContainer.style.display = "none";
            } else {
                quickContainer.style.display = ""; // Reset
            }
        }

        renderBreadcrumbs();

        // files can be either string[] (names only) or object[] (with metadata)
        // Normalize to always have name, size, mtime, isFolder
        var normalizedFiles = [];
        if (files && files.length > 0) {
            for (var i = 0; i < files.length; i++) {
                var item = files[i];
                if (!item) continue;
                var fn = typeof item === "string" ? item : item.name;
                if (!fn) continue;

                var meta = (typeof item === "string") ? getDiskFileMetadata(item) : item;

                // ASSERTION: Fallback cache check
                if (fileSource.startsWith("fallback_")) {
                    console.error("  [ASSERTION FAILED] Fallback cache used during subfolder view! File: '" + fn + "' | Source: " + fileSource + " | CurrentFolder: '" + normCurrentDir + "'");
                    console.error("   WHO: renderPrototypeFileList | FROM: " + fileSource + " | WHY: files parameter was undefined/null during render!");
                }

                var isFolderFlag = false;
                if (meta) {
                    isFolderFlag = !!(meta.isFolder || meta.is_dir || meta.is_folder);
                } else if (typeof item === "object") {
                    isFolderFlag = !!(item.isFolder || item.is_dir || item.is_folder);
                } else if (window._recentlyCreatedFolders && window._recentlyCreatedFolders[fn]) {
                    isFolderFlag = true;
                }

                normalizedFiles.push({
                    name: fn,
                    size: meta ? meta.size : "--",
                    mtime: meta ? meta.mtime : 0,
                    isFolder: isFolderFlag
                });
            }
        }

        // DELEGATE TO PROJECTION LAYER (THE GOLDEN INVARIANT)
        // The Scheduler already runs Projection before calling the renderer.
        // When called from the Scheduler, `files` is already a pre-projected ViewModel.
        var viewModel;
        if (reason === 'scheduler' && Array.isArray(files) && files.length > 0 && files[0].hasOwnProperty('uploading')) {
            // Already projected by Scheduler: API → Repository → Scheduler → Projection → Renderer
            viewModel = files;
        } else {
            // Legacy callers: run Projection inline (temporary until all callers consolidated)
            var storeState = window.LanvanStore ? Object.assign({}, window.LanvanStore.state) : { currentFolder: normCurrentDir, pendingOps: {} };
            var liveUploadQueue = Array.isArray(window.uploadQueue) ? window.uploadQueue : [];
            storeState.currentFolder = normCurrentDir;
            storeState.uploadQueue = liveUploadQueue;
            if (!storeState.pendingOps) {
                storeState.pendingOps = {};
            }
            var projectionEngine = window.projectionLayer || (typeof window.ProjectionLayer === 'function' ? new window.ProjectionLayer() : window.ProjectionLayer);
            viewModel = projectionEngine ? projectionEngine.buildCurrentFolderViewModel(storeState, files) : normalizedFiles;

            var traceId = Math.random().toString(36).substring(2, 7);
            console.log("🛠️ [TRACE @" + traceId + " @ app-init.js:348] renderPrototypeFileList triggered | Reason: " + reason + " | Folder: '" + (normCurrentDir || "Home") + "'");
            console.log("   ↳ Disk Payload: " + (files ? files.length : 0) + " items | Active Queue: " + liveUploadQueue.length + " items");
            console.log("✨ [TRACE @" + traceId + " @ app-init.js:364] View Model Ready | Visible Count: " + (Array.isArray(viewModel) ? viewModel.length : 0) + " | Files: [" + (Array.isArray(viewModel) ? viewModel.map(function (f) { return f.name + (f.isFolder ? '(dir)' : '(file)'); }).join(", ") : "?") + "]");
        }

        normalizedFiles = Array.isArray(viewModel) ? viewModel : (viewModel.visibleFiles || []);
        var activeUploads = (viewModel && Array.isArray(viewModel.activeUploads)) ? viewModel.activeUploads : [];
        var originalFilesForQuickAccess = normalizedFiles.slice();

        console.log("✨ [TRACE @" + traceId + " @ app-init.js:364] View Model Ready | Visible Count: " + normalizedFiles.length + " | Files: [" + normalizedFiles.map(function (f) { return f.name + (f.isFolder ? '(dir)' : '(file)'); }).join(", ") + "]");

        // ASSERTIONS: Verify every dynamically merged active upload in current view
        activeUploads.forEach(function (item) {
            if (!item || !item.name) return;
            var qi = (window.uploadQueue || []).find(function (q) { return q && window.getItemName(q) === item.name; });
            if (qi) {
                var itemDir = cleanFolderPath(window.getItemFolder(qi));
                if (itemDir !== normCurrentDir) {
                    console.error("  [ASSERTION FAILED] Queue item from wrong folder rendered! File: '" + item.name + "' | Item targetDir: '" + itemDir + "' | currentFolder: '" + normCurrentDir + "'");
                    console.error("   WHO: renderPrototypeFileList | FROM: uploadQueue merge | WHY: targetDir mismatch! ('" + itemDir + "' !== '" + normCurrentDir + "')");
                }
            }
        });

        // Apply client-side Type Filtering
        if (typeFilter !== "all") {
            normalizedFiles = normalizedFiles.filter(function (f) {
                return getFileItemType(f) === typeFilter;
            });
        }

        // Apply client-side Search Filtering
        var toolbarSearchInputEl = document.getElementById("toolbarSearchInput");
        var searchQuery = toolbarSearchInputEl ? toolbarSearchInputEl.value.trim().toLowerCase() : "";
        if (searchQuery) {
            normalizedFiles = normalizedFiles.filter(function (f) {
                if (!f || !f.name) return false;
                return f.name.toLowerCase().indexOf(searchQuery) !== -1;
            });
        }

        // Apply client-side Sorting
        normalizedFiles.sort(function (a, b) {
            // Folders top / mixed logic
            if (sortFolders === "top") {
                if (a.isFolder && !b.isFolder) return -1;
                if (!a.isFolder && b.isFolder) return 1;
            }

            var comparison = 0;
            if (sortBy === "name") {
                comparison = a.name.localeCompare(b.name, undefined, { numeric: true, sensitivity: 'base' });
            } else if (sortBy === "date") {
                var timeA = a.mtime || (a.uploading ? Date.now() / 1000 : 0);
                var timeB = b.mtime || (b.uploading ? Date.now() / 1000 : 0);
                comparison = timeA - timeB;
            } else if (sortBy === "size") {
                var bytesA = parseSizeToBytes(a.size, a.isFolder);
                var bytesB = parseSizeToBytes(b.size, b.isFolder);
                comparison = bytesA - bytesB;
            }

            return sortDirection === "asc" ? comparison : -comparison;
        });

        var savedViewModeForSignature = "grid";
        try {
            savedViewModeForSignature = localStorage.getItem("lanvan_view_mode") || "grid";
        } catch (e) { }

        var renderSignature = [
            normCurrentDir,
            savedViewModeForSignature,
            typeFilter,
            searchQuery,
            normalizedFiles.map(function (f) {
                if (!f) return "";
                return [
                    f.name || "",
                    f.isFolder ? 1 : 0,
                    f.uploading ? 1 : 0,
                    Math.round((f.uploadProgress || 0) * 10) / 10,
                    f.uploadStatus || "",
                    f.size || "",
                    f.mtime || 0
                ].join("|");
            }).join("||")
        ].join("::");

        var isStillShowingLoadingShell = false;
        try {
            isStillShowingLoadingShell = !!container.querySelector(".loading-shell") ||
                /Loading files\.\.\./i.test(container.textContent || "");
        } catch (e) { }

        if (window._prototypeRenderHasPainted && window._lastPrototypeRenderSignature === renderSignature && !isStillShowingLoadingShell) {
            return;
        }
        window._lastPrototypeRenderSignature = renderSignature;

        // Sync dropdown checkmarks and header arrows
        updateSortCheckmarks();
        updateSortHeaderArrows();

        // Update file count in prototype panel meta
        if (filePanelMeta) {
            filePanelMeta.textContent = normalizedFiles.length
                ? normalizedFiles.length + " file" + (normalizedFiles.length === 1 ? "" : "s")
                : "";
        }

        var fileTableHead = document.getElementById("fileTableHead");
        var listBtn = document.getElementById("listViewBtn");
        var gridBtn = document.getElementById("gridViewBtn");

        if (savedViewModeForSignature === "grid") {
            container.classList.add("grid-mode");
            if (fileTableHead) fileTableHead.style.display = "none";
            if (gridBtn) gridBtn.classList.add("active");
            if (listBtn) listBtn.classList.remove("active");
        } else {
            container.classList.remove("grid-mode");
            if (fileTableHead) fileTableHead.style.display = "";
            if (listBtn) listBtn.classList.add("active");
            if (gridBtn) gridBtn.classList.remove("active");
        }

        if (!normalizedFiles || normalizedFiles.length === 0) {
            prototypeSelectedItems = [];
            window._contextMenuTarget = "";

            // Hide file table header when list is empty to prevent DOM overlap
            if (fileTableHead) fileTableHead.style.display = "none";

            var queue = window.uploadQueue || [];
            var activeUploadsCount = queue.filter(function (item) {
                return item.status === "UPLOADING" || item.status === "QUEUED" || item.status === "PROCESSING" || item.status === "PAUSED";
            }).length;

            if (searchQuery) {
                container.innerHTML =
                    '<div class="empty-dropzone-wrapper" style="grid-column: 1 / -1; width:100%; flex:1; min-height:300px; display:flex; flex-direction:column; align-items:center; justify-content:center; text-align:center; padding:3rem 0; margin:auto;">' +
                    '<div class="avatar-icon" style="width:64px;height:64px;border-radius:18px;margin-bottom:1rem;background:var(--toggle-bg);color:var(--text-muted);display:flex;align-items:center;justify-content:center;">' +
                    '<i data-lucide="search-x" style="width:32px;height:32px;"></i></div>' +
                    '<div style="font-size:1.05rem; font-weight:600; color:var(--text-color); margin-bottom:0.25rem;">No files matching "' + escapeHtml(searchQuery) + '"</div>' +
                    '<div style="font-size:0.82rem; color:var(--text-muted); margin-bottom:1rem;">Check spelling or try searching for another term.</div>' +
                    '<button class="filter-chip" onclick="clearToolbarSearch()" style="display:inline-flex; align-items:center; gap:0.35rem; font-size:0.8rem; font-weight:700; border:1px solid var(--border-color); background:var(--card-bg); color:var(--primary); border-radius:999px; padding:0.4rem 0.9rem; cursor:pointer;">Clear search</button>' +
                    '</div>';
            } else if (typeFilter !== "all") {
                container.innerHTML =
                    '<div class="empty-dropzone-wrapper" style="grid-column: 1 / -1; width:100%; flex:1; min-height:300px; display:flex; flex-direction:column; align-items:center; justify-content:center; text-align:center; padding:3rem 0; margin:auto;">' +
                    '<div class="avatar-icon" style="width:64px;height:64px;border-radius:18px;margin-bottom:1rem;background:var(--toggle-bg);color:var(--text-muted);display:flex;align-items:center;justify-content:center;">' +
                    '<i data-lucide="file-x" style="width:32px;height:32px;"></i></div>' +
                    '<div style="font-size:1.05rem; font-weight:600; color:var(--text-color); margin-bottom:0.25rem;">No ' + escapeHtml(typeFilter) + ' files found</div>' +
                    '<div style="font-size:0.82rem; color:var(--text-muted); margin-bottom:1rem;">No files match the active type filter.</div>' +
                    '<button class="filter-chip" onclick="clearTypeFilter(event)" style="display:inline-flex; align-items:center; gap:0.35rem; font-size:0.8rem; font-weight:700; border:1px solid var(--border-color); background:var(--card-bg); color:var(--primary); border-radius:999px; padding:0.4rem 0.9rem; cursor:pointer;">Clear filter</button>' +
                    '</div>';
            } else if (activeUploadsCount > 0) {
                container.innerHTML =
                    '<div class="empty-dropzone-wrapper" style="grid-column: 1 / -1; width:100%; flex:1; min-height:380px; display:flex; flex-direction:column; align-items:center; justify-content:center; text-align:center; padding:3rem 0; margin:auto;">' +
                    '<div class="avatar-icon avatar-folder" style="width:72px;height:72px;border-radius:18px;margin-bottom:1rem;">' +
                    '<i data-lucide="upload-cloud" style="width:34px;height:34px;"></i></div>' +
                    '<div style="font-size:1.05rem; font-weight:500; color:var(--text-color); margin-bottom:0.25rem;">Uploading ' + activeUploadsCount + ' file' + (activeUploadsCount === 1 ? '' : 's') + '...</div>' +
                    '<div style="font-size:0.8rem; color:var(--text-muted);">Files will appear here when upload completes.</div>' +
                    '</div>';
            } else {
                container.innerHTML =
                    '<div class="empty-dropzone-wrapper" style="grid-column: 1 / -1; width:100%; flex:1; min-height:380px; display:flex; flex-direction:column; align-items:center; justify-content:center; text-align:center; padding:3rem 0; margin:auto;">' +
                    '<div class="empty-dropzone-target" style="display:inline-flex; flex-direction:column; align-items:center; justify-content:center; padding:1.5rem 2.5rem; border-radius:16px; cursor:pointer; transition:background-color 0.2s ease;" onclick="if(typeof handleFileSelection===\'function\'){handleFileSelection(\'file\');}else{var fi=document.getElementById(\'fileInput\');if(fi){fi.value=\'\';fi.click();}}">' +
                    '<div class="avatar-icon avatar-folder" style="width:72px;height:72px;border-radius:18px;margin-bottom:1rem;">' +
                    '<i data-lucide="folder-open" style="width:34px;height:34px;"></i></div>' +
                    '<div style="font-size:1.05rem; font-weight:500; color:var(--text-color); margin-bottom:0.25rem;">Drop files here</div>' +
                    '<div style="font-size:0.8rem; color:var(--text-muted);">or right-click to upload / create folders.</div>' +
                    '</div>' +
                    '</div>';
            }
            window._prototypeRenderHasPainted = true;
            refreshLucideIcons(container);
            updateSelectionToolbar();
            try {
                renderQuickAccess(originalFilesForQuickAccess
                    .filter(function (f) { return !f.isFolder && !f.uploading; }));
            } catch (e) {
                console.error("[LANVAN UI] Quick access render failed during empty-state paint:", e);
            }
            return;
        }

        var isGrid = container.classList.contains("grid-mode");
        var html = "";
        for (var i = 0; i < normalizedFiles.length; i++) {
            var fileData = normalizedFiles[i];
            if (typeof fileData === 'string') {
                fileData = { name: fileData };
            }
            var name = fileData.name || "";
            if (!name) continue;

            // Fallback to FileRepository cache for full size/date metadata if missing
            var repoCache = window.FileRepository ? window.FileRepository.getFolderCache(normCurrentDir) : [];
            if ((!fileData.size && !fileData.mtime && !fileData.modified) && repoCache.length > 0) {
                var cachedMatch = repoCache.find(function (c) {
                    return c && typeof c === 'object' && c.name === name;
                });
                if (cachedMatch) {
                    fileData = Object.assign({}, cachedMatch, fileData);
                }
            }

            var isFolderItem = !!(fileData.isFolder || fileData.is_dir || fileData.is_folder);
            var ext = name.split(".").pop().toLowerCase();
            var info = isFolderItem
                ? { avatarClass: "avatar-folder", iconName: "folder" }
                : getFileTypeInfo(name, ext);
            var rawSize = fileData.size || fileData.size_formatted || fileData.formatted_size;
            if (!rawSize && typeof fileData.size_bytes === 'number') {
                rawSize = formatSize(fileData.size_bytes);
            }
            if (!rawSize && typeof fileData.fileSize === 'number') {
                rawSize = formatSize(fileData.fileSize);
            }
            var size = isFolderItem ? "-" : (rawSize || "--");
            var dateStr = fileData.modified || fileData.date || fileData.dateStr || fileData.modified_formatted || "--";
            var subtitle = isFolderItem ? (fileData.formattedSubtitle || "Folder") : "File";
            if (dateStr === "--" && fileData.mtime) {
                var d = new Date(fileData.mtime * 1000);
                dateStr = d.toLocaleDateString(undefined, { month: "short", day: "numeric" });
            }
            if (isGrid) {
                html += buildGridItem(
                    name,
                    info,
                    size,
                    dateStr,
                    subtitle,
                    isFolderItem,
                    !!fileData.uploading,
                    fileData.uploadProgress || 0,
                    fileData.uploadId,
                    fileData.uploadStatus
                );
            } else {
                html += buildListItem(
                    name,
                    info,
                    size,
                    dateStr,
                    subtitle,
                    isFolderItem,
                    !!fileData.uploading,
                    fileData.uploadProgress || 0,
                    fileData.uploadId,
                    fileData.uploadStatus
                );
            }
        }
        window._prototypeRenderHasPainted = true;
        // Preserve existing ALREADY-LOADED video and image previews to eliminate blank flickers
        var existingPreviews = {};
        var existingItems = container.querySelectorAll(".m3-list-item");
        for (var k = 0; k < existingItems.length; k++) {
            var fn = existingItems[k].getAttribute("data-filename");
            var prev = existingItems[k].querySelector(".grid-card-preview");
            if (fn && prev) {
                var vid = prev.querySelector("video");
                var img = prev.querySelector("img");
                // Only preserve if video has decoded frame (readyState >= 2) or image is loaded (naturalWidth > 0)
                var isVidReady = vid && vid.readyState >= 2 && vid.networkState !== 3;
                var isImgReady = img && img.complete && img.naturalWidth > 0;
                if (isVidReady || isImgReady) {
                    existingPreviews[fn] = prev;
                }
            }
        }

        var prevChildCount = container.children.length;
        var stackTrace = (new Error()).stack || "";
        var callerLine = stackTrace.split("\n")[2] || "";
        console.log("[DOM-WRITE-TRACE] 💥 DOM WRITE TO #" + (container.id || "nasFileList") + "\n" +
                    "   Timestamp: " + performance.now().toFixed(1) + "ms\n" +
                    "   File: app-init.js:645\n" +
                    "   Function: renderPrototypeFileList\n" +
                    "   Caller: " + callerLine.trim() + "\n" +
                    "   Target Element: #" + (container.id || "nasFileList") + "\n" +
                    "   Previous Child Count: " + prevChildCount + "\n" +
                    "   HTML Length: " + html.length + "\n" +
                    "   Reason: " + (renderReason || "prototype_render") + "\n" +
                    "   Call Stack:\n" + stackTrace);

        var oldDomItems = Array.prototype.slice.call(container.querySelectorAll(".m3-list-item")).map(function(el) { return el.getAttribute("data-filename") || el.textContent.trim(); });
        container.innerHTML = html;
        var newDomItems = Array.prototype.slice.call(container.querySelectorAll(".m3-list-item")).map(function(el) { return el.getAttribute("data-filename") || el.textContent.trim(); });

        console.log("[DOM-WRITE-TRACE] ✅ New Child Count: " + container.children.length + " | Visible List Items: [" + newDomItems.join(", ") + "]");

        // Re-insert loaded preview elements to keep video/image frames smooth without reloading
        var newItems = container.querySelectorAll(".m3-list-item");
        for (var n = 0; n < newItems.length; n++) {
            var itemFn = newItems[n].getAttribute("data-filename");
            var oldPrev = existingPreviews[itemFn];
            var newPrev = newItems[n].querySelector(".grid-card-preview");
            if (oldPrev && newPrev) {
                newPrev.parentNode.replaceChild(oldPrev, newPrev);
            }
        }

        // Attach click handlers — pass full normalized data for folder detection
        attachListItemHandlers(container, normalizedFiles.map(function (f) { return f.name; }), normalizedFiles);

        // Sync selection state: purge any deleted or uploading items from prototypeSelectedItems
        var validNames = normalizedFiles.map(function (f) { return f.name; });
        if (Array.isArray(prototypeSelectedItems)) {
            prototypeSelectedItems = prototypeSelectedItems.filter(function (name) {
                return validNames.indexOf(name) !== -1 && !isItemUploading(name);
            });
            var renderedItems = container.querySelectorAll(".m3-list-item");
            for (var s = 0; s < renderedItems.length; s++) {
                var itemFn = renderedItems[s].getAttribute("data-filename");
                if (itemFn && prototypeSelectedItems.indexOf(itemFn) !== -1) {
                    renderedItems[s].classList.add("selected");
                } else {
                    renderedItems[s].classList.remove("selected");
                }
            }
        }
        updateSelectionToolbar();

        // Also render quick access cards (only non-folders)
        try {
            renderQuickAccess(originalFilesForQuickAccess
                .filter(function (f) { return !f.isFolder && !f.uploading; }));
        } catch (e) {
            console.error("[LANVAN UI] Quick access render failed during file-list paint:", e);
        }

        refreshLucideIcons(container);
    }

    /**
     * Determine file type icon and avatar class.
     */
    function getFileTypeInfo(name, ext) {
        var imageExts = ["png", "jpg", "jpeg", "gif", "webp", "svg", "bmp", "ico"];
        var videoExts = ["mp4", "mov", "avi", "mkv", "webm", "flv", "wmv"];
        var audioExts = ["mp3", "wav", "ogg", "flac", "aac", "m4a"];
        var archiveExts = ["zip", "rar", "7z", "tar", "gz", "bz2"];
        var docExts = ["pdf", "doc", "docx", "xls", "xlsx", "ppt", "pptx", "txt", "md", "csv"];

        if (imageExts.indexOf(ext) !== -1) return { avatarClass: "avatar-image", iconName: "image" };
        if (videoExts.indexOf(ext) !== -1) return { avatarClass: "avatar-video", iconName: "video" };
        if (audioExts.indexOf(ext) !== -1) return { avatarClass: "avatar-audio", iconName: "music" };
        if (archiveExts.indexOf(ext) !== -1) return { avatarClass: "avatar-archive", iconName: "archive" };
        if (docExts.indexOf(ext) !== -1) return { avatarClass: "avatar-doc", iconName: "file-text" };
        return { avatarClass: "avatar-doc", iconName: "file" };
    }

    // buildListItem and buildGridItem are provided by m3-file-renderer.js module

    /**
     * Attach click handlers to prototype list items after render.
     * @param {Element} container - The list container
     * @param {string[]} files - Array of file/folder names
     * @param {object[]} filesData - Array of file metadata objects
     */
    function attachListItemHandlers(container, files, filesData) {
        var items = container.querySelectorAll(".m3-list-item");
        for (var i = 0; i < items.length; i++) {
            (function (item, index) {
                var name = files[index];
                var itemData = (filesData || [])[index] || {};
                var folderFlag = item.getAttribute("data-is-folder") === "1" || !!itemData.isFolder;

                // Click / Tap handler (Single click selects item or enters folder)
                item.addEventListener("click", function (e) {
                    if (e.target.closest("button")) return;

                    var isSelected = prototypeSelectedItems.indexOf(name) !== -1 || item.classList.contains("selected");

                    // Folder navigation logic: always allow entering folders even if uploads are active inside
                    if (folderFlag) {
                        if (prototypeSelectedItems.length > 0) {
                            handleListItemClick(item, index, files);
                        } else {
                            navigateIntoFolder(name);
                        }
                        return;
                    }

                    // If a FILE is uploading and NOT selected, prevent selecting it
                    if ((itemData.uploading || isItemUploading(name)) && !isSelected) {
                        return;
                    }

                    // Single click selects or unselects file item
                    handleListItemClick(item, index, files);
                });

                // Context menu listener on item row
                item.addEventListener("contextmenu", function (e) {
                    if (e.target.closest("button")) return;
                    if (!folderFlag && (itemData.uploading || isItemUploading(name))) {
                        e.preventDefault();
                        e.stopPropagation();
                        return;
                    }
                    e.preventDefault();
                    openRowMenu(e, name);
                });

                // Double-click handler for desktop mouse
                item.addEventListener("dblclick", function (e) {
                    if (e.target.closest("button")) return;
                    if (folderFlag) {
                        navigateIntoFolder(name);
                        return;
                    }
                    if (itemData.uploading || isItemUploading(name)) return;
                    window.openFilePreview(name);
                });

                // Cancel upload button
                var cancelBtn = item.querySelector('[data-action="cancel-upload"]');
                if (cancelBtn) {
                    cancelBtn.addEventListener("click", function (e) {
                        e.stopPropagation();
                        var uploadId = cancelBtn.getAttribute("data-upload-id");
                        if (uploadId && typeof window.cancelUpload === "function") {
                            window.cancelUpload(parseInt(uploadId));
                        }
                    });
                }

                // Play/Pause toggle button click listener
                var playPauseBtn = item.querySelector('[data-action="pause-upload"], [data-action="resume-upload"]');
                if (playPauseBtn) {
                    playPauseBtn.addEventListener("click", function (e) {
                        e.stopPropagation();
                        var uploadId = playPauseBtn.getAttribute("data-upload-id");
                        var action = playPauseBtn.getAttribute("data-action");
                        if (uploadId) {
                            var parsedId = parseInt(uploadId);
                            if (action === "pause-upload" && typeof window.pauseUpload === "function") {
                                window.pauseUpload(parsedId);
                            } else if (action === "resume-upload" && typeof window.resumeUpload === "function") {
                                window.resumeUpload(parsedId);
                            }
                        }
                    });
                }

                // Download button
                var dlBtn = item.querySelector('[data-action="download"]');
                if (dlBtn) {
                    dlBtn.addEventListener("click", function (e) {
                        e.stopPropagation();
                        var fname = dlBtn.getAttribute("data-filename");
                        var isF = dlBtn.getAttribute("data-is-folder") === "1";
                        if (isF) {
                            downloadFolderAsZip(fname);
                        } else {
                            downloadFileByName(fname);
                        }
                    });
                }

                // Rename button (files only)
                var renameBtn = item.querySelector('[data-action="rename"]');
                if (renameBtn) {
                    renameBtn.addEventListener("click", function (e) {
                        e.stopPropagation();
                        var fname = renameBtn.getAttribute("data-filename");
                        prototypeSelectedItems = [fname];
                        window._contextMenuTarget = fname;
                        window.openRenameModal();
                    });
                }

                // Star button (files only)
                // Menu button
                var menuBtn = item.querySelector('[data-action="menu"]');
                if (menuBtn) {
                    menuBtn.addEventListener("click", function (e) {
                        e.stopPropagation();
                        var fname = menuBtn.getAttribute("data-filename");
                        if (isItemUploading(fname)) return;
                        openRowMenu(e, fname);
                    });
                }
            })(items[i], i);
        }
    }

    /**
     * Navigate into a subfolder, updating breadcrumbs and fetching contents.
     */
    var lastFolderNavTime = 0;
    function navigateIntoFolder(folderName) {
        var now = Date.now();
        if (now - lastFolderNavTime < 400) {
            return;
        }
        lastFolderNavTime = now;

        var base = (typeof window.getCurrentFolderPath === "function")
            ? window.getCurrentFolderPath()
            : currentFolderPath;
        if (base === "Home") base = "";
        base = cleanFolderPath(base);

        // Allow navigating to subfolders with the same name (e.g. "SameTest/SameTest")
        // Only prevent the no-op case where we'd navigate into the exact same path
        var newPath = base ? (base + "/" + folderName) : folderName;
        if (newPath === cleanFolderPath((typeof window.getCurrentFolderPath === "function") ? window.getCurrentFolderPath() : currentFolderPath)) {
            return;
        }

        console.log("%c[LANVAN UI] 📂 Navigating into folder: '%s'", "color:#3b82f6; font-weight:bold;", newPath);
        prototypeSelectedItems = [];
        updateSelectionToolbar();

        window.currentFolderPath = newPath;
        if (window.history && typeof window.history.replaceState === "function") {
            try {
                window.history.replaceState({ folder: newPath }, "", window.location.pathname);
            } catch (e) { }
        }
    }

    /**
     * Handle item click — toggle selection.
     */
    var prototypeSelectedItems = [];
    Object.defineProperty(window, 'prototypeSelectedItems', {
        get: function () {
            if (typeof window.LanvanStore !== 'undefined' && window.LanvanStore.getState) {
                return window.LanvanStore.getState().selection || prototypeSelectedItems;
            }
            return prototypeSelectedItems;
        },
        set: function (val) {
            prototypeSelectedItems = Array.isArray(val) ? val : [];
            if (typeof window.LanvanStore !== 'undefined' && window.LanvanStore.dispatch) {
                window.LanvanStore.dispatch("SET_SELECTION", { files: prototypeSelectedItems }, "NORMAL");
            }
        },
        configurable: true
    });

    function handleListItemClick(item, index, files) {
        var name = files[index];
        console.log("%c[LANVAN UI] 👆 Item clicked: '%s'", "color:#10b981; font-weight:bold;", name);
        var pos = prototypeSelectedItems.indexOf(name);
        if (pos > -1 || item.classList.contains("selected")) {
            if (pos > -1) prototypeSelectedItems.splice(pos, 1);
            item.classList.remove("selected");
        } else {
            if (!isItemUploading(name)) {
                prototypeSelectedItems.push(name);
                item.classList.add("selected");
            }
        }
        updateSelectionToolbar();
    }

    function isItemUploading(filename) {
        if (!filename) return false;
        if (lastRenderedFiles && lastRenderedFiles.length > 0) {
            var r = lastRenderedFiles.find(function (f) {
                return f && (f.name === filename || (typeof f === 'string' && f === filename));
            });
            if (r && (r.uploading || r.uploadStatus)) return true;
        }
        var queue = window.uploadQueue || [];
        var targetBase = filename.split("/").pop().split("\\").pop();
        for (var i = 0; i < queue.length; i++) {
            var item = queue[i];
            if (!item) continue;
            var status = item.status;
            if (status === 'UPLOADING' || status === 'QUEUED' || status === 'PROCESSING' || status === 'PAUSED') {
                var names = [
                    item.fileName,
                    item.name,
                    item.file ? item.file.name : "",
                    item.relativePath,
                    typeof window.getItemName === "function" ? window.getItemName(item) : ""
                ];
                for (var j = 0; j < names.length; j++) {
                    var n = names[j];
                    if (!n) continue;
                    if (n === filename || n.split("/").pop().split("\\").pop() === targetBase) return true;
                }
            }
        }
        return false;
    }

    /**
     * Update selection toolbar based on prototypeSelectedItems.
     */
    // updateSelectionToolbar and clearSelection are provided by selection-manager.js module

    /**
     * Sync prototype clipboard from production #clipboardHistoryContent DOM.
     */
    function syncPrototypeClipboard() {
        var protoContainer = document.getElementById("clipboardHistory");
        var prodContainer = document.getElementById("clipboardHistoryContent");
        if (!protoContainer || !prodContainer) return;

        // Production stores clipboard items as child elements
        var items = prodContainer.querySelectorAll("div[style]");
        if (items.length === 0) {
            // Try reading innerText as fallback
            var text = prodContainer.innerText.trim();
            if (!text || text.indexOf("No clipboard items") !== -1) {
                protoContainer.innerHTML =
                    '<div style="text-align:center; padding:2rem; color:var(--text-muted); font-size:0.85rem;">No items in clipboard history yet.</div>';
                return;
            }
        }

        var html = "";
        for (var i = 0; i < items.length; i++) {
            var itemText = items[i].innerText.trim();
            if (!itemText) continue;
            html +=
                '<div class="m3-list-item" style="cursor:pointer;">' +
                '<div class="file-name-cell" style="flex:1;min-width:0;margin-right:1rem;">' +
                '<div class="avatar-icon" style="background:#e8def8;color:#1d192b;"><i data-lucide="link"></i></div>' +
                '<div class="item-main" style="flex:1;min-width:0;">' +
                '<div class="item-title" style="white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">' +
                escapeHtml(itemText) +
                "</div>" +
                '<div class="item-subtitle">Text</div>' +
                "</div>" +
                "</div>" +
                '<div class="row-actions" style="display:flex;align-items:center;gap:0.35rem;">' +
                '<button class="btn-icon" onclick="event.stopPropagation();copyToClipboard(\'' +
                escapeHtml(itemText).replace(/'/g, "\\'") +
                "');\" title=\"Copy\">" +
                '<i data-lucide="copy" style="width:16px;height:16px;"></i>' +
                "</button>" +
                "</div>" +
                "</div>";
        }
        protoContainer.innerHTML = html || '<div style="text-align:center; padding:2rem; color:var(--text-muted); font-size:0.85rem;">No items in clipboard history yet.</div>';
        if (window.lucide) lucide.createIcons();
    }

    // =========================================================================
    // 3. PROTOTYPE UI HANDLERS — Stubs wired to production
    // =========================================================================

    // --- View Switching ---
    window.switchView = function (tab) {
        if (!tab || tab === "recent") tab = "file";
        window.activeTab = tab;

        var fileView = document.getElementById("fileView");
        var clipView = document.getElementById("clipboardView");

        // Sidebar items
        var sideFile = document.getElementById("sideItemFile");
        var sideClip = document.getElementById("sideItemClipboard");

        // Bottom nav items
        var navFile = document.getElementById("navItemFile");
        var navClip = document.getElementById("navItemClipboard");

        // Clear selection when switching views
        window.clearSelection();

        // Deactivate all sidebar items
        var allSideItems = [sideFile, sideClip];
        for (var i = 0; i < allSideItems.length; i++) {
            if (allSideItems[i]) allSideItems[i].classList.remove("active");
        }

        // Deactivate all nav items
        var allNavItems = [navFile, navClip];
        for (var j = 0; j < allNavItems.length; j++) {
            if (allNavItems[j]) allNavItems[j].classList.remove("active");
        }

        if (tab === "clipboard") {
            if (fileView) fileView.style.display = "none";
            if (clipView) clipView.style.display = "flex";
            if (sideClip) sideClip.classList.add("active");
            if (navClip) navClip.classList.add("active");
            if (typeof refreshClipboardHistory === "function") refreshClipboardHistory();
        } else {
            if (fileView) fileView.style.display = "flex";
            if (clipView) clipView.style.display = "none";
            if (sideFile) sideFile.classList.add("active");
            if (navFile) navFile.classList.add("active");

            if (typeof lastRenderedFiles !== "undefined") {
                renderPrototypeFileList(lastRenderedFiles);
            }
        }
    };

    // --- Theme ---
    window.setThemePreference = function (theme) {
        localStorage.setItem("theme_preference", theme);
        // Keep legacy dark_mode_enabled in sync
        localStorage.setItem("dark_mode_enabled", theme === "dark" ? "1" : "0");
        if (typeof window.applyThemePreference === "function") {
            window.applyThemePreference(theme);
        }
    };

    window.toggleDarkMode = function () {
        var currentPref = localStorage.getItem("theme_preference") || "system";
        var nextPref = "system";
        if (currentPref === "system") {
            nextPref = "light";
        } else if (currentPref === "light") {
            nextPref = "dark";
        } else {
            nextPref = "system";
        }
        window.setThemePreference(nextPref);
    };

    // --- Settings Dialog ---
    window.openSettingsDialog = function () {
        var dialog = document.getElementById("settingsDialog");
        if (!dialog) return;

        // Sync AES toggle from production
        var aesProd = document.getElementById("enableEncryption");
        var aesSetting = document.getElementById("aesSettingToggle");
        if (aesProd && aesSetting) aesSetting.checked = aesProd.checked;

        // Sync theme preferences
        var themePref = localStorage.getItem("theme_preference") || "system";
        if (typeof window.applyThemePreference === "function") {
            window.applyThemePreference(themePref);
        }

        dialog.style.display = "flex";

        // Wire AES setting toggle to production
        if (aesSetting) {
            aesSetting.onchange = function () {
                if (aesProd) {
                    aesProd.checked = this.checked;
                    localStorage.setItem("aes_enabled", this.checked ? "1" : "0");
                    // Trigger change event on production toggle for ui-modules.js handlers
                    aesProd.dispatchEvent(new Event("change", { bubbles: true }));
                }
            };
        }
    };

    window.closeSettingsDialog = function () {
        var dialog = document.getElementById("settingsDialog");
        if (dialog) dialog.style.display = "none";
    };

    // --- Upload Triggers ---
    window.triggerFileInput = function (type) {
        if (type === "folder") {
            var prodFolderInput = document.getElementById("folderInput") || document.getElementById("hiddenFolderInput");
            if (prodFolderInput) {
                prodFolderInput.setAttribute("webkitdirectory", "");
                prodFolderInput.setAttribute("directory", "");
                prodFolderInput.setAttribute("mozdirectory", "");
                prodFolderInput.value = "";
                prodFolderInput.click();
            }
        } else {
            var prodFileInput = document.getElementById("fileInput");
            if (prodFileInput) {
                prodFileInput.value = "";
                prodFileInput.click();
            }
        }
    };

    window.showMobileUploadMenu = function (event) {
        if (event) event.stopPropagation();
        var sheet = document.getElementById("mobileAddSheetOverlay");
        if (sheet) sheet.classList.add("active");
    };

    window.closeMobileAddSheet = function () {
        var sheet = document.getElementById("mobileAddSheetOverlay");
        if (sheet) sheet.classList.remove("active");
    };

    // --- File Operations ---
    window.downloadSelected = function () {
        var items = prototypeSelectedItems.slice();
        var target = window._contextMenuTarget || "";

        if (items.length === 0 && target) {
            items = [target];
        }
        window._contextMenuTarget = "";

        if (items.length === 0) return;

        var index = 0;
        function downloadNext() {
            if (index >= items.length) {
                if (typeof showToast === "function") {
                    showToast("Downloaded " + items.length + " item(s).", 3000);
                }
                window.clearSelection();
                return;
            }
            var targetItem = items[index];
            var isFolder = false;
            var listEl = document.querySelector('#nasFileList [data-filename="' + targetItem.replace(/"/g, '&quot;') + '"]');
            if (listEl) {
                isFolder = listEl.getAttribute("data-is-folder") === "1";
            }
            if (!isFolder) {
                var foundMeta = getDiskFileMetadata(targetItem);
                if (foundMeta && (foundMeta.isFolder || foundMeta.is_dir)) isFolder = true;
            }

            if (isFolder) {
                downloadFolderAsZip(targetItem);
            } else {
                downloadFileByName(targetItem);
            }

            index++;
            if (index < items.length) {
                setTimeout(downloadNext, 300); // 300ms delay between downloads
            }
        }
        downloadNext();
    };

    window.downloadSelectedAsZip = function () {
        var menu = document.getElementById("contextMenu");
        if (menu) menu.style.display = "none";

        var items = prototypeSelectedItems.slice();
        var target = window._contextMenuTarget || "";

        if (items.length === 0 && target) {
            items = [target];
        }
        window._contextMenuTarget = "";

        if (items.length === 0) return;

        if (typeof showToast === "function") {
            showToast("Preparing ZIP archive...", 0);
        }

        fetch("/api/files/download-zip", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ files: items })
        })
            .then(function (res) {
                if (!res.ok) {
                    if (res.status === 404) {
                        window.location.href = "/download-all";
                        return null;
                    }
                    throw new Error("Status " + res.status);
                }

                var contentLength = res.headers.get("Content-Length");
                var totalBytes = contentLength ? parseInt(contentLength, 10) : 0;
                var receivedBytes = 0;
                var chunks = [];

                if (!res.body || !res.body.getReader) {
                    if (typeof showToast === "function") {
                        showToast("Processing ZIP download...", 0);
                    }
                    return res.blob();
                }

                var reader = res.body.getReader();

                function readChunk() {
                    return reader.read().then(function (result) {
                        if (result.done) {
                            return new Blob(chunks, { type: "application/zip" });
                        }
                        chunks.push(result.value);
                        receivedBytes += result.value.length;

                        if (typeof showToast === "function") {
                            var recvMB = (receivedBytes / (1024 * 1024)).toFixed(1);
                            if (totalBytes > 0) {
                                var pct = Math.min(100, Math.round((receivedBytes / totalBytes) * 100));
                                var totalMB = (totalBytes / (1024 * 1024)).toFixed(1);
                                showToast("Processing ZIP download: " + recvMB + " / " + totalMB + " MB (" + pct + "%)", 0);
                            } else {
                                showToast("Processing ZIP download: " + recvMB + " MB transferred...", 0);
                            }
                        }

                        return readChunk();
                    });
                }

                return readChunk();
            })
            .then(function (blob) {
                if (!blob) return;
                var url = URL.createObjectURL(blob);
                var a = document.createElement("a");
                a.href = url;
                a.download = items.length === 1 ? items[0] + ".zip" : "selected_files.zip";
                document.body.appendChild(a);
                a.click();
                document.body.removeChild(a);
                URL.revokeObjectURL(url);
                if (typeof showToast === "function") {
                    showToast("ZIP download started!", 3500);
                }
                window.clearSelection();
            })
            .catch(function (err) {
                console.error("ZIP download error:", err);
                if (typeof showToast === "function") {
                    showToast("Error downloading ZIP archive.", 4000);
                }
            });
    };

    window.deleteSelected = function () {
        if (typeof window.closePreviewModal === "function") {
            window.closePreviewModal();
        }
        var itemsToDelete = [];
        var target = window._contextMenuTarget || "";

        if (prototypeSelectedItems.length > 0) {
            // If targeted item is in the selected list or target was not explicitly set for another item, delete all selected items
            if (target && prototypeSelectedItems.indexOf(target) !== -1) {
                itemsToDelete = prototypeSelectedItems.slice();
            } else if (!target) {
                itemsToDelete = prototypeSelectedItems.slice();
            } else {
                // Targeted single item outside active multi-selection
                itemsToDelete = [target];
            }
        } else if (target) {
            itemsToDelete = [target];
        }

        // Always clear context menu target after reading
        window._contextMenuTarget = "";

        if (itemsToDelete.length === 0) return;

        var completed = 0;
        var failed = [];

        function deleteNext(index) {
            if (index >= itemsToDelete.length) {
                if (failed.length > 0) {
                    if (typeof showToast === "function") showToast("Deleted " + completed + " item(s). " + failed.length + " failed.", 4000);
                } else {
                    if (typeof showToast === "function") showToast("Deleted " + completed + " item(s) successfully.", 3000);
                }
                window._contextMenuTarget = "";
                window.clearSelection();
                if (typeof refreshFileList === "function") refreshFileList();
                if (typeof window.requestSafeVisibleFilesRefresh === "function") {
                    window.requestSafeVisibleFilesRefresh(120);
                } else if (typeof fetchFilesData === "function") {
                    fetchFilesData().then(function (fd) { renderPrototypeFileList(fd); });
                }
                return;
            }

            var filename = itemsToDelete[index];
            if (window._recentlyCreatedFolders) {
                delete window._recentlyCreatedFolders[filename];
            }

            // Abort active upload transfers & mark queue items as deleted immediately
            window._cancelledFilesMap = window._cancelledFilesMap || {};
            var parentPath = (currentFolderPath === "Home" || currentFolderPath === "Home/" || !currentFolderPath) ? "" : currentFolderPath;
            var cleanParent = parentPath.replace(/^Home\/?/, "");
            var fullRelPath = cleanParent ? (cleanParent + "/" + filename) : filename;
            window._cancelledFilesMap[fullRelPath] = true;
            window._cancelledFilesMap["Home/" + fullRelPath] = true;
            window._cancelledFilesMap[filename] = true;

            if (Array.isArray(window.uploadQueue)) {
                var basename = filename.split('/').pop().split('\\').pop();
                window.uploadQueue.forEach(function (qi) {
                    if (!qi) return;
                    var qiName = (qi.fileName || qi.name || "");
                    var qiFolder = (qi.targetDir || qi.parent_path || qi.folder || "").replace(/^Home\/?/, "");
                    if (qiName === basename || qiName === filename || qiFolder === filename || qiFolder.startsWith(filename + "/")) {
                        if (qi.xhr) {
                            try { qi.xhr.abort(); } catch (err) { }
                        }
                        qi.status = 'DELETED';
                        qi.error = 'Deleted by user';
                    }
                });
                if (typeof saveUploadQueueToStorage === "function") saveUploadQueueToStorage();
                if (typeof renderUploadTray === "function") renderUploadTray();
            }

            // Check if this is a folder by looking at rendered list and stored metadata
            var isFolder = false;
            var listItems = document.querySelectorAll('#nasFileList .m3-list-item');
            for (var k = 0; k < listItems.length; k++) {
                var itemFn = listItems[k].getAttribute("data-filename");
                if (itemFn === filename || (typeof escapeHtml === "function" && itemFn === escapeHtml(filename))) {
                    isFolder = listItems[k].getAttribute("data-is-folder") === "1";
                    break;
                }
            }
            if (!isFolder) {
                var foundData = getDiskFileMetadata(filename);
                if (foundData) isFolder = !!(foundData.isFolder || foundData.is_dir);
            }

            var formData = new FormData();
            formData.append("filename", filename);
            if (cleanParent) formData.append("parent_path", cleanParent);

            var url, method;
            if (isFolder) {
                url = "/delete-folder/" + encodeURIComponent(filename);
                method = "POST";
            } else {
                url = "/delete/" + encodeURIComponent(filename);
                method = "POST";
            }

            var xhr = new XMLHttpRequest();
            xhr.open(method, url);
            xhr.onload = function () {
                completed++;
                if (typeof window.triggerInstantUIUpdate === "function") window.triggerInstantUIUpdate();
                deleteNext(index + 1);
            };
            xhr.onerror = function () {
                completed++; // Count as handled since queue items were aborted/deleted
                if (typeof window.triggerInstantUIUpdate === "function") window.triggerInstantUIUpdate();
                deleteNext(index + 1);
            };
            xhr.send(formData);
        }

        deleteNext(0);
    };

    function downloadFileByName(filename) {
        if (!filename) return;
        var isFolder = false;
        var listEl = document.querySelector('#nasFileList [data-filename="' + filename.replace(/"/g, '&quot;') + '"]');
        if (listEl) {
            isFolder = listEl.getAttribute("data-is-folder") === "1";
        }
        if (!isFolder) {
            var foundMeta = getDiskFileMetadata(filename);
            if (foundMeta && (foundMeta.isFolder || foundMeta.is_dir)) isFolder = true;
        }

        if (isFolder) {
            downloadFolderAsZip(filename);
            return;
        }

        var link = document.createElement("a");
        link.href = "/download/" + encodeURIComponent(filename);
        link.download = filename;
        link.style.display = "none";
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
    }

    function downloadFolderAsZip(folderName) {
        if (!folderName) return;
        // Use the production folder-download endpoint which returns ZIP
        var link = document.createElement("a");
        link.href = "/download-folder/" + encodeURIComponent(folderName);
        link.download = folderName + ".zip";
        link.style.display = "none";
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
    }

    // --- Item Selection Helper ---
    window.setSelectedItem = function (filename) {
        if (!filename || isItemUploading(filename)) return;
        prototypeSelectedItems = [filename];
        var items = document.querySelectorAll("#nasFileList .m3-list-item");
        for (var i = 0; i < items.length; i++) {
            var itemFn = items[i].getAttribute("data-filename");
            if (itemFn === filename) {
                items[i].classList.add("selected");
            } else {
                items[i].classList.remove("selected");
            }
        }
        if (typeof updateSelectionToolbar === "function") {
            updateSelectionToolbar();
        }
    };

    window.handleCopyStreamLinkFromMenu = function () {
        var menu = document.getElementById("contextMenu");
        if (menu) menu.style.display = "none";
        var fname = window._contextMenuTarget || (prototypeSelectedItems && prototypeSelectedItems[0]) || "";
        if (fname && typeof copyVideoStreamUrl === "function") {
            copyVideoStreamUrl(fname);
        }
    };

    // --- Context Menu ---
    window.openRowMenu = function (event, filename) {
        event.stopPropagation();
        if (isItemUploading(filename)) {
            if (event.preventDefault) event.preventDefault();
            var menuToHide = document.getElementById("contextMenu");
            if (menuToHide) menuToHide.style.display = "none";
            return;
        }
        var menu = document.getElementById("contextMenu");
        var genericOps = document.getElementById("genericMenuOptions");
        var itemOps = document.getElementById("itemMenuOptions");
        if (!menu) return;

        if (genericOps) genericOps.style.display = "none";
        if (itemOps) itemOps.style.display = "block";

        window._contextMenuTarget = filename;

        // Smart Selection Logic for Right-Click Context Menu:
        // If filename is NOT currently part of prototypeSelectedItems, select ONLY filename.
        // If filename IS ALREADY in prototypeSelectedItems (multi-selection), PRESERVE ALL selected items!
        if (filename) {
            var alreadySelected = Array.isArray(prototypeSelectedItems) && prototypeSelectedItems.indexOf(filename) !== -1;
            if (!alreadySelected) {
                prototypeSelectedItems = [filename];
            }
            // Sync visual DOM selection state across list items and quick cards
            var items = document.querySelectorAll("#nasFileList .m3-list-item, .quick-card");
            for (var i = 0; i < items.length; i++) {
                var itemFn = items[i].getAttribute("data-filename");
                if (itemFn && prototypeSelectedItems.indexOf(itemFn) !== -1) {
                    items[i].classList.add("selected");
                } else {
                    items[i].classList.remove("selected");
                }
            }
            if (typeof updateSelectionToolbar === "function") {
                updateSelectionToolbar();
            }
        }

        // Check if target item is a folder
        var isTargetFolder = false;
        var targetName = filename || (prototypeSelectedItems && prototypeSelectedItems[0]) || "";
        if (targetName) {
            var listEl = document.querySelector('#nasFileList [data-filename="' + targetName.replace(/"/g, '&quot;') + '"]');
            if (listEl) {
                isTargetFolder = listEl.getAttribute("data-is-folder") === "1";
            } else {
                var meta = getDiskFileMetadata(targetName);
                if (meta) isTargetFolder = !!meta.isFolder;
            }
        }

        // Context menu items visibility based on multi-selection count & item type
        var isSingle = prototypeSelectedItems.length <= 1;

        var renameItem = document.getElementById("renameMenuItem");
        if (renameItem) renameItem.style.display = "flex";

        // Preview item: HIDE if target is a folder OR if multiple items selected
        var previewItem = document.getElementById("previewMenuItem");
        if (previewItem) previewItem.style.display = (isSingle && !isTargetFolder) ? "flex" : "none";

        var downloadText = document.getElementById("downloadMenuText");
        var downloadZipItem = document.getElementById("downloadZipMenuItem");
        if (isSingle && isTargetFolder) {
            if (downloadText) downloadText.textContent = "Download as ZIP";
            if (downloadZipItem) downloadZipItem.style.display = "none";
        } else if (isSingle) {
            if (downloadText) downloadText.textContent = "Download";
            if (downloadZipItem) downloadZipItem.style.display = "none";
        } else {
            if (downloadText) downloadText.textContent = "Download individually";
            if (downloadZipItem) downloadZipItem.style.display = "flex";
        }

        // Show/Hide "Copy Stream Link" option if single item and target file is a video
        var copyStreamLinkItem = document.getElementById("copyStreamLinkMenuItem");
        if (copyStreamLinkItem) {
            var ext = filename ? filename.split(".").pop().toLowerCase() : "";
            var videoExts = ["mp4", "webm", "mov", "mkv", "avi", "3gp", "m4v", "ts", "flv"];
            if (isSingle && videoExts.indexOf(ext) !== -1) {
                copyStreamLinkItem.style.display = "flex";
            } else {
                copyStreamLinkItem.style.display = "none";
            }
        }

        // Position at cursor, only reposition if menu won't fit
        var top = event.clientY;
        var left = event.clientX;
        if (top + 100 > window.innerHeight) top = window.innerHeight - 105;
        if (left + 190 > window.innerWidth) left = window.innerWidth - 200;
        menu.style.left = left + "px";
        menu.style.top = top + "px";
        menu.style.display = "block";
    };



    // Close context menu on mousedown (before click fires on menu items)
    var menuCloseTimer = null;
    document.addEventListener("mousedown", function (e) {
        // Clear any pending close timer
        if (menuCloseTimer) {
            clearTimeout(menuCloseTimer);
            menuCloseTimer = null;
        }

        var menu = document.getElementById("contextMenu");
        if (menu && menu.style.display === "block") {
            // If clicking outside the menu, close it immediately
            if (!menu.contains(e.target)) {
                menu.style.display = "none";
            }
            // If clicking inside the menu, let the click through
        }

        var sortMenu = document.getElementById("sortDropdownMenu");
        if (sortMenu && sortMenu.style.display === "block" && !sortMenu.contains(e.target)) {
            sortMenu.style.display = "none";
        }
        var typeMenu = document.getElementById("typeDropdownMenu");
        if (typeMenu && typeMenu.style.display === "block" && !typeMenu.contains(e.target)) {
            typeMenu.style.display = "none";
        }
    });

    // --- Dialog Openers ---
    window.openRenameModal = function () {
        if (typeof window.closePreviewModal === "function") {
            window.closePreviewModal();
        }
        var targets = prototypeSelectedItems.slice();
        if (targets.length === 0 && window._contextMenuTarget) {
            targets = [window._contextMenuTarget];
        }
        if (targets.length === 0) return;

        var dialog = document.getElementById("renameDialog");
        var input = document.getElementById("renameInput");
        var titleNode = document.getElementById("renameDialogTitle");
        if (!dialog || !input) return;

        if (targets.length > 1) {
            if (titleNode) titleNode.textContent = "Batch Rename (" + targets.length + " items)";
            input.value = "Item";
        } else {
            if (titleNode) titleNode.textContent = "Rename";
            input.value = targets[0];
        }
        dialog.style.display = "flex";

        if (!input.__keyListenerWired) {
            input.__keyListenerWired = true;
            input.addEventListener("keydown", function (e) {
                if (e.key === "Enter") {
                    e.preventDefault();
                    e.stopPropagation();
                    window.submitRename();
                } else if (e.key === "Escape") {
                    e.preventDefault();
                    e.stopPropagation();
                    window.closeRenameDialog();
                }
            });
        }

        // Pre-select only the filename part, NOT the extension
        setTimeout(function () {
            input.focus();
            var val = input.value;
            var dotIdx = val.lastIndexOf(".");
            var selectEnd = (dotIdx > 0) ? dotIdx : val.length;
            if (input.setSelectionRange) {
                input.setSelectionRange(0, selectEnd);
            } else {
                input.select();
            }
        }, 10);
    };

    window.closeRenameDialog = function () {
        var dialog = document.getElementById("renameDialog");
        if (dialog) dialog.style.display = "none";
    };

    // Alias used by some HTML
    window.closeRenameModal = window.closeRenameDialog;

    // -------------------------------------------------------------------------
    // Move Modal — full folder tree browser
    // -------------------------------------------------------------------------
    window.openMoveModal = function () {
        if (typeof window.closePreviewModal === "function") {
            window.closePreviewModal();
        }
        var targets = prototypeSelectedItems.slice();
        if (targets.length === 0 && window._contextMenuTarget) {
            targets = [window._contextMenuTarget];
        }
        if (targets.length === 0) return;

        itemsToMove = targets.slice();
        isCreatingFolderInMove = false;

        // Set dialog title
        var titleNode = document.getElementById("moveDialogTitle");
        if (titleNode) {
            titleNode.textContent = itemsToMove.length === 1
                ? "Move " + itemsToMove[0]
                : "Move " + itemsToMove.length + " items";
        }

        // Start at current folder root
        moveCurrentPath = ["Home"];
        moveTargetFolder = "Home";
        renderMoveFolderContents();

        var dialog = document.getElementById("moveFileDialog");
        if (dialog) dialog.style.display = "flex";
    };

    window.closeMoveDialog = function () {
        itemsToMove = [];
        isCreatingFolderInMove = false;
        var dialog = document.getElementById("moveFileDialog");
        if (dialog) dialog.style.display = "none";
    };

    window.closeMoveModal = window.closeMoveDialog;

    window.navigateMoveUp = function () {
        if (moveCurrentPath.length > 1) {
            moveCurrentPath.pop();
            renderMoveFolderContents();
        }
    };

    window.handleNewFolderInMove = function () {
        isCreatingFolderInMove = true;
        var dlg = document.getElementById("newFolderDialog");
        var inp = document.getElementById("newFolderNameInput");
        if (!dlg) return;
        dlg.style.display = "flex";
        if (inp) {
            inp.value = "Untitled folder";
            function doFocusAndSelect() {
                try {
                    inp.focus({ preventScroll: true });
                    if (typeof inp.setSelectionRange === "function") {
                        inp.setSelectionRange(0, inp.value.length);
                    } else if (typeof inp.select === "function") {
                        inp.select();
                    }
                } catch (e) { }
            }
            requestAnimationFrame(function () {
                requestAnimationFrame(doFocusAndSelect);
            });
            setTimeout(doFocusAndSelect, 50);
            setTimeout(doFocusAndSelect, 150);
        }
    };

    function renderMoveFolderContents() {
        var optionsList = document.getElementById("moveFolderOptions");
        var prevBtn = document.getElementById("movePrevBtn");
        var breadcrumbs = document.getElementById("moveBreadcrumbs");
        if (!optionsList) return;

        var currentFolderStr = moveCurrentPath.join("/");
        moveTargetFolder = currentFolderStr;

        // Show/hide back button
        if (prevBtn) prevBtn.style.display = moveCurrentPath.length > 1 ? "flex" : "none";

        // Render breadcrumbs
        if (breadcrumbs) {
            breadcrumbs.innerHTML = "";
            for (var b = 0; b < moveCurrentPath.length; b++) {
                if (b > 0) {
                    var sep = document.createElement("span");
                    sep.className = "breadcrumb-separator";
                    sep.innerHTML = '<i data-lucide="chevron-right" style="width:12px;height:12px;"></i>';
                    breadcrumbs.appendChild(sep);
                }
                (function (idx) {
                    var bItem = document.createElement("span");
                    bItem.style.cursor = idx < moveCurrentPath.length - 1 ? "pointer" : "default";
                    bItem.style.color = idx < moveCurrentPath.length - 1 ? "var(--primary)" : "var(--text-color)";
                    bItem.textContent = moveCurrentPath[idx];
                    if (idx < moveCurrentPath.length - 1) {
                        bItem.onclick = function () {
                            moveCurrentPath = moveCurrentPath.slice(0, idx + 1);
                            renderMoveFolderContents();
                        };
                    }
                    breadcrumbs.appendChild(bItem);
                })(b);
            }
            if (window.lucide) lucide.createIcons();
        }

        // Fetch folder contents from backend
        optionsList.innerHTML = '<div style="padding:1rem;text-align:center;color:var(--text-muted);font-size:0.8rem;">Loading...</div>';

        var fetchUrl;
        if (moveCurrentPath.length === 1 && moveCurrentPath[0] === "Home") {
            fetchUrl = "/api/folders";
        } else {
            // Build the subfolder path relative to upload root (strip "Home/")
            var subPath = moveCurrentPath.slice(1).join("/");
            fetchUrl = "/api/folders/" + encodeURIComponent(subPath) + "/files";
        }

        fetch(fetchUrl)
            .then(function (r) { return r.json(); })
            .then(function (data) {
                optionsList.innerHTML = "";
                var items = [];
                if (data.folders) {
                    // Root level: only show folders
                    items = data.folders;
                } else if (data.files) {
                    // Subfolder level: only show sub-folders
                    items = data.files.filter(function (f) { return f.isFolder || f.is_folder; });
                }

                // Filter out items being moved (can't move into themselves)
                items = items.filter(function (f) { return itemsToMove.indexOf(f.name) === -1; });

                if (items.length === 0) {
                    optionsList.innerHTML = '<div style="padding:1.5rem;text-align:center;color:var(--text-muted);font-size:0.8rem;">No subfolders here</div>';
                    return;
                }

                items.forEach(function (folderItem) {
                    var row = document.createElement("div");
                    row.style.cssText = "display:grid;grid-template-columns:1fr auto;align-items:center;padding:0.55rem 0.6rem;font-size:0.78rem;border-radius:6px;cursor:pointer;transition:background-color 0.15s ease;";
                    row.innerHTML =
                        '<div style="display:flex;align-items:center;gap:0.5rem;min-width:0;">' +
                        '<i data-lucide="folder" style="width:16px;height:16px;color:var(--primary);"></i>' +
                        '<span style="white-space:nowrap;overflow:hidden;text-overflow:ellipsis;font-weight:600;">' + escapeHtml(folderItem.name) + '</span>' +
                        '</div>' +
                        '<i data-lucide="chevron-right" style="width:14px;height:14px;color:var(--text-muted);"></i>';
                    row.onmouseover = function () { row.style.backgroundColor = "var(--hover-bg)"; };
                    row.onmouseout = function () { row.style.backgroundColor = "transparent"; };
                    row.onclick = function () {
                        moveCurrentPath.push(folderItem.name);
                        renderMoveFolderContents();
                    };
                    optionsList.appendChild(row);
                });

                if (window.lucide) lucide.createIcons();
            })
            .catch(function () {
                optionsList.innerHTML = '<div style="padding:1.5rem;text-align:center;color:var(--text-muted);font-size:0.8rem;">Failed to load folders</div>';
            });
    }

    // openNewFolderDialog and closeNewFolderDialog are provided by dialog-manager.js module

    // --- Sort & Filter ---
    // parseSizeToBytes is provided by sorting-manager.js module

    function getFileItemType(fileData) {
        if (fileData.isFolder) return "folder";
        var name = fileData.name || "";
        var ext = name.split(".").pop().toLowerCase();

        var imageExts = ["png", "jpg", "jpeg", "gif", "webp", "svg", "bmp", "ico"];
        var videoExts = ["mp4", "mov", "avi", "mkv", "webm", "flv", "wmv"];
        var audioExts = ["mp3", "wav", "ogg", "flac", "aac", "m4a"];
        var archiveExts = ["zip", "rar", "7z", "tar", "gz", "bz2"];
        var docExts = ["pdf", "doc", "docx", "xls", "xlsx", "ppt", "pptx", "txt", "md", "csv"];

        if (imageExts.indexOf(ext) !== -1) return "image";
        if (videoExts.indexOf(ext) !== -1) return "video";
        if (audioExts.indexOf(ext) !== -1) return "audio";
        if (archiveExts.indexOf(ext) !== -1) return "archive";
        if (docExts.indexOf(ext) !== -1) return "doc";
        return "doc";
    }

    function updateSortCheckmarks() {
        var byName = document.getElementById("check-by-name");
        var byDate = document.getElementById("check-by-date");
        var bySize = document.getElementById("check-by-size");
        if (byName) byName.style.visibility = sortBy === "name" ? "visible" : "hidden";
        if (byDate) byDate.style.visibility = sortBy === "date" ? "visible" : "hidden";
        if (bySize) bySize.style.visibility = sortBy === "size" ? "visible" : "hidden";

        var dirAsc = document.getElementById("check-dir-asc");
        var dirDesc = document.getElementById("check-dir-desc");
        if (dirAsc) dirAsc.style.visibility = sortDirection === "asc" ? "visible" : "hidden";
        if (dirDesc) dirDesc.style.visibility = sortDirection === "desc" ? "visible" : "hidden";

        var foldTop = document.getElementById("check-folders-top");
        var foldMixed = document.getElementById("check-folders-mixed");
        if (foldTop) foldTop.style.visibility = sortFolders === "top" ? "visible" : "hidden";
        if (foldMixed) foldMixed.style.visibility = sortFolders === "mixed" ? "visible" : "hidden";
    }

    function updateSortHeaderArrows() {
        var arrowName = document.getElementById("sortArrow-name");
        var arrowDate = document.getElementById("sortArrow-date");
        var arrowSize = document.getElementById("sortArrow-size");

        var iconMarkup = sortDirection === "asc"
            ? '<i data-lucide="chevron-down" class="sort-header-icon" title="Ascending"></i>'
            : '<i data-lucide="chevron-up" class="sort-header-icon" title="Descending"></i>';

        if (arrowName) arrowName.innerHTML = sortBy === "name" ? iconMarkup : "";
        if (arrowDate) arrowDate.innerHTML = sortBy === "date" ? iconMarkup : "";
        if (arrowSize) arrowSize.innerHTML = sortBy === "size" ? iconMarkup : "";
        if (window.lucide) lucide.createIcons();
    }

    window.setSortOption = function (category, value) {
        if (category === "by") sortBy = value;
        else if (category === "direction") sortDirection = value;
        else if (category === "folders") sortFolders = value;

        var el = document.getElementById("sortDropdownMenu");
        if (el) el.style.display = "none";

        updateSortCheckmarks();
        updateSortHeaderArrows();

        refreshFileList('sort_changed');
    };

    window.setTypeFilter = function (type) {
        typeFilter = type;
        var wrapper = document.getElementById("typeBtnWrapper");
        if (wrapper) {
            if (type === "all") {
                wrapper.innerHTML =
                    '<button class="filter-chip" id="typeDropdownBtn" onclick="toggleTypeDropdown(event)" style="display: inline-flex; align-items: center; gap: 0.35rem; font-size: 0.76rem; font-weight: 700; border: 1px solid var(--border-color); background: var(--card-bg); color: var(--text-color); border-radius: 999px; padding: 0 0.8rem; height: 32px; box-sizing: border-box; cursor: pointer;">' +
                    '<span>Type</span>' +
                    '<i data-lucide="chevron-down" style="width: 12px; height: 12px;"></i>' +
                    '</button>';
            } else {
                var labelMap = {
                    folder: "Folder",
                    image: "Photos",
                    video: "Videos",
                    audio: "Audio",
                    doc: "Documents",
                    archive: "Archives"
                };
                var text = labelMap[type] || "Type";
                wrapper.innerHTML =
                    '<div class="filter-chip active" id="typeDropdownBtn" style="display: inline-flex; align-items: center; padding: 0; border: none; background: var(--primary-container); border-radius: 999px; overflow: hidden; height: 32px; box-sizing: border-box;">' +
                    '<button onclick="toggleTypeDropdown(event)" style="display: flex; align-items: center; gap: 0.25rem; font-size: 0.76rem; font-weight: 700; background: transparent; border: none; color: var(--primary); padding: 0 0.55rem 0 0.85rem; cursor: pointer; height: 100%;">' +
                    '<span>Type: ' + text + '</span>' +
                    '<i data-lucide="chevron-down" style="width: 12px; height: 12px;"></i>' +
                    '</button>' +
                    '<span style="width: 1px; height: 14px; background: rgba(11, 87, 208, 0.25); display: inline-block;"></span>' +
                    '<button onclick="clearTypeFilter(event)" style="display: flex; align-items: center; justify-content: center; background: transparent; border: none; color: var(--primary); width: 28px; height: 100%; padding: 0; cursor: pointer;" title="Clear filter">' +
                    '<i data-lucide="x" style="width: 13px; height: 13px;"></i>' +
                    '</button>' +
                    '</div>';
            }
        }

        var menu = document.getElementById("typeDropdownMenu");
        if (menu) {
            menu.style.display = "none";
            var checkmarks = {
                all: "check",
                image: "image",
                video: "video",
                audio: "music",
                doc: "file-text",
                folder: "folder",
                archive: "archive"
            };

            var items = menu.querySelectorAll(".context-item");
            var keys = Object.keys(checkmarks);
            for (var idx = 0; idx < items.length; idx++) {
                var item = items[idx];
                var icon = item.querySelector("i");
                if (icon) {
                    var itemType = keys[idx];
                    if (itemType === type) {
                        icon.setAttribute("data-lucide", "check");
                        icon.style.color = "var(--primary)";
                    } else {
                        icon.setAttribute("data-lucide", checkmarks[itemType]);
                        icon.style.color = "";
                    }
                }
            }
        }

        if (window.lucide) lucide.createIcons();
        window.clearSelection();

        refreshFileList('filter_changed');
    };

    window.clearTypeFilter = function (event) {
        if (event) event.stopPropagation();
        window.setTypeFilter("all");
    };



    window.toggleSortMenu = function (event) {
        event.stopPropagation();
        var menu = document.getElementById("sortDropdownMenu");
        if (!menu) return;
        var isVisible = menu.style.display === "block";

        // Hide context menu if open
        var contextMenu = document.getElementById("contextMenu");
        if (contextMenu) contextMenu.style.display = "none";

        if (!isVisible) {
            updateSortCheckmarks();
            var rect = event.currentTarget.getBoundingClientRect();
            menu.style.display = "block";
            var menuHeight = 280;
            var top = rect.bottom + 6;
            if (top + menuHeight > window.innerHeight) {
                top = Math.max(10, rect.top - menuHeight - 4);
            }
            var left = Math.max(10, rect.right - 180);
            menu.style.left = left + "px";
            menu.style.top = top + "px";
        } else {
            menu.style.display = "none";
        }
    };

    window.toggleTypeDropdown = function (event) {
        event.stopPropagation();
        var menu = document.getElementById("typeDropdownMenu");
        if (!menu) return;
        menu.style.display = menu.style.display === "block" ? "none" : "block";
    };

    window.handleHeaderSortClick = function (column) {
        if (sortBy === column) {
            sortDirection = sortDirection === "asc" ? "desc" : "asc";
        } else {
            sortBy = column;
            sortDirection = "asc";
        }
        updateSortHeaderArrows();
        updateSortCheckmarks();
        refreshFileList('header_sort_changed');
    };

    // --- View Mode ---
    window.setViewMode = function (mode) {
        var fileList = document.getElementById("nasFileList");
        var fileTableHead = document.getElementById("fileTableHead");
        var listBtn = document.getElementById("listViewBtn");
        var gridBtn = document.getElementById("gridViewBtn");

        try {
            localStorage.setItem("lanvan_view_mode", mode);
            document.documentElement.setAttribute("data-view-mode", mode);
        } catch (e) { }

        // Instant view mode toggle (< 1ms HTML template swap)
        if (fileList) {
            if (mode === "grid") {
                fileList.classList.add("grid-mode");
                if (fileTableHead) fileTableHead.style.display = "none";
            } else {
                fileList.classList.remove("grid-mode");
                if (fileTableHead) fileTableHead.style.display = "";
            }
        }
        if (listBtn) listBtn.classList.toggle("active", mode === "list");
        if (gridBtn) gridBtn.classList.toggle("active", mode === "grid");

        if (typeof lastRenderedFiles !== "undefined") {
            triggerInstantUIUpdate();
        }
    };

    // --- Clipboard Prototype Handlers ---
    window.addClipboardItem = function () {
        var protoInput = document.getElementById("clipboardInput");
        var prodInput = document.getElementById("clipboardTextInput");
        if (!protoInput) return;

        var text = protoInput.value.trim();
        if (!text) return;

        // Copy to production textarea and trigger production handler
        if (prodInput) prodInput.value = text;
        if (typeof addTextToClipboard === "function") {
            addTextToClipboard();
        }
        protoInput.value = "";
    };

    window.clearClipboardInput = function () {
        var input = document.getElementById("clipboardInput");
        if (input) {
            input.value = "";
            input.focus();
        }
    };

    window.handleClipboardMenuDownload = function () {
        if (typeof downloadClipboardHistory === "function") {
            downloadClipboardHistory();
        }
    };

    window.handleClipboardMenuDelete = function () {
        if (typeof clearAllClipboardHistory === "function") {
            clearAllClipboardHistory();
        }
    };

    // --- Stub Operations (no production equivalent yet) ---
    window.submitNewFolder = function () {
        console.log("[submitNewFolder] Start");
        var input = document.getElementById("newFolderNameInput");
        var name = (input && input.value.trim()) || "Untitled folder";
        console.log("[submitNewFolder] Folder name:", name);
        if (!name) return;

        window._recentlyCreatedFolders = window._recentlyCreatedFolders || {};
        window._recentlyCreatedFolders[name] = true;

        var formData = new FormData();
        formData.append("folder_name", name);

        var parentPath = "";
        if (isCreatingFolderInMove) {
            parentPath = moveCurrentPath.length > 1 ? moveCurrentPath.slice(1).join("/") : "";
        } else {
            if (currentFolderPath && currentFolderPath !== "Home") {
                if (currentFolderPath.indexOf("Home/") === 0) {
                    parentPath = currentFolderPath.substring(5);
                } else if (currentFolderPath !== "Home") {
                    parentPath = currentFolderPath;
                }
            }
        }
        console.log("[submitNewFolder] parentPath resolved to:", parentPath);
        if (parentPath) {
            formData.append("parent_path", parentPath);
        }

        var repoPromise = (window.FileRepository && typeof window.FileRepository.createFolder === 'function')
            ? window.FileRepository.createFolder(name, parentPath)
            : fetch("/api/files/mkdir", { method: "POST", body: formData }).then(function (r) { return r.json(); });

        repoPromise
            .then(function (data) {
                if (data.status === "success") {
                    if (typeof showToast === "function") showToast("Folder '" + name + "' created.", 3000);
                    // If creating from within move dialog, refresh move folder tree
                    if (isCreatingFolderInMove) {
                        isCreatingFolderInMove = false;
                        renderMoveFolderContents();
                    } else {
                        if (typeof refreshFileList === "function") refreshFileList();
                        if (typeof window.requestSafeVisibleFilesRefresh === "function") {
                            window.requestSafeVisibleFilesRefresh(120);
                        } else if (typeof fetchFilesData === "function") {
                            fetchFilesData().then(function (fd) { renderPrototypeFileList(fd); });
                        }
                    }
                } else {
                    if (typeof showToast === "function") showToast(data.msg || "Failed to create folder.", 4000);
                }
            })
            .catch(function () {
                if (typeof showToast === "function") showToast("Network error creating folder.", 4000);
            });

        window.closeNewFolderDialog();
    };

    window.submitRename = function () {
        if (typeof window.closePreviewModal === "function") {
            window.closePreviewModal();
        }
        var itemsToRename = prototypeSelectedItems.slice();
        if (itemsToRename.length === 0 && window._contextMenuTarget) {
            itemsToRename = [window._contextMenuTarget];
        }
        if (itemsToRename.length === 0) {
            window.closeRenameDialog();
            return;
        }

        var newBaseName = (document.getElementById("renameInput") || {}).value;
        if (!newBaseName) {
            window.closeRenameDialog();
            return;
        }

        var completed = 0;
        var failed = [];

        function renameNext(index) {
            if (index >= itemsToRename.length) {
                if (failed.length > 0) {
                    if (typeof showToast === "function") showToast("Renamed " + completed + " item(s). " + failed.length + " failed.", 4000);
                } else {
                    if (typeof showToast === "function") showToast("Successfully renamed " + completed + " item(s).", 3000);
                }
                window._contextMenuTarget = "";
                window.clearSelection();
                if (typeof window.requestSafeVisibleFilesRefresh === "function") {
                    window.requestSafeVisibleFilesRefresh(120);
                } else if (typeof fetchFilesData === "function") {
                    fetchFilesData().then(function (fd) { renderPrototypeFileList(fd); });
                }
                return;
            }

            var oldName = itemsToRename[index];

            // Determine if the item is a folder
            var isFolder = false;
            var listEl = document.querySelector('#nasFileList [data-filename="' + oldName.replace(/"/g, '&quot;') + '"]');
            if (listEl) {
                isFolder = listEl.getAttribute("data-is-folder") === "1";
            } else {
                var meta = getDiskFileMetadata(oldName);
                if (meta) isFolder = !!(meta.isFolder || meta.is_dir);
            }

            var nameToUse = "";

            if (itemsToRename.length === 1) {
                // SINGLE FILE / FOLDER RENAME:
                // User has full control. Allow changing the extension if typed.
                if (isFolder) {
                    nameToUse = newBaseName;
                } else {
                    var oldDot = oldName.lastIndexOf(".");
                    var oldExt = oldDot > 0 ? oldName.substring(oldDot) : "";
                    var newDot = newBaseName.lastIndexOf(".");

                    if (newDot > 0) {
                        // User typed a name WITH an extension (e.g. myfile.pdf)
                        nameToUse = newBaseName;
                    } else {
                        // User typed a name WITHOUT an extension (e.g. myfile) -> keep original extension
                        nameToUse = newBaseName + oldExt;
                    }
                }
            } else {
                // MULTI-ITEM BATCH RENAME:
                // Do not change individual item extensions. Strip extension from input if user typed one.
                var cleanBase = newBaseName;
                var baseDot = newBaseName.lastIndexOf(".");
                if (baseDot > 0) {
                    cleanBase = newBaseName.substring(0, baseDot);
                }

                var suffix = index > 0 ? " (" + index + ")" : "";

                if (isFolder) {
                    nameToUse = cleanBase + suffix;
                } else {
                    var oldDotIdx = oldName.lastIndexOf(".");
                    var itemExt = oldDotIdx > 0 ? oldName.substring(oldDotIdx) : "";
                    nameToUse = cleanBase + suffix + itemExt;
                }
            }

            if (nameToUse === oldName) {
                completed++;
                renameNext(index + 1);
                return;
            }

            var formData = new FormData();
            formData.append("filename", oldName);
            var parentPath = cleanFolderPath(currentFolderPath);
            var repoPromise = (window.FileRepository && typeof window.FileRepository.renameItem === 'function')
                ? window.FileRepository.renameItem(oldName, nameToUse, isFolder, parentPath)
                : fetch("/api/files/rename", { method: "POST", body: formData }).then(function (r) { return r.json(); });

            repoPromise
                .then(function (data) {
                    if (data.status === "success") {
                        completed++;
                        if (Array.isArray(window.uploadQueue)) {
                            window.uploadQueue.forEach(function (qi) {
                                var qiName = qi.fileName || qi.name || "";
                                if (qiName === oldName) {
                                    qi.fileName = nameToUse;
                                    if (qi.name) qi.name = nameToUse;
                                }
                            });
                            saveUploadQueueToStorage();
                            if (typeof scheduleUploadTrayRender === "function") {
                                scheduleUploadTrayRender();
                            } else if (typeof renderUploadTray === "function") {
                                renderUploadTray();
                            }
                        }
                    } else {
                        failed.push(oldName);
                    }
                    renameNext(index + 1);
                })
                .catch(function () {
                    failed.push(oldName);
                    renameNext(index + 1);
                });
        }

        renameNext(0);
        window.closeRenameDialog();
    };

    window.submitMove = function () {
        // Use itemsToMove if populated by openMoveModal, else fall back to prototypeSelectedItems
        var filesToMove = (itemsToMove.length > 0 ? itemsToMove : prototypeSelectedItems).slice();
        if (filesToMove.length === 0) {
            window.closeMoveDialog();
            return;
        }

        // Destination is the current move dialog path (strip "Home" prefix since backend uses relative paths)
        var destination = moveCurrentPath.length > 1 ? moveCurrentPath.slice(1).join("/") : "";
        var sourceFolder = cleanFolderPath(currentFolderPath);
        var repoPromise = (window.FileRepository && typeof window.FileRepository.moveItems === 'function')
            ? window.FileRepository.moveItems(filesToMove, destination, sourceFolder)
            : (function () {
                var completed = 0;
                var failed = [];
                function moveNext(index) {
                    if (index >= filesToMove.length) {
                        return Promise.resolve({ status: "success", completed: completed, failed: failed });
                    }
                    var filename = filesToMove[index];
                    var formData = new FormData();
                    formData.append("filename", filename);
                    formData.append("destination", destination);
                    return fetch("/api/files/move", { method: "POST", body: formData })
                        .then(function (r) { return r.json(); })
                        .then(function (data) {
                            if (data.status === "success") completed++; else failed.push(filename);
                            return moveNext(index + 1);
                        })
                        .catch(function () {
                            failed.push(filename);
                            return moveNext(index + 1);
                        });
                }
                return moveNext(0);
            })();

        repoPromise
            .then(function (data) {
                var failedCount = (data && data.failed && data.failed.length) ? data.failed.length : 0;
                if (typeof showToast === "function") {
                    if (failedCount > 0) {
                        showToast("Moved file(s) with " + failedCount + " failure(s).", 4000);
                    } else {
                        showToast("Moved file(s) to '" + (destination || "Home") + "'.", 3000);
                    }
                }
                window.clearSelection();
                itemsToMove = [];
                if (typeof refreshFileList === "function") refreshFileList();
                if (typeof window.requestSafeVisibleFilesRefresh === "function") {
                    window.requestSafeVisibleFilesRefresh(120);
                } else if (typeof fetchFilesData === "function") {
                    fetchFilesData().then(function (fd) { renderPrototypeFileList(fd); });
                }
                window.closeMoveDialog();
            })
            .catch(function () {
                if (typeof showToast === "function") showToast("Failed to move file(s).", 4000);
                window.closeMoveDialog();
            });
    };

    window.cancelSelectedUpload = function () {
        if (typeof cancelAllUploads === "function") {
            cancelAllUploads();
        }
    };

    // --- QR & Connect ---
    window.setConnectMode = function (mode) {
        var lanTab = document.getElementById("lanIpTab");
        var mdnsTab = document.getElementById("mdnsTab");
        var qrLanTab = document.getElementById("connectQrLanIpTab");
        var qrMdnsTab = document.getElementById("connectQrMdnsTab");

        var isMdns = mode === "mdns";
        if (lanTab) lanTab.classList.toggle("active", !isMdns);
        if (mdnsTab) mdnsTab.classList.toggle("active", isMdns);
        if (qrLanTab) qrLanTab.classList.toggle("active", !isMdns);
        if (qrMdnsTab) qrMdnsTab.classList.toggle("active", isMdns);

        if (window._currentNetworkInfo) {
            var url = window._currentNetworkInfo.lanIpUrl;
            if (isMdns && window._currentNetworkInfo.networkInfo && window._currentNetworkInfo.networkInfo.mdns) {
                url = window._currentNetworkInfo.networkInfo.mdns.url || url;
            }
            window._currentNetworkInfo.fullUrl = url;
            window._currentNetworkInfo.currentMode = mode;
            renderSidebarQR();
            renderDialogQR();
        }

        if (typeof updateMDNSStatus === "function") updateMDNSStatus();
    };

    window.openConnectQrDialog = function () {
        var dialog = document.getElementById("connectQrDialog");
        if (!dialog) return;
        dialog.style.display = "flex";
        renderDialogQR();
        // Load QR from production
        if (typeof showConnectionInfo === "function") {
            // Populate address in prototype QR dialog
            var protoAddr = document.getElementById("connectQrDialogAddress");
            if (protoAddr && window._currentNetworkInfo) {
                protoAddr.textContent = window._currentNetworkInfo.fullUrl || "";
            }
        }
    };

    window.closeConnectQrDialog = function () {
        var dialog = document.getElementById("connectQrDialog");
        if (dialog) dialog.style.display = "none";
    };

    window.copyConnectAddress = function () {
        var addr = document.getElementById("connectAddress") || document.getElementById("connectQrDialogAddress");
        var textToCopy = addr ? addr.textContent.trim() : "";
        if (!textToCopy || textToCopy === "...") {
            textToCopy = window.location.origin;
        }

        if (textToCopy) {
            if (navigator.clipboard && navigator.clipboard.writeText) {
                navigator.clipboard.writeText(textToCopy).catch(function () {
                    fallbackCopyTextToClipboard(textToCopy);
                });
            } else {
                fallbackCopyTextToClipboard(textToCopy);
            }
        }

        var tooltip = document.querySelector(".connect-tooltip");
        if (tooltip) {
            tooltip.textContent = "Copied successfully!";
            tooltip.classList.add("copied");
            setTimeout(function () {
                tooltip.textContent = "Click to copy";
                tooltip.classList.remove("copied");
            }, 1800);
        }
    };

    function fallbackCopyTextToClipboard(text) {
        var textArea = document.createElement("textarea");
        textArea.value = text;
        textArea.style.position = "fixed";
        textArea.style.top = "0";
        textArea.style.left = "0";
        textArea.style.width = "2em";
        textArea.style.height = "2em";
        textArea.style.padding = "0";
        textArea.style.border = "none";
        textArea.style.outline = "none";
        textArea.style.boxShadow = "none";
        textArea.style.background = "transparent";
        textArea.style.opacity = "0.01";
        textArea.style.zIndex = "999999";
        document.body.appendChild(textArea);
        textArea.focus();
        textArea.select();
        if (typeof textArea.setSelectionRange === "function") {
            textArea.setSelectionRange(0, 99999);
        }
        var success = false;
        try {
            success = document.execCommand('copy');
        } catch (err) {
            console.error('[COPY] Fallback copy error', err);
        }
        document.body.removeChild(textArea);
        return success;
    }

    window.closePreviewModal = function () {
        var modal = document.getElementById("previewModal");
        if (modal) {
            modal.style.display = "none";
            modal.style.pointerEvents = "none";
            var bodyEl = document.getElementById("previewBody");
            if (bodyEl) {
                var mediaEls = bodyEl.querySelectorAll("video, audio, iframe");
                for (var i = 0; i < mediaEls.length; i++) {
                    try {
                        if (typeof mediaEls[i].pause === "function") mediaEls[i].pause();
                        mediaEls[i].removeAttribute("src");
                        if (typeof mediaEls[i].load === "function") mediaEls[i].load();
                    } catch (e) { }
                }
                bodyEl.innerHTML = "";
            }
            window.currentPreviewFilename = "";
            var ctxMenu = document.getElementById("previewContextMenu");
            if (ctxMenu) ctxMenu.style.display = "none";
        }
    };

    window.openFilePreview = function (filename) {
        if (!filename) return;
        window.currentPreviewFilename = filename;
        var modal = document.getElementById("previewModal");
        var titleEl = document.getElementById("previewTitle");
        var bodyEl = document.getElementById("previewBody");
        var dlBtn = document.getElementById("previewDownloadBtn");
        if (!modal || !bodyEl) return;

        var downloadUrl = "/download/" + encodeURIComponent(filename);
        if (titleEl) titleEl.textContent = filename;
        if (dlBtn) {
            dlBtn.href = downloadUrl + "?download=1";
            dlBtn.download = filename;
        }

        var ext = filename.split(".").pop().toLowerCase();
        var escName = escapeHtml(filename);

        var imageExts = ["jpg", "jpeg", "png", "gif", "webp", "svg", "bmp"];
        var videoExts = ["mp4", "webm", "mov", "mkv", "avi"];
        var audioExts = ["mp3", "wav", "ogg", "flac", "m4a", "aac"];
        var textExts = ["txt", "json", "py", "js", "css", "html", "md", "csv", "log", "xml", "yaml", "yml"];

        bodyEl.innerHTML = "";
        bodyEl.style.padding = "";

        var docExts = ["doc", "docx", "ppt", "pptx", "xls", "xlsx", "rtf", "odt"];

        var streamBtn = document.getElementById("previewStreamBtn");
        if (streamBtn) {
            if (videoExts.indexOf(ext) !== -1) {
                streamBtn.style.display = "inline-flex";
            } else {
                streamBtn.style.display = "none";
            }
        }

        if (imageExts.indexOf(ext) !== -1) {
            bodyEl.innerHTML = '<div class="image-preview-wrapper" style="position:relative; width:100%; height:100%; min-height:70vh; flex:1; display:flex; align-items:center; justify-content:center; overflow:hidden; background:rgba(18,20,26,0.5); border-radius:14px; padding:1.5rem;">' +
                '<img id="lanvanZoomImage" src="' + downloadUrl + '" alt="' + escName + '" style="max-width:90vw; max-height:84vh; width:auto; height:auto; object-fit:contain; border-radius:8px; display:block; margin:auto; box-shadow:0 16px 48px rgba(0,0,0,0.6); transition:transform 0.15s ease-out; cursor:grab;" />' +
                '</div>';
            modal.style.display = "flex";
            refreshLucideIcons(bodyEl);
            setupImageZoomAndPan();
        } else if (videoExts.indexOf(ext) !== -1) {
            bodyEl.innerHTML = '<div style="width:100%; height:100%; min-height:70vh; flex:1; display:flex; align-items:center; justify-content:center; background:rgba(18,20,26,0.5); border-radius:14px; padding:1.5rem;">' +
                '<video src="' + downloadUrl + '" controls autoplay playsinline preload="auto" tabindex="0" style="max-width:90vw; max-height:84vh; width:auto; height:auto; object-fit:contain; border-radius:8px; outline:none; background:transparent; box-shadow:0 16px 48px rgba(0,0,0,0.6);"></video>' +
                '</div>';
            modal.style.display = "flex";
            var vid = bodyEl.querySelector("video");
            if (vid) vid.focus();
        } else if (audioExts.indexOf(ext) !== -1) {
            bodyEl.innerHTML = '<div style="display:flex; flex-direction:column; align-items:center; justify-content:center; gap:1.4rem; width:100%; height:100%; min-height:70vh; flex:1; padding:2.5rem; background:rgba(18,20,26,0.5); border-radius:14px; text-align:center;">' +
                '<div class="avatar-icon avatar-audio" style="width:84px; height:84px; border-radius:24px; background:rgba(168, 85, 247, 0.15); display:flex; align-items:center; justify-content:center; box-shadow:0 8px 24px rgba(168,85,247,0.2);">' +
                '<i data-lucide="music" style="width:42px; height:42px; color:#c084fc;"></i>' +
                '</div>' +
                '<div style="font-weight:700; color:#ffffff; font-size:1.35rem; text-align:center; word-break:break-all; max-width:600px;">' + escName + '</div>' +
                '<audio src="' + downloadUrl + '" controls autoplay style="width:100%; max-width:460px; outline:none; border-radius:30px;"></audio>' +
                '</div>';
            modal.style.display = "flex";
            refreshLucideIcons(bodyEl);
        } else if (ext === "pdf") {
            bodyEl.style.padding = "0";
            bodyEl.innerHTML = '<div style="width:100%; height:100%; min-height:70vh; flex:1; background:rgba(18,20,26,0.5); border-radius:14px; overflow:hidden;">' +
                '<iframe src="' + downloadUrl + '" style="width:100%; height:100%; border:none; display:block;"></iframe>' +
                '</div>';
            modal.style.display = "flex";
        } else if (docExts.indexOf(ext) !== -1) {
            bodyEl.innerHTML = '<div style="width:100%; text-align:center; color:var(--text-color); padding:1rem;">Rendering Word document...</div>';
            modal.style.display = "flex";

            function renderDocCardFallback() {
                bodyEl.innerHTML = '<div style="display:flex; flex-direction:column; align-items:center; justify-content:center; gap:1.4rem; width:100%; height:100%; min-height:70vh; flex:1; padding:2.5rem; background:rgba(18, 20, 26, 0.5); border-radius:14px; color:#fff; text-align:center;">' +
                    '<div class="avatar-icon avatar-doc" style="width:84px; height:84px; border-radius:24px; background:rgba(239, 68, 68, 0.14); display:flex; align-items:center; justify-content:center; box-shadow:0 8px 24px rgba(239,68,68,0.15);">' +
                    '<i data-lucide="file-text" style="width:42px; height:42px; color:#ef4444;"></i>' +
                    '</div>' +
                    '<div style="font-weight:700; font-size:1.4rem; color:#ffffff; text-align:center; word-break:break-all; max-width:600px;">' + escName + '</div>' +
                    '<div style="font-size:0.95rem; color:rgba(255,255,255,0.75); text-align:center; max-width:440px;">No in-app preview available for this document format.</div>' +
                    '<a href="' + downloadUrl + '?download=1" download class="gdrive-doc-fallback-btn">' +
                    '<i data-lucide="download" style="width:18px; height:18px;"></i> Download File' +
                    '</a>' +
                    '</div>';
                refreshLucideIcons(bodyEl);
            }

            fetch(downloadUrl)
                .then(function (res) { return res.arrayBuffer(); })
                .then(function (buffer) {
                    if (window.docx && window.docx.renderAsync) {
                        bodyEl.innerHTML = '<div id="docxRenderTarget" style="width:100%; max-height:85vh; overflow-y:auto; padding:1.5rem; display:flex; flex-direction:column; align-items:center; background:rgba(18,20,26,0.5); border-radius:14px;"></div>';
                        var target = document.getElementById("docxRenderTarget");
                        window.docx.renderAsync(buffer, target, null, {
                            inBase64Output: false,
                            className: "docx",
                            ignoreWidth: false,
                            ignoreHeight: false,
                            ignoreMargins: false,
                            breakPages: true
                        })
                            .then(function () {
                                console.log("[DOCX-PREVIEW] Successfully rendered docx document!");
                            })
                            .catch(function (err) {
                                console.error("[DOCX-PREVIEW] Render error:", err);
                                renderDocCardFallback();
                            });
                    } else {
                        renderDocCardFallback();
                    }
                })
                .catch(renderDocCardFallback);
        } else if (textExts.indexOf(ext) !== -1) {
            bodyEl.innerHTML = '<div style="width:100%; text-align:center; color:var(--text-color); padding:1rem;">Loading content...</div>';
            modal.style.display = "flex";
            fetch(downloadUrl)
                .then(function (res) { return res.text(); })
                .then(function (text) {
                    bodyEl.innerHTML = '<div style="width:100%; height:100%; min-height:70vh; flex:1; background:rgba(18,20,26,0.5); border-radius:14px; padding:1.5rem;">' +
                        '<pre style="max-height:68vh; width:100%; overflow:auto; background:var(--card-bg); padding:1rem; border-radius:8px; white-space:pre-wrap; word-break:break-word; text-align:left; font-family:monospace; color:var(--text-color); font-size:0.85rem; margin:0; border:1px solid var(--border-color);"></pre>' +
                        '</div>';
                    var pre = bodyEl.querySelector("pre");
                    if (pre) pre.textContent = text;
                })
                .catch(function () {
                    bodyEl.innerHTML = '<div style="color:var(--danger); padding:1rem;">Failed to load text preview.</div>';
                });
        } else {
            bodyEl.innerHTML = '<div style="display:flex; flex-direction:column; align-items:center; justify-content:center; gap:1.4rem; width:100%; height:100%; min-height:70vh; flex:1; padding:2.5rem; background:rgba(18,20,26,0.5); border-radius:14px; color:#fff; text-align:center;">' +
                '<div class="avatar-icon avatar-doc" style="width:84px; height:84px; border-radius:24px; background:rgba(239, 68, 68, 0.14); display:flex; align-items:center; justify-content:center; box-shadow:0 8px 24px rgba(239,68,68,0.15);">' +
                '<i data-lucide="file" style="width:42px; height:42px; color:#ef4444;"></i>' +
                '</div>' +
                '<div style="font-weight:700; color:#ffffff; font-size:1.4rem; text-align:center; word-break:break-all; max-width:600px;">' + escName + '</div>' +
                '<div style="font-size:0.95rem; color:rgba(255,255,255,0.75); text-align:center; max-width:440px;">No in-app preview available for this file type.</div>' +
                '<a href="' + downloadUrl + '?download=1" download class="gdrive-doc-fallback-btn">' +
                '<i data-lucide="download" style="width:18px; height:18px;"></i> Download File' +
                '</a>' +
                '</div>';
            modal.style.display = "flex";
            modal.style.pointerEvents = "auto";
            refreshLucideIcons(bodyEl);
        }
    };

    window.openFilePreviewTarget = function () {
        var target = window._contextMenuTarget || (prototypeSelectedItems.length > 0 ? prototypeSelectedItems[0] : "");
        window._contextMenuTarget = "";
        if (target) {
            window.openFilePreview(target);
        }
    };

    // Keyboard controls for preview modal: Escape closes, Space/Arrows control video
    document.addEventListener("keydown", function (e) {
        var modal = document.getElementById("previewModal");
        if (!modal || modal.style.display === "none") return;

        if (e.key === "Escape" || e.key === "Esc") {
            e.preventDefault();
            window.closePreviewModal();
            return;
        }

        if (document.activeElement && (document.activeElement.tagName === "INPUT" || document.activeElement.tagName === "TEXTAREA")) {
            return;
        }

        var video = modal.querySelector("video");
        if (!video) return;

        // If the native <video controls> element has focus, let the browser handle
        // spacebar natively — don't intercept it. Only intercept when focus is
        // elsewhere in the modal so the page doesn't scroll.
        if (e.key === "ArrowLeft") {
            e.preventDefault();
            e.stopPropagation();
            video.currentTime = Math.max(0, video.currentTime - 10);
        } else if (e.key === "ArrowRight") {
            e.preventDefault();
            e.stopPropagation();
            video.currentTime = Math.min(video.duration || 0, video.currentTime + 10);
        } else if ((e.key === " " || e.code === "Space") && document.activeElement !== video) {
            // Only handle spacebar when the video element itself does NOT have focus.
            // When video has focus, the browser's native controls handle space correctly.
            e.preventDefault();
            e.stopPropagation();
            if (video.paused) { video.play(); } else { video.pause(); }
        } else if (e.key === " " || e.code === "Space") {
            // Video has focus — just suppress page scroll, let native controls handle play/pause
            e.preventDefault();
            e.stopPropagation();
        }
    });

    // Generic context menu opener (for empty space right-click)
    window.showGenericContextMenu = function (x, y) {
        if (typeof x !== 'number') x = 200;
        if (typeof y !== 'number') y = 200;
        var menu = document.getElementById("contextMenu");
        if (!menu) return;
        var genericOps = document.getElementById("genericMenuOptions");
        var itemOps = document.getElementById("itemMenuOptions");
        if (genericOps) genericOps.style.display = "block";
        if (itemOps) itemOps.style.display = "none";
        menu.style.left = x + "px";
        menu.style.top = y + "px";
        menu.style.display = "block";
    };

    window.showToast = function (message, duration) {
        if (!message) return;
        var dur = duration || 3000;
        var isMobile = window.innerWidth <= 768;
        var bottomPos = isMobile ? "90px" : "32px";
        var toast = document.getElementById("lanvanGlobalToast");
        if (!toast) {
            toast = document.createElement("div");
            toast.id = "lanvanGlobalToast";
            toast.className = "lanvan-toast";
            toast.style.cssText = "position:fixed; left:50%; transform:translateX(-50%) translateY(16px); background:rgba(20, 22, 30, 0.95); color:#ffffff; padding:11px 24px; border-radius:30px; font-size:0.88rem; font-weight:600; z-index:999999; border:1px solid rgba(255,255,255,0.2); backdrop-filter:blur(16px); box-shadow:0 14px 40px rgba(0,0,0,0.6); opacity:0; transition:all 0.22s cubic-bezier(0.16, 1, 0.3, 1); pointer-events:none; font-family:inherit; text-align:center; max-width:90vw; word-break:break-word;";
            document.body.appendChild(toast);
        }

        toast.style.bottom = bottomPos;
        toast.textContent = message;
        toast.style.display = "block";
        requestAnimationFrame(function () {
            toast.style.opacity = "1";
            toast.style.transform = "translateX(-50%) translateY(0px)";
        });

        if (window._lanvanToastTimer) {
            clearTimeout(window._lanvanToastTimer);
            window._lanvanToastTimer = null;
        }

        if (dur > 0) {
            window._lanvanToastTimer = setTimeout(function () {
                toast.style.opacity = "0";
                toast.style.transform = "translateX(-50%) translateY(16px)";
                setTimeout(function () {
                    toast.style.display = "none";
                }, 220);
            }, dur);
        }
    };

    window.copyVideoStreamUrl = function (filename) {
        var fn = filename || window.currentPreviewFilename || (window._contextMenuTarget || (prototypeSelectedItems && prototypeSelectedItems[0]));
        if (!fn) return;
        var fullUrl = window.location.origin + "/download/" + encodeURIComponent(fn);

        var copied = fallbackCopyTextToClipboard(fullUrl);
        if (!copied && navigator.clipboard && navigator.clipboard.writeText) {
            navigator.clipboard.writeText(fullUrl).catch(function () {
                fallbackCopyTextToClipboard(fullUrl);
            });
        }

        // 1. Toast Notification
        window.showToast('Stream link copied to clipboard!', 3000);

        // 2. Button Visual Feedback (if in preview modal)
        var streamBtn = document.getElementById("previewStreamBtn");
        if (streamBtn) {
            var origHtml = streamBtn.innerHTML;
            streamBtn.innerHTML = '<i data-lucide="check" style="width:16px;height:16px;color:#4ade80;"></i><span>Copied!</span>';
            if (typeof refreshLucideIcons === "function") refreshLucideIcons(streamBtn);
            setTimeout(function () {
                streamBtn.innerHTML = origHtml;
                if (typeof refreshLucideIcons === "function") refreshLucideIcons(streamBtn);
            }, 2000);
        }
    };

    // --- Right-Click Context Menu for Preview Modal ---
    window.downloadPreviewFile = function (filename) {
        var menu = document.getElementById("previewContextMenu");
        if (menu) menu.style.display = "none";
        var fn = filename || window.currentPreviewFilename;
        if (!fn) return;
        var a = document.createElement("a");
        a.href = "/download/" + encodeURIComponent(fn) + "?download=1";
        a.download = fn;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
    };

    function showPreviewContextMenu(x, y, filename) {
        var menu = document.getElementById("previewContextMenu");
        if (!menu) {
            menu = document.createElement("div");
            menu.id = "previewContextMenu";
            menu.className = "context-menu";
            menu.style.cssText = "position:fixed; z-index:20000; min-width:190px; padding:6px 0; border-radius:12px; background:var(--card-bg, #1e2026); border:1px solid var(--border-color, rgba(255,255,255,0.15)); box-shadow:0 12px 36px rgba(0,0,0,0.5); display:none;";
            document.body.appendChild(menu);

            document.addEventListener("click", function () {
                menu.style.display = "none";
            });
        }

        var escFn = escapeHtml(filename);
        var ext = filename.split(".").pop().toLowerCase();
        var videoExts = ["mp4", "webm", "mov", "mkv", "avi", "3gp", "m4v", "ts", "flv"];
        var isVideo = videoExts.indexOf(ext) !== -1;

        var html = '';
        if (isVideo) {
            html += '<div class="menu-item" onclick="copyVideoStreamUrl(\'' + escFn + '\')" style="display:flex; align-items:center; gap:10px; padding:9px 16px; cursor:pointer; font-size:0.9rem; font-weight:500; color:var(--text-color, #fff); border-radius:6px; margin:0 4px; transition:background 0.15s ease;">' +
                '<i data-lucide="tv" style="width:16px; height:16px; color:var(--primary, #3b82f6);"></i> Copy Stream Link' +
                '</div>';
        }
        html += '<div class="menu-item" onclick="downloadPreviewFile(\'' + escFn + '\')" style="display:flex; align-items:center; gap:10px; padding:9px 16px; cursor:pointer; font-size:0.9rem; font-weight:500; color:var(--text-color, #fff); border-radius:6px; margin:0 4px; transition:background 0.15s ease;">' +
            '<i data-lucide="download" style="width:16px; height:16px; color:var(--primary, #3b82f6);"></i> Download' +
            '</div>';

        menu.innerHTML = html;
        menu.style.display = "block";

        var menuWidth = menu.offsetWidth || 190;
        var menuHeight = menu.offsetHeight || 100;
        var posX = Math.min(x, window.innerWidth - menuWidth - 10);
        var posY = Math.min(y, window.innerHeight - menuHeight - 10);

        menu.style.left = posX + "px";
        menu.style.top = posY + "px";

        if (window.refreshLucideIcons) {
            window.refreshLucideIcons(menu);
        }
    }

    var previewModalEl = document.getElementById("previewModal");
    if (previewModalEl) {
        previewModalEl.addEventListener("dblclick", function (e) {
            if (e.target.tagName !== "PRE" && e.target.tagName !== "CODE" && e.target.tagName !== "INPUT" && e.target.tagName !== "TEXTAREA") {
                e.preventDefault();
                e.stopPropagation();
            }
        });
        previewModalEl.addEventListener("contextmenu", function (e) {
            e.preventDefault();
            e.stopPropagation();
            var fn = window.currentPreviewFilename;
            if (!fn) {
                var titleEl = document.getElementById("previewTitle");
                if (titleEl) fn = titleEl.textContent.trim();
            }
            if (fn) {
                showPreviewContextMenu(e.clientX, e.clientY, fn);
            }
        });
    }

    // =========================================================================
    // IMAGE ZOOM & PAN FUNCTIONALITY
    // =========================================================================
    var currentImageScale = 1;
    var currentImageTransX = 0;
    var currentImageTransY = 0;
    var isDraggingImage = false;
    var dragStartX = 0;
    var dragStartY = 0;

    window.updateImageTransform = function () {
        var img = document.getElementById("lanvanZoomImage");
        var label = document.getElementById("zoomPercentLabel");
        if (!img) return;
        img.style.transform = "translate(" + currentImageTransX + "px, " + currentImageTransY + "px) scale(" + currentImageScale + ")";
        if (label) label.textContent = Math.round(currentImageScale * 100) + "%";
        img.style.cursor = currentImageScale > 1 ? (isDraggingImage ? "grabbing" : "grab") : "grab";
    };

    window.zoomPreviewImage = function (delta) {
        currentImageScale = Math.max(0.5, Math.min(4, currentImageScale + delta));
        if (currentImageScale === 1) {
            currentImageTransX = 0;
            currentImageTransY = 0;
        }
        window.updateImageTransform();
    };

    window.resetPreviewImageZoom = function () {
        currentImageScale = 1;
        currentImageTransX = 0;
        currentImageTransY = 0;
        window.updateImageTransform();
    };

    function setupImageZoomAndPan() {
        currentImageScale = 1;
        currentImageTransX = 0;
        currentImageTransY = 0;
        isDraggingImage = false;

        var img = document.getElementById("lanvanZoomImage");
        var wrapper = img ? img.parentElement : null;
        if (!img || !wrapper) return;

        // Mouse Wheel Zoom
        wrapper.addEventListener("wheel", function (e) {
            e.preventDefault();
            var zoomDelta = e.deltaY < 0 ? 0.2 : -0.2;
            window.zoomPreviewImage(zoomDelta);
        }, { passive: false });

        // Double Click to Toggle 1x / 2x Zoom
        img.addEventListener("dblclick", function (e) {
            e.stopPropagation();
            if (currentImageScale > 1.2) {
                window.resetPreviewImageZoom();
            } else {
                currentImageScale = 2;
                window.updateImageTransform();
            }
        });

        // Mouse Drag to Pan Image
        img.addEventListener("mousedown", function (e) {
            if (e.button !== 0) return;
            isDraggingImage = true;
            dragStartX = e.clientX - currentImageTransX;
            dragStartY = e.clientY - currentImageTransY;
            img.style.cursor = "grabbing";
            e.preventDefault();
        });

        document.addEventListener("mousemove", function (e) {
            if (!isDraggingImage) return;
            currentImageTransX = e.clientX - dragStartX;
            currentImageTransY = e.clientY - dragStartY;
            window.updateImageTransform();
        });

        document.addEventListener("mouseup", function () {
            if (isDraggingImage) {
                isDraggingImage = false;
                window.updateImageTransform();
            }
        });
    }

    window.copyToClipboard = function (text) {
        if (navigator.clipboard) {
            navigator.clipboard.writeText(text);
        }
    };

    // =========================================================================
    // 4. DROPZONE INTEGRATION — Wire prototype dropzone to production handlers
    // =========================================================================

    function setupDropzone() {
        // Match prototype: context menu on the entire app container (.android-app)
        var appContainer = document.querySelector(".android-app");
        if (appContainer) {
            appContainer.addEventListener("contextmenu", function (e) {
                e.preventDefault();

                var menu = document.getElementById("contextMenu");
                if (!menu) return;

                // Hide menu first (close if already open)
                menu.style.display = "none";

                var genericOps = document.getElementById("genericMenuOptions");
                var itemOps = document.getElementById("itemMenuOptions");
                var clipboardOps = document.getElementById("clipboardMenuOptions");

                // Check if right-clicking on a file item or quick card
                var itemRow = e.target.closest(".m3-list-item");
                var quickCard = e.target.closest(".quick-card");
                var targetItem = itemRow || quickCard;

                if (targetItem) {
                    var filename = targetItem.getAttribute("data-filename") || "";
                    if (genericOps) genericOps.style.display = "none";
                    if (itemOps) itemOps.style.display = "block";
                    if (clipboardOps) clipboardOps.style.display = "none";
                    openRowMenu(e, filename);
                    return;
                } else {
                    // Right-clicked on empty space — show generic menu
                    if (genericOps) genericOps.style.display = "block";
                    if (itemOps) itemOps.style.display = "none";
                    if (clipboardOps) clipboardOps.style.display = "none";
                    window.clearSelection();
                }

                // Position at cursor, only move if truly overflows
                var top = e.clientY;
                var left = e.clientX;
                // Generic menu is ~96px (3 items), item menu ~144px (4 items)
                if (top + 144 > window.innerHeight) top = window.innerHeight - 150;
                if (left + 190 > window.innerWidth) left = window.innerWidth - 200;
                menu.style.left = left + "px";
                menu.style.top = top + "px";
                menu.style.display = "block";
            });

            // Hide context menu when a menu item is clicked
            var contextMenu = document.getElementById("contextMenu");
            if (contextMenu) {
                contextMenu.addEventListener("click", function (e) {
                    if (e.target.closest(".context-item")) {
                        contextMenu.style.display = "none";
                    }
                });
            }
        }

        var dropzone = document.getElementById("nasDropzone");
        if (!dropzone) return;

        // Wire drag events to production drop-zone handlers
        dropzone.addEventListener("dragenter", function (e) {
            e.preventDefault();
            dropzone.classList.add("drag-over");
        });

        dropzone.addEventListener("dragover", function (e) {
            e.preventDefault();
        });

        dropzone.addEventListener("dragleave", function () {
            dropzone.classList.remove("drag-over");
        });

        dropzone.addEventListener("drop", function (e) {
            e.preventDefault();
            dropzone.classList.remove("drag-over");
            var files = e.dataTransfer.files;
            if (files.length > 0) {
                // Route directly to production addToUploadQueue
                if (typeof addToUploadQueue === "function") {
                    addToUploadQueue(Array.from(files));
                    if (typeof showUploadManager === "function") showUploadManager();
                    if (typeof startNextUpload === "function") startNextUpload();
                }
            }
        });

        // Click on empty "Drop files here" area triggers file input strictly when inner target card is clicked
        dropzone.addEventListener("click", function (e) {
            if (e.target.closest(".empty-dropzone-target")) {
                var fi = document.getElementById("fileInput");
                if (fi) {
                    fi.value = "";
                    fi.click();
                }
            }
        });
    }

    // =========================================================================
    // 5. SEARCH INTEGRATION — Client-side filtering & Autocomplete Dropdown
    // =========================================================================

    var searchSelectedIndex = -1;

    function hideSearchAutocomplete() {
        var menu = document.getElementById("searchAutocompleteMenu");
        if (menu) menu.style.display = "none";
        searchSelectedIndex = -1;
    }

    function updateAutocompleteHighlight(itemEls) {
        for (var i = 0; i < itemEls.length; i++) {
            if (i === searchSelectedIndex) {
                itemEls[i].classList.add("selected");
                itemEls[i].scrollIntoView({ block: "nearest" });
            } else {
                itemEls[i].classList.remove("selected");
            }
        }
    }

    function renderSearchAutocomplete(query) {
        var menu = document.getElementById("searchAutocompleteMenu");
        if (!menu) return;

        var q = (query || "").trim().toLowerCase();
        if (!q) {
            hideSearchAutocomplete();
            return;
        }

        var path = (typeof window.getCurrentFolderPath === "function")
            ? window.getCurrentFolderPath()
            : (window.currentFolderPath || "");
        var allItems = (window.FileRepository && typeof window.FileRepository.getFolderCache === 'function') ? window.FileRepository.getFolderCache(path) : [];
        var matches = allItems.filter(function (item) {
            if (!item || !item.name) return false;
            return item.name.toLowerCase().indexOf(q) !== -1;
        }).slice(0, 4);

        if (matches.length === 0) {
            menu.innerHTML =
                '<div class="search-autocomplete-header">Search Suggestions</div>' +
                '<div style="padding: 0.75rem 0.65rem; font-size: 0.8rem; color: var(--text-muted); text-align: center;">No matching files or folders</div>';
            menu.style.display = "block";
            searchSelectedIndex = -1;
            return;
        }

        var html = '<div class="search-autocomplete-header">Quick Results</div>';
        for (var i = 0; i < matches.length; i++) {
            var item = matches[i];
            var name = item.name;
            var isFolder = !!item.isFolder;
            var itemType = isFolder ? "folder" : getFileItemType({ name: name });

            var iconName = "file-text";
            var labelType = "FILE";

            if (isFolder) {
                iconName = "folder";
                labelType = "FOLDER";
            } else if (itemType === "image") {
                iconName = "image";
                labelType = "IMAGE";
            } else if (itemType === "video") {
                iconName = "video";
                labelType = "VIDEO";
            } else if (itemType === "audio") {
                iconName = "music";
                labelType = "AUDIO";
            } else if (itemType === "archive") {
                iconName = "archive";
                labelType = "ARCHIVE";
            } else if (itemType === "doc") {
                iconName = "file-text";
                labelType = "DOCUMENT";
            }

            var sizeStr = item.size && item.size !== "--" ? item.size : "";
            var subText = labelType + (sizeStr ? " • " + sizeStr : "") + " • Home";

            html +=
                '<div class="search-autocomplete-item" data-index="' + i + '" data-filename="' + escapeHtml(name) + '" data-is-folder="' + (isFolder ? "true" : "false") + '">' +
                '<div class="search-autocomplete-icon type-' + itemType + '">' +
                '<i data-lucide="' + iconName + '" style="width: 18px; height: 18px;"></i>' +
                '</div>' +
                '<div class="search-autocomplete-details">' +
                '<div class="search-autocomplete-title">' + escapeHtml(name) + '</div>' +
                '<div class="search-autocomplete-sub">' + escapeHtml(subText) + '</div>' +
                '</div>' +
                '</div>';
        }

        menu.innerHTML = html;
        menu.style.display = "block";
        searchSelectedIndex = -1;
        if (window.lucide) lucide.createIcons();

        // Add Click Handlers to Autocomplete Items
        var itemEls = menu.querySelectorAll(".search-autocomplete-item");
        for (var k = 0; k < itemEls.length; k++) {
            itemEls[k].addEventListener("click", function (e) {
                e.stopPropagation();
                var fname = this.getAttribute("data-filename");
                var folder = this.getAttribute("data-is-folder") === "true";
                hideSearchAutocomplete();

                if (folder) {
                    window.currentFolderPath = fname;
                    prototypeSelectedItems = [];
                    updateSelectionToolbar();
                    fetchFilesData().then(function (fd) {
                        renderPrototypeFileList(fd);
                    });
                } else {
                    prototypeSelectedItems = [fname];
                    renderPrototypeFileList();
                    if (typeof openFilePreview === "function") {
                        openFilePreview(fname);
                    }
                }
            });
        }
    }

    function setupSearch() {
        var toolbarInput = document.getElementById("toolbarSearchInput");
        var toolbarClearBtn = document.getElementById("clearToolbarSearchBtn");

        if (toolbarInput) {
            toolbarInput.addEventListener("input", function () {
                var q = this.value.trim();
                if (toolbarClearBtn) toolbarClearBtn.style.display = q ? "inline-flex" : "none";
                renderPrototypeFileList();
                renderSearchAutocomplete(q);
            });

            toolbarInput.addEventListener("keydown", function (e) {
                var menu = document.getElementById("searchAutocompleteMenu");
                var itemEls = menu ? menu.querySelectorAll(".search-autocomplete-item") : [];

                if (e.key === "ArrowDown" && itemEls.length > 0) {
                    e.preventDefault();
                    searchSelectedIndex = Math.min(itemEls.length - 1, searchSelectedIndex + 1);
                    updateAutocompleteHighlight(itemEls);
                } else if (e.key === "ArrowUp" && itemEls.length > 0) {
                    e.preventDefault();
                    searchSelectedIndex = Math.max(0, searchSelectedIndex - 1);
                    updateAutocompleteHighlight(itemEls);
                } else if (e.key === "Enter" && searchSelectedIndex >= 0 && itemEls[searchSelectedIndex]) {
                    e.preventDefault();
                    itemEls[searchSelectedIndex].click();
                } else if (e.key === "Escape") {
                    hideSearchAutocomplete();
                    if (this.value) {
                        clearToolbarSearch();
                    } else {
                        this.blur();
                    }
                }
            });

            window.clearToolbarSearch = function () {
                if (toolbarInput) {
                    toolbarInput.value = "";
                    if (toolbarClearBtn) toolbarClearBtn.style.display = "none";
                    hideSearchAutocomplete();
                    fetchFilesData().then(function (fd) {
                        renderPrototypeFileList(fd);
                    });
                    toolbarInput.focus();
                }
            };

            // Global Ctrl+K Shortcut to Focus Search
            document.addEventListener("keydown", function (e) {
                if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
                    e.preventDefault();
                    if (toolbarInput) {
                        toolbarInput.focus();
                        toolbarInput.select();
                        if (toolbarInput.value.trim()) {
                            renderSearchAutocomplete(toolbarInput.value.trim());
                        }
                    }
                }
            });

            // Hide Autocomplete Menu on Outside Click
            document.addEventListener("click", function (e) {
                if (!e.target.closest("#toolbarSearchWrapper") && !e.target.closest("#searchAutocompleteMenu")) {
                    hideSearchAutocomplete();
                }
            });
        }

        var searchInput = document.getElementById("searchInput");
        var clearBtn = document.getElementById("clearSearchBtn");
        if (!searchInput) return;

        // Cache of last known files for filtering
        var lastFiles = [];

        searchInput.addEventListener("input", function () {
            var query = this.value.trim().toLowerCase();
            if (clearBtn) clearBtn.classList.toggle("visible", !!query);

            if (!query) {
                // Re-render full list
                renderPrototypeFileList(lastFiles);
                document.getElementById("searchResultsPanel").classList.remove("active");
                return;
            }

            // Filter lastFiles client-side
            var results = lastFiles.filter(function (f) {
                return f.toLowerCase().indexOf(query) !== -1;
            });
            renderSearchResults(results, query);
        });

        if (clearBtn) {
            clearBtn.addEventListener("click", function () {
                searchInput.value = "";
                searchInput.focus();
                renderPrototypeFileList(lastFiles);
                document.getElementById("searchResultsPanel").classList.remove("active");
                clearBtn.classList.remove("visible");
            });
        }

        // Update lastFiles whenever prototype list renders
        var _origRender = renderPrototypeFileList;
        renderPrototypeFileList = function (files, renderReason) {
            if (files) {
                lastFiles = files.slice();
                var taggedFolderPath = getTaggedFolderPath(files);
                if (taggedFolderPath !== null) {
                    tagFilesWithFolder(lastFiles, taggedFolderPath);
                }
            }
            _origRender(files, renderReason);
        };
    }

    function renderSearchResults(results, query) {
        var panel = document.getElementById("searchResultsPanel");
        if (!panel) return;

        panel.classList.add("active");

        if (results.length === 0) {
            panel.innerHTML =
                '<div class="search-results-list"><div class="search-results-empty">No matches found for "' +
                escapeHtml(query) +
                '".</div></div>';
            return;
        }

        var html = '<div class="search-results-list">';
        for (var i = 0; i < results.length; i++) {
            var name = results[i];
            var ext = name.split(".").pop().toLowerCase();
            var info = getFileTypeInfo(name, ext);
            html +=
                '<div class="search-result-item" data-filename="' +
                escapeHtml(name) +
                '">' +
                '<div class="search-result-main">' +
                '<div class="search-result-icon ' +
                info.avatarClass +
                '"><i data-lucide="' +
                info.iconName +
                '" style="width:18px;height:18px;"></i></div>' +
                '<div class="search-result-copy">' +
                '<div class="search-result-name">' +
                escapeHtml(name) +
                "</div>" +
                '<div class="search-result-meta">File</div>' +
                "</div>" +
                "</div>" +
                '<div class="search-result-badge">File</div>' +
                "</div>";
        }
        html += "</div>";
        panel.innerHTML = html;

        var items = panel.querySelectorAll(".search-result-item");
        for (var j = 0; j < items.length; j++) {
            items[j].addEventListener("click", function () {
                var fname = this.getAttribute("data-filename");
                // Scroll to and highlight the file in the list
                var listItem = document.querySelector(
                    '#nasFileList [data-filename="' + fname.replace(/"/g, '"') + '"]'
                );
                if (listItem) listItem.scrollIntoView({ behavior: "smooth", block: "center" });
                panel.classList.remove("active");
            });
        }
        if (window.lucide) lucide.createIcons();
    }

    // =========================================================================
    // 4.5 UPLOAD TOAST TRAY — Mirror production uploadQueue to prototype tray
    // =========================================================================

    if (typeof window.uploadManagerExpanded === "undefined") {
        window.uploadManagerExpanded = false;
    }

    // Delegates to the canonical RenderScheduler pipeline.
    // RenderScheduler handles rAF coalescing, single-flight guard, and hash-based dedup.
    // Upload tray updates are separate from the file-list render pipeline.
    var _instantUIUpdateScheduled = false;
    window.triggerInstantUIUpdate = function () {
        if (_instantUIUpdateScheduled) return;
        _instantUIUpdateScheduled = true;
        var repoCount = 0;
        try { repoCount = (window.FileRepository && window.FileRepository.getFolderCache) ? window.FileRepository.getFolderCache(window.LanvanStore ? window.LanvanStore.state.currentFolder : "").length : -1; } catch(e) {}
        console.log("[FLICKER-TRACE] ⚡ triggerInstantUIUpdate | Repo cache: " + repoCount + " items | UploadQueue: " + (Array.isArray(window.uploadQueue) ? window.uploadQueue.length : 0) + " items | Scheduler available: " + !!(window.RenderScheduler && typeof window.RenderScheduler.requestRender === 'function'));
        // Reset debounce on next frame — RenderScheduler has its own coalescing
        requestAnimationFrame(function () { _instantUIUpdateScheduled = false; });
        // Canonical pipeline: Store → Repository → Scheduler → Projection → Renderer
        if (window.RenderScheduler && typeof window.RenderScheduler.requestRender === 'function') {
            window.RenderScheduler.requestRender('instant_update');
        }
        // Upload tray is independent of file-list render — update it directly
        if (typeof window.scheduleUploadTrayRender === "function") {
            window.scheduleUploadTrayRender();
        } else if (typeof renderUploadTray === "function") {
            renderUploadTray();
        }
    };

    function _doInstantUIUpdate() {
        if (typeof window.scheduleUploadTrayRender === "function") {
            window.scheduleUploadTrayRender();
        } else if (typeof renderUploadTray === "function") {
            renderUploadTray();
        }
        var container = document.getElementById("nasFileList");
        if (container && window.uploadQueue) {
            var normCurrentDir = cleanFolderPath(currentFolderPath);
            var missingRow = false;

            window.uploadQueue.forEach(function (item) {
                if (item && (item.status === 'QUEUED' || item.status === 'UPLOADING' || item.status === 'PROCESSING' || item.status === 'PAUSED')) {
                    var itemName = item.fileName || (item.file && item.file.name) || item.name;
                    var rawDir = item.targetDir || item.parent_path || item.folder || "";
                    var relDir = getRelativeItemDir(rawDir, normCurrentDir);
                    if (relDir === null) return;
                    var checkName = relDir === "" ? itemName : relDir.split("/")[0];
                    if (checkName) {
                        var targetKey = checkName.trim().toLowerCase();
                        var allRows = container.querySelectorAll('.m3-list-item');
                        var foundRow = false;
                        for (var r = 0; r < allRows.length; r++) {
                            var rowFn = allRows[r].getAttribute('data-filename');
                            if (rowFn && rowFn.trim().toLowerCase() === targetKey) {
                                foundRow = true;
                                break;
                            }
                        }
                        if (!foundRow) missingRow = true;
                    }
                }
            });

            var hasCancelled = window.uploadQueue.some(function (i) { return i && i.status === 'CANCELLED'; });
            var hasTimedOut = window.uploadQueue.some(function (i) { return i && i.status === 'COMPLETED' && i._dismissTimer; });

            // Skip full re-render if the only missing rows are cancelled items (already handled by row.remove below)
            if (missingRow && hasCancelled && !hasTimedOut) {
                // A cancel was detected — DOM row was already removed below, just update progress for remaining rows
                missingRow = false;
            }

            if (missingRow && typeof lastRenderedFiles !== "undefined" && !window._instantRenderInProgress) {
                window._instantRenderInProgress = true;
                renderPrototypeFileList(lastRenderedFiles);
                setTimeout(function () { window._instantRenderInProgress = false; }, 200);
            } else {
                // Pass 1: Aggregate items into per-row progress data
                // This prevents synthetic folder rows from bouncing between individual file progress values
                var rowDataMap = {};

                window.uploadQueue.forEach(function (item) {
                    if (!item) return;
                    var itemName = item.fileName || (item.file && item.file.name) || item.name;
                    if (!itemName) return;
                    var rawDir = item.targetDir || item.parent_path || item.folder || "";
                    var relDir = getRelativeItemDir(rawDir, normCurrentDir);
                    if (relDir === null) return;
                    var checkName = relDir === "" ? itemName : relDir.split("/")[0];
                    var isFolder = relDir !== "";

                    if (!rowDataMap[checkName]) {
                        rowDataMap[checkName] = {
                            isFolder: isFolder,
                            totalBytes: 0,
                            uploadedBytes: 0,
                            status: 'QUEUED',
                            hasCancelled: false,
                            hasUploading: false,
                            hasPaused: false,
                            itemCount: 0
                        };
                    }

                    var rd = rowDataMap[checkName];
                    rd.itemCount++;

                    if (item.status === 'CANCELLED') {
                        rd.hasCancelled = true;
                        return;
                    }

                    var fileSize = item.fileSize || (item.file && item.file.size) || 0;
                    var bytesDone = 0;
                    if (item.status === 'COMPLETED') {
                        bytesDone = fileSize;
                    } else {
                        bytesDone = item.bytesUploaded || 0;
                        if (!bytesDone && item.progress && fileSize) {
                            bytesDone = (fileSize * item.progress) / 100;
                        }
                    }
                    rd.totalBytes += fileSize;
                    rd.uploadedBytes += bytesDone;

                    if (item.status === 'UPLOADING' || item.status === 'PROCESSING') rd.hasUploading = true;
                    if (item.status === 'PAUSED') rd.hasPaused = true;
                    if (item.status === 'CANCELLED') rd.hasCancelled = true;
                });

                // Pass 2: Update DOM rows with aggregated progress
                Object.keys(rowDataMap).forEach(function (checkName) {
                    var rd = rowDataMap[checkName];
                    var escName = escapeHtml(checkName);
                    var row = container.querySelector('.m3-list-item[data-filename="' + escName + '"]');
                    if (!row) return;

                    // Calculate aggregated progress
                    var progress = rd.totalBytes > 0 ? Math.round((rd.uploadedBytes / rd.totalBytes) * 100) : 0;
                    progress = Math.min(progress, 100);
                    var statusLabel = rd.hasPaused ? 'Paused' : (rd.hasUploading ? 'Uploading' : (rd.hasCancelled ? 'Cancelled' : 'Queued'));
                    var statusKey = rd.hasPaused ? 'PAUSED' : (rd.hasUploading ? 'UPLOADING' : (rd.hasCancelled ? 'CANCELLED' : 'QUEUED'));

                    // Update subtitle text
                    var subtitleCell = row.querySelector('.item-subtitle');
                    if (subtitleCell) {
                        var newSub = progress + "% • " + statusLabel;
                        if (subtitleCell.textContent !== newSub) subtitleCell.textContent = newSub;
                    }
                    var dateCell = row.querySelector('.item-date');
                    if (dateCell) {
                        if (dateCell.textContent !== statusLabel) dateCell.textContent = statusLabel;
                    }

                    // Update row progress bar (list view)
                    var bar = row.querySelector('.row-progress-bar');
                    if (bar) {
                        bar.style.width = progress + "%";
                    }

                    // Update grid B4 overlay elements
                    var b4Num = row.querySelector('.b4-num');
                    if (b4Num) {
                        var newNum = progress + "%";
                        if (b4Num.textContent !== newNum) b4Num.textContent = newNum;
                    }
                    var b4Sub = row.querySelector('.b4-sub');
                    if (b4Sub) {
                        if (b4Sub.textContent !== statusLabel) b4Sub.textContent = statusLabel;
                    }
                    var b4Strip = row.querySelector('.b4-bottom-strip');
                    if (b4Strip) {
                        b4Strip.style.width = progress + "%";
                    }

                    // Update grid water fill bar
                    var waterBar = row.querySelector('.grid-water-progress-bar');
                    if (waterBar) {
                        waterBar.style.height = progress + "%";
                    }

                    // Sync play/pause button state
                    var playPauseBtn = row.querySelector('[data-action="pause-upload"], [data-action="resume-upload"]');
                    if (playPauseBtn) {
                        var currentAction = playPauseBtn.getAttribute("data-action");
                        var svgPlay = '<svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor" stroke="none"><polygon points="5 3 19 12 5 21 5 3"></polygon></svg>';
                        var svgPause = '<svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor" stroke="none"><rect x="6" y="4" width="4" height="16"></rect><rect x="14" y="4" width="4" height="16"></rect></svg>';

                        if (statusKey === 'PAUSED' && currentAction === 'pause-upload') {
                            playPauseBtn.setAttribute("data-action", "resume-upload");
                            playPauseBtn.setAttribute("title", "Resume upload");
                            playPauseBtn.innerHTML = svgPlay;
                        } else if (statusKey !== 'PAUSED' && currentAction === 'resume-upload') {
                            playPauseBtn.setAttribute("data-action", "pause-upload");
                            playPauseBtn.setAttribute("title", "Pause upload");
                            playPauseBtn.innerHTML = svgPause;
                        }
                    }
                });
            }
        }
    };

    window.pauseAllUploads = function () {
        var queue = window.uploadQueue || [];
        queue.forEach(function (item) {
            if (item && (item.status === "UPLOADING" || item.status === "QUEUED" || item.status === "PROCESSING")) {
                if (typeof window.pauseUpload === "function") {
                    window.pauseUpload(item.id);
                } else if (typeof window.pauseUploadItem === "function") {
                    window.pauseUploadItem(item.id);
                } else {
                    item.status = "PAUSED";
                    if (item.xhr) { try { item.xhr.abort(); } catch (e) { } }
                }
            }
        });
        window.uploadManagerExpanded = true; // Auto-expand when paused
        window.triggerInstantUIUpdate();
    };

    window.resumeAllUploads = function () {
        var queue = window.uploadQueue || [];
        queue.forEach(function (item) {
            if (item && item.status === "PAUSED") {
                if (typeof window.resumeUpload === "function") {
                    window.resumeUpload(item.id);
                } else if (typeof window.resumeUploadItem === "function") {
                    window.resumeUploadItem(item.id);
                } else {
                    item.status = "UPLOADING";
                }
            }
        });
        window.uploadManagerExpanded = false; // Auto-collapse when resumed
        window.triggerInstantUIUpdate();
    };

    // buildTrayItemHtml, wireTrayItemListeners, buildHeaderActionsHtml, and wireHeaderActions are provided by upload-tray-renderer.js module

    window.navigateToPathAndSelect = function (targetPath, filename) {
        window.currentFolderPath = targetPath || "";
        prototypeSelectedItems = [];
        updateSelectionToolbar();
        renderBreadcrumbs();
        fetchFilesData().then(function (fd) {
            renderPrototypeFileList(fd);
            setTimeout(function () {
                var allItems = document.querySelectorAll("#nasFileList .m3-list-item");
                var matchedEl = null;
                var matchedName = null;

                // 1. Try exact match
                for (var i = 0; i < allItems.length; i++) {
                    var curName = allItems[i].getAttribute("data-filename");
                    if (curName === filename) {
                        matchedEl = allItems[i];
                        matchedName = curName;
                        break;
                    }
                }

                // 2. If no exact match (e.g. server auto-renamed duplicate "60mb file.pdf" -> "60mb file_1.pdf"), match base name & extension
                if (!matchedEl && filename) {
                    var dotIdx = filename.lastIndexOf(".");
                    var base = dotIdx > 0 ? filename.substring(0, dotIdx) : filename;
                    var ext = dotIdx > 0 ? filename.substring(dotIdx) : "";

                    for (var j = 0; j < allItems.length; j++) {
                        var cName = allItems[j].getAttribute("data-filename") || "";
                        if (ext) {
                            if (cName.startsWith(base) && cName.endsWith(ext)) {
                                matchedEl = allItems[j];
                                matchedName = cName;
                                break;
                            }
                        } else if (cName.startsWith(base)) {
                            matchedEl = allItems[j];
                            matchedName = cName;
                            break;
                        }
                    }
                }

                if (matchedEl && matchedName) {
                    prototypeSelectedItems = [matchedName];
                    matchedEl.classList.add("selected");
                    updateSelectionToolbar();
                    matchedEl.scrollIntoView({ behavior: "smooth", block: "center" });
                }
            }, 100);
        });
    };

    function saveUploadQueueToStorage() {
        if (!window.uploadQueue) return;
        var serialized = window.uploadQueue.map(function (item) {
            return {
                id: item.id,
                fileName: item.fileName || item.name,
                fileSize: item.fileSize || item.size,
                progress: item.progress,
                status: item.status,
                uploadTime: item.uploadTime,
                isFolder: item.isFolder,
                targetDir: item.targetDir || currentFolderPath || ""
            };
        });
        // Keep in localStorage as fast client cache (HTTP POST loop removed)
        try { localStorage.setItem("lanvan_upload_queue", JSON.stringify(serialized)); } catch (e) { }
    }

    // Debounced tray render — collapses rapid calls into one per animation frame
    var _trayRenderScheduled = false;
    window.scheduleUploadTrayRender = function () {
        if (_trayRenderScheduled) return;
        _trayRenderScheduled = true;
        requestAnimationFrame(function () {
            _trayRenderScheduled = false;
            renderUploadTray();
        });
    };

    function refreshLucideIcons(el) {
        if (window.lucide && typeof window.lucide.createIcons === "function") {
            window.lucide.createIcons({ nameAttr: "data-lucide", attrs: {}, nodes: el ? [el] : undefined });
        }
    }
    window.refreshLucideIcons = refreshLucideIcons;

    function renderUploadTray() {
        window.renderUploadTray = renderUploadTray;
        var stack = document.getElementById("uploadToastStack");
        if (!stack) return;

        var queue = window.uploadQueue || [];
        var activeUploads = queue.filter(function (item) {
            return item.status === "UPLOADING" || item.status === "QUEUED" || item.status === "PROCESSING" || item.status === "PAUSED" || item.status === "COMPLETED" || item.status === "DELETED";
        });

        // Make sure stack is always active/visible
        stack.classList.add("active");

        if (!stack.__delegatedEvents) {
            stack.__delegatedEvents = true;
            stack.addEventListener("click", function (e) {
                var cancelBtn = e.target.closest(".upload-toast-cancel-text");
                if (cancelBtn) {
                    e.stopPropagation();
                    var uploadId = cancelBtn.getAttribute("data-upload-id");
                    if (uploadId && typeof window.cancelUpload === "function") {
                        window.cancelUpload(parseInt(uploadId, 10) || uploadId);
                    }
                    return;
                }
                var resumeBtn = e.target.closest(".upload-toast-resume-text");
                if (resumeBtn) {
                    e.stopPropagation();
                    var uploadId = resumeBtn.getAttribute("data-upload-id");
                    if (uploadId && typeof window.resumeUpload === "function") {
                        window.resumeUpload(parseInt(uploadId, 10) || uploadId);
                    }
                    return;
                }
            });
        }

        // Sort priority:
        // 1. Uploading / Active
        // 2. In Queue / Paused
        // 3. Completed (latest first)
        // 4. Deleted
        activeUploads.sort(function (a, b) {
            function getCategoryScore(item) {
                if (item.status === 'UPLOADING' || item.status === 'PROCESSING') return 1;
                if (item.status === 'QUEUED' || item.status === 'PAUSED') return 2;
                if (item.status === 'COMPLETED') return 3;
                if (item.status === 'DELETED') return 4;
                return 5;
            }

            var scoreA = getCategoryScore(a);
            var scoreB = getCategoryScore(b);

            if (scoreA !== scoreB) {
                return scoreA - scoreB;
            }

            // Within completed category: latest first
            if (scoreA === 3) {
                var idA = a.id || 0;
                var idB = b.id || 0;
                return idB - idA;
            }

            // Default order by ID ascending
            return (a.id || 0) - (b.id || 0);
        });

        // Record old positions of existing elements for FLIP transition
        var bodyEl = stack.querySelector(".upload-toast-body");
        var oldRects = {};
        if (bodyEl) {
            var children = bodyEl.children;
            for (var n = 0; n < children.length; n++) {
                var child = children[n];
                var idAttr = child.getAttribute("id");
                if (idAttr) {
                    oldRects[idAttr] = child.getBoundingClientRect();
                }
            }
        }

        // Calculations
        var totalCount = activeUploads.length;
        var activePendingCount = activeUploads.filter(function (item) { return item.status === "UPLOADING" || item.status === "PROCESSING" || item.status === "QUEUED"; }).length;
        var pausedCount = activeUploads.filter(function (item) { return item.status === "PAUSED"; }).length;
        var completedOrDeletedCount = activeUploads.filter(function (item) { return item.status === "COMPLETED" || item.status === "DELETED"; }).length;
        var isAllCompleted = totalCount > 0 && completedOrDeletedCount === totalCount && pausedCount === 0 && activePendingCount === 0;

        // Cap completed/deleted display to recent 5 items max to prevent tray overflow
        if (completedOrDeletedCount > 5) {
            var activePendingItems = activeUploads.filter(function (item) {
                return item.status === "UPLOADING" || item.status === "PROCESSING" || item.status === "QUEUED" || item.status === "PAUSED";
            });
            var completedItems = activeUploads.filter(function (item) {
                return item.status === "COMPLETED" || item.status === "DELETED";
            }).slice(0, 5);
            activeUploads = activePendingItems.concat(completedItems);
        }

        // Auto-dismiss completed tray batch after 5 seconds
        if (isAllCompleted && totalCount > 0) {
            if (!window._trayAutoDismissTimer) {
                window._trayAutoDismissTimer = setTimeout(function () {
                    window._trayAutoDismissTimer = null;
                    if (window.LanvanStore) {
                        window.LanvanStore.dispatch("CLEAR_COMPLETED_UPLOADS");
                        renderUploadTray();
                    }
                }, 5000);
            }
        } else {
            if (window._trayAutoDismissTimer) {
                clearTimeout(window._trayAutoDismissTimer);
                window._trayAutoDismissTimer = null;
            }
        }

        // Auto-remove individual deleted or cancelled items from tray after 2 seconds
        activeUploads.forEach(function (item) {
            if (item && (item.status === 'DELETED' || item.status === 'CANCELLED') && !item._dismissTimer) {
                item._dismissTimer = setTimeout(function () {
                    if (window.LanvanStore) {
                        var curQueue = window.LanvanStore.getState().uploadQueue.filter(function (i) { return i && i.id != item.id; });
                        window.LanvanStore.dispatch("SYNC_QUEUE", { queue: curQueue });
                        renderUploadTray();
                    }
                }, 2000);
            }
        });

        saveUploadQueueToStorage();

        if (totalCount === 0 || window.uploadTrayDocked) {
            stack.classList.add("empty-state");
        } else {
            stack.classList.remove("empty-state");
        }

        // Calculate summary using centralized pure helpers (single source of truth)
        var batchSummary = window.buildUploadBatchSummary
            ? window.buildUploadBatchSummary(window.uploadQueue || [])
            : { totalFiles: totalCount, isComplete: isAllCompleted, percent: 0, totalSpeed: 0, status: 'IDLE' };
        var formatted = window.formatUploadBatchStatus
            ? window.formatUploadBatchStatus(batchSummary)
            : { title: "Uploading...", subtitle: "", percent: 0, speedStr: "", status: "UPLOADING" };

        var avgPct = formatted.percent;
        var headerTitle = formatted.line1;
        var headerSubtitle = formatted.line2 || "";

        var headerTitleEl = stack.querySelector(".upload-toast-header-title");
        var headerProgressBar = stack.querySelector(".header-progress-bar");
        bodyEl = stack.querySelector(".upload-toast-body");

        if (!headerTitleEl || !bodyEl) {
            // Full initial render
            var itemsHtml = "";
            for (var i = 0; i < activeUploads.length; i++) {
                itemsHtml += buildTrayItemHtml(activeUploads[i]);
            }

            var isBodyCollapsed = !window.uploadManagerExpanded;
            var bodyClass = isBodyCollapsed ? "upload-toast-body collapsed" : "upload-toast-body";
            var headerActionsHtml = buildHeaderActionsHtml(isAllCompleted, pausedCount, window.uploadManagerExpanded, totalCount, window.uploadTrayDocked);

            var widgetHtml =
                '<div class="upload-toast-header" style="position: relative; overflow: hidden;">' +
                '<div class="header-progress-bar" style="position: absolute; top:0; left:0; bottom:0; background: rgba(59, 130, 246, 0.08); z-index: 1; transition: width 0.2s ease-out; width: ' + avgPct + '%;"></div>' +
                '<div style="position: relative; z-index: 2; display: flex; flex-direction: column; min-width: 0; flex: 1;">' +
                '<span class="upload-toast-header-title">' + headerTitle + '</span>' +
                '<div class="upload-toast-header-subtitle" style="font-size:0.72rem;color:var(--text-muted);opacity:0.85;white-space:nowrap;overflow:hidden;display:flex;align-items:center;justify-content:space-between;gap:8px;width:100%;' + (headerSubtitle ? '' : 'display:none;') + '">' +
                '<span class="tray-speed-text">' + (formatted.speed || headerSubtitle) + '</span>' +
                '</div>' +
                '</div>' +
                '<div class="upload-toast-header-actions" style="position: relative; z-index: 2; display: flex; align-items: center;">' +
                headerActionsHtml +
                '</div>' +
                '</div>' +
                '<div class="' + bodyClass + '">' +
                itemsHtml +
                '</div>';

            stack.innerHTML = widgetHtml;
            refreshLucideIcons(stack);

            // Wire header actions
            wireHeaderActions(stack.querySelector(".upload-toast-header-actions"));

            // Wire header panel manual toggle (only expands if uploads exist)
            stack.querySelector(".upload-toast-header").addEventListener("click", function (e) {
                if (!e.target.closest(".upload-toast-header-actions")) {
                    var queue = window.uploadQueue || [];
                    var hasItems = queue.some(function (item) {
                        return item && (item.status === "UPLOADING" || item.status === "QUEUED" || item.status === "PROCESSING" || item.status === "PAUSED" || item.status === "COMPLETED" || item.status === "DELETED");
                    });
                    if (!hasItems) return; // Do not expand when empty

                    window.uploadManagerExpanded = !window.uploadManagerExpanded;
                    var body = stack.querySelector(".upload-toast-body");
                    if (body) {
                        if (window.uploadManagerExpanded) {
                            body.classList.remove("collapsed");
                        } else {
                            body.classList.add("collapsed");
                        }
                    }
                    // Re-render header to flip the chevron icon
                    var actionsEl = stack.querySelector(".upload-toast-header-actions");
                    if (actionsEl) {
                        actionsEl.innerHTML = buildHeaderActionsHtml(isAllCompleted, pausedCount, window.uploadManagerExpanded, totalCount, window.uploadTrayDocked);
                        wireHeaderActions(actionsEl);
                    }
                }
            });

            // Re-query newly created elements
            headerTitleEl = stack.querySelector(".upload-toast-header-title");
            headerProgressBar = stack.querySelector(".header-progress-bar");
            bodyEl = stack.querySelector(".upload-toast-body");

            // Wire listeners for initially rendered items
            for (var i = 0; i < activeUploads.length; i++) {
                var item = activeUploads[i];
                var itemEl = stack.querySelector("#toast-item-" + item.id);
                if (itemEl) {
                    wireTrayItemListeners(itemEl, item);
                }
            }
        }

        // In-place updates via cached DOM references:
        if (!stack._trayDOMCache) {
            stack._trayDOMCache = {
                title: stack.querySelector(".upload-toast-header-title"),
                subtitle: stack.querySelector(".upload-toast-header-subtitle"),
                speedEl: stack.querySelector(".tray-speed-text"),
                progressBar: stack.querySelector(".header-progress-bar")
            };
        }
        var trayDOM = stack._trayDOMCache;

        if (trayDOM.title && trayDOM.title.textContent !== headerTitle) {
            trayDOM.title.textContent = headerTitle;
        }
        if (trayDOM.subtitle) {
            if (headerSubtitle) {
                if (trayDOM.subtitle.style.display !== "") trayDOM.subtitle.style.display = "";
                var speedTxt = formatted.speed || headerSubtitle;
                if (trayDOM.speedEl && trayDOM.speedEl.textContent !== speedTxt) trayDOM.speedEl.textContent = speedTxt;
            } else {
                if (trayDOM.subtitle.style.display !== "none") trayDOM.subtitle.style.display = "none";
            }
        }
        if (trayDOM.progressBar) {
            var newWidth = avgPct + "%";
            if (trayDOM.progressBar.style.width !== newWidth) {
                trayDOM.progressBar.style.width = newWidth;
            }
        }

        // 2. Header Actions Toggle Swap — ONLY update if HTML content actually changed (prevents button flickering)
        var actionsContainer = stack.querySelector(".upload-toast-header-actions");
        if (actionsContainer) {
            var newActionsHtml = buildHeaderActionsHtml(isAllCompleted, pausedCount, window.uploadManagerExpanded, totalCount, window.uploadTrayDocked);
            if (actionsContainer.getAttribute("data-last-html") !== newActionsHtml) {
                actionsContainer.setAttribute("data-last-html", newActionsHtml);
                actionsContainer.innerHTML = newActionsHtml;
                wireHeaderActions(actionsContainer);
                refreshLucideIcons(actionsContainer);
            }
        }

        // 3. Body Collapsed State — respects uploadManagerExpanded regardless of docked state
        if (bodyEl) {
            if (window.uploadManagerExpanded) {
                bodyEl.classList.remove("collapsed");
            } else {
                bodyEl.classList.add("collapsed");
            }
        }

        // 4. Update File List In-Place
        var activeIds = {};
        for (var i = 0; i < activeUploads.length; i++) {
            var item = activeUploads[i];
            activeIds[item.id] = true;
            var itemEl = bodyEl.querySelector("#toast-item-" + item.id);
            if (!itemEl) {
                var tempDiv = document.createElement("div");
                tempDiv.innerHTML = buildTrayItemHtml(item);
                var newItemEl = tempDiv.firstChild;
                bodyEl.appendChild(newItemEl);
                refreshLucideIcons(newItemEl);
                wireTrayItemListeners(newItemEl, item);
            } else {
                var pct = Math.round(item.progress || 0);
                var sizeStr = formatSize(item.fileSize);

                var metaText = "";
                var fillStyle = "";
                var actionHtml = "";

                if (item.status === 'DELETED') {
                    metaText = sizeStr;
                    fillStyle = 'rgba(220, 38, 38, 0.12)';
                    pct = 100;
                    actionHtml = '<span style="color: #dc2626; display: flex; align-items: center; margin-right: 8px;"><i data-lucide="trash-2" style="width:16px;height:16px;"></i></span>';
                } else if (item.status === 'COMPLETED' || (pct >= 100 && item.status !== 'UPLOADING' && item.status !== 'PAUSED')) {
                    var timeStr = item.uploadTime ? item.uploadTime + "s" : "completed";
                    metaText = sizeStr + " • Completed (" + timeStr + ")";
                    fillStyle = 'rgba(24, 128, 56, 0.08)';
                    pct = 100;
                    actionHtml = '<span style="color: var(--green); display: flex; align-items: center; margin-right: 8px;"><i data-lucide="check" style="width:16px;height:16px;"></i></span>';
                } else if (item.status === 'QUEUED') {
                    metaText = sizeStr + " • Queued";
                    fillStyle = 'transparent';
                    pct = 0;
                } else {
                    metaText = sizeStr + " • " + pct + "%";
                    fillStyle = 'rgba(59, 130, 246, 0.08)';
                }

                var metaEl = itemEl.querySelector(".upload-toast-meta");
                if (metaEl && metaEl.textContent !== metaText) metaEl.textContent = metaText;

                var progressFill = itemEl.querySelector(".toast-progress-bar");
                if (progressFill) {
                    var newWidth = pct + "%";
                    if (progressFill.style.width !== newWidth) progressFill.style.width = newWidth;
                    if (progressFill.style.background !== fillStyle) progressFill.style.background = fillStyle;
                }

                if (item.status === 'COMPLETED' || item.status === 'DELETED') {
                    var actionsContainer = itemEl.querySelector(".upload-toast-actions");
                    if (actionsContainer && actionsContainer.querySelector(".upload-toast-cancel-text")) {
                        actionsContainer.innerHTML = actionHtml;
                        refreshLucideIcons(actionsContainer);
                    }
                    wireTrayItemListeners(itemEl, item);
                }

                // Re-order only if the element is not already in the correct position (prevents hover flickering)
                if (bodyEl.children[i] !== itemEl) {
                    bodyEl.appendChild(itemEl);
                }
            }
        }

        // Remove completed/removed items
        var existingItems = bodyEl.querySelectorAll(".upload-toast");
        for (var j = 0; j < existingItems.length; j++) {
            var itemEl = existingItems[j];
            var idAttr = itemEl.getAttribute("id");
            if (idAttr) {
                var itemId = parseInt(idAttr.replace("toast-item-", ""));
                if (!activeIds[itemId]) {
                    itemEl.remove();
                }
            }
        }

        // 5. Trigger FLIP animation for smooth sliding position transitions
        if (bodyEl) {
            var children = bodyEl.children;
            requestAnimationFrame(function () {
                for (var n = 0; n < children.length; n++) {
                    var child = children[n];
                    var idAttr = child.getAttribute("id");
                    if (idAttr && oldRects[idAttr]) {
                        var oldRect = oldRects[idAttr];
                        var newRect = child.getBoundingClientRect();
                        var deltaY = oldRect.top - newRect.top;
                        if (deltaY !== 0) {
                            child.style.transition = 'none';
                            child.style.transform = 'translateY(' + deltaY + 'px)';
                            child.offsetHeight; // Force reflow
                            child.style.transition = 'transform 0.4s cubic-bezier(0.2, 0.8, 0.2, 1)';
                            child.style.transform = 'translateY(0)';
                        }
                    }
                }
            });
        }

        refreshLucideIcons(stack);
    }

    // Poll uploadQueue for changes every 500ms while uploads are active
    var uploadTrayInterval = null;
    function startUploadTrayPolling() {
        if (uploadTrayInterval) return;
        uploadTrayInterval = setInterval(function () {
            var queue = window.uploadQueue || [];
            var activeCount = queue.filter(function (item) {
                return item.status === "UPLOADING" || item.status === "QUEUED" || item.status === "PROCESSING" || item.status === "PAUSED";
            }).length;
            if (activeCount === 0) {
                renderUploadTray(); // One final render to show completion
                clearInterval(uploadTrayInterval);
                uploadTrayInterval = null;
            } else {
                renderUploadTray();
            }
        }, 500);
    }

    // Listen for production upload events to start/stop polling
    document.addEventListener("DOMContentLoaded", function () {
        // Watch the upload queue via the production autoUpload/addToUploadQueue
        // We check every time the file list renders
        var origAddToQueue = window.addToUploadQueue;
        if (typeof origAddToQueue === "function") {
            window.addToUploadQueue = function (files) {
                origAddToQueue(files);
                startUploadTrayPolling();
            };
        }
    });

    // =========================================================================
    // 5.5 QUICK ACCESS CARDS — Show recent files from production data
    // =========================================================================

    function renderQuickAccess(files) {
        var container = document.getElementById("quickAccessContainer");
        if (!container) return;

        // Hide Recents (Quick Access) on mobile screens OR inside a subfolder OR on Recent view
        var tab = window.activeTab || "file";
        var activeFolder = (typeof window.getCurrentFolderPath === "function")
            ? window.getCurrentFolderPath()
            : (typeof currentFolderPath !== "undefined" ? currentFolderPath : "");
        if (window.innerWidth <= 550 || (activeFolder && activeFolder !== "Home" && activeFolder !== "") || tab === "recent") {
            container.style.display = "none";
            return;
        }
        container.style.display = ""; // Reset display

        if (!files || files.length === 0) {
            container.innerHTML = "";
            return;
        }

        // Take up to 4 recent files
        var recentFiles = files.slice(0, 4);
        var html = "";
        for (var i = 0; i < recentFiles.length; i++) {
            var item = recentFiles[i];
            var name = typeof item === "string" ? item : (item.name || item.filename || "");
            var ext = name.split(".").pop().toLowerCase();
            var info = getFileTypeInfo(name, ext);
            var escName = escapeHtml(name);
            var sizeBytes = typeof item === "object" && typeof item.size === "number" ? item.size : 0;
            var formattedSize = sizeBytes > 0 ? formatBytes(sizeBytes) : "";
            var typeLabel = ext ? ext.toUpperCase() : "FILE";
            var subtitle = formattedSize ? (typeLabel + " - " + formattedSize) : typeLabel;

            html +=
                '<div class="quick-card" data-filename="' + escName + '">' +
                '<div class="quick-icon ' + info.avatarClass + '"><i data-lucide="' + info.iconName + '"></i></div>' +
                '<div class="quick-copy" style="flex:1;min-width:0;">' +
                '<div class="quick-title" title="' + escName + '">' + escName + '</div>' +
                '<div class="quick-subtitle">' + subtitle + '</div>' +
                '</div>' +
                '<div class="quick-hover-actions" style="display:flex;align-items:center;gap:4px;flex-shrink:0;">' +
                '<button class="btn-icon" data-action="download" data-filename="' + escName + '" title="Download" style="width:24px;height:24px;padding:0;display:flex;align-items:center;justify-content:center;background:transparent;border:none;color:var(--text-muted);cursor:pointer;">' +
                '<i data-lucide="download" style="width:14px;height:14px;"></i>' +
                '</button>' +
                '<button class="btn-icon" data-action="menu" data-filename="' + escName + '" title="More actions" style="width:24px;height:24px;padding:0;display:flex;align-items:center;justify-content:center;background:transparent;border:none;color:var(--text-muted);cursor:pointer;">' +
                '<i data-lucide="more-vertical" style="width:14px;height:14px;"></i>' +
                '</button>' +
                '</div>' +
                '</div>';
        }
        container.innerHTML = html;

        refreshLucideIcons(container);

        // Action Handlers
        var downloadBtns = container.querySelectorAll('button[data-action="download"]');
        for (var d = 0; d < downloadBtns.length; d++) {
            downloadBtns[d].addEventListener("click", function (e) {
                e.stopPropagation();
                var fname = this.getAttribute("data-filename");
                if (fname) {
                    var link = document.createElement("a");
                    link.href = "/download/" + encodeURIComponent(fname);
                    link.download = fname;
                    document.body.appendChild(link);
                    link.click();
                    document.body.removeChild(link);
                }
            });
        }

        var menuBtns = container.querySelectorAll('button[data-action="menu"]');
        for (var m = 0; m < menuBtns.length; m++) {
            menuBtns[m].addEventListener("click", function (e) {
                e.stopPropagation();
                var fname = this.getAttribute("data-filename");
                if (fname && typeof window.openRowMenu === "function") {
                    window.openRowMenu(e, fname);
                }
            });
        }

        // Click card to select
        var cards = container.querySelectorAll(".quick-card");
        for (var k = 0; k < cards.length; k++) {
            cards[k].addEventListener("click", function (e) {
                if (e.target.closest("button")) return;
                var fname = this.getAttribute("data-filename");
                if (prototypeSelectedItems.indexOf(fname) === -1) {
                    prototypeSelectedItems = [fname];
                }
                renderPrototypeFileList();
            });
        }

        refreshLucideIcons(container);
    }

    // =========================================================================
    // 6. INITIALIZATION — Kick off on DOM ready
    // =========================================================================

    // Fetch full file data with metadata from API (includes folders)
    // Delegated to FileRepository for AbortController in-flight request cancellation
    function fetchFilesData() {
        var path = (typeof window.getCurrentFolderPath === "function")
            ? window.getCurrentFolderPath()
            : (window.currentFolderPath || "");

        if (window.FileRepository && typeof window.FileRepository.fetchFolderContents === 'function') {
            return window.FileRepository.fetchFolderContents(path);
        }

        // Fallback for bootstrap race before FileRepository instantiation
        var cleanPath = cleanFolderPath(path);
        var url = cleanPath ? ("/api/folders/" + encodeURIComponent(cleanPath) + "/files") : "/api/files";
        return fetch(url)
            .then(function (r) { return r.ok ? r.json() : { files: [] }; })
            .then(function (data) {
                var files = (data && (data.files_data || data.files)) ? (data.files_data || data.files) : [];
                return tagFilesWithFolder(files, cleanPath);
            })
            .catch(function () { return tagFilesWithFolder([], cleanPath); });
    }

    // Render QR code in sidebar using production QR API
    function renderSidebarQR() {
        var qrBox = document.getElementById("qrBox");
        var connectAddress = document.getElementById("connectAddress");
        if (!qrBox) return;

        var url = window.location.origin;
        if (window._currentNetworkInfo && window._currentNetworkInfo.fullUrl) {
            url = window._currentNetworkInfo.fullUrl;
        }

        if (connectAddress) {
            connectAddress.textContent = url;
        }

        // Generate fresh QR each time via cache-busting random string
        qrBox.innerHTML = "";
        var qrApiUrl = "/api/qr-code?text=" + encodeURIComponent(url) + "&size=140&_=" + Math.random().toString(36).substr(2, 9);
        var img = document.createElement("img");
        img.alt = "QR Code";
        img.style.cssText = "width:102px;height:102px;object-fit:contain;display:block;margin:0 auto;";
        img.src = qrApiUrl;
        img.onerror = function () {
            qrBox.innerHTML = '<div style="font-size:0.6rem;color:var(--text-muted);text-align:center;padding:8px;">Scan to connect</div>';
        };
        qrBox.appendChild(img);
    }

    // Render QR code in Dialog using production QR API
    function renderDialogQR() {
        var dialogBox = document.getElementById("connectQrDialogBox");
        var dialogAddress = document.getElementById("connectQrDialogAddress");
        if (!dialogBox) return;

        var url = window.location.origin;
        if (window._currentNetworkInfo && window._currentNetworkInfo.fullUrl) {
            url = window._currentNetworkInfo.fullUrl;
        }

        if (dialogAddress) {
            dialogAddress.textContent = url;
        }

        dialogBox.innerHTML = "";
        var qrApiUrl = "/api/qr-code?text=" + encodeURIComponent(url) + "&size=200&_=" + Math.random().toString(36).substr(2, 9);
        var img = document.createElement("img");
        img.alt = "QR Code";
        img.style.cssText = "max-width:100%;max-height:100%;object-fit:contain;display:block;margin:0 auto;";
        img.src = qrApiUrl;
        img.onerror = function () {
            dialogBox.innerHTML = '<div style="font-size:0.8rem;color:var(--text-muted);text-align:center;padding:12px;">Scan to connect</div>';
        };
        dialogBox.appendChild(img);
    }

    // Delegates to the canonical rendering pipeline.
    // refreshFileList fetches API → writes Repository → triggers Scheduler → Projection → Renderer.
    function triggerInstantRefresh() {
        if (typeof refreshFileList === "function") {
            refreshFileList('instant_refresh');
        }
    }
    window.triggerInstantRefresh = triggerInstantRefresh;

    // Debounced refresh that routes through the canonical pipeline.
    // Preserves identical debounce timing and coalescing behavior.
    window.requestSafeVisibleFilesRefresh = function (delayMs) {
        var waitMs = typeof delayMs === "number" ? delayMs : 150;
        if (window._safeVisibleFilesRefreshTimer) {
            clearTimeout(window._safeVisibleFilesRefreshTimer);
            window._safeVisibleFilesRefreshTimer = null;
        }
        window._safeVisibleFilesRefreshTimer = setTimeout(function () {
            window._safeVisibleFilesRefreshTimer = null;
            if (typeof refreshFileList === "function") {
                refreshFileList('safe_visible_refresh');
            }
        }, waitMs);
    };

    function init() {
        window.uploadTrayDocked = true;
        try {
            var urlParams = new URLSearchParams(window.location.search);
            var folderParam = urlParams.get("folder");
            if (folderParam) {
                window.currentFolderPath = cleanFolderPath(folderParam);
                if (window.history && typeof window.history.replaceState === "function") {
                    try {
                        window.history.replaceState({ folder: window.currentFolderPath }, "", window.location.pathname);
                    } catch (e) { }
                }
            }
        } catch (e) { }
        // Restore upload queue from server (clears on server restart = clears on data clear)
        fetch("/api/upload-history")
            .then(function (r) { return r.json(); })
            .then(function (restoredQueue) {
                var queueList = Array.isArray(restoredQueue) ? restoredQueue : ((restoredQueue && restoredQueue.queue) ? restoredQueue.queue : []);
                if (queueList.length > 0) {
                    queueList.forEach(function (item) {
                        if (item.status === "UPLOADING" || item.status === "QUEUED") {
                            item.status = "PAUSED";
                        }
                    });
                    if (window.LanvanStore) {
                        window.LanvanStore.dispatch("SYNC_QUEUE", { queue: queueList });
                    }
                    try { localStorage.setItem("lanvan_upload_queue", JSON.stringify(queueList)); } catch (e) { }
                    startUploadTrayPolling();
                    renderUploadTray();
                } else {
                    try { localStorage.removeItem("lanvan_upload_queue"); } catch (e) { }
                    if (window.LanvanStore) {
                        window.LanvanStore.dispatch("SYNC_QUEUE", { queue: [] });
                    }
                    renderUploadTray();
                }
            })
            .catch(function () {
                try {
                    var stored = localStorage.getItem("lanvan_upload_queue");
                    if (stored) {
                        var q = JSON.parse(stored);
                        if (Array.isArray(q) && window.LanvanStore) {
                            window.LanvanStore.dispatch("SYNC_QUEUE", { queue: q });
                            startUploadTrayPolling();
                        }
                    }
                } catch (e) { }
                renderUploadTray();
            });

        setupDropzone();
        setupSearch();

        // Keyboard Shortcuts: Ctrl+A, Delete, F2
        document.addEventListener("keydown", function (e) {
            var active = document.activeElement;
            var isInputActive = active && (active.tagName === "INPUT" || active.tagName === "TEXTAREA" || active.isContentEditable);

            // Escape Key to Close Settings Dialog / Context Menus / Clear Selection
            if (e.key === "Escape" || e.key === "Esc") {
                var settingsDialog = document.getElementById("settingsDialog");
                if (settingsDialog && settingsDialog.style.display !== "none" && settingsDialog.style.display !== "") {
                    if (typeof window.closeSettingsDialog === "function") {
                        window.closeSettingsDialog();
                    } else {
                        settingsDialog.style.display = "none";
                    }
                    return;
                }
                var contextMenu = document.getElementById("contextMenu");
                if (contextMenu && contextMenu.style.display !== "none") {
                    contextMenu.style.display = "none";
                    return;
                }
                if (typeof window.clearSelection === "function") {
                    window.clearSelection();
                }
            }

            // Ctrl+A Select All Files/Folders
            if ((e.ctrlKey || e.metaKey) && (e.key === "a" || e.key === "A")) {
                if (isInputActive) return; // Let standard input selection work
                e.preventDefault();
                var items = document.querySelectorAll("#nasFileList .m3-list-item");
                if (items.length === 0) return;

                prototypeSelectedItems = [];
                for (var i = 0; i < items.length; i++) {
                    var item = items[i];
                    var name = item.getAttribute("data-filename");
                    if (name) {
                        prototypeSelectedItems.push(name);
                        item.classList.add("selected");
                    }
                }
                updateSelectionToolbar();
            }

            // Delete Key to Delete Selected Items
            if (e.key === "Delete" || e.key === "Del") {
                if (isInputActive) return;
                e.preventDefault();
                if (typeof deleteSelected === "function") {
                    deleteSelected();
                }
            }

            // F2 Key to Rename Selected Items
            if (e.key === "F2") {
                if (isInputActive) return;
                e.preventDefault();
                if (prototypeSelectedItems.length > 0 && typeof openRenameModal === "function") {
                    openRenameModal();
                }
            }
        });

        var folderInput = document.getElementById("newFolderNameInput");
        if (folderInput) {
            folderInput.addEventListener("keydown", function (e) {
                if (e.key === "Enter") {
                    e.preventDefault();
                    submitNewFolder();
                }
            });
        }

        // Global document click listener for outside selection clearing and uploader tray collapse
        document.addEventListener("click", function (e) {
            // 1. Unselect items when clicking outside list items, cards, or control elements
            if (typeof prototypeSelectedItems !== "undefined" && prototypeSelectedItems.length > 0) {
                var isListItem = e.target.closest(".m3-list-item");
                var isQuickCard = e.target.closest(".quick-card");
                var isSelectionToolbar = e.target.closest("#selectionContent");
                var isContextMenu = e.target.closest("#contextMenu");
                var isModal = e.target.closest(".modal") || e.target.closest(".modal-overlay") || e.target.closest("[role='dialog']");
                var isControlBtn = e.target.closest("button") || e.target.closest("input");

                if (!isListItem && !isQuickCard && !isSelectionToolbar && !isContextMenu && !isModal && !isControlBtn) {
                    if (typeof window.clearSelection === "function") {
                        window.clearSelection();
                    }
                }
            }

            // 2. Click outside uploader notification widget to collapse expanded list
            if (window.uploadManagerExpanded) {
                var stack = document.getElementById("uploadToastStack");
                if (stack && !stack.contains(e.target)) {
                    window.uploadManagerExpanded = false;
                    if (typeof scheduleUploadTrayRender === "function") {
                        scheduleUploadTrayRender();
                    } else if (typeof renderUploadTray === "function") {
                        renderUploadTray();
                    }
                }
            }
        });

        // Restore saved view mode preference immediately on page load
        try {
            var savedViewModeOnLoad = localStorage.getItem("lanvan_view_mode") || "grid";
            if (typeof window.setViewMode === "function") {
                window.setViewMode(savedViewModeOnLoad);
            }
        } catch (e) { }

        // F5 Trace Instrumentation Helper
        window.__logF5Trace = function(checkpointName) {
            try {
                var folder = typeof window.getCurrentFolderPath === "function" ? window.getCurrentFolderPath() : (window.currentFolderPath || "");
                var repoCount = (window.FileRepository && typeof window.FileRepository.getFolderCache === "function") 
                    ? (window.FileRepository.getFolderCache(folder) || []).length : 0;
                
                var projCount = 0;
                if (window.ProjectionLayer) {
                    var storeState = window.LanvanStore ? Object.assign({}, window.LanvanStore.state) : { currentFolder: folder, uploadQueue: [] };
                    storeState.currentFolder = folder;
                    var engine = window.projectionLayer || (typeof window.ProjectionLayer === 'function' ? new window.ProjectionLayer() : window.ProjectionLayer);
                    if (engine && engine.buildCurrentFolderViewModel) {
                        var vm = engine.buildCurrentFolderViewModel(storeState, window.FileRepository ? window.FileRepository.getFolderCache(folder) : []);
                        projCount = Array.isArray(vm) ? vm.length : ((vm && vm.visibleFiles) ? vm.visibleFiles.length : 0);
                    }
                }

                var container = document.getElementById("nasFileList");
                var domCount = container ? container.querySelectorAll(".m3-list-item").length : 0;

                console.log("[F5-TRACE] 📍 Checkpoint: " + checkpointName +
                    " | Timestamp: " + performance.now().toFixed(1) + "ms" +
                    " | Repo count: " + repoCount +
                    " | Projection count: " + projCount +
                    " | DOM count: " + domCount);
            } catch (e) {
                console.error("[F5-TRACE] Error logging trace:", e);
            }
        };

        // Show loading state immediately
        var container = document.getElementById("nasFileList");
        if (container) {
            container.innerHTML =
                '<div style="display:flex; flex-direction:column; align-items:center; justify-content:center; text-align:center; padding:3rem 0; width:100%;">' +
                '<div style="width:40px; height:40px; border:4px solid var(--border-color); border-top:4px solid var(--primary); border-radius:50%; animation:spin 1s linear infinite; margin-bottom:1rem;"></div>' +
                '<div style="font-size:0.9rem; color:var(--text-muted);">Loading files...</div>' +
                "</div>";
            if (!document.getElementById("lanvan-spin-keyframes")) {
                var style = document.createElement("style");
                style.id = "lanvan-spin-keyframes";
                style.textContent = "@keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }";
                document.head.appendChild(style);
            }
        }

        window.__logF5Trace("1. Before fetchFilesData()");

        // Fetch full file data with metadata from API
        fetchFilesData().then(function (filesData) {
            window.__logF5Trace("2. After fetchFilesData()");
            renderPrototypeFileList(filesData);
        });

        // Also try reading from production #fileGrid (server-rendered files)
        var fileGrid = document.getElementById("fileGrid");
        if (fileGrid) {
            var cards = fileGrid.querySelectorAll(".file-card .file-name");
            if (cards.length > 0) {
                var initialFiles = [];
                for (var i = 0; i < cards.length; i++) {
                    initialFiles.push(cards[i].textContent.trim());
                }
                renderPrototypeFileList(initialFiles);
            }
        }

        // Fetch network info to populate window._currentNetworkInfo and render QR code
        fetch('/api/network-info')
            .then(function (res) { return res.json(); })
            .then(function (data) {
                var protocol = window.location.protocol;
                var port = window.location.port;
                var lanIp = data.lan_ip || window.location.hostname;
                var lanIpUrl = protocol + '//' + lanIp;
                if (port && port !== '80' && port !== '443') {
                    lanIpUrl += ':' + port;
                }
                var fullUrl = lanIpUrl;
                var useMDNS = data.mdns && data.mdns.status === 'active';
                if (useMDNS && data.mdns.url) {
                    fullUrl = data.mdns.url;
                }
                window._currentNetworkInfo = {
                    networkInfo: data,
                    lanIpUrl: lanIpUrl,
                    useMDNS: useMDNS,
                    fullUrl: fullUrl,
                    currentMode: useMDNS ? "mdns" : "ip"
                };

                // Sync tab UI highlights with initial default URL
                var lanTab = document.getElementById("lanIpTab");
                var mdnsTab = document.getElementById("mdnsTab");
                var qrLanTab = document.getElementById("connectQrLanIpTab");
                var qrMdnsTab = document.getElementById("connectQrMdnsTab");
                if (lanTab) lanTab.classList.toggle("active", !useMDNS);
                if (mdnsTab) mdnsTab.classList.toggle("active", useMDNS);
                if (qrLanTab) qrLanTab.classList.toggle("active", !useMDNS);
                if (qrMdnsTab) qrMdnsTab.classList.toggle("active", useMDNS);

                renderSidebarQR();
            }).catch(function (err) {
                console.error("Failed to load initial network info:", err);
                renderSidebarQR();
            });

        // Initial clipboard sync
        if (typeof refreshClipboardHistory === "function") {
            setTimeout(function () {
                refreshClipboardHistory();
            }, 500);
        }

        // Clean event-driven DOM progress updater (no setInterval polling)
        window.updatePrototypeRowProgress = function (item) {
            if (!item || !item.fileName) return;

            if (item.status === 'COMPLETED') {
                var hasOtherActiveUploads = Array.isArray(window.uploadQueue) && window.uploadQueue.some(function (qi) {
                    return qi && qi.id !== item.id && (qi.status === 'UPLOADING' || qi.status === 'QUEUED' || qi.status === 'PROCESSING' || qi.status === 'PAUSED');
                });

                if (!hasOtherActiveUploads) {
                    setTimeout(function () {
                        if (typeof triggerInstantRefresh === 'function') {
                            triggerInstantRefresh();
                        } else if (typeof refreshFileList === 'function') {
                            refreshFileList();
                        }
                    }, 150);
                }
                return;
            }

            var container = document.getElementById("nasFileList");
            if (!container) return;

            var normCurrentDir = cleanFolderPath(currentFolderPath);
            var itemDir = cleanFolderPath(item.targetDir || item.parent_path || item.folder || "");

            if (itemDir === normCurrentDir) {
                var progress = Math.round(item.progress || 0);
                var escName = escapeHtml(item.fileName);
                var row = container.querySelector('.m3-list-item[data-filename="' + escName + '"]');
                if (row) {
                    var subtitleCell = row.querySelector('.item-subtitle');
                    if (subtitleCell) {
                        var statusTxt = item.status === 'PAUSED' ? 'Paused' : (item.status === 'PROCESSING' ? 'Processing' : 'Uploading');
                        var rowSub = progress + "% • " + statusTxt;
                        if (item.status === 'UPLOADING' && item.speed > 0 && item.fileSize && item.bytesUploaded) {
                            var remBytes = item.fileSize - item.bytesUploaded;
                            if (remBytes > 0) {
                                var etaSec = remBytes / item.speed;
                                var formattedEta = window.formatUploadBatchStatus ? (Math.round(etaSec) < 60 ? Math.round(etaSec) + 's' : Math.floor(Math.round(etaSec)/60) + 'm ' + (Math.round(etaSec)%60) + 's') : '';
                                if (formattedEta) rowSub += " • ETA " + formattedEta;
                            }
                        }
                        subtitleCell.textContent = rowSub;
                    }
                    var dateCell = row.querySelector('.item-date');
                    if (dateCell) {
                        dateCell.textContent = item.status === 'PAUSED' ? 'Paused' : (item.status === 'PROCESSING' ? 'Processing' : 'Uploading');
                    }
                    var bar = row.querySelector('.row-progress-bar');
                    if (bar) {
                        bar.style.width = progress + "%";
                    }

                    var playPauseBtn = row.querySelector('[data-action="pause-upload"], [data-action="resume-upload"]');
                    if (playPauseBtn) {
                        var currentAction = playPauseBtn.getAttribute("data-action");
                        if (item.status === 'PAUSED' && currentAction === 'pause-upload') {
                            playPauseBtn.setAttribute("data-action", "resume-upload");
                            playPauseBtn.setAttribute("title", "Resume upload");
                            playPauseBtn.innerHTML = '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="currentColor" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="lucide lucide-play"><polygon points="6 3 20 12 6 21 6 3"/></svg>';
                        } else if (item.status !== 'PAUSED' && currentAction === 'resume-upload') {
                            playPauseBtn.setAttribute("data-action", "pause-upload");
                            playPauseBtn.setAttribute("title", "Pause upload");
                            playPauseBtn.innerHTML = '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="lucide lucide-pause"><rect width="4" height="16" x="6" y="4"/><rect width="4" height="16" x="14" y="4"/></svg>';
                        }
                    }
                } else {
                    if (typeof window.triggerInstantUIUpdate === 'function') {
                        window.triggerInstantUIUpdate();
                    } else if (typeof lastRenderedFiles !== 'undefined') {
                        renderPrototypeFileList(lastRenderedFiles);
                    }
                }
            }
        };

        window.onUploadQueueAdded = function (files) {
            console.log("[app-init] onUploadQueueAdded hook fired!", files);
            window.uploadTrayDocked = false;
            if (typeof renderUploadTray === "function") {
                renderUploadTray();
            }
            if (typeof lastRenderedFiles !== "undefined" && typeof renderPrototypeFileList === "function") {
                renderPrototypeFileList(lastRenderedFiles);
            }
            startUploadTrayPolling();
        };

        // Define authoritative navigation helper
        window.navigateToFolder = function (folderPath) {
            var cleanFolder = String(folderPath || "").replace(/^Home\/?/, "").replace(/^Home$/, "").replace(/^\/+|\/+$/g, "");
            console.log("📂 [LANVAN UI] Navigating to folder: '" + (cleanFolder || "Home") + "'");
            if (window.LanvanStore) {
                window.LanvanStore.dispatch("SET_CURRENT_FOLDER", { folderPath: cleanFolder });
            } else {
                window.currentFolderPath = cleanFolder;
                // fetchFolderContents writes to Repository; Scheduler handles the render
                // via navigationGeneration increment in Store dispatch
                if (window.FileRepository) {
                    window.FileRepository.fetchFolderContents(cleanFolder);
                }
            }
        };

        // Subscribe to Store for Navigation Invariant
        // Store dispatch increments navigationGeneration → Scheduler subscriber fires requestRender()
        if (window.LanvanStore && typeof window.LanvanStore.subscribe === 'function') {
            window.LanvanStore.subscribe(function (state, action) {
                if (!action) return;
                if (action.type === 'SET_CURRENT_FOLDER' || action.type === 'NAVIGATE_FOLDER' || action.type === 'NAVIGATION') {
                    var targetFolder = state.currentFolder || "";
                    currentFolderPath = targetFolder;
                    console.log("🛠️ [TRACE @ app-init.js:4580] Store Subscription Triggered Navigation -> '" + (targetFolder || "Home") + "'");
                    
                    // fetchFolderContents writes to Repository; Navigation Controller requests render upon promise resolution
                    if (window.FileRepository && typeof window.FileRepository.fetchFolderContents === 'function') {
                        window.FileRepository.fetchFolderContents(targetFolder)
                            .then(function () {
                                var activeFolder = (typeof window.getCurrentFolderPath === 'function')
                                    ? window.getCurrentFolderPath()
                                    : (window.currentFolderPath || '');
                                activeFolder = (activeFolder === 'Home' || activeFolder === 'Home/') ? '' : activeFolder;
                                if (activeFolder === targetFolder) {
                                    if (window.RenderScheduler && typeof window.RenderScheduler.requestRender === 'function') {
                                        window.RenderScheduler.requestRender('nav_hydrated');
                                    }
                                }
                            })
                            .catch(function (err) {
                                console.error("  Error fetching folder contents on navigation:", err);
                            });
                    }
                }
            });
        }

        // Render empty manager on load so it is visible by default
        renderUploadTray();

        // Wire the RenderScheduler to the prototype renderer so the
        // unidirectional Store→Projection→Renderer pipeline is complete.
        if (window.RenderScheduler && typeof window.RenderScheduler.setRenderer === 'function') {
            window.RenderScheduler.setRenderer(function(viewModel) {
                renderPrototypeFileList(viewModel, 'scheduler');
            });
        }

        if (typeof window.refreshFileList === 'function') {
            window.refreshFileList('bootstrap');
        }

        console.log("[app-init] Prototype UI adapter initialized. " +
            "Wrapped updateFileDisplay=" + (typeof updateFileDisplay === "function") +
            ", refreshClipboardHistory=" + (typeof refreshClipboardHistory === "function"));
    }

    // Run after production JS has loaded (main-app.js and ui-modules.js are in base.html after this script)
    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", function () {
            // Small delay to ensure production scripts have run
            setTimeout(init, 100);
        });
    } else {
        setTimeout(init, 100);
    }
})();
