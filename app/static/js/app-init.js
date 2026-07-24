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
            fetchFilesData().then(function (fd) {
                renderPrototypeFileList(fd);
            });
        };
        updateFileDisplay.__prototypeWrapped = true;
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

    var currentFolderPath = "Home";
    Object.defineProperty(window, 'currentFolderPath', {
        get: function () { return currentFolderPath; },
        set: function (val) { currentFolderPath = val; },
        configurable: true
    });

    window.getCurrentFolderPath = function () {
        var p = currentFolderPath || "";
        return (p === "Home" || p === "Home/") ? "" : p;
    };

    // Intercept network requests to automatically append parent_path to upload FormData
    // and log detailed error info to the console if requests fail.
    (function () {
        const _originalOpen = XMLHttpRequest.prototype.open;
        XMLHttpRequest.prototype.open = function (method, url) {
            this._url = url;
            return _originalOpen.apply(this, arguments);
        };

        const _originalSend = XMLHttpRequest.prototype.send;
        XMLHttpRequest.prototype.send = function (body) {
            if (body instanceof FormData) {
                if (window.currentFolderPath && window.currentFolderPath !== "Home") {
                    var parentPath = window.currentFolderPath;
                    if (parentPath.indexOf("Home/") === 0) {
                        parentPath = parentPath.substring(5);
                    } else if (parentPath === "Home") {
                        parentPath = "";
                    }
                    if (parentPath && !body.has("parent_path")) {
                        body.append("parent_path", parentPath);
                    }
                }
            }

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
            if (options && options.body instanceof FormData) {
                if (window.currentFolderPath && window.currentFolderPath !== "Home") {
                    var parentPath = window.currentFolderPath;
                    if (parentPath.indexOf("Home/") === 0) {
                        parentPath = parentPath.substring(5);
                    } else if (parentPath === "Home") {
                        parentPath = "";
                    }
                    if (parentPath && !options.body.has("parent_path")) {
                        options.body.append("parent_path", parentPath);
                    }
                }
            }
            return _originalFetch.apply(this, arguments)
                .then(function (response) {
                    if (!response.ok) {
                        console.error("[Network Error] Fetch failed with status " + response.status + " for URL: " + url);
                    }
                    return response;
                })
                .catch(function (error) {
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

    // Star state persisted in localStorage
    var starredItems = JSON.parse(localStorage.getItem("starred_items") || "[]");
    function isStarred(name) { return starredItems.indexOf(name) !== -1; }
    function toggleStar(name, btnEl) {
        var idx = starredItems.indexOf(name);
        if (idx !== -1) { starredItems.splice(idx, 1); }
        else { starredItems.push(name); }
        localStorage.setItem("starred_items", JSON.stringify(starredItems));
        if (btnEl) {
            var icon = btnEl.querySelector("i[data-lucide='star']");
            if (icon) {
                icon.style.fill = isStarred(name) ? "var(--yellow, #f59e0b)" : "none";
                icon.style.color = isStarred(name) ? "var(--yellow, #f59e0b)" : "";
            }
        }
    }

    function renderBreadcrumbs() {
        var container = document.getElementById("breadcrumbsContainer");
        if (!container) return;
        container.innerHTML = "";

        // Always start from "Home", then show current subfolder path parts
        // currentFolderPath: "Home" | "FolderA" | "FolderA/SubFolder"
        var fullParts = ["Home"];
        if (currentFolderPath && currentFolderPath !== "Home" && currentFolderPath !== "") {
            // currentFolderPath is stored without "Home/" prefix
            var subParts = currentFolderPath.split("/");
            fullParts = fullParts.concat(subParts);
        }

        for (var i = 0; i < fullParts.length; i++) {
            if (i > 0) {
                var sep = document.createElement("span");
                sep.className = "breadcrumb-separator";
                sep.innerHTML = '<i data-lucide="chevron-right" style="width:16px;height:16px;"></i>';
                container.appendChild(sep);
            }
            var bItem = document.createElement("span");
            bItem.className = "breadcrumb-item";
            bItem.textContent = fullParts[i];
            if (i < fullParts.length - 1) {
                // Clickable — navigate to that level
                (function (idx) {
                    bItem.onclick = function () {
                        if (idx === 0) {
                            // Go back to root
                            currentFolderPath = "Home";
                        } else {
                            // Navigate to the subfolder path (strip "Home" prefix)
                            currentFolderPath = fullParts.slice(1, idx + 1).join("/");
                        }
                        prototypeSelectedItems = [];
                        updateSelectionToolbar();
                        renderBreadcrumbs();
                        fetchFilesData().then(function (filesData) {
                            renderPrototypeFileList(filesData);
                        });
                    };
                })(i);
                bItem.style.cursor = "pointer";
            }
            container.appendChild(bItem);
        }

        // Update panel title icon
        var panelIcon = document.getElementById("desktopPanelTitleIcon");
        if (panelIcon) {
            panelIcon.setAttribute("data-lucide", "folder");
        }
        if (window.lucide) lucide.createIcons();
    }

    /**
     * Render files in prototype #nasFileList from the same data production uses.
     * @param {string[]} files - Array of filenames from production API
     */
    var lastFilesData = [];
    var lastRenderedFiles = [];
    window.activeTab = "file";

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

    function renderPrototypeFileList(files) {
        lastRenderedFiles = files;
        var container = document.getElementById("nasFileList");
        var filePanelMeta = document.getElementById("filePanelMeta");
        if (!container) return;

        // Hide Recents (Quick Access) if inside a subfolder
        var quickContainer = document.getElementById("quickAccessContainer");
        if (quickContainer) {
            if (currentFolderPath && currentFolderPath !== "Home" && currentFolderPath !== "") {
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
                if (typeof item === "string") {
                    var meta = lastFilesData.find(function (f) { return f && f.name === item; });
                    normalizedFiles.push({
                        name: item,
                        size: meta ? meta.size : "--",
                        mtime: meta ? meta.mtime : 0,
                        isFolder: meta ? !!meta.isFolder : false
                    });
                } else if (item.name) {
                    normalizedFiles.push({
                        name: item.name,
                        size: item.size || "--",
                        mtime: item.mtime || 0,
                        isFolder: !!item.isFolder
                    });
                }
            }
        }

        // Retrieve active uploads from global window.uploadQueue for the current folder
        var activeUploads = [];
        var normCurrentDir = (currentFolderPath === "Home" || currentFolderPath === "Home/" || !currentFolderPath) ? "" : currentFolderPath;

        if (window.uploadQueue && window.uploadQueue.length > 0) {
            window.uploadQueue.forEach(function (item) {
                if (item && item.fileName && (item.status === 'queued' || item.status === 'uploading' || item.status === 'processing' || item.status === 'paused')) {
                    var itemDir = item.targetDir || item.parent_path || item.folder || "";
                    if (itemDir === "Home" || itemDir === "Home/") itemDir = "";

                    // Only display active upload row if it belongs to the folder currently being viewed
                    if (itemDir === normCurrentDir) {
                        // Check if the file is already in normalizedFiles (e.g. overwriting)
                        var existingItem = normalizedFiles.find(function (f) { return f && f.name === item.fileName; });
                        if (existingItem) {
                            existingItem.uploading = true;
                            existingItem.uploadProgress = Math.round(item.progress || 0);
                            existingItem.uploadStatus = item.status;
                            existingItem.uploadId = item.id;
                        } else {
                            activeUploads.push({
                                name: item.fileName,
                                size: formatSize(item.fileSize),
                                mtime: Math.floor(Date.now() / 1000),
                                isFolder: false,
                                uploading: true,
                                uploadProgress: Math.round(item.progress || 0),
                                uploadStatus: item.status,
                                uploadId: item.id
                            });
                        }
                    }
                }
            });
        }

        // Merge active uploads
        normalizedFiles = activeUploads.concat(normalizedFiles);

        var originalFilesForQuickAccess = normalizedFiles.slice();

        // Apply client-side Type Filtering
        if (typeFilter !== "all") {
            normalizedFiles = normalizedFiles.filter(function (f) {
                return getFileItemType(f) === typeFilter;
            });
        }

        // Apply Tab-level Filtering (Recent vs Starred)
        var tab = window.activeTab || "file";
        if (tab === "recent") {
            // Show only files (excluding folders) for Recents
            normalizedFiles = normalizedFiles.filter(function (f) {
                return !f.isFolder;
            });
        } else if (tab === "starred") {
            // Show only starred files/folders
            normalizedFiles = normalizedFiles.filter(function (f) {
                return isStarred(f.name);
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

        // Sync dropdown checkmarks and header arrows
        updateSortCheckmarks();
        updateSortHeaderArrows();

        // Update file count in prototype panel meta
        if (filePanelMeta) {
            filePanelMeta.textContent = normalizedFiles.length
                ? normalizedFiles.length + " file" + (normalizedFiles.length === 1 ? "" : "s")
                : "";
        }

        if (!normalizedFiles || normalizedFiles.length === 0) {
            // Render quick access cards (empty when normalizedFiles is 0)
            renderQuickAccess(originalFilesForQuickAccess
                .filter(function (f) { return !f.isFolder && !f.uploading; })
                .map(function (f) { return f.name; }));

            // Check if uploads are active — show different message
            var queue = window.uploadQueue || [];
            var activeUploadsCount = queue.filter(function (item) {
                return item.status === "uploading" || item.status === "queued" || item.status === "processing";
            }).length;
            if (activeUploadsCount > 0) {
                container.innerHTML =
                    '<div style="display:flex; flex-direction:column; align-items:center; justify-content:center; text-align:center; padding:3rem 0; width:100%;">' +
                    '<div class="avatar-icon avatar-folder" style="width:72px;height:72px;border-radius:18px;margin-bottom:1rem;">' +
                    '<i data-lucide="upload-cloud" style="width:34px;height:34px;"></i></div>' +
                    '<div style="font-size:1.05rem; font-weight:500; color:var(--text-color); margin-bottom:0.25rem;">Uploading ' + activeUploadsCount + ' file' + (activeUploadsCount === 1 ? '' : 's') + '...</div>' +
                    '<div style="font-size:0.8rem; color:var(--text-muted);">Files will appear here when upload completes.</div>' +
                    "</div>";
            } else {
                container.innerHTML =
                    '<div style="display:flex; flex-direction:column; align-items:center; justify-content:center; text-align:center; padding:3rem 0; width:100%;">' +
                    '<div class="avatar-icon avatar-folder" style="width:72px;height:72px;border-radius:18px;margin-bottom:1rem;">' +
                    '<i data-lucide="folder-open" style="width:34px;height:34px;"></i></div>' +
                    '<div style="font-size:1.05rem; font-weight:500; color:var(--text-color); margin-bottom:0.25rem;">Drop files here</div>' +
                    '<div style="font-size:0.8rem; color:var(--text-muted);">or right-click to upload / create folders.</div>' +
                    "</div>";
            }
            refreshLucideIcons(container);
            return;
        }

        var html = "";
        for (var i = 0; i < normalizedFiles.length; i++) {
            var fileData = normalizedFiles[i];
            var name = fileData.name;
            var ext = name.split(".").pop().toLowerCase();
            var info = fileData.isFolder
                ? { avatarClass: "avatar-folder", iconName: "folder" }
                : getFileTypeInfo(name, ext);
            var size = fileData.size || "--";
            var dateStr = "--";
            var subtitle = fileData.isFolder ? "Folder" : "File";
            if (fileData.mtime) {
                var d = new Date(fileData.mtime * 1000);
                dateStr = d.toLocaleDateString(undefined, { month: "short", day: "numeric" });
            }
            html += buildListItem(
                name,
                info,
                size,
                dateStr,
                subtitle,
                !!fileData.isFolder,
                !!fileData.uploading,
                fileData.uploadProgress || 0,
                fileData.uploadId,
                fileData.uploadStatus
            );
        }
        container.innerHTML = html;

        // Attach click handlers — pass full normalized data for folder detection
        attachListItemHandlers(container, normalizedFiles.map(function (f) { return f.name; }), normalizedFiles);

        // Also render quick access cards (only non-folders)
        renderQuickAccess(originalFilesForQuickAccess
            .filter(function (f) { return !f.isFolder && !f.uploading; })
            .map(function (f) { return f.name; }));

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

    /**
     * Build a single prototype-styled list item HTML.
     * @param {string} name - File/folder name
     * @param {object} info - {avatarClass, iconName}
     * @param {string} size - Formatted size string
     * @param {string} date - Formatted date string
     * @param {string} subtitle - "File" or "Folder"
     * @param {boolean} isFolder - Whether item is a folder
     */
    function buildListItem(name, info, size, date, subtitle, isFolder, isUploading, uploadProgress, uploadId, uploadStatus) {
        var escName = escapeHtml(name);
        var sizeStr = size || "--";
        var dateStr = date || "--";
        var subtitleText = subtitle || (isFolder ? "Folder" : "File");
        if (isUploading) {
            subtitleText = uploadProgress + "% • " + (uploadStatus === 'paused' ? 'Paused' : 'Uploading');
        }
        var starred = isStarred(name);
        var starFill = starred ? "var(--yellow, #f59e0b)" : "none";
        var starColor = starred ? "var(--yellow, #f59e0b)" : "";

        var displaySize = isFolder ? "-" : sizeStr;
        var progressBarHtml = isUploading
            ? '<div class="row-progress-bar" style="position:absolute; top:0; bottom:0; left:0; background:rgba(59, 130, 246, 0.08); width:' + uploadProgress + '%; transition:width 0.25s ease-out; pointer-events:none; z-index:1;"></div>'
            : '';

        var actionsHtml = '';
        if (isUploading) {
            var playPauseBtn = '';
            if (uploadStatus === 'paused') {
                playPauseBtn = '<button class="btn-icon" title="Resume upload" data-action="resume-upload" data-upload-id="' + uploadId + '">' +
                    '<i data-lucide="play" style="width:16px;height:16px;"></i>' +
                    '</button>';
            } else {
                playPauseBtn = '<button class="btn-icon" title="Pause upload" data-action="pause-upload" data-upload-id="' + uploadId + '">' +
                    '<i data-lucide="pause" style="width:16px;height:16px;"></i>' +
                    '</button>';
            }
            actionsHtml = playPauseBtn +
                '<button class="btn-icon" title="Cancel upload" data-action="cancel-upload" data-upload-id="' + uploadId + '">' +
                '<i data-lucide="x" style="width:16px;height:16px;"></i>' +
                '</button>';
        } else {
            actionsHtml =
                '<button class="btn-icon hover-btn" title="Download" data-action="download" data-filename="' + escName + '" data-is-folder="' + (isFolder ? '1' : '0') + '">' +
                '<i data-lucide="download" style="width:16px;height:16px;"></i>' +
                '</button>' +
                (isFolder ? '' :
                    '<button class="btn-icon hover-btn" title="Rename" data-action="rename" data-filename="' + escName + '">' +
                    '<i data-lucide="edit-2" style="width:16px;height:16px;"></i>' +
                    '</button>' +
                    '<button class="btn-icon hover-btn" title="Star" data-action="star" data-filename="' + escName + '" style="color:' + starColor + ';">' +
                    '<i data-lucide="star" style="width:16px;height:16px;fill:' + starFill + ';"></i>' +
                    '</button>'
                ) +
                '<button class="btn-icon" title="More actions" data-action="menu" data-filename="' + escName + '">' +
                '<i data-lucide="more-vertical" style="width:16px;height:16px;"></i>' +
                '</button>';
        }

        var displayDate = isUploading ? (uploadStatus === 'paused' ? 'Paused' : 'Uploading') : dateStr;

        return (
            '<div class="m3-list-item' + (isUploading ? ' uploading' : '') + '" data-filename="' + escName + '" data-is-folder="' + (isFolder ? '1' : '0') + '" style="' + (isUploading ? 'position:relative; overflow:hidden;' : '') + '">' +
            progressBarHtml +
            '<div class="file-name-cell" style="position:relative; z-index:2;">' +
            '<div class="avatar-icon ' + info.avatarClass + '"><i data-lucide="' + info.iconName + '"></i></div>' +
            '<div class="item-main">' +
            '<div class="item-title">' + escName + '</div>' +
            '<div class="item-subtitle">' + subtitleText + '</div>' +
            '</div>' +
            '</div>' +
            '<div class="item-date" style="position:relative; z-index:2;">' + displayDate + '</div>' +
            '<div class="item-size" style="position:relative; z-index:2;">' + displaySize + '</div>' +
            '<div class="row-actions" style="position:relative; z-index:2;">' +
            actionsHtml +
            '</div>' +
            '</div>'
        );
    }

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

                // Click / Tap handler
                item.addEventListener("click", function (e) {
                    if (e.target.closest("button")) return;
                    if (itemData.uploading) return; // Prevent selection/navigation if uploading

                    var isTouch = e.pointerType === "touch" || e.pointerType === "pen" || ("ontouchstart" in window && window.innerWidth < 1024);
                    if (folderFlag && isTouch) {
                        navigateIntoFolder(name);
                        return;
                    }
                    handleListItemClick(item, index, files);
                });

                // Double-click handler for desktop mouse
                item.addEventListener("dblclick", function (e) {
                    if (e.target.closest("button")) return;
                    if (itemData.uploading) return; // Prevent navigation if uploading
                    if (folderFlag) {
                        navigateIntoFolder(name);
                    }
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
                var starBtn = item.querySelector('[data-action="star"]');
                if (starBtn) {
                    starBtn.addEventListener("click", function (e) {
                        e.stopPropagation();
                        var fname = starBtn.getAttribute("data-filename");
                        toggleStar(fname, starBtn);
                    });
                }

                // Menu button
                var menuBtn = item.querySelector('[data-action="menu"]');
                if (menuBtn) {
                    menuBtn.addEventListener("click", function (e) {
                        e.stopPropagation();
                        var fname = menuBtn.getAttribute("data-filename");
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

        var base = currentFolderPath;
        if (base === "Home") base = "";

        // Guard: check if currentFolderPath already ends with this folderName
        var parts = base ? base.split("/") : [];
        if (parts.length > 0 && parts[parts.length - 1] === folderName) {
            return;
        }

        currentFolderPath = base ? (base + "/" + folderName) : folderName;
        prototypeSelectedItems = [];
        updateSelectionToolbar();
        renderBreadcrumbs();
        fetchFilesData().then(function (fd) {
            renderPrototypeFileList(fd);
        });
    }

    /**
     * Handle item click — toggle selection.
     */
    var prototypeSelectedItems = [];

    function handleListItemClick(item, index, files) {
        var name = files[index];
        var pos = prototypeSelectedItems.indexOf(name);
        if (pos > -1) {
            prototypeSelectedItems.splice(pos, 1);
            item.classList.remove("selected");
        } else {
            prototypeSelectedItems.push(name);
            item.classList.add("selected");
        }
        updateSelectionToolbar();
    }

    /**
     * Update selection toolbar based on prototypeSelectedItems.
     */
    function updateSelectionToolbar() {
        var defaultContent = document.getElementById("toolbarDefaultContent");
        var selectionContent = document.getElementById("toolbarSelectionContent");
        if (!defaultContent || !selectionContent) return;

        if (prototypeSelectedItems.length > 0) {
            defaultContent.style.display = "none";
            selectionContent.style.display = "flex";
            selectionContent.innerHTML =
                '<div style="display:flex;align-items:center;gap:0.5rem;font-size:0.85rem;font-weight:700;color:var(--primary);">' +
                '<button class="btn-icon" onclick="clearSelection()" title="Clear selection" style="width:32px;height:32px;color:var(--primary);">' +
                '<i data-lucide="x" style="width:18px;height:18px;"></i></button>' +
                "<span>" +
                prototypeSelectedItems.length +
                " selected</span></div>" +
                '<div style="display:flex;align-items:center;gap:0.25rem;">' +
                (prototypeSelectedItems.length === 1
                    ? '<button class="btn-icon" onclick="openRenameModal()" title="Rename" style="width:34px;height:34px;color:var(--primary);"><i data-lucide="pencil" style="width:16px;height:16px;"></i></button>'
                    : "") +
                '<button class="btn-icon" onclick="downloadSelected()" title="Download selected" style="width:34px;height:34px;color:var(--primary);"><i data-lucide="download" style="width:16px;height:16px;"></i></button>' +
                '<button class="btn-icon" onclick="openMoveModal()" title="Move selected" style="width:34px;height:34px;color:var(--primary);"><i data-lucide="folder-input" style="width:16px;height:16px;"></i></button>' +
                '<button class="btn-icon" onclick="deleteSelected()" title="Delete selected" style="width:34px;height:34px;color:var(--danger);"><i data-lucide="trash-2" style="width:16px;height:16px;"></i></button>' +
                "</div>";
        } else {
            defaultContent.style.display = "flex";
            selectionContent.style.display = "none";
            selectionContent.innerHTML = "";
        }
        if (window.lucide) lucide.createIcons();
    }

    /**
     * Clear all selection.
     */
    window.clearSelection = function () {
        prototypeSelectedItems = [];
        var items = document.querySelectorAll("#nasFileList .m3-list-item.selected");
        for (var i = 0; i < items.length; i++) {
            items[i].classList.remove("selected");
        }
        updateSelectionToolbar();
    };

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
        window.activeTab = tab;
        var fileView = document.getElementById("fileView");
        var clipView = document.getElementById("clipboardView");

        // Sidebar items
        var sideFile = document.getElementById("sideItemFile");
        var sideClip = document.getElementById("sideItemClipboard");
        var sideRecent = document.getElementById("sideItemRecent");
        var sideStarred = document.getElementById("sideItemStarred");

        // Bottom nav items
        var navFile = document.getElementById("navItemFile");
        var navClip = document.getElementById("navItemClipboard");
        var navRecent = document.getElementById("navItemRecent");
        var navStarred = document.getElementById("navItemStarred");

        // Clear selection when switching views
        window.clearSelection();

        // Deactivate all sidebar items
        var allSideItems = [sideFile, sideClip, sideRecent, sideStarred];
        for (var i = 0; i < allSideItems.length; i++) {
            if (allSideItems[i]) allSideItems[i].classList.remove("active");
        }

        // Deactivate all nav items
        var allNavItems = [navFile, navClip, navRecent, navStarred];
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
            // file, recent, starred — all show file view
            if (fileView) fileView.style.display = "flex";
            if (clipView) clipView.style.display = "none";

            // Highlight correct sidebar item based on tab
            if (tab === "recent" && sideRecent) {
                sideRecent.classList.add("active");
                if (navRecent) navRecent.classList.add("active");
            } else if (tab === "starred" && sideStarred) {
                sideStarred.classList.add("active");
                if (navStarred) navStarred.classList.add("active");
            } else {
                // Default: Files
                if (sideFile) sideFile.classList.add("active");
                if (navFile) navFile.classList.add("active");
            }

            // Re-render prototype list to apply correct tab filters
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
        if (items.length === 0) return;

        var index = 0;
        function downloadNext() {
            if (index >= items.length) {
                if (typeof showToast === "function") {
                    showToast("Downloaded " + items.length + " file(s).", 3000);
                }
                window.clearSelection();
                return;
            }
            downloadFileByName(items[index]);
            index++;
            if (index < items.length) {
                setTimeout(downloadNext, 300); // 300ms delay between downloads
            } else {
                downloadNext(); // Last one — no delay needed
            }
        }
        downloadNext();
    };

    window.deleteSelected = function () {
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
                fetchFilesData().then(function (fd) { renderPrototypeFileList(fd); });
                return;
            }

            var filename = itemsToDelete[index];

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
            if (!isFolder && Array.isArray(lastFilesData)) {
                var foundData = lastFilesData.find(function (f) { return f && f.name === filename; });
                if (foundData) isFolder = !!foundData.isFolder;
            }

            var url, method;
            if (isFolder) {
                // Use folder delete endpoint
                url = "/delete-folder/" + encodeURIComponent(filename);
                method = "POST";
            } else {
                url = "/delete/" + encodeURIComponent(filename);
                method = "POST";
            }

            var xhr = new XMLHttpRequest();
            xhr.open(method, url);
            xhr.onload = function () {
                if (xhr.status === 200 || xhr.status === 302) {
                    completed++;
                    // Mark matching upload queue items as deleted
                    if (Array.isArray(window.uploadQueue)) {
                        var basename = filename.split('/').pop().split('\\').pop();
                        window.uploadQueue.forEach(function (qi) {
                            var qiName = (qi.fileName || qi.name || "");
                            if (qi.status === 'completed' && (qiName === basename || qiName === filename)) {
                                qi.status = 'deleted';
                            }
                        });
                        saveUploadQueueToStorage();
                        if (typeof renderUploadTray === 'function') renderUploadTray();
                    }
                } else { failed.push(filename); }
                deleteNext(index + 1);
            };
            xhr.onerror = function () {
                failed.push(filename);
                deleteNext(index + 1);
            };
            xhr.send();
        }

        deleteNext(0);
    };

    function downloadFileByName(filename) {
        if (!filename) return;
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

    // --- Context Menu ---
    window.openRowMenu = function (event, filename) {
        event.stopPropagation();
        var menu = document.getElementById("contextMenu");
        var genericOps = document.getElementById("genericMenuOptions");
        var itemOps = document.getElementById("itemMenuOptions");
        if (!menu) return;

        if (genericOps) genericOps.style.display = "none";
        if (itemOps) itemOps.style.display = "block";

        // Set context menu target
        window._contextMenuTarget = filename;

        // Sync star status in menu
        var starText = document.getElementById("menuStarText");
        var starIcon = document.getElementById("menuStarIcon");
        var starred = isStarred(filename);
        if (starText) {
            starText.textContent = starred ? "Remove Star" : "Add to Starred";
        }
        if (starIcon) {
            starIcon.style.fill = starred ? "var(--yellow, #f59e0b)" : "none";
            starIcon.style.color = starred ? "var(--yellow, #f59e0b)" : "currentColor";
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

    window.handleMenuStarToggle = function () {
        var name = window._contextMenuTarget || "";
        if (name) {
            toggleStar(name);
            fetchFilesData().then(function (fd) {
                renderPrototypeFileList(fd);
            });
        }
        var menu = document.getElementById("contextMenu");
        if (menu) menu.style.display = "none";
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
        var name = prototypeSelectedItems[0] || (window._contextMenuTarget || "");
        var dialog = document.getElementById("renameDialog");
        var input = document.getElementById("renameInput");
        if (!dialog || !input) return;
        input.value = name;
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
            var dotIdx = name.lastIndexOf(".");
            var selectEnd = (dotIdx > 0) ? dotIdx : name.length;
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

    window.openNewFolderDialog = function () {
        // Hide context menu immediately so it doesn't intercept clicks
        var contextMenu = document.getElementById("contextMenu");
        if (contextMenu) contextMenu.style.display = "none";

        var dialog = document.getElementById("newFolderDialog");
        var input = document.getElementById("newFolderNameInput");
        if (!dialog) return;

        dialog.style.display = "flex";

        if (input) {
            input.value = "Untitled folder";

            function doFocusAndSelect() {
                try {
                    input.focus({ preventScroll: true });
                    if (typeof input.setSelectionRange === "function") {
                        input.setSelectionRange(0, input.value.length);
                    } else if (typeof input.select === "function") {
                        input.select();
                    }
                } catch (e) { }
            }

            //  dual RAF + timeout fallback for modal animation / layout engine readiness
            requestAnimationFrame(function () {
                requestAnimationFrame(function () {
                    doFocusAndSelect();
                });
            });
            setTimeout(doFocusAndSelect, 50);
            setTimeout(doFocusAndSelect, 150);
        }
    };

    window.closeNewFolderDialog = function () {
        var dialog = document.getElementById("newFolderDialog");
        if (dialog) dialog.style.display = "none";
    };

    // --- Sort & Filter ---
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
            ? '<span style="display:inline-flex; align-items:center; justify-content:center; width:18px; height:18px; border-radius:50%; background:var(--secondary-container); color:var(--primary); margin-left:2px;" title="A to Z"><i data-lucide="arrow-down" style="width:12px;height:12px;"></i></span>'
            : '<span style="display:inline-flex; align-items:center; justify-content:center; width:18px; height:18px; border-radius:50%; background:var(--secondary-container); color:var(--primary); margin-left:2px;" title="Z to A"><i data-lucide="arrow-up" style="width:12px;height:12px;"></i></span>';

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

        fetchFilesData().then(function (fd) {
            renderPrototypeFileList(fd);
        });
    };

    window.setTypeFilter = function (type) {
        typeFilter = type;
        var wrapper = document.getElementById("typeBtnWrapper");
        if (wrapper) {
            if (type === "all") {
                wrapper.innerHTML =
                    '<button class="filter-chip" id="typeDropdownBtn" onclick="toggleTypeDropdown(event)" style="display: flex; align-items: center; gap: 0.35rem; font-size: 0.76rem; font-weight: 700; border: 1px solid var(--border-color); background: var(--card-bg); color: var(--text-color); border-radius: 999px; padding: 0.45rem 0.8rem; cursor: pointer;">' +
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
                    '<div class="filter-chip active" id="typeDropdownBtn" style="display: flex; align-items: center; padding: 0; border: none; background: var(--primary-container); border-radius: 999px; overflow: hidden; height: 30px;">' +
                    '<button onclick="toggleTypeDropdown(event)" style="display: flex; align-items: center; gap: 0.25rem; font-size: 0.76rem; font-weight: 700; background: transparent; border: none; color: var(--primary); padding: 0.45rem 0.55rem 0.45rem 0.85rem; cursor: pointer; height: 100%;">' +
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

        fetchFilesData().then(function (fd) {
            renderPrototypeFileList(fd);
        });
    };

    window.clearTypeFilter = function (event) {
        if (event) event.stopPropagation();
        window.setTypeFilter("all");
    };

    window.setSearchQuery = function (value) {
        var searchInput = document.getElementById("searchInput");
        if (searchInput) {
            searchInput.value = value;
            searchInput.dispatchEvent(new Event("input", { bubbles: true }));
        }
    };

    window.clearSearchQuery = function (event) {
        if (event) event.preventDefault();
        var searchInput = document.getElementById("searchInput");
        if (searchInput) {
            searchInput.value = "";
            searchInput.dispatchEvent(new Event("input", { bubbles: true }));
        }
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
        fetchFilesData().then(function (fd) {
            renderPrototypeFileList(fd);
        });
    };

    // --- View Mode ---
    window.setViewMode = function (mode) {
        var fileList = document.getElementById("nasFileList");
        var fileTableHead = document.getElementById("fileTableHead");
        var listBtn = document.getElementById("listViewBtn");
        var gridBtn = document.getElementById("gridViewBtn");

        if (fileList) {
            if (mode === "grid") {
                fileList.classList.add("grid-mode");
                if (fileTableHead) fileTableHead.style.display = "none";
            } else {
                fileList.classList.remove("grid-mode");
                if (fileTableHead) fileTableHead.style.display = "grid";
            }
        }
        if (listBtn) listBtn.classList.toggle("active", mode === "list");
        if (gridBtn) gridBtn.classList.toggle("active", mode === "grid");
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

        console.log("[submitNewFolder] Sending fetch request...");

        fetch("/api/files/mkdir", { method: "POST", body: formData })
            .then(function (r) { return r.json(); })
            .then(function (data) {
                if (data.status === "success") {
                    if (typeof showToast === "function") showToast("Folder '" + name + "' created.", 3000);
                    // If creating from within move dialog, refresh move folder tree
                    if (isCreatingFolderInMove) {
                        isCreatingFolderInMove = false;
                        renderMoveFolderContents();
                    } else {
                        fetchFilesData().then(function (fd) { renderPrototypeFileList(fd); });
                        if (typeof refreshFileList === "function") refreshFileList();
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
                fetchFilesData().then(function (fd) { renderPrototypeFileList(fd); });
                return;
            }

            var oldName = itemsToRename[index];

            // Build the new name
            var nameToUse = newBaseName;

            // For multiple items, append index suffix: test, test (1), test (2)...
            if (itemsToRename.length > 1) {
                if (index > 0) {
                    nameToUse = newBaseName + " (" + index + ")";
                }
            }

            // Determine if the item is a folder
            var isFolder = false;
            var listEl = document.querySelector('#nasFileList [data-filename="' + oldName.replace(/"/g, '&quot;') + '"]');
            if (listEl) {
                isFolder = listEl.getAttribute("data-is-folder") === "1";
            } else {
                var meta = lastFilesData.find(function (f) { return f.name === oldName; });
                if (meta) isFolder = !!meta.isFolder;
            }

            // If it's a file, preserve the extension
            if (!isFolder) {
                var dotIdx = oldName.lastIndexOf(".");
                if (dotIdx > 0) {
                    var ext = oldName.substring(dotIdx);
                    // Check if newBaseName already has an extension
                    var targetDot = newBaseName.lastIndexOf(".");
                    if (targetDot > 0) {
                        var userBase = newBaseName.substring(0, targetDot);
                        if (itemsToRename.length > 1 && index > 0) {
                            nameToUse = userBase + " (" + index + ")" + ext;
                        } else {
                            nameToUse = userBase + ext;
                        }
                    } else {
                        nameToUse = nameToUse + ext;
                    }
                }
            }

            if (nameToUse === oldName) {
                completed++;
                renameNext(index + 1);
                return;
            }

            var formData = new FormData();
            formData.append("filename", oldName);
            formData.append("new_name", nameToUse);

            fetch("/api/files/rename", { method: "POST", body: formData })
                .then(function (r) { return r.json(); })
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

        var completed = 0;
        var failed = [];

        function moveNext(index) {
            if (index >= filesToMove.length) {
                if (failed.length > 0) {
                    if (typeof showToast === "function") showToast("Moved " + completed + " file(s). " + failed.length + " failed.", 4000);
                } else {
                    if (typeof showToast === "function") showToast("Moved " + completed + " file(s) to '" + (destination || "Home") + "'.", 3000);
                }
                window.clearSelection();
                itemsToMove = [];
                if (typeof refreshFileList === "function") refreshFileList();
                fetchFilesData().then(function (fd) { renderPrototypeFileList(fd); });
                window.closeMoveDialog();
                return;
            }

            var filename = filesToMove[index];
            var formData = new FormData();
            formData.append("filename", filename);
            formData.append("destination", destination);

            fetch("/api/files/move", { method: "POST", body: formData })
                .then(function (r) { return r.json(); })
                .then(function (data) {
                    if (data.status === "success") {
                        completed++;
                        if (Array.isArray(window.uploadQueue)) {
                            window.uploadQueue.forEach(function (qi) {
                                var qiName = qi.fileName || qi.name || "";
                                if (qiName === filename) {
                                    qi.targetDir = destination || "";
                                }
                            });
                            saveUploadQueueToStorage();
                            if (typeof scheduleUploadTrayRender === "function") {
                                scheduleUploadTrayRender();
                            } else if (typeof renderUploadTray === "function") {
                                renderUploadTray();
                            }
                        }
                    }
                    else { failed.push(filename); }
                    moveNext(index + 1);
                })
                .catch(function () {
                    failed.push(filename);
                    moveNext(index + 1);
                });
        }

        moveNext(0);
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
        var addr = document.getElementById("connectQrDialogAddress");
        if (addr && addr.textContent && navigator.clipboard) {
            navigator.clipboard.writeText(addr.textContent);
        }
    };

    // --- Preview ---
    window.closePreviewModal = function () {
        var modal = document.getElementById("previewModal");
        if (modal) modal.style.display = "none";
    };

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
                    var nameEl = targetItem.querySelector(".item-title, .quick-title");
                    var itemName = nameEl ? nameEl.textContent.trim() : filename;

                    // Select this item if not already selected
                    if (prototypeSelectedItems.indexOf(itemName) === -1) {
                        prototypeSelectedItems = [itemName];
                        var allItems = document.querySelectorAll("#nasFileList .m3-list-item");
                        for (var i = 0; i < allItems.length; i++) {
                            var curName = allItems[i].getAttribute("data-filename");
                            if (curName === itemName) {
                                allItems[i].classList.add("selected");
                            } else {
                                allItems[i].classList.remove("selected");
                            }
                        }
                        updateSelectionToolbar();
                    }

                    if (genericOps) genericOps.style.display = "none";
                    if (itemOps) itemOps.style.display = "block";
                    if (clipboardOps) clipboardOps.style.display = "none";
                    window._contextMenuTarget = filename;
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

        // Click on empty "Drop files here" area triggers file input
        // (production #drop-zone already handles its own click separately)
    }

    // =========================================================================
    // 5. SEARCH INTEGRATION — Client-side filtering
    // =========================================================================

    function setupSearch() {
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
        renderPrototypeFileList = function (files) {
            if (files) lastFiles = files.slice();
            _origRender(files);
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

    window.triggerInstantUIUpdate = function () {
        if (typeof window.scheduleUploadTrayRender === "function") {
            window.scheduleUploadTrayRender();
        } else if (typeof renderUploadTray === "function") {
            renderUploadTray();
        }
        var container = document.getElementById("nasFileList");
        if (container && window.uploadQueue) {
            window.uploadQueue.forEach(function (item) {
                if (item && item.fileName) {
                    var escName = escapeHtml(item.fileName);
                    var row = container.querySelector('.m3-list-item[data-filename="' + escName + '"]');
                    if (row) {
                        if (item.status === 'cancelled') {
                            row.remove();
                        } else if (item.status === 'queued' || item.status === 'uploading' || item.status === 'processing' || item.status === 'paused') {
                            var progress = Math.round(item.progress || 0);
                            var subtitleCell = row.querySelector('.item-subtitle');
                            if (subtitleCell) {
                                subtitleCell.textContent = progress + "% • " + (item.status === 'paused' ? 'Paused' : 'Uploading');
                            }
                            var dateCell = row.querySelector('.item-date');
                            if (dateCell) {
                                dateCell.textContent = item.status === 'paused' ? 'Paused' : 'Uploading';
                            }
                            var bar = row.querySelector('.row-progress-bar');
                            if (bar) {
                                bar.style.width = progress + "%";
                            }
                            var playPauseBtn = row.querySelector('[data-action="pause-upload"], [data-action="resume-upload"]');
                            if (playPauseBtn) {
                                var currentAction = playPauseBtn.getAttribute("data-action");
                                if (item.status === 'paused' && currentAction === 'pause-upload') {
                                    playPauseBtn.setAttribute("data-action", "resume-upload");
                                    playPauseBtn.setAttribute("title", "Resume upload");
                                    playPauseBtn.innerHTML = '<i data-lucide="play" style="width:16px;height:16px;"></i>';
                                    if (window.lucide) lucide.createIcons();
                                } else if (item.status !== 'paused' && currentAction === 'resume-upload') {
                                    playPauseBtn.setAttribute("data-action", "pause-upload");
                                    playPauseBtn.setAttribute("title", "Pause upload");
                                    playPauseBtn.innerHTML = '<i data-lucide="pause" style="width:16px;height:16px;"></i>';
                                    if (window.lucide) lucide.createIcons();
                                }
                            }
                        }
                    }
                }
            });
        }
    };

    window.pauseAllUploads = function () {
        var queue = window.uploadQueue || [];
        queue.forEach(function (item) {
            if (item.status === "uploading" || item.status === "queued") {
                if (typeof window.pauseUpload === "function") {
                    window.pauseUpload(item.id);
                }
            }
        });
        window.uploadManagerExpanded = true;
        window.triggerInstantUIUpdate();
    };

    window.resumeAllUploads = function () {
        var queue = window.uploadQueue || [];
        queue.forEach(function (item) {
            if (item.status === "paused") {
                if (typeof window.resumeUpload === "function") {
                    window.resumeUpload(item.id);
                }
            }
        });
        window.triggerInstantUIUpdate();
    };

    function buildTrayItemHtml(item) {
        var pct = Math.round(item.progress || 0);
        var name = escapeHtml(item.fileName || "Unknown");
        var sizeStr = formatSize(item.fileSize);

        var metaText = "";
        var fillStyle = "";
        var actionHtml = "";

        if (item.status === 'deleted') {
            metaText = sizeStr;
            fillStyle = 'background: rgba(220, 38, 38, 0.12); width: 100%;';
            actionHtml = '<span style="color: #dc2626; display: flex; align-items: center; margin-right: 8px;"><i data-lucide="trash-2" style="width:16px;height:16px;"></i></span>';
        } else if (item.status === 'completed') {
            var timeStr = item.uploadTime ? item.uploadTime + "s" : "completed";
            metaText = sizeStr + " • Completed (" + timeStr + ")";
            fillStyle = 'background: rgba(24, 128, 56, 0.08); width: 100%;';
            actionHtml = '<span style="color: var(--green); display: flex; align-items: center; margin-right: 8px;"><i data-lucide="check" style="width:16px;height:16px;"></i></span>';
        } else if (item.status === 'queued') {
            metaText = sizeStr + " • Queued";
            fillStyle = 'background: transparent; width: 0%;';
            actionHtml = '<button type="button" class="upload-toast-cancel-text" data-upload-id="' + item.id + '" title="Cancel upload">' +
                '<span>Cancel</span>' +
                '</button>';
        } else {
            metaText = sizeStr + " • " + pct + "%";
            fillStyle = 'background: rgba(59, 130, 246, 0.08); width: ' + pct + '%;';
            actionHtml = '<button type="button" class="upload-toast-cancel-text" data-upload-id="' + item.id + '" title="Cancel upload">' +
                '<span>Cancel</span>' +
                '</button>';
        }

        var completedClass = (item.status === 'completed') ? ' completed-toast' : (item.status === 'deleted' ? ' deleted-toast' : '');
        var cursorStyle = (item.status === 'completed' || item.status === 'deleted') ? ' cursor: pointer;' : '';
        var itemTargetDir = item.targetDir || "";

        return '<div class="upload-toast' + completedClass + '" id="toast-item-' + item.id + '" style="position:relative; overflow:hidden;' + cursorStyle + '" data-target-dir="' + escapeHtml(itemTargetDir) + '" data-filename="' + name + '">' +
            '<div class="toast-progress-bar" style="position:absolute; top:0; bottom:0; left:0; ' + fillStyle + ' transition:width 0.2s ease-out; pointer-events:none; z-index:1;"></div>' +
            '<div class="upload-toast-top" style="position:relative; z-index:2; width:100%;">' +
            '<div class="upload-toast-title">' +
            '<span class="upload-toast-filename" title="' + name + '">' + name + "</span>" +
            '<span class="upload-toast-meta">' + metaText + "</span>" +
            "</div>" +
            '<div class="upload-toast-actions">' +
            actionHtml +
            "</div>" +
            "</div>" +
            "</div>";
    }

    function wireTrayItemListeners(el, item) {
        var cancelBtn = el.querySelector(".upload-toast-cancel-text");
        if (cancelBtn && !cancelBtn.__cancelWired) {
            cancelBtn.__cancelWired = true;
            cancelBtn.addEventListener("click", function (e) {
                e.stopPropagation();
                if (typeof window.cancelUpload === "function") {
                    window.cancelUpload(item.id);
                }
            });
        }
        if (item.status === 'completed' && !el.__navWired) {
            el.__navWired = true;
            el.style.cursor = "pointer";
            el.addEventListener("click", function (e) {
                if (e.target.closest("button") || e.target.closest(".upload-toast-actions")) return;
                if (typeof window.navigateToPathAndSelect === "function") {
                    window.navigateToPathAndSelect(item.targetDir || "", item.fileName || item.name || "");
                }
            });
        } else if (item.status === 'deleted' && !el.__navWired) {
            el.__navWired = true;
            el.style.cursor = "pointer";
            el.addEventListener("click", function (e) {
                if (e.target.closest("button") || e.target.closest(".upload-toast-actions")) return;
                if (typeof showToast === "function") showToast('\u26a0\ufe0f "' + (item.fileName || item.name || 'File') + '" was deleted and no longer exists.', 3000);
            });
        }
    }

    window.showGenericContextMenu = function (x, y) {
        var menu = document.getElementById("contextMenu");
        if (!menu) return;
        var genericOps = document.getElementById("genericMenuOptions");
        var itemOps = document.getElementById("itemMenuOptions");
        var clipboardOps = document.getElementById("clipboardMenuOptions");

        if (genericOps) genericOps.style.display = "block";
        if (itemOps) itemOps.style.display = "none";
        if (clipboardOps) clipboardOps.style.display = "none";
        if (typeof window.clearSelection === "function") {
            window.clearSelection();
        }

        // Adjust position so it doesn't overflow
        if (y + 144 > window.innerHeight) y = window.innerHeight - 150;
        if (x + 190 > window.innerWidth) x = window.innerWidth - 200;
        menu.style.left = x + "px";
        menu.style.top = y + "px";
        menu.style.display = "block";
    };

    function buildHeaderActionsHtml(isAllCompleted, pausedCount, expanded, totalCount, docked) {
        var toggleHtml = "";
        var actionBtnHtml = "";

        if (docked) {
            // Left button: Chevron toggle (^ / v) when items exist
            if (totalCount > 0) {
                var chevronIcon = expanded ? "chevron-down" : "chevron-up";
                toggleHtml = '<button type="button" class="upload-toast-header-btn header-expand-dock-btn" title="Toggle detailed list">' +
                    '<i data-lucide="' + chevronIcon + '"></i>' +
                    '</button>';
            }
            // Right button: Plus (+) button
            actionBtnHtml = '<button type="button" class="upload-toast-header-btn open-menu-btn" title="Upload or Create">' +
                '<i data-lucide="plus"></i>' +
                '</button>';
            return toggleHtml + actionBtnHtml;
        }

        // Standard actions when NOT docked (bottom-right overlay)
        if (totalCount > 0) {
            if (isAllCompleted) {
                var chevronIcon = expanded ? "chevron-down" : "chevron-up";
                toggleHtml = '<button type="button" class="upload-toast-header-btn header-expand-btn" title="Toggle detailed list">' +
                    '<i data-lucide="' + chevronIcon + '"></i>' +
                    '</button>';
            } else {
                if (pausedCount > 0) {
                    toggleHtml = '<button type="button" class="upload-toast-header-btn header-playpause-btn" title="Resume all uploads" data-action="resume">' +
                        '<i data-lucide="play" style="fill: currentColor;"></i>' +
                        '</button>';
                } else {
                    toggleHtml = '<button type="button" class="upload-toast-header-btn header-playpause-btn" title="Pause all uploads" data-action="pause">' +
                        '<i data-lucide="pause"></i>' +
                        '</button>';
                }
            }
            actionBtnHtml += '<button type="button" class="upload-toast-header-btn close-panel-btn" title="Cancel all uploads and close">' +
                '<i data-lucide="x"></i>' +
                '</button>';
        } else {
            actionBtnHtml = '<button type="button" class="upload-toast-header-btn open-menu-btn" title="Upload or Create">' +
                '<i data-lucide="plus"></i>' +
                '</button>';
        }

        return toggleHtml + actionBtnHtml;
    }

    function wireHeaderActions(actionsContainer) {
        var playPauseBtn = actionsContainer.querySelector(".header-playpause-btn");
        if (playPauseBtn) {
            playPauseBtn.addEventListener("click", function (e) {
                e.stopPropagation();
                var action = this.getAttribute("data-action");
                if (action === "pause") {
                    window.pauseAllUploads();
                } else {
                    window.resumeAllUploads();
                }
            });
        }
        var expandBtn = actionsContainer.querySelector(".header-expand-btn");
        if (expandBtn) {
            expandBtn.addEventListener("click", function (e) {
                e.stopPropagation();
                window.uploadManagerExpanded = !window.uploadManagerExpanded;
                renderUploadTray();
            });
        }
        var expandDockBtn = actionsContainer.querySelector(".header-expand-dock-btn");
        if (expandDockBtn) {
            expandDockBtn.addEventListener("click", function (e) {
                e.stopPropagation();
                window.uploadManagerExpanded = !window.uploadManagerExpanded;
                renderUploadTray();
            });
        }
        var closeBtn = actionsContainer.querySelector(".close-panel-btn");
        if (closeBtn) {
            closeBtn.addEventListener("click", function (e) {
                e.stopPropagation();
                if (typeof window.cancelAllUploads === "function") {
                    window.cancelAllUploads();
                }
            });
        }
        var openMenuBtn = actionsContainer.querySelector(".open-menu-btn");
        if (openMenuBtn) {
            openMenuBtn.addEventListener("click", function (e) {
                e.stopPropagation();
                var rect = this.getBoundingClientRect();
                if (typeof window.showGenericContextMenu === "function") {
                    window.showGenericContextMenu(rect.left - 120, rect.top - 110);
                }
            });
        }
    }
    window.navigateToPathAndSelect = function (targetPath, filename) {
        currentFolderPath = targetPath || "";
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
        // Persist to server (cleared on every server restart)
        fetch("/api/upload-history", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(serialized)
        }).catch(function () { });
        // Also keep in localStorage as in-tab fast cache
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
            return item.status === "uploading" || item.status === "queued" || item.status === "processing" || item.status === "paused" || item.status === "completed" || item.status === "deleted";
        });

        // Make sure stack is always active/visible
        stack.classList.add("active");

        // Sort priority:
        // 1. Uploading / Active
        // 2. In Queue / Paused
        // 3. Completed (latest first)
        // 4. Deleted
        activeUploads.sort(function (a, b) {
            function getCategoryScore(item) {
                if (item.status === 'uploading' || item.status === 'processing') return 1;
                if (item.status === 'queued' || item.status === 'paused') return 2;
                if (item.status === 'completed') return 3;
                if (item.status === 'deleted') return 4;
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
        var activePendingCount = activeUploads.filter(function (item) { return item.status === "uploading" || item.status === "processing" || item.status === "queued"; }).length;
        var pausedCount = activeUploads.filter(function (item) { return item.status === "paused"; }).length;
        var completedOrDeletedCount = activeUploads.filter(function (item) { return item.status === "completed" || item.status === "deleted"; }).length;
        var isAllCompleted = totalCount > 0 ? (completedOrDeletedCount === totalCount) : true;

        saveUploadQueueToStorage();

        if (totalCount === 0 || window.uploadTrayDocked) {
            stack.classList.add("empty-state");
        } else {
            stack.classList.remove("empty-state");
        }

        var avgPct = totalCount > 0 ? Math.round(activeUploads.reduce(function (sum, item) { return sum + (item.progress || 0); }, 0) / totalCount) : 0;
        var totalSpeedBytes = activeUploads.reduce(function (sum, item) { return sum + (item.speed || 0); }, 0);
        var totalSpeedMB = (totalSpeedBytes / (1024 * 1024)).toFixed(1) + " MB/s";

        // Calculate summary header title
        var headerTitle = "";
        if (totalCount === 0) {
            headerTitle = "No pending uploads";
        } else if (isAllCompleted || activePendingCount === 0) {
            headerTitle = "Uploads completed (" + totalCount + ")";
        } else if (pausedCount === totalCount) {
            headerTitle = "Uploads paused (" + totalCount + ")";
        } else {
            headerTitle = "Uploading " + activePendingCount + " " + (activePendingCount === 1 ? "file" : "files") + " • " + totalSpeedMB;
        }

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
                '<span class="upload-toast-header-title" style="position: relative; z-index: 2;">' + headerTitle + '</span>' +
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

            // Wire header panel manual toggle
            stack.querySelector(".upload-toast-header").addEventListener("click", function (e) {
                if (!e.target.closest(".upload-toast-header-actions")) {
                    // Header title click always just toggles expand/collapse (never undocks)
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

        // In-place updates:
        // 1. Header Title & Progress Fill
        if (headerTitleEl) headerTitleEl.textContent = headerTitle;
        if (headerProgressBar) {
            headerProgressBar.style.width = avgPct + "%";
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

                if (item.status === 'deleted') {
                    metaText = sizeStr;
                    fillStyle = 'rgba(220, 38, 38, 0.12)';
                    pct = 100;
                    actionHtml = '<span style="color: #dc2626; display: flex; align-items: center; margin-right: 8px;"><i data-lucide="trash-2" style="width:16px;height:16px;"></i></span>';
                } else if (item.status === 'completed') {
                    var timeStr = item.uploadTime ? item.uploadTime + "s" : "completed";
                    metaText = sizeStr + " • Completed (" + timeStr + ")";
                    fillStyle = 'rgba(24, 128, 56, 0.08)';
                    pct = 100;
                    actionHtml = '<span style="color: var(--green); display: flex; align-items: center; margin-right: 8px;"><i data-lucide="check" style="width:16px;height:16px;"></i></span>';
                } else if (item.status === 'queued') {
                    metaText = sizeStr + " • Queued";
                    fillStyle = 'transparent';
                    pct = 0;
                } else {
                    metaText = sizeStr + " • " + pct + "%";
                    fillStyle = 'rgba(59, 130, 246, 0.08)';
                }

                var metaEl = itemEl.querySelector(".upload-toast-meta");
                if (metaEl) metaEl.textContent = metaText;

                var progressFill = itemEl.querySelector(".toast-progress-bar");
                if (progressFill) {
                    progressFill.style.width = pct + "%";
                    progressFill.style.background = fillStyle;
                }

                if (item.status === 'completed' || item.status === 'deleted') {
                    var actionsContainer = itemEl.querySelector(".upload-toast-actions");
                    if (actionsContainer && actionsContainer.querySelector(".upload-toast-cancel-text")) {
                        actionsContainer.innerHTML = actionHtml;
                        refreshLucideIcons(actionsContainer);
                    }
                    wireTrayItemListeners(itemEl, item);
                }

                // Sink items based on sort order
                bodyEl.appendChild(itemEl);
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
                return item.status === "uploading" || item.status === "queued" || item.status === "processing" || item.status === "paused";
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

        // Hide Recents (Quick Access) if inside a subfolder OR on Recent/Starred views
        var tab = window.activeTab || "file";
        if ((currentFolderPath && currentFolderPath !== "Home" && currentFolderPath !== "") || tab === "recent" || tab === "starred") {
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
            var name = recentFiles[i];
            var ext = name.split(".").pop().toLowerCase();
            var info = getFileTypeInfo(name, ext);
            var escName = escapeHtml(name);

            html +=
                '<div class="quick-card" data-filename="' + escName + '">' +
                '<div class="quick-icon ' + info.avatarClass + '"><i data-lucide="' + info.iconName + '"></i></div>' +
                '<div class="quick-copy" style="flex:1;min-width:0;">' +
                '<div class="quick-title">' + escName + "</div>" +
                '<div class="quick-subtitle">File</div>' +
                "</div>" +
                "</div>";
        }
        container.innerHTML = html;

        // Click to select
        var cards = container.querySelectorAll(".quick-card");
        for (var k = 0; k < cards.length; k++) {
            cards[k].addEventListener("click", function () {
                var fname = this.getAttribute("data-filename");
                if (prototypeSelectedItems.indexOf(fname) === -1) {
                    prototypeSelectedItems = [fname];
                }
                // Scroll to highlight
                var listItem = document.querySelector('#nasFileList [data-filename="' + fname.replace(/"/g, '"') + '"]');
                if (listItem) listItem.scrollIntoView({ behavior: "smooth", block: "center" });
                updateSelectionToolbar();
            });
        }

        refreshLucideIcons(container);
    }

    // =========================================================================
    // 6. INITIALIZATION — Kick off on DOM ready
    // =========================================================================

    // Fetch full file data with metadata from API (includes folders)
    // Respects currentFolderPath for subfolder navigation
    function fetchFilesData() {
        // If we're in a subfolder (currentFolderPath is not "Home"), fetch that folder's contents
        var isSubfolder = currentFolderPath && currentFolderPath !== "Home" && currentFolderPath !== "";

        if (isSubfolder) {
            // Subfolder: use /api/folders/{folder_name}/files
            // currentFolderPath may be "FolderA" or "FolderA/SubFolder" — encode properly
            var encodedPath = encodeURIComponent(currentFolderPath);
            return fetch("/api/folders/" + encodedPath + "/files")
                .then(function (r) {
                    if (r.status === 404) {
                        currentFolderPath = "Home";
                        prototypeSelectedItems = [];
                        updateSelectionToolbar();
                        renderBreadcrumbs();
                        return fetchFilesData();
                    }
                    return r.json();
                })
                .then(function (data) {
                    if (data && data.files) {
                        return data.files.map(function (f) {
                            return {
                                name: f.name,
                                size: f.size || "--",
                                mtime: f.mtime || 0,
                                isFolder: !!f.isFolder
                            };
                        });
                    }
                    return [];
                })
                .catch(function () { return []; });
        }

        // Root: fetch files + folders in parallel
        var filePromise = fetch("/api/files")
            .then(function (r) { return r.json(); })
            .then(function (data) {
                if (data.files_data) {
                    lastFilesData = data.files_data;
                }
                return data.files_data || data.files || [];
            })
            .catch(function () {
                return [];
            });

        var folderPromise = fetch("/api/folders")
            .then(function (r) { return r.json(); })
            .then(function (data) {
                if (data.folders) {
                    // Convert folder objects to file-like format
                    return data.folders.map(function (f) {
                        return { name: f.name, size: f.size_formatted || "--", mtime: f.created || 0, isFolder: true };
                    });
                }
                return [];
            })
            .catch(function () {
                return [];
            });

        return Promise.all([filePromise, folderPromise]).then(function (results) {
            var files = results[0];
            var folders = results[1];
            // Folders first, then files (matching prototype)
            return folders.concat(files);
        });
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

    // Trigger instant file list refresh after upload completes
    function triggerInstantRefresh() {
        fetchFilesData().then(function (filesData) {
            renderPrototypeFileList(filesData);
        });
        if (typeof refreshFileList === "function") {
            refreshFileList();
        }
    }

    function init() {
        window.uploadTrayDocked = true;
        // Restore upload queue from server (clears on server restart = clears on data clear)
        fetch("/api/upload-history")
            .then(function (r) { return r.json(); })
            .then(function (restoredQueue) {
                if (Array.isArray(restoredQueue) && restoredQueue.length > 0) {
                    restoredQueue.forEach(function (item) {
                        if (item.status === "uploading" || item.status === "queued") {
                            item.status = "paused";
                        }
                    });
                    window.uploadQueue = restoredQueue;
                    // Also sync localStorage to match server
                    try { localStorage.setItem("lanvan_upload_queue", JSON.stringify(restoredQueue)); } catch (e) { }
                    startUploadTrayPolling();
                    renderUploadTray();
                } else {
                    // Server returned empty - clear localStorage too
                    try { localStorage.removeItem("lanvan_upload_queue"); } catch (e) { }
                    window.uploadQueue = window.uploadQueue || [];
                    renderUploadTray();
                }
            })
            .catch(function () {
                // Fallback: try localStorage if server unreachable
                try {
                    var stored = localStorage.getItem("lanvan_upload_queue");
                    if (stored) {
                        var q = JSON.parse(stored);
                        if (Array.isArray(q)) {
                            window.uploadQueue = q;
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

        // Click outside uploader notification widget to collapse expanded list
        document.addEventListener("click", function (e) {
            if (!window.uploadManagerExpanded) return;
            var stack = document.getElementById("uploadToastStack");
            if (stack && !stack.contains(e.target)) {
                window.uploadManagerExpanded = false;
                if (typeof scheduleUploadTrayRender === "function") {
                    scheduleUploadTrayRender();
                } else if (typeof renderUploadTray === "function") {
                    renderUploadTray();
                }
            }
        });

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

        // Fetch full file data with metadata from API
        fetchFilesData().then(function (filesData) {
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
            var container = document.getElementById("nasFileList");
            if (!container) return;

            var normCurrentDir = (currentFolderPath === "Home" || currentFolderPath === "Home/" || !currentFolderPath) ? "" : currentFolderPath;
            var itemDir = item.targetDir || item.parent_path || item.folder || "";
            if (itemDir === "Home" || itemDir === "Home/") itemDir = "";

            if (itemDir === normCurrentDir) {
                var progress = Math.round(item.progress || 0);
                var escName = escapeHtml(item.fileName);
                var row = container.querySelector('.m3-list-item[data-filename="' + escName + '"]');
                if (row) {
                    var subtitleCell = row.querySelector('.item-subtitle');
                    if (subtitleCell) {
                        subtitleCell.textContent = progress + "% • " + (item.status === 'paused' ? 'Paused' : 'Uploading');
                    }
                    var dateCell = row.querySelector('.item-date');
                    if (dateCell) {
                        dateCell.textContent = item.status === 'paused' ? 'Paused' : 'Uploading';
                    }
                    var bar = row.querySelector('.row-progress-bar');
                    if (bar) {
                        bar.style.width = progress + "%";
                    }

                    var playPauseBtn = row.querySelector('[data-action="pause-upload"], [data-action="resume-upload"]');
                    if (playPauseBtn) {
                        var currentAction = playPauseBtn.getAttribute("data-action");
                        if (item.status === 'paused' && currentAction === 'pause-upload') {
                            playPauseBtn.setAttribute("data-action", "resume-upload");
                            playPauseBtn.setAttribute("title", "Resume upload");
                            playPauseBtn.innerHTML = '<i data-lucide="play" style="width:16px;height:16px;"></i>';
                            refreshLucideIcons(playPauseBtn);
                        } else if (item.status !== 'paused' && currentAction === 'resume-upload') {
                            playPauseBtn.setAttribute("data-action", "pause-upload");
                            playPauseBtn.setAttribute("title", "Pause upload");
                            playPauseBtn.innerHTML = '<i data-lucide="pause" style="width:16px;height:16px;"></i>';
                            refreshLucideIcons(playPauseBtn);
                        }
                    }
                } else if (!item._rowRendered) {
                    item._rowRendered = true;
                    if (typeof lastRenderedFiles !== 'undefined') {
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
            startUploadTrayPolling();
            var checkInterval = setInterval(function () {
                var queue = window.uploadQueue || [];
                var activeCount = queue.filter(function (item) {
                    return item.status === "uploading" || item.status === "queued" || item.status === "processing" || item.status === "paused";
                }).length;
                if (activeCount === 0) {
                    clearInterval(checkInterval);
                    setTimeout(triggerInstantRefresh, 500);
                }
            }, 500);
        };

        // Render empty manager on load so it is visible by default
        renderUploadTray();

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