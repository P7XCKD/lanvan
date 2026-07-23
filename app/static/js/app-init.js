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
            _originalUpdateFileDisplay(files);
            // Also fetch folders so they don't disappear during auto-refresh
            fetch("/api/folders")
                .then(function (r) { return r.json(); })
                .then(function (data) {
                    var folderItems = (data.folders || []).map(function (f) {
                        return { name: f.name, size: f.size_formatted || "--", mtime: f.created || 0, isFolder: true };
                    });
                    // Folders first, then files
                    renderPrototypeFileList(folderItems.concat(files || []));
                })
                .catch(function () {
                    renderPrototypeFileList(files);
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

    // Current folder path for breadcrumb navigation (e.g. "Home" or "Home/FolderName")
    var currentFolderPath = "Home";

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
    // Store last files_data for metadata access (name, size, mtime)
    var lastFilesData = [];

    function renderPrototypeFileList(files) {
        var container = document.getElementById("nasFileList");
        var filePanelMeta = document.getElementById("filePanelMeta");
        if (!container) return;

        // files can be either string[] (names only) or object[] (with metadata)
        // Normalize to always have name, size, mtime
        var normalizedFiles = [];
        if (files && files.length > 0) {
            for (var i = 0; i < files.length; i++) {
                if (typeof files[i] === "string") {
                    // Find metadata from lastFilesData
                    var meta = lastFilesData.find(function (f) { return f.name === files[i]; });
                    normalizedFiles.push({
                        name: files[i],
                        size: meta ? meta.size : "--",
                        mtime: meta ? meta.mtime : 0
                    });
                } else {
                    normalizedFiles.push(files[i]);
                }
            }
        }

        // Update file count in prototype panel meta
        if (filePanelMeta) {
            filePanelMeta.textContent = normalizedFiles.length
                ? normalizedFiles.length + " file" + (normalizedFiles.length === 1 ? "" : "s")
                : "";
        }

        if (!normalizedFiles || normalizedFiles.length === 0) {
            // Check if uploads are active — show different message
            var queue = window.uploadQueue || [];
            var activeUploads = queue.filter(function (item) {
                return item.status === "uploading" || item.status === "queued" || item.status === "processing";
            });
            if (activeUploads.length > 0) {
                container.innerHTML =
                    '<div style="display:flex; flex-direction:column; align-items:center; justify-content:center; text-align:center; padding:3rem 0; width:100%;">' +
                    '<div class="avatar-icon avatar-folder" style="width:72px;height:72px;border-radius:18px;margin-bottom:1rem;">' +
                    '<i data-lucide="upload-cloud" style="width:34px;height:34px;"></i></div>' +
                    '<div style="font-size:1.05rem; font-weight:500; color:var(--text-color); margin-bottom:0.25rem;">Uploading ' + activeUploads.length + ' file' + (activeUploads.length === 1 ? '' : 's') + '...</div>' +
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
            if (window.lucide) lucide.createIcons();
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
            html += buildListItem(name, info, size, dateStr, subtitle, !!fileData.isFolder);
        }
        container.innerHTML = html;

        // Attach click handlers — pass full normalized data for folder detection
        attachListItemHandlers(container, normalizedFiles.map(function (f) { return f.name; }), normalizedFiles);

        // Also render quick access cards (only non-folders)
        renderQuickAccess(normalizedFiles
            .filter(function (f) { return !f.isFolder; })
            .map(function (f) { return f.name; }));

        if (window.lucide) lucide.createIcons();
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
    function buildListItem(name, info, size, date, subtitle, isFolder) {
        var escName = escapeHtml(name);
        var sizeStr = size || "--";
        var dateStr = date || "--";
        var subtitleText = subtitle || (isFolder ? "Folder" : "File");
        var starred = isStarred(name);
        var starFill = starred ? "var(--yellow, #f59e0b)" : "none";
        var starColor = starred ? "var(--yellow, #f59e0b)" : "";
        // Folders show "--" for size column; files show size
        var displaySize = isFolder ? "-" : sizeStr;
        return (
            '<div class="m3-list-item" data-filename="' + escName + '" data-is-folder="' + (isFolder ? '1' : '0') + '">' +
            '<div class="file-name-cell">' +
            '<div class="avatar-icon ' + info.avatarClass + '"><i data-lucide="' + info.iconName + '"></i></div>' +
            '<div class="item-main">' +
            '<div class="item-title">' + escName + '</div>' +
            '<div class="item-subtitle">' + subtitleText + '</div>' +
            '</div>' +
            '</div>' +
            '<div class="item-date">' + dateStr + '</div>' +
            '<div class="item-size">' + displaySize + '</div>' +
            '<div class="row-actions">' +
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
            '</button>' +
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

                // Single click: select (and navigate into folder on mobile)
                item.addEventListener("click", function (e) {
                    if (e.target.closest("button")) return;
                    var isMobile = window.innerWidth < 768;
                    if (folderFlag && isMobile) {
                        // Mobile: single-click navigates into folder
                        navigateIntoFolder(name);
                        return;
                    }
                    handleListItemClick(item, index, files);
                });

                // Double-click: navigate into folder (desktop)
                item.addEventListener("dblclick", function (e) {
                    if (e.target.closest("button")) return;
                    if (folderFlag) {
                        navigateIntoFolder(name);
                    }
                });

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
    function navigateIntoFolder(folderName) {
        // Build the full path from the current folder
        if (currentFolderPath === "Home" || currentFolderPath === "") {
            currentFolderPath = folderName;
        } else {
            currentFolderPath = currentFolderPath + "/" + folderName;
        }
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
            var prodFolderInput = document.getElementById("folderInput");
            if (prodFolderInput) prodFolderInput.click();
        } else {
            var prodFileInput = document.getElementById("fileInput");
            if (prodFileInput) prodFileInput.click();
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
        if (prototypeSelectedItems.length === 0) return;

        var itemsToDelete = prototypeSelectedItems.slice();
        var completed = 0;
        var failed = [];

        function deleteNext(index) {
            if (index >= itemsToDelete.length) {
                if (failed.length > 0) {
                    if (typeof showToast === "function") showToast("Deleted " + completed + " item(s). " + failed.length + " failed.", 4000);
                } else {
                    if (typeof showToast === "function") showToast("Deleted " + completed + " item(s) successfully.", 3000);
                }
                window.clearSelection();
                if (typeof refreshFileList === "function") refreshFileList();
                fetchFilesData().then(function(fd) { renderPrototypeFileList(fd); });
                return;
            }

            var filename = itemsToDelete[index];

            // Check if this is a folder by looking at the rendered list
            var listEl = document.querySelector('#nasFileList [data-filename="' + filename.replace(/"/g, '&quot;') + '"]');
            var isFolder = listEl && listEl.getAttribute("data-is-folder") === "1";

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
                if (xhr.status === 200 || xhr.status === 302) { completed++; }
                else { failed.push(filename); }
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
        var name = prototypeSelectedItems[0] || (window._contextMenuTarget || "");
        var dialog = document.getElementById("renameDialog");
        var input = document.getElementById("renameInput");
        if (!dialog || !input) return;
        input.value = name;
        dialog.style.display = "flex";
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
        if (inp) { inp.value = "Untitled folder"; inp.focus(); inp.select(); }
        dlg.style.display = "flex";
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
                (function(idx) {
                    var bItem = document.createElement("span");
                    bItem.style.cursor = idx < moveCurrentPath.length - 1 ? "pointer" : "default";
                    bItem.style.color = idx < moveCurrentPath.length - 1 ? "var(--primary)" : "var(--text-color)";
                    bItem.textContent = moveCurrentPath[idx];
                    if (idx < moveCurrentPath.length - 1) {
                        bItem.onclick = function() {
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
            .then(function(r) { return r.json(); })
            .then(function(data) {
                optionsList.innerHTML = "";
                var items = [];
                if (data.folders) {
                    // Root level: only show folders
                    items = data.folders;
                } else if (data.files) {
                    // Subfolder level: only show sub-folders
                    items = data.files.filter(function(f) { return f.isFolder || f.is_folder; });
                }

                // Filter out items being moved (can't move into themselves)
                items = items.filter(function(f) { return itemsToMove.indexOf(f.name) === -1; });

                if (items.length === 0) {
                    optionsList.innerHTML = '<div style="padding:1.5rem;text-align:center;color:var(--text-muted);font-size:0.8rem;">No subfolders here</div>';
                    return;
                }

                items.forEach(function(folderItem) {
                    var row = document.createElement("div");
                    row.style.cssText = "display:grid;grid-template-columns:1fr auto;align-items:center;padding:0.55rem 0.6rem;font-size:0.78rem;border-radius:6px;cursor:pointer;transition:background-color 0.15s ease;";
                    row.innerHTML =
                        '<div style="display:flex;align-items:center;gap:0.5rem;min-width:0;">' +
                        '<i data-lucide="folder" style="width:16px;height:16px;color:var(--primary);"></i>' +
                        '<span style="white-space:nowrap;overflow:hidden;text-overflow:ellipsis;font-weight:600;">' + escapeHtml(folderItem.name) + '</span>' +
                        '</div>' +
                        '<i data-lucide="chevron-right" style="width:14px;height:14px;color:var(--text-muted);"></i>';
                    row.onmouseover = function() { row.style.backgroundColor = "var(--hover-bg)"; };
                    row.onmouseout = function() { row.style.backgroundColor = "transparent"; };
                    row.onclick = function() {
                        moveCurrentPath.push(folderItem.name);
                        renderMoveFolderContents();
                    };
                    optionsList.appendChild(row);
                });

                if (window.lucide) lucide.createIcons();
            })
            .catch(function() {
                optionsList.innerHTML = '<div style="padding:1.5rem;text-align:center;color:var(--text-muted);font-size:0.8rem;">Failed to load folders</div>';
            });
    }

    window.openNewFolderDialog = function () {
        var dialog = document.getElementById("newFolderDialog");
        var input = document.getElementById("newFolderNameInput");
        if (!dialog) return;
        if (input) {
            input.value = "Untitled folder";
            input.focus();
            input.select();
        }
        dialog.style.display = "flex";
    };

    window.closeNewFolderDialog = function () {
        var dialog = document.getElementById("newFolderDialog");
        if (dialog) dialog.style.display = "none";
    };

    // --- Sort & Filter ---
    window.setSortOption = function (category, value) {
        var el = document.getElementById("sortDropdownMenu");
        if (el) el.style.display = "none";
    };

    window.setTypeFilter = function (type) {
        var el = document.getElementById("typeDropdownMenu");
        if (el) el.style.display = "none";
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
        menu.style.display = menu.style.display === "block" ? "none" : "block";
    };

    window.toggleTypeDropdown = function (event) {
        event.stopPropagation();
        var menu = document.getElementById("typeDropdownMenu");
        if (!menu) return;
        menu.style.display = menu.style.display === "block" ? "none" : "block";
    };

    window.handleHeaderSortClick = function (column) {
        console.log("Header sort:", column);
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
        var input = document.getElementById("newFolderNameInput");
        var name = (input && input.value.trim()) || "Untitled folder";
        if (!name) return;

        var formData = new FormData();
        formData.append("folder_name", name);
        if (isCreatingFolderInMove) {
            var destination = moveCurrentPath.length > 1 ? moveCurrentPath.slice(1).join("/") : "";
            formData.append("parent_path", destination);
        }

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
                        fetchFilesData().then(function(fd) { renderPrototypeFileList(fd); });
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
        var oldName = prototypeSelectedItems[0] || (window._contextMenuTarget || "");
        var newName = (document.getElementById("renameInput") || {}).value;
        if (!oldName || !newName || newName === oldName) {
            window.closeRenameDialog();
            return;
        }

        var formData = new FormData();
        formData.append("filename", oldName);
        formData.append("new_name", newName);

        fetch("/api/files/rename", { method: "POST", body: formData })
            .then(function (r) { return r.json(); })
            .then(function (data) {
                if (data.status === "success") {
                    if (typeof showToast === "function") showToast("Renamed to '" + newName + "'.", 3000);
                    if (typeof refreshFileList === "function") refreshFileList();
                } else {
                    if (typeof showToast === "function") showToast(data.msg || "Rename failed.", 4000);
                }
            })
            .catch(function () {
                if (typeof showToast === "function") showToast("Network error renaming file.", 4000);
            });

        window.closeRenameDialog();
        window.clearSelection();
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
                fetchFilesData().then(function(fd) { renderPrototypeFileList(fd); });
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
                    if (data.status === "success") { completed++; }
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
        if (lanTab) lanTab.classList.toggle("active", mode === "ip");
        if (mdnsTab) mdnsTab.classList.toggle("active", mode === "mdns");
        if (qrLanTab) qrLanTab.classList.toggle("active", mode === "ip");
        if (qrMdnsTab) qrMdnsTab.classList.toggle("active", mode === "mdns");

        if (window._currentNetworkInfo) {
            var url = window._currentNetworkInfo.lanIpUrl;
            if (mode === "mdns" && window._currentNetworkInfo.networkInfo && window._currentNetworkInfo.networkInfo.mdns) {
                url = window._currentNetworkInfo.networkInfo.mdns.url || url;
            }
            window._currentNetworkInfo.fullUrl = url;
            renderSidebarQR();
        }

        if (typeof updateMDNSStatus === "function") updateMDNSStatus();
    };

    window.openConnectQrDialog = function () {
        var dialog = document.getElementById("connectQrDialog");
        if (!dialog) return;
        dialog.style.display = "flex";
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

    function renderUploadTray() {
        var stack = document.getElementById("uploadToastStack");
        if (!stack) return;

        var queue = window.uploadQueue || [];
        var activeUploads = queue.filter(function (item) {
            return item.status === "uploading" || item.status === "queued" || item.status === "processing";
        });

        if (activeUploads.length === 0) {
            stack.classList.remove("active");
            stack.innerHTML = "";
            return;
        }

        stack.classList.add("active");
        var html = "";

        for (var i = 0; i < activeUploads.length; i++) {
            var item = activeUploads[i];
            var pct = Math.round(item.progress || 0);
            var name = escapeHtml(item.fileName || "Unknown");
            var speed = item.speed ? (item.speed / (1024 * 1024)).toFixed(1) + " MB/s" : "";
            var statusText = item.status === "processing" ? "Processing..." : "Uploading";

            html +=
                '<div class="upload-toast">' +
                '<div class="upload-toast-top">' +
                '<div class="upload-toast-title">' +
                '<span class="upload-toast-filename" title="' + name + '">' + name + "</span>" +
                '<span class="upload-toast-meta">' + speed + "</span>" +
                "</div>" +
                '<div class="upload-toast-actions">' +
                '<button type="button" class="upload-toast-cancel-pill" data-upload-id="' + item.id + '" title="Cancel upload">' +
                '<i data-lucide="x"></i><span>Cancel</span>' +
                "</button>" +
                "</div>" +
                "</div>" +
                '<div class="upload-toast-bottom">' +
                "<span>" + statusText + "</span>" +
                '<span class="upload-toast-status">' + pct + "%</span>" +
                "</div>" +
                '<div class="upload-toast-progress">' +
                '<div class="upload-toast-progress-fill" style="width:' + pct + '%"></div>' +
                "</div>" +
                "</div>";
        }

        stack.innerHTML = html;

        // Wire cancel buttons
        var cancelBtns = stack.querySelectorAll(".upload-toast-cancel-pill");
        for (var j = 0; j < cancelBtns.length; j++) {
            cancelBtns[j].addEventListener("click", function (e) {
                var uploadId = this.getAttribute("data-upload-id");
                if (uploadId && typeof cancelUpload === "function") {
                    cancelUpload(parseInt(uploadId));
                }
            });
        }

        if (window.lucide) lucide.createIcons();
    }

    // Poll uploadQueue for changes every 500ms while uploads are active
    var uploadTrayInterval = null;
    function startUploadTrayPolling() {
        if (uploadTrayInterval) return;
        uploadTrayInterval = setInterval(function () {
            var queue = window.uploadQueue || [];
            var activeCount = queue.filter(function (item) {
                return item.status === "uploading" || item.status === "queued" || item.status === "processing";
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
        if (!container || !files || files.length === 0) {
            if (container) container.innerHTML = "";
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

        if (window.lucide) lucide.createIcons();
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
                .then(function (r) { return r.json(); })
                .then(function (data) {
                    if (data.files) {
                        return data.files.map(function(f) {
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

        // Use production generateQRCode() from main-app.js (generates proper QR via API)
        qrBox.innerHTML = "";
        if (typeof generateQRCode === "function") {
            try {
                var qrResult = generateQRCode(url, 140);
                if (qrResult && qrResult.primary) {
                    var qrImg = document.createElement("img");
                    qrImg.src = qrResult.primary;
                    qrImg.alt = "QR Code";
                    qrImg.style.cssText = "width:100%;height:100%;object-fit:contain;display:block;";
                    qrBox.appendChild(qrImg);
                    return;
                }
            } catch(e) {}
        }
        // Fallback: use API endpoint directly
        var qrApiUrl = "/api/qr-code?text=" + encodeURIComponent(url) + "&size=200";
        var img = document.createElement("img");
        img.alt = "QR Code";
        img.style.cssText = "width:100%;height:100%;object-fit:contain;display:block;";
        img.src = qrApiUrl;
        qrBox.appendChild(img);
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
        setupDropzone();
        setupSearch();

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
                if (data.mdns && data.mdns.status === 'active' && data.mdns.url) {
                    fullUrl = data.mdns.url;
                }
                window._currentNetworkInfo = {
                    networkInfo: data,
                    lanIpUrl: lanIpUrl,
                    useMDNS: data.mdns && data.mdns.status === 'active',
                    fullUrl: fullUrl
                };
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

        // Wrap addToUploadQueue to trigger instant refresh after uploads complete
        var origAddToQueue = window.addToUploadQueue;
        if (typeof origAddToQueue === "function" && !origAddToQueue.__refreshWrapped) {
            window.addToUploadQueue = function (files) {
                origAddToQueue(files);
                startUploadTrayPolling();
                var checkInterval = setInterval(function () {
                    var queue = window.uploadQueue || [];
                    var activeCount = queue.filter(function (item) {
                        return item.status === "uploading" || item.status === "queued" || item.status === "processing";
                    }).length;
                    if (activeCount === 0) {
                        clearInterval(checkInterval);
                        setTimeout(triggerInstantRefresh, 500);
                    }
                }, 500);
            };
            window.addToUploadQueue.__refreshWrapped = true;
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