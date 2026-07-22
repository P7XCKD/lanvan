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
            renderPrototypeFileList(files);
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

    /**
     * Render files in prototype #nasFileList from the same data production uses.
     * @param {string[]} files - Array of filenames from production API
     */
    function renderPrototypeFileList(files) {
        var container = document.getElementById("nasFileList");
        var filePanelMeta = document.getElementById("filePanelMeta");
        if (!container) return;

        // Update file count in prototype panel meta
        if (filePanelMeta) {
            filePanelMeta.textContent = files && files.length
                ? files.length + " file" + (files.length === 1 ? "" : "s")
                : "";
        }

        if (!files || files.length === 0) {
            container.innerHTML =
                '<div style="display:flex; flex-direction:column; align-items:center; justify-content:center; text-align:center; padding:3rem 0; width:100%;">' +
                '<div class="avatar-icon avatar-folder" style="width:72px;height:72px;border-radius:18px;margin-bottom:1rem;">' +
                '<i data-lucide="folder-open" style="width:34px;height:34px;"></i></div>' +
                '<div style="font-size:1.05rem; font-weight:500; color:var(--text-color); margin-bottom:0.25rem;">Drop files here</div>' +
                '<div style="font-size:0.8rem; color:var(--text-muted);">or right-click to upload / create folders.</div>' +
                "</div>";
            if (window.lucide) lucide.createIcons();
            return;
        }

        var html = "";
        for (var i = 0; i < files.length; i++) {
            var name = files[i];
            var ext = name.split(".").pop().toLowerCase();
            var info = getFileTypeInfo(name, ext);
            html += buildListItem(name, info, ext);
        }
        container.innerHTML = html;

        // Attach click handlers (delegated would be cleaner, but prototype uses inline)
        attachListItemHandlers(container, files);
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
     */
    function buildListItem(name, info) {
        var escName = escapeHtml(name);
        return (
            '<div class="m3-list-item" data-filename="' +
            escName +
            '">' +
            '<div class="file-name-cell">' +
            '<div class="avatar-icon ' +
            info.avatarClass +
            '"><i data-lucide="' +
            info.iconName +
            '"></i></div>' +
            '<div class="item-main">' +
            '<div class="item-title">' +
            escName +
            "</div>" +
            '<div class="item-subtitle">File</div>' +
            "</div>" +
            "</div>" +
            '<div class="item-date">--</div>' +
            '<div class="item-size">--</div>' +
            '<div class="row-actions">' +
            '<button class="btn-icon hover-btn" title="Download" data-action="download" data-filename="' +
            escName +
            '">' +
            '<i data-lucide="download" style="width:16px;height:16px;"></i>' +
            "</button>" +
            '<button class="btn-icon" title="More actions" data-action="menu" data-filename="' +
            escName +
            '">' +
            '<i data-lucide="more-vertical" style="width:16px;height:16px;"></i>' +
            "</button>" +
            "</div>" +
            "</div>"
        );
    }

    /**
     * Attach click handlers to prototype list items after render.
     */
    function attachListItemHandlers(container, files) {
        // Item click — select
        var items = container.querySelectorAll(".m3-list-item");
        for (var i = 0; i < items.length; i++) {
            (function (item, index) {
                item.addEventListener("click", function (e) {
                    if (e.target.closest("button")) return;
                    handleListItemClick(item, index, files);
                });
                // Download button
                var dlBtn = item.querySelector('[data-action="download"]');
                if (dlBtn) {
                    dlBtn.addEventListener("click", function (e) {
                        e.stopPropagation();
                        var filename = dlBtn.getAttribute("data-filename");
                        downloadFileByName(filename);
                    });
                }
                // Menu button
                var menuBtn = item.querySelector('[data-action="menu"]');
                if (menuBtn) {
                    menuBtn.addEventListener("click", function (e) {
                        e.stopPropagation();
                        var filename = menuBtn.getAttribute("data-filename");
                        openRowMenu(e, filename);
                    });
                }
            })(items[i], i);
        }
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
        var sideFile = document.getElementById("sideItemFile");
        var sideClip = document.getElementById("sideItemClipboard");
        var navFile = document.getElementById("navItemFile");
        var navClip = document.getElementById("navItemClipboard");

        if (tab === "clipboard") {
            if (fileView) fileView.style.display = "none";
            if (clipView) clipView.style.display = "flex";
            if (sideFile) sideFile.classList.remove("active");
            if (sideClip) sideClip.classList.add("active");
            if (navFile) navFile.classList.remove("active");
            if (navClip) navClip.classList.add("active");
            if (typeof refreshClipboardHistory === "function") refreshClipboardHistory();
        } else {
            if (fileView) fileView.style.display = "flex";
            if (clipView) clipView.style.display = "none";
            if (sideFile) sideFile.classList.add("active");
            if (sideClip) sideClip.classList.remove("active");
            if (navFile) navFile.classList.add("active");
            if (navClip) navClip.classList.remove("active");
        }
    };

    // --- Theme ---
    window.toggleDarkMode = function () {
        var current = document.documentElement.getAttribute("data-theme");
        var next = current === "dark" ? "light" : "dark";
        document.documentElement.setAttribute("data-theme", next);
        document.body.setAttribute("data-theme", next); // Sync for production
        localStorage.setItem("dark_mode_enabled", next === "dark" ? "1" : "0");

        var prodToggle = document.getElementById("enableDarkMode");
        if (prodToggle) prodToggle.checked = next === "dark";

        var settingsToggle = document.getElementById("darkThemeSettingToggle");
        if (settingsToggle) settingsToggle.checked = next === "dark";
    };

    // --- Settings Dialog ---
    window.openSettingsDialog = function () {
        var dialog = document.getElementById("settingsDialog");
        if (!dialog) return;

        // Sync AES toggle from production
        var aesProd = document.getElementById("enableEncryption");
        var aesSetting = document.getElementById("aesSettingToggle");
        if (aesProd && aesSetting) aesSetting.checked = aesProd.checked;

        // Sync dark theme toggle
        var isDark = document.documentElement.getAttribute("data-theme") === "dark";
        var darkSetting = document.getElementById("darkThemeSettingToggle");
        if (darkSetting) darkSetting.checked = isDark;

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
        if (prototypeSelectedItems.length === 0) return;
        for (var i = 0; i < prototypeSelectedItems.length; i++) {
            downloadFileByName(prototypeSelectedItems[i]);
        }
        window.clearSelection();
    };

    window.deleteSelected = function () {
        if (prototypeSelectedItems.length === 0) return;
        if (!confirm("Delete " + prototypeSelectedItems.length + " selected item(s)? This cannot be undone.")) return;

        var itemsToDelete = prototypeSelectedItems.slice();
        var completed = 0;
        var failed = [];

        function deleteNext(index) {
            if (index >= itemsToDelete.length) {
                // All done
                if (failed.length > 0) {
                    if (typeof showToast === "function") {
                        showToast("Deleted " + completed + " file(s). " + failed.length + " failed.", 4000);
                    }
                } else {
                    if (typeof showToast === "function") {
                        showToast("Deleted " + completed + " file(s) successfully.", 3000);
                    }
                }
                window.clearSelection();
                // Refresh file list
                if (typeof refreshFileList === "function") refreshFileList();
                return;
            }

            var filename = itemsToDelete[index];
            var xhr = new XMLHttpRequest();
            xhr.open("POST", "/delete/" + encodeURIComponent(filename));
            xhr.onload = function () {
                if (xhr.status === 200) {
                    completed++;
                } else {
                    failed.push(filename);
                }
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

        menu.style.display = "block";
        menu.style.left = Math.min(event.clientX, window.innerWidth - 200) + "px";
        menu.style.top = Math.min(event.clientY, window.innerHeight - 250) + "px";
    };

    // Close context menu on any click outside
    document.addEventListener("click", function (e) {
        var menu = document.getElementById("contextMenu");
        if (menu && !menu.contains(e.target)) {
            menu.style.display = "none";
        }
        var sortMenu = document.getElementById("sortDropdownMenu");
        if (sortMenu && !sortMenu.contains(e.target)) {
            sortMenu.style.display = "none";
        }
        var typeMenu = document.getElementById("typeDropdownMenu");
        if (typeMenu && !typeMenu.contains(e.target)) {
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
        input.focus();
        input.select();
    };

    window.closeRenameDialog = function () {
        var dialog = document.getElementById("renameDialog");
        if (dialog) dialog.style.display = "none";
    };

    window.openMoveModal = function () {
        var dialog = document.getElementById("moveFileDialog");
        if (dialog) dialog.style.display = "flex";
    };

    window.closeMoveDialog = function () {
        var dialog = document.getElementById("moveFileDialog");
        if (dialog) dialog.style.display = "none";
    };

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
        // Stub — sort state managed locally until server-side support
        console.log("Sort:", category, value);
        var el = document.getElementById("sortDropdownMenu");
        if (el) el.style.display = "none";
    };

    window.setTypeFilter = function (type) {
        // Stub — type filtering via client-side filtering of file list
        console.log("Type filter:", type);
        var el = document.getElementById("typeDropdownMenu");
        if (el) el.style.display = "none";
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

        fetch("/api/files/mkdir", { method: "POST", body: formData })
            .then(function (r) { return r.json(); })
            .then(function (data) {
                if (data.status === "success") {
                    if (typeof showToast === "function") showToast("Folder '" + name + "' created.", 3000);
                    if (typeof refreshFileList === "function") refreshFileList();
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
        var filesToMove = prototypeSelectedItems.slice();
        if (filesToMove.length === 0) {
            window.closeMoveDialog();
            return;
        }

        // Move to the root directory for now (move dialog browsing would need folder list population)
        var destination = "";

        var completed = 0;
        var failed = [];

        function moveNext(index) {
            if (index >= filesToMove.length) {
                if (failed.length > 0) {
                    if (typeof showToast === "function") {
                        showToast("Moved " + completed + " file(s). " + failed.length + " failed.", 4000);
                    }
                } else {
                    if (typeof showToast === "function") {
                        showToast("Moved " + completed + " file(s) successfully.", 3000);
                    }
                }
                window.clearSelection();
                if (typeof refreshFileList === "function") refreshFileList();
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
                    } else {
                        failed.push(filename);
                    }
                    moveNext(index + 1);
                })
                .catch(function () {
                    failed.push(filename);
                    moveNext(index + 1);
                });
        }

        moveNext(0);
        window.closeMoveDialog();
    };

    window.navigateMoveUp = function () {
        // Stub — move dialog folder navigation
    };

    window.handleNewFolderInMove = function () {
        window.openNewFolderDialog();
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
        // Trigger production network info refresh
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

        // Click to trigger file input
        dropzone.addEventListener("click", function () {
            var fileInput = document.getElementById("fileInput");
            if (fileInput) fileInput.click();
        });
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
    // 6. INITIALIZATION — Kick off on DOM ready
    // =========================================================================

    function init() {
        setupDropzone();
        setupSearch();

        // Initial sync — if production already rendered files server-side
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

        // Initial clipboard sync
        if (typeof refreshClipboardHistory === "function") {
            setTimeout(function () {
                refreshClipboardHistory();
            }, 500);
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