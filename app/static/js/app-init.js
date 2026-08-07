
    // setViewMode
    // requestAnimationFrame
    // isTargetFolder
    // (isSingle && !isTargetFolder)
    // SINGLE FILE / FOLDER RENAME
    // MULTI-ITEM BATCH RENAME
    // downloadSelectedAsZip
    // downloadZipMenuItem
    // _doInstantUIUpdate
    // toggleDarkMode
    // clearTypeFilter
    // alreadySelected
    // selectedItems.indexOf(filename)

/**
 * Application Initialization & UI Integration Layer
 *
 * Thin translation adapter that bridges the state store, repository,
 * projection engine, and render scheduler to the DOM. Does not implement
 * business logic, networking, encryption, or upload management.
 *
 * Design invariants:
 * - All state flows through LanvanStore (single source of truth)
 * - DOM renders are scheduled through RenderScheduler (rAF coalescing)
 * - File cache reads route through FileRepository (AbortController aware)
 * - Upload state transitions are validated by UploadStatus FSM
 */

(function () {
    "use strict";

    // GUARD: Prevent double-wrapping if script loads multiple times
    if (window.__appInitLoaded) {
        console.log("[app-init] Already loaded — skipping duplicate initialization");
        return;
    }
    window.__appInitLoaded = true;

    // Disable browser native spellcheck, autocomplete, and writing assist overlays globally
    function disableBrowserAssist(el) {
        if (!el || !el.setAttribute) return;
        el.setAttribute('autocomplete', 'off');
        el.setAttribute('autocorrect', 'off');
        el.setAttribute('autocapitalize', 'off');
        el.setAttribute('spellcheck', 'false');
        el.setAttribute('data-gramm', 'false');
        el.setAttribute('data-enable-grammarly', 'false');
    }

    function initBrowserAssist() {
        document.querySelectorAll('input, textarea').forEach(disableBrowserAssist);
        const observer = new MutationObserver(function (mutations) {
            mutations.forEach(function (mutation) {
                mutation.addedNodes.forEach(function (node) {
                    if (node.nodeType === 1) {
                        if (node.matches && node.matches('input, textarea')) disableBrowserAssist(node);
                        if (node.querySelectorAll) node.querySelectorAll('input, textarea').forEach(disableBrowserAssist);
                    }
                });
            });
        });
        if (document.body) {
            observer.observe(document.body, { childList: true, subtree: true });
        }
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initBrowserAssist);
    } else {
        initBrowserAssist();
    }

    // Wrap updateFileDisplay() — called by production refreshFileList() and auto-refresh
    // Guard: only wrap if not already wrapped by a previous partial load
    if (typeof updateFileDisplay === "function" && !updateFileDisplay.__renderWrapped) {
        const _originalUpdateFileDisplay = updateFileDisplay;
        updateFileDisplay = function (files) {
            var normCurrentDir = cleanFolderPath(currentFolderPath);
            if (Array.isArray(files)) {
                var taggedFolder = getTaggedFolderPath(files);
                if (taggedFolder !== null && taggedFolder !== normCurrentDir) {
                    console.warn("[UPDATE FILE DISPLAY] Ignoring stale payload for folder '" + taggedFolder + "' while active view is '" + normCurrentDir + "'.");
                    return;
                }
                renderFileList(tagFilesWithFolder(files, normCurrentDir));
            } else {
                fetchFilesData().then(function (fd) {
                    renderFileList(fd);
                }).catch(function (err) {
                    console.error("fetchFilesData error:", err);
                });
            }
        };
        updateFileDisplay.__renderWrapped = true;
        window.updateFileDisplay = updateFileDisplay;
    }

    // Wrap refreshClipboardHistory() — called by production WebSocket and manual refresh
    if (typeof refreshClipboardHistory === "function" && !refreshClipboardHistory.__renderWrapped) {
        const _originalRefreshClipboardHistory = refreshClipboardHistory;
        refreshClipboardHistory = async function () {
            await _originalRefreshClipboardHistory();
            // After production refreshes, also render clipboard view
            // Production stores data in #clipboardHistoryContent DOM
            setTimeout(() => syncClipboardView(), 100);
        };
        refreshClipboardHistory.__renderWrapped = true;
    }

    // =========================================================================
    // 2. FILE RENDERERS — Consume production data, output Lanvan DOM
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



    // renderBreadcrumbs is provided by breadcrumb-nav.js module

    /**
     * Render files in production #nasFileList from the same data production uses.
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
    window.activeTab = document.documentElement.dataset.activeTab || null;


    // --- Explorer Navigation Compatibility Stubs (Delegated to BreadcrumbNav) ---
    // function cleanFolderPath
    
    // cleanFolderPath helper
    // getRelativeItemDir
    var cleanFolderPath = function(path) { return window.BreadcrumbNav.cleanFolderPath(path); };
    var tagFilesWithFolder = function(files, folderPath) { return window.BreadcrumbNav.tagFilesWithFolder(files, folderPath); };
    var getTaggedFolderPath = function(files) { return window.BreadcrumbNav.getTaggedFolderPath(files); };
        // function getRelativeItemDir
    var getRelativeItemDir = function(itemDir, normCurrentDir) { return window.BreadcrumbNav.getRelativeItemDir(itemDir, normCurrentDir); };
    window.cleanFolderPath = cleanFolderPath;
    window.tagFilesWithFolder = tagFilesWithFolder;
    window.getTaggedFolderPath = getTaggedFolderPath;
    window.getRelativeItemDir = getRelativeItemDir;
    window.navigateIntoFolder = function() { return window.BreadcrumbNav.navigateIntoFolder.apply(this, arguments); };
    window.navigateToFolder = function() { return window.BreadcrumbNav.navigateToFolder.apply(this, arguments); };
    window.navigateToPathAndSelect = function() { return window.BreadcrumbNav.navigateToPathAndSelect.apply(this, arguments); };
    window.switchView = function() { return window.BreadcrumbNav.switchView.apply(this, arguments); };
    window.updateExplorerLayoutState = function() { return window.BreadcrumbNav.updateExplorerLayoutState.apply(this, arguments); };

    var folderFilesCache = {}; // Folder-scoped disk file cache keyed by cleanFolderPath

    function renderFileList(files, renderReason) {
        if (window.__lanvanTimelineTracker) {
            var fCount = Array.isArray(files) ? files.length : (files ? 1 : 0);
            window.__lanvanTimelineTracker.recordEvent("renderView", "reason: " + renderReason + ", filesArg: " + fCount);
        }
        if (typeof window.__logF5Trace === "function") {
            window.__logF5Trace("5. After renderFileList() entry");
        }
        if (typeof window !== "undefined") {
            window.renderFileList = renderFileList;
            // Backward-compat alias — external callers using the old name continue to work
            window.renderPrototypeFileList = window.renderFileList;
        }
        var normCurrentDir = cleanFolderPath((typeof window.getCurrentFolderPath === "function")
            ? window.getCurrentFolderPath()
            : currentFolderPath);
        var reason = renderReason || "render_view";
        var container = document.getElementById("nasFileList");
        var filePanelMeta = document.getElementById("filePanelMeta");
        if (!container) return;
        var activeTab = document.documentElement.dataset.activeTab || (window.activeTab || 'file');
        if (activeTab !== 'file') {
            if (files) lastRenderedFiles = files;
            return;
        }

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

        var quickContainer = document.getElementById("quickAccessContainer");
        if (quickContainer) {
            if ((normCurrentDir && normCurrentDir !== "") || !files || files.length === 0) {
                quickContainer.style.display = "none";
            } else {
                quickContainer.style.display = "";
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
                    console.error("   WHO: renderFileList | FROM: " + fileSource + " | WHY: files parameter was undefined/null during render!");
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
            storeState.sortBy = sortBy;
            storeState.sortDirection = sortDirection;
            storeState.sortFolders = sortFolders;
            if (!storeState.pendingOps) {
                storeState.pendingOps = {};
            }
            var projectionEngine = window.projectionLayer || (typeof window.ProjectionLayer === 'function' ? new window.ProjectionLayer() : window.ProjectionLayer);
            viewModel = projectionEngine ? projectionEngine.buildCurrentFolderViewModel(storeState, files) : normalizedFiles;

            var traceId = Math.random().toString(36).substring(2, 7);
            console.log("🛠️ [TRACE @" + traceId + " @ app-init.js:348] renderFileList triggered | Reason: " + reason + " | Folder: '" + (normCurrentDir || "Home") + "'");
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
                    console.error("   WHO: renderFileList | FROM: uploadQueue merge | WHY: targetDir mismatch! ('" + itemDir + "' !== '" + normCurrentDir + "')");
                }
            }
        });

        // Apply client-side Type Filtering
        if (typeFilter !== "all") {
            normalizedFiles = normalizedFiles.filter(function (f) {
                return getFileItemType(f) === typeFilter;
            });
        }

        // Apply Universal client-side Search Filtering (.slice(0, 4) static signature guard)
        var toolbarSearchInputEl = document.getElementById("toolbarSearchInput");
        var searchQuery = toolbarSearchInputEl ? toolbarSearchInputEl.value.trim().toLowerCase() : "";
        if (searchQuery) {
            var universalSource = (window.FileRepository && typeof window.FileRepository.getAllCachedFiles === "function")
                ? window.FileRepository.getAllCachedFiles()
                : normalizedFiles;
            normalizedFiles = universalSource.filter(function (f) {
                if (!f) return false;
                var nameStr = typeof f === "string" ? f : f.name;
                if (!nameStr) return false;
                return nameStr.toLowerCase().indexOf(searchQuery) !== -1;
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
                var nameA = String(a.name || "").toLowerCase();
                var nameB = String(b.name || "").toLowerCase();
                comparison = nameA.localeCompare(nameB, undefined, { numeric: true, sensitivity: 'base' });
            } else if (sortBy === "date") {
                var parseDate = window.parseDateToTimestamp || function (d) { return typeof d === 'number' ? d : 0; };
                var timeA = parseDate(a.mtime || a.date || a.modified || (a.uploading ? Date.now() / 1000 : 0));
                var timeB = parseDate(b.mtime || b.date || b.modified || (b.uploading ? Date.now() / 1000 : 0));
                comparison = timeA - timeB;
            } else if (sortBy === "size") {
                var parseBytes = window.parseSizeToBytes || function () { return 0; };
                var bytesA = parseBytes(a.size || a.fileSize, a.isFolder);
                var bytesB = parseBytes(b.size || b.fileSize, b.isFolder);
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
            sortBy,
            sortDirection,
            sortFolders,
            normalizedFiles.map(function (f) {
                if (!f) return "";
                return [
                    f.name || "",
                    f.isFolder ? 1 : 0,
                    f.uploading ? 1 : 0,
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

        if (window._renderHasPainted && window._lastRenderSignature === renderSignature && !isStillShowingLoadingShell) {
            return;
        }
        window._lastRenderSignature = renderSignature;

        // Sync dropdown checkmarks and header arrows
        updateSortCheckmarks();
        updateSortHeaderArrows();

        // Update file and folder count in file panel meta
        if (filePanelMeta) {
            var folderCount = 0;
            var fileCount = 0;
            if (Array.isArray(normalizedFiles)) {
                for (var fIdx = 0; fIdx < normalizedFiles.length; fIdx++) {
                    if (normalizedFiles[fIdx] && normalizedFiles[fIdx].isFolder) {
                        folderCount++;
                    } else {
                        fileCount++;
                    }
                }
            }
            var parts = [];
            if (fileCount > 0) {
                parts.push(fileCount + " file" + (fileCount === 1 ? "" : "s"));
            }
            if (folderCount > 0) {
                parts.push(folderCount + " folder" + (folderCount === 1 ? "" : "s"));
            }
            filePanelMeta.textContent = parts.length > 0 ? parts.join(", ") : "";
        }

        var fileTableHead = document.getElementById("fileTableHead");
        var listBtn = document.getElementById("listViewBtn");
        var gridBtn = document.getElementById("gridViewBtn");

        var hasFiles = normalizedFiles && normalizedFiles.length > 0;
        updateExplorerLayoutState({
            hasFiles: hasFiles,
            viewMode: savedViewModeForSignature
        });

        if (!hasFiles) {
            container.style.display = "flex";
            container.style.flexDirection = "column";
            container.style.alignItems = "stretch";
            container.style.justifyContent = "stretch";
            container.style.flex = "1";
            container.style.height = "100%";
            window.selectedItems = [];
            window._contextMenuTarget = "";

            var queue = window.uploadQueue || [];
            var activeUploadsCount = queue.filter(function (item) {
                return item.status === "UPLOADING" || item.status === "QUEUED" || item.status === "PROCESSING" || item.status === "PAUSED";
            }).length;

            if (searchQuery) {
                container.innerHTML =
                    '<div class="empty-dropzone-wrapper" style="grid-column: 1 / -1; width:100%; height:100%; flex:1; display:flex; flex-direction:column; align-items:center; justify-content:center; text-align:center; padding:0; margin:auto;">' +
                    '<div class="avatar-icon" style="width:64px;height:64px;border-radius:18px;margin-bottom:1rem;background:var(--toggle-bg);color:var(--text-muted);display:flex;align-items:center;justify-content:center;">' +
                    '<i data-lucide="search-x" style="width:32px;height:32px;"></i></div>' +
                    '<div style="font-size:1.05rem; font-weight:600; color:var(--text-color); margin-bottom:0.25rem;">No files matching "' + escapeHtml(searchQuery) + '"</div>' +
                    '<div style="font-size:0.82rem; color:var(--text-muted); margin-bottom:1rem;">Check spelling or try searching for another term.</div>' +
                    '<button class="filter-chip" onclick="clearToolbarSearch()" style="display:inline-flex; align-items:center; gap:0.35rem; font-size:0.8rem; font-weight:700; border:1px solid var(--border-color); background:var(--card-bg); color:var(--primary); border-radius:999px; padding:0.4rem 0.9rem; cursor:pointer;">Clear search</button>' +
                    '</div>';
            } else if (typeFilter !== "all") {
                container.innerHTML =
                    '<div class="empty-dropzone-wrapper" style="grid-column: 1 / -1; width:100%; height:100%; flex:1; display:flex; flex-direction:column; align-items:center; justify-content:center; text-align:center; padding:0; margin:auto;">' +
                    '<div class="avatar-icon" style="width:64px;height:64px;border-radius:18px;margin-bottom:1rem;background:var(--toggle-bg);color:var(--text-muted);display:flex;align-items:center;justify-content:center;">' +
                    '<i data-lucide="file-x" style="width:32px;height:32px;"></i></div>' +
                    '<div style="font-size:1.05rem; font-weight:600; color:var(--text-color); margin-bottom:0.25rem;">No ' + escapeHtml(typeFilter) + ' files found</div>' +
                    '<div style="font-size:0.82rem; color:var(--text-muted); margin-bottom:1rem;">No files match the active type filter.</div>' +
                    '<button class="filter-chip" onclick="clearTypeFilter(event)" style="display:inline-flex; align-items:center; gap:0.35rem; font-size:0.8rem; font-weight:700; border:1px solid var(--border-color); background:var(--card-bg); color:var(--primary); border-radius:999px; padding:0.4rem 0.9rem; cursor:pointer;">Clear filter</button>' +
                    '</div>';
            } else if (activeUploadsCount > 0) {
                container.innerHTML =
                    '<div class="empty-dropzone-wrapper" style="grid-column: 1 / -1; width:100%; height:100%; flex:1; display:flex; flex-direction:column; align-items:center; justify-content:center; text-align:center; padding:0; margin:auto;">' +
                    '<div class="empty-dropzone-target" style="display:inline-flex; flex-direction:column; align-items:center; justify-content:center; padding:1.5rem 2.5rem; border-radius:16px; cursor:pointer; transition:background-color 0.2s ease;" onclick="if(typeof handleFileSelection===\'function\'){handleFileSelection(\'file\');}else{var fi=document.getElementById(\'fileInput\');if(fi){fi.value=\'\';fi.click();}}">' +
                    '<div class="avatar-icon avatar-folder" style="width:72px;height:72px;border-radius:18px;margin-bottom:1rem;">' +
                    '<i data-lucide="upload-cloud" style="width:34px;height:34px;"></i></div>' +
                    '<div style="font-size:1.05rem; font-weight:500; color:var(--text-color); margin-bottom:0.25rem;">Uploading ' + activeUploadsCount + ' file' + (activeUploadsCount === 1 ? '' : 's') + '...</div>' +
                    '<div style="font-size:0.8rem; color:var(--text-muted);">Files will appear here when upload completes. Click to add more.</div>' +
                    '</div>' +
                    '</div>';
            } else {
                container.innerHTML =
                    '<div class="empty-dropzone-wrapper" style="grid-column: 1 / -1; width:100%; height:100%; flex:1; display:flex; flex-direction:column; align-items:center; justify-content:center; text-align:center; padding:0; margin:auto;">' +
                    '<div class="empty-dropzone-target" style="display:inline-flex; flex-direction:column; align-items:center; justify-content:center; padding:1.5rem 2.5rem; border-radius:16px; cursor:pointer; transition:background-color 0.2s ease;" onclick="if(typeof handleFileSelection===\'function\'){handleFileSelection(\'file\');}else{var fi=document.getElementById(\'fileInput\');if(fi){fi.value=\'\';fi.click();}}">' +
                    '<div class="avatar-icon avatar-folder" style="width:72px;height:72px;border-radius:18px;margin-bottom:1rem;">' +
                    '<i data-lucide="folder-open" style="width:34px;height:34px;"></i></div>' +
                    '<div style="font-size:1.05rem; font-weight:500; color:var(--text-color); margin-bottom:0.25rem;">Drop files here</div>' +
                    '<div style="font-size:0.8rem; color:var(--text-muted);">or right-click to upload / create folders.</div>' +
                    '</div>' +
                    '</div>';
            }
            window._renderHasPainted = true;
            if (typeof window.refreshLucideIcons === "function") window.refreshLucideIcons(container);
            updateSelectionToolbar();
            try {
                renderQuickAccess(originalFilesForQuickAccess
                    .filter(function (f) { return !f.isFolder && !f.uploading; }));
            } catch (e) {
                console.error("[LANVAN UI] Quick access render failed during empty-state paint:", e);
            }
            return;
        }

        container.classList.remove("empty-state");
        container.style.display = "";
        container.style.flexDirection = "";
        container.style.alignItems = "";
        container.style.justifyContent = "";
        container.style.flex = "";
        container.style.minHeight = "";
        container.style.height = "";
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
            var rawDate = fileData.modified || fileData.date || fileData.dateStr || fileData.modified_formatted || fileData.mtime || "--";
            var dateStr = typeof formatLastModified === 'function' ? formatLastModified(rawDate) : rawDate;
            var locationText = (searchQuery && fileData.location) ? ("in " + fileData.location) : "";
            var subtitle = isFolderItem
                ? (locationText ? "Folder • " + locationText : (fileData.formattedSubtitle || "Folder"))
                : (locationText ? locationText : "File");
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
        window._renderHasPainted = true;
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
            "   Function: renderFileList\n" +
            "   Caller: " + callerLine.trim() + "\n" +
            "   Target Element: #" + (container.id || "nasFileList") + "\n" +
            "   Previous Child Count: " + prevChildCount + "\n" +
            "   HTML Length: " + html.length + "\n" +
            "   Reason: " + (renderReason || "file_render") + "\n" +
            "   Call Stack:\n" + stackTrace);

        var oldDomItems = Array.prototype.slice.call(container.querySelectorAll(".m3-list-item")).map(function (el) { return el.getAttribute("data-filename") || el.textContent.trim(); });
        container.innerHTML = html;
        var newDomItems = Array.prototype.slice.call(container.querySelectorAll(".m3-list-item")).map(function (el) { return el.getAttribute("data-filename") || el.textContent.trim(); });

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

        // Sync selection state: purge any deleted or uploading items from selectedItems
        var validNames = normalizedFiles.map(function (f) { return f.name; });
        if (Array.isArray(selectedItems)) {
            selectedItems = selectedItems.filter(function (name) {
                return validNames.indexOf(name) !== -1 && !isItemUploading(name);
            });
            var renderedItems = container.querySelectorAll(".m3-list-item");
            for (var s = 0; s < renderedItems.length; s++) {
                var itemFn = renderedItems[s].getAttribute("data-filename");
                if (itemFn && selectedItems.indexOf(itemFn) !== -1) {
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

        if (typeof window.refreshLucideIcons === "function") window.refreshLucideIcons(container);
        syncFileTableHeadWidth();
    }

    function syncFileTableHeadWidth() {
        var head = document.getElementById("fileTableHead");
        var list = document.getElementById("nasFileList");
        if (!head || !list) return;

        var mode = document.documentElement.getAttribute("data-view-mode") || (list.classList.contains("grid-mode") ? "grid" : "list");
        if (mode === "grid") {
            head.style.removeProperty("padding-right");
            return;
        }

        var scrollbarWidth = list.offsetWidth - list.clientWidth;
        head.style.setProperty("padding-right", (12 + Math.max(0, scrollbarWidth)) + "px", "important");
    }
    window.syncFileTableHeadWidth = syncFileTableHeadWidth;
    window.addEventListener("resize", syncFileTableHeadWidth);

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
     * Attach click handlers to file list items after render.
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

                // Touch / Pointer long-press selection handler for mobile devices
                var touchStartPos = null;
                var isLongPress = false;
                var longPressTimer = null;

                item.addEventListener("touchstart", function (e) {
                    if (e.touches.length > 1) return;
                    touchStartPos = { x: e.touches[0].clientX, y: e.touches[0].clientY };
                    isLongPress = false;

                    longPressTimer = setTimeout(function () {
                        isLongPress = true;
                        handleListItemClick(item, index, files, { isLongPress: true });
                    }, 400);
                }, { passive: true });

                item.addEventListener("touchmove", function (e) {
                    if (touchStartPos && e.touches.length === 1) {
                        var dx = Math.abs(e.touches[0].clientX - touchStartPos.x);
                        var dy = Math.abs(e.touches[0].clientY - touchStartPos.y);
                        if (dx > 10 || dy > 10) {
                            if (longPressTimer) clearTimeout(longPressTimer);
                        }
                    }
                }, { passive: true });

                item.addEventListener("touchend", function (e) {
                    if (longPressTimer) clearTimeout(longPressTimer);
                    if (isLongPress) {
                        e.preventDefault();
                        e.stopPropagation();
                        window._justHandledTouchSelection = true;
                        setTimeout(function () { window._justHandledTouchSelection = false; }, 350);
                    }
                });

                // Primary Click / Tap Handler (Exclusive Selection Mode Priority & Ctrl/Cmd Multi-Select)
                item.addEventListener("click", function (e) {
                    if (window._justFinishedMarqueeDrag || window._justHandledTouchSelection) {
                        e.stopPropagation();
                        e.preventDefault();
                        return;
                    }
                    if (e.target.closest("button")) return;

                    var currentSelection = window.selectedItems || [];

                    // 1. CTRL / CMD / SHIFT CLICK OR EXCLUSIVE SELECTION MODE PRIORITY
                    if (e.ctrlKey || e.metaKey || e.shiftKey || currentSelection.length > 0) {
                        e.preventDefault();
                        e.stopPropagation();
                        handleListItemClick(item, index, files, e);
                        return;
                    }

                    // 2. NORMAL PIPELINE (NO SELECTION ACTIVE)
                    if (folderFlag) {
                        navigateIntoFolder(name);
                        return;
                    }

                    // If a FILE is uploading and NOT selected, prevent selection
                    if ((itemData.uploading || isItemUploading(name))) {
                        return;
                    }

                    // Single click on file selects the item
                    e.preventDefault();
                    e.stopPropagation();
                    handleListItemClick(item, index, files, e);
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
                    var currentSelection = window.selectedItems || [];
                    if (currentSelection.length > 0) {
                        e.preventDefault();
                        e.stopPropagation();
                        return;
                    }
                    if (folderFlag) {
                        navigateIntoFolder(name);
                        return;
                    }
                    if (itemData.uploading || isItemUploading(name)) return;
                    if (typeof window.openFilePreview === "function") window.openFilePreview(name);
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
                        selectedItems = [fname];
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
    /**
     * Handle item click — toggle selection.
     */
    var selectedItems = [];
    Object.defineProperty(window, 'selectedItems', {
        get: function () {
            if (typeof window.LanvanStore !== 'undefined' && window.LanvanStore.getState) {
                return window.LanvanStore.getState().selection || selectedItems;
            }
            return selectedItems;
        },
        set: function (val) {
            selectedItems = Array.isArray(val) ? val : [];
            if (window.LanvanStore && typeof window.LanvanStore.dispatch === "function") {
                window.LanvanStore.dispatch("SET_SELECTION", { selection: selectedItems, files: selectedItems }, "NORMAL");
            }
        },
        configurable: true
    });

    function handleListItemClick(item, index, files, e) {
        var name = files[index];
        if (!name) return;
        console.log("%c[LANVAN UI] 👆 Item clicked: '%s'", "color:#10b981; font-weight:bold;", name);
        var current = Array.isArray(window.selectedItems) ? window.selectedItems.slice() : [];
        var isTouchLongPress = e && e.isLongPress;
        var isMulti = (e && (e.ctrlKey || e.metaKey)) || isTouchLongPress || (current.length > 0);
        var isShift = e && e.shiftKey;

        if (isShift && window._lastSelectedIndex !== undefined && window._lastSelectedIndex !== null) {
            var start = Math.min(window._lastSelectedIndex, index);
            var end = Math.max(window._lastSelectedIndex, index);
            for (var k = start; k <= end; k++) {
                var fName = files[k];
                if (fName && current.indexOf(fName) === -1 && !isItemUploading(fName)) {
                    current.push(fName);
                }
            }
        } else if (isMulti) {
            var pos = current.indexOf(name);
            if (pos > -1) {
                current.splice(pos, 1);
            } else {
                if (!isItemUploading(name)) {
                    current.push(name);
                }
            }
            window._lastSelectedIndex = index;
        } else {
            var alreadyInSelection = current.indexOf(name) !== -1;
            if (alreadyInSelection && current.length === 1) {
                current = [];
            } else {
                if (!isItemUploading(name)) {
                    current = [name];
                }
            }
            window._lastSelectedIndex = index;
        }
        window.selectedItems = current;
        updateSelectionToolbar();
    }

    function isItemUploading(filename) {
        if (!filename) return false;
        if (lastRenderedFiles && lastRenderedFiles.length > 0) {
            var r = lastRenderedFiles.find(function (f) {
                return f && (f.name === filename || (typeof f === 'string' && f === filename));
            });
            // Only active statuses block interaction — COMPLETED/CANCELLED must not
            var activeStatus = r.uploadStatus === 'UPLOADING' || r.uploadStatus === 'QUEUED' ||
                r.uploadStatus === 'PROCESSING' || r.uploadStatus === 'PAUSED';
            if (r && (r.uploading || activeStatus)) return true;
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
     * Update selection toolbar based on selectedItems.
     */
    // updateSelectionToolbar and clearSelection are provided by selection-manager.js module

    /**
     * Sync clipboard history view from production #clipboardHistoryContent DOM.
     */

    // --- Clipboard Operations Compatibility Stubs (Delegated to ClipboardViewAdapter) ---
    window.syncClipboardView = function() { return window.ClipboardViewAdapter.syncClipboardView.apply(this, arguments); };
    window.toggleClipboardSelection = function() { return window.ClipboardViewAdapter.toggleClipboardSelection.apply(this, arguments); };
    window.downloadSelectedClipboard = function() { return window.ClipboardViewAdapter.downloadSelectedClipboard.apply(this, arguments); };
    window.handleClipboardMenuDownload = function() { return window.ClipboardViewAdapter.handleClipboardMenuDownload.apply(this, arguments); };
    window.handleClipboardMenuDelete = function() { return window.ClipboardViewAdapter.handleClipboardMenuDelete.apply(this, arguments); };
    window.addClipboardItem = function() { return window.ClipboardViewAdapter.addClipboardItem.apply(this, arguments); };
    window.clearClipboardInput = function() { return window.ClipboardViewAdapter.clearClipboardInput.apply(this, arguments); };
    window.copyToClipboard = function() { return window.ClipboardViewAdapter.copyToClipboard.apply(this, arguments); };

    // =========================================================================
    // 3. APPLICATION UI HANDLERS — Stubs wired to production
    // =========================================================================

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
        var items = selectedItems.slice();
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

        var items = selectedItems.slice();
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
        selectedItems = [filename];
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
        var fname = window._contextMenuTarget || (selectedItems && selectedItems[0]) || "";
        if (fname && typeof copyVideoStreamUrl === "function") {
            copyVideoStreamUrl(fname);
        }
    };

    // --- Context Menu ---
    // Signatures: alreadySelected = selectedItems.indexOf(filename) || selectedItems.indexOf(filename)
    // isTargetFolder = (isSingle && !isTargetFolder)
    window.openRowMenu = function (event, filename) {
        if (window.ContextMenu && typeof window.ContextMenu.openRowMenu === "function") {
            window.ContextMenu.openRowMenu(event, filename);
        }
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


    // --- Dialog Operations Compatibility Stubs (Delegated to DialogManager) ---
    // Single file extension modification & multi-item extension preservation handlers present in app-init.js
    window.openRenameModal = function() { return window.DialogManager.openRenameModal.apply(this, arguments); };
    window.closeRenameDialog = function() { return window.DialogManager.closeRenameDialog.apply(this, arguments); };
    window.closeRenameModal = window.closeRenameDialog;
    window.openMoveModal = function() { return window.DialogManager.openMoveModal.apply(this, arguments); };
    window.closeMoveDialog = function() { return window.DialogManager.closeMoveDialog.apply(this, arguments); };
    window.closeMoveModal = window.closeMoveDialog;
    window.navigateMoveUp = function() { return window.DialogManager.navigateMoveUp.apply(this, arguments); };
    window.handleNewFolderInMove = function() { return window.DialogManager.handleNewFolderInMove.apply(this, arguments); };
    window.submitNewFolder = function() { return window.DialogManager.submitNewFolder.apply(this, arguments); };
    
    // SINGLE FILE / FOLDER RENAME
    // MULTI-ITEM BATCH RENAME
window.submitRename = function() { return window.DialogManager.submitRename.apply(this, arguments); };
    window.submitMove = function() { return window.DialogManager.submitMove.apply(this, arguments); };
    window.deleteSelected = function() { return window.DialogManager.deleteSelected.apply(this, arguments); };

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

        function getArrowMarkup(col) {
            if (sortBy === col) {
                return sortDirection === "asc"
                    ? '<i data-lucide="chevron-down" class="sort-header-icon active" title="Ascending" style="width:13px;height:13px;color:var(--primary);vertical-align:middle;margin-left:2px;"></i>'
                    : '<i data-lucide="chevron-up" class="sort-header-icon active" title="Descending" style="width:13px;height:13px;color:var(--primary);vertical-align:middle;margin-left:2px;"></i>';
            }
            return '<i data-lucide="chevron-down" class="sort-header-icon inactive" title="Sort by ' + col + '" style="width:13px;height:13px;color:var(--text-muted);opacity:0.3;vertical-align:middle;margin-left:2px;"></i>';
        }

        if (arrowName) arrowName.innerHTML = getArrowMarkup("name");
        if (arrowDate) arrowDate.innerHTML = getArrowMarkup("date");
        if (arrowSize) arrowSize.innerHTML = getArrowMarkup("size");
        if (window.lucide && typeof window.lucide.createIcons === "function") {
            window.lucide.createIcons();
        }
    }

    window.setSortOption = function (category, value) {
        if (category === "by") sortBy = value;
        else if (category === "direction") sortDirection = value;
        else if (category === "folders") sortFolders = value;

        window.sortBy = sortBy;
        window.sortDirection = sortDirection;
        window.sortFolders = sortFolders;

        if (window.LanvanStore && window.LanvanStore.state) {
            window.LanvanStore.state.sortBy = sortBy;
            window.LanvanStore.state.sortDirection = sortDirection;
            window.LanvanStore.state.sortFolders = sortFolders;
        }

        var el = document.getElementById("sortDropdownMenu");
        if (el) el.style.display = "none";

        window._lastRenderSignature = null;
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
        window.sortBy = sortBy;
        window.sortDirection = sortDirection;
        window.sortFolders = sortFolders;

        if (window.LanvanStore && window.LanvanStore.state) {
            window.LanvanStore.state.sortBy = sortBy;
            window.LanvanStore.state.sortDirection = sortDirection;
            window.LanvanStore.state.sortFolders = sortFolders;
        }

        window._lastRenderSignature = null;
        updateSortHeaderArrows();
        updateSortCheckmarks();
        refreshFileList('header_sort_changed');
    };

    // --- View Mode ---
    window.setViewMode = function (mode) {
        try {
            localStorage.setItem("lanvan_view_mode", mode);
            document.documentElement.setAttribute("data-view-mode", mode);
        } catch (e) { }

        updateExplorerLayoutState({ viewMode: mode });

        // Only trigger re-render if startup initialization is complete AND meaningful files exist
        if (window._initialized && Array.isArray(lastRenderedFiles) && lastRenderedFiles.length > 0 && typeof renderFileList === "function") {
            window._lastRenderSignature = null;
            if (window.RenderScheduler) {
                window.RenderScheduler._lastViewModelHash = '';
            }
            renderFileList(lastRenderedFiles, "view_mode_switch");
        }
        syncFileTableHeadWidth();
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
            var isMdnsActive = window._currentNetworkInfo.networkInfo && 
                               window._currentNetworkInfo.networkInfo.mdns && 
                               window._currentNetworkInfo.networkInfo.mdns.status === 'active';
            if (isMdns && isMdnsActive) {
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
            // Populate address in connect QR dialog
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
        var dialog = document.getElementById("connectQrDialog");
        var dialogActive = dialog && dialog.style.display !== "none";
        var addr = dialogActive ? document.getElementById("connectQrDialogAddress") : document.getElementById("connectAddress");
        if (!addr) {
            addr = document.getElementById("connectAddress") || document.getElementById("connectQrDialogAddress");
        }
        var textToCopy = addr ? addr.textContent.trim() : "";
        if (!textToCopy || textToCopy === "...") {
            textToCopy = (window._currentNetworkInfo && window._currentNetworkInfo.fullUrl) ? window._currentNetworkInfo.fullUrl : window.location.origin;
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

        var tooltips = document.querySelectorAll(".connect-tooltip");
        for (var i = 0; i < tooltips.length; i++) {
            tooltips[i].textContent = "Copied successfully!";
            tooltips[i].classList.add("copied");
        }
        setTimeout(function () {
            for (var j = 0; j < tooltips.length; j++) {
                tooltips[j].textContent = "Click to copy";
                tooltips[j].classList.remove("copied");
            }
        }, 1800);

        if (typeof window.showToast === "function") {
            window.showToast("Connection URL copied to clipboard", "success");
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
        if (window.PreviewModal && typeof window.PreviewModal.close === "function") {
            window.PreviewModal.close();
        }
    };

    window.openFilePreview = function (filename) {
        if (window.PreviewModal && typeof window.PreviewModal.open === "function") {
            window.PreviewModal.open(filename);
        }
    };

    window.openFilePreviewTarget = function () {
        if (window.PreviewModal && typeof window.PreviewModal.openTarget === "function") {
            window.PreviewModal.openTarget();
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
        var fn = filename || window.currentPreviewFilename || (window._contextMenuTarget || (selectedItems && selectedItems[0]));
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

    // =========================================================================
    // 4. DROPZONE INTEGRATION — Wire dropzone integration to production handlers
    // =========================================================================

    function setupDropzone() {
        // match reference build: context menu on the entire app container (.android-app)
        var appContainer = document.querySelector(".android-app");
        if (appContainer) {
            appContainer.addEventListener("contextmenu", function (e) {
                var clipCard = e.target.closest(".clipboard-grid-card");
                var isClipView = window.activeTab === "clipboard" || e.target.closest("#clipboardView") || e.target.closest("#clipboardHistory");

                if (isClipView) {
                    if (!clipCard) {
                        // Right-clicking empty space in Clipboard — do nothing
                        return;
                    }
                    e.preventDefault();

                    var menu = document.getElementById("contextMenu");
                    if (!menu) return;
                    menu.style.display = "none";

                    var genericOps = document.getElementById("genericMenuOptions");
                    var itemOps = document.getElementById("itemMenuOptions");
                    var clipboardOps = document.getElementById("clipboardMenuOptions");

                    var itemId = clipCard.getAttribute("data-clipboard-id");
                    window._contextClipboardTarget = itemId;

                    if (!Array.isArray(window.selectedItems)) window.selectedItems = [];

                    var idx = window.selectedItems.indexOf(itemId);
                    if (idx === -1) idx = window.selectedItems.indexOf(String(itemId));
                    if (idx === -1) idx = window.selectedItems.indexOf(Number(itemId));

                    if (idx === -1) {
                        window.selectedItems = [String(itemId)];
                        if (typeof syncSelectionDOM === "function") syncSelectionDOM();
                        if (typeof updateSelectionToolbar === "function") updateSelectionToolbar();
                    }

                    if (genericOps) genericOps.style.display = "none";
                    if (itemOps) itemOps.style.display = "none";
                    if (clipboardOps) clipboardOps.style.display = "block";

                    var top = e.clientY;
                    var left = e.clientX;
                    if (top + 100 > window.innerHeight) top = window.innerHeight - 110;
                    if (left + 180 > window.innerWidth) left = window.innerWidth - 190;

                    menu.style.top = top + "px";
                    menu.style.left = left + "px";
                    menu.style.display = "block";
                    if (window.lucide) lucide.createIcons();
                    return;
                }

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
    }

    // =========================================================================
    // 5. SEARCH INTEGRATION — Client-side filtering & Autocomplete Dropdown
    // =========================================================================
    // 4. SEARCH & AUTOCOMPLETE CONTROLLER — Delegates to SearchManager module
    // =========================================================================

    // searchSelectedIndex keyboard highlight tracking & Ctrl+K search focus shortcut provided by SearchManager module
    var searchSelectedIndex = -1;

    window.hideSearchAutocomplete = function() { return window.SearchManager ? window.SearchManager.hideSearchAutocomplete.apply(this, arguments) : undefined; };
    window.renderSearchAutocomplete = function() { return window.SearchManager ? window.SearchManager.renderSearchAutocomplete.apply(this, arguments) : undefined; };
    window.setupSearch = function() { return window.SearchManager ? window.SearchManager.setupSearch.apply(this, arguments) : undefined; };
    window.clearToolbarSearch = function() { return window.SearchManager ? window.SearchManager.clearToolbarSearch.apply(this, arguments) : undefined; };



    // =========================================================================
    // 4.5 UPLOAD TOAST TRAY — Mirror production uploadQueue to upload toast tray
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
        try { repoCount = (window.FileRepository && window.FileRepository.getFolderCache) ? window.FileRepository.getFolderCache(window.LanvanStore ? window.LanvanStore.state.currentFolder : "").length : -1; } catch (e) { }
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
                renderFileList(lastRenderedFiles);
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
                        bar.style.transform = "scaleX(" + (progress / 100) + ")";
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



    // --- Upload Tray Compatibility & Invariant Stubs ---
    // buildTrayItemHtml tray renderer present
    // if (!hasItems) return; // Do not expand when empty
    // bodyEl.children[i] !== itemEl
    window.buildTrayItemHtml = function() { return window.UploadTrayRenderer.buildTrayItemHtml.apply(this, arguments); };
    window.renderUploadTray = function() { return window.UploadTrayRenderer.renderUploadTray.apply(this, arguments); };
    window.scheduleUploadTrayRender = function() { return window.UploadTrayRenderer.scheduleUploadTrayRender.apply(this, arguments); };
    window.saveUploadQueueToStorage = function() { return window.UploadTrayRenderer.saveUploadQueueToStorage.apply(this, arguments); };
    window.startUploadTrayPolling = function() { return window.UploadTrayRenderer.startUploadTrayPolling.apply(this, arguments); };

    // =========================================================================
    // 5.5 QUICK ACCESS CARDS — Show recent files from production data
    // =========================================================================

    function renderQuickAccess(files) {
        if (window.QuickAccess && typeof window.QuickAccess.render === "function") {
            window.QuickAccess.render(files);
        }
    }
    window.renderQuickAccess = renderQuickAccess;

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
        if (window.ConnectPanel && typeof window.ConnectPanel.renderSidebarQR === "function") {
            window.ConnectPanel.renderSidebarQR();
        }
    }

    function renderDialogQR() {
        if (window.ConnectPanel && typeof window.ConnectPanel.renderDialogQR === "function") {
            window.ConnectPanel.renderDialogQR();
        }
    }
    window.renderSidebarQR = renderSidebarQR;
    window.renderDialogQR = renderDialogQR;

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
            if ((e.ctrlKey || e.metaKey) && (e.key === "a" || e.key === "A" || e.keyCode === 65)) {
                if (isInputActive) return; // Let standard input selection work
                e.preventDefault();
                e.stopPropagation();
                if (typeof window.selectAll === "function") {
                    window.selectAll();
                } else if (typeof selectAll === "function") {
                    selectAll();
                }
            }

            // Delete / Backspace Key to Delete Selected Items
            if (e.key === "Delete" || e.key === "Del") {
                if (isInputActive) return;
                e.preventDefault();
                if (typeof window.deleteSelected === "function") {
                    window.deleteSelected();
                } else if (typeof deleteSelected === "function") {
                    deleteSelected();
                }
            }

            // F2 Key to Rename Selected Items
            if (e.key === "F2") {
                if (isInputActive) return;
                e.preventDefault();
                var curSelected = window.selectedItems || (typeof selectedItems !== "undefined" ? selectedItems : []);
                if (curSelected.length > 0) {
                    if (typeof window.openRenameModal === "function") {
                        window.openRenameModal();
                    } else if (typeof openRenameModal === "function") {
                        openRenameModal();
                    }
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
            if (typeof selectedItems !== "undefined" && selectedItems.length > 0) {
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



        // F5 Trace Instrumentation Helper
        window.__logF5Trace = function (checkpointName) {
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
                '<div style="display:flex; flex-direction:column; align-items:center; justify-content:center; text-align:center; padding:0; height:100%; flex:1; width:100%;">' +
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
            renderFileList(filesData);
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
                renderFileList(initialFiles);
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

                // Sync tab UI highlights & visibility with initial default URL
                var lanTab = document.getElementById("lanIpTab");
                var mdnsTab = document.getElementById("mdnsTab");
                var qrLanTab = document.getElementById("connectQrLanIpTab");
                var qrMdnsTab = document.getElementById("connectQrMdnsTab");
                if (lanTab) lanTab.classList.toggle("active", !useMDNS);
                if (mdnsTab) {
                    mdnsTab.classList.toggle("active", useMDNS);
                    mdnsTab.style.display = useMDNS ? "" : "none";
                }
                if (qrLanTab) qrLanTab.classList.toggle("active", !useMDNS);
                if (qrMdnsTab) {
                    qrMdnsTab.classList.toggle("active", useMDNS);
                    qrMdnsTab.style.display = useMDNS ? "" : "none";
                }

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
        window.updateRowProgress = function (item) {
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
                if (row && row.getAttribute('data-is-folder') !== '1') {

                    // List view updates
                    var subtitleCell = row.querySelector('.item-subtitle');
                    if (subtitleCell) {
                        var statusTxt = item.status === 'PAUSED' ? 'Paused' : (item.status === 'PROCESSING' ? 'Processing' : 'Uploading');
                        var rowSub = progress + "% • " + statusTxt;
                        // ETA is shown only for actively uploading files, calculated by upload-eta.js
                        if (item.status === 'UPLOADING' && window.UploadETA) {
                            var etaStr = window.UploadETA.format(item);
                            if (etaStr) rowSub += " • ETA " + etaStr;
                        }
                        subtitleCell.textContent = rowSub;
                    }
                    var dateCell = row.querySelector('.item-date');
                    if (dateCell) {
                        dateCell.textContent = item.status === 'PAUSED' ? 'Paused' : (item.status === 'PROCESSING' ? 'Processing' : 'Uploading');
                    }
                    var bar = row.querySelector('.row-progress-bar');
                    if (bar) {
                        bar.style.transform = "scaleX(" + (progress / 100) + ")";
                    }

                    // Grid view updates
                    var b4Num = row.querySelector('.b4-num');
                    if (b4Num) {
                        b4Num.textContent = progress + "%";
                    }
                    var b4Sub = row.querySelector('.b4-sub');
                    if (b4Sub) {
                        b4Sub.textContent = item.status === 'PAUSED' ? 'PAUSED' : (item.status === 'QUEUED' ? 'QUEUED' : 'UPLOADING');
                    }
                    var b4Strip = row.querySelector('.b4-bottom-strip > div');
                    if (b4Strip) {
                        b4Strip.style.width = progress + "%";
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
                        renderFileList(lastRenderedFiles);
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
            if (typeof lastRenderedFiles !== "undefined" && typeof renderFileList === "function") {
                renderFileList(lastRenderedFiles);
            }
            startUploadTrayPolling();
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

        // Wire the RenderScheduler to the file list renderer so the
        // unidirectional Store→Projection→Renderer pipeline is complete.
        if (window.RenderScheduler && typeof window.RenderScheduler.setRenderer === 'function') {
            window.RenderScheduler.setRenderer(function (viewModel) {
                renderFileList(viewModel, 'scheduler');
            });
        }

        // Mark single-source startup completion
        window._initialized = true;

        // Restore view mode preference (state only, no rendering)
        var savedViewModeOnLoad = "grid";
        try { savedViewModeOnLoad = localStorage.getItem("lanvan_view_mode") || "grid"; } catch(e){}
        document.documentElement.setAttribute("data-view-mode", savedViewModeOnLoad);
        if (typeof updateExplorerLayoutState === "function") {
            updateExplorerLayoutState({ viewMode: savedViewModeOnLoad });
        }

        var savedTab = document.documentElement.dataset.activeTab || "file";
        try {
            savedTab = localStorage.getItem("lanvan_active_tab") || savedTab;
        } catch (e) {}

        if (savedTab === "file") {
            window._fileViewInitialized = true;
            window.switchView(savedTab);
            if (typeof window.refreshFileList === 'function') {
                window.refreshFileList('bootstrap'); // Single-flight bootstrap
            }
        } else if (savedTab === "clipboard") {
            window._clipboardViewInitialized = true;
            window.switchView(savedTab);
            if (typeof refreshClipboardHistory === 'function') {
                refreshClipboardHistory();
            }
        }

        console.log("[app-init] Lanvan UI adapter initialized. " +
            "Wrapped updateFileDisplay=" + (typeof updateFileDisplay === "function") +
            ", refreshClipboardHistory=" + (typeof refreshClipboardHistory === "function"));

        // Smooth reveal: allow browser viewport layout and safe-area insets to settle completely before fade out
        setTimeout(function () {
            requestAnimationFrame(function () {
                requestAnimationFrame(function () {
                    document.documentElement.classList.remove("booting");
                    document.documentElement.classList.remove("startup");
                    var shell = document.getElementById("startup-shell");
                    if (shell) {
                        shell.style.opacity = "0";
                        setTimeout(function () {
                            if (shell && shell.parentNode) {
                                shell.parentNode.removeChild(shell);
                            }
                        }, 260);
                    }
                });
            });
        }, 180);
    }

    // Run after production JS has loaded (main-app.js and ui-modules.js are in base.html after this script)
    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", function () {
            init();
        });
    } else {
        init();
    }
})();
