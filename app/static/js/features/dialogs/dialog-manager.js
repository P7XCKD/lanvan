/**
 * Dialog Manager
 *
 * Centralized manager for modal dialogs (new folder, connect QR, rename, move, delete).
 * Manages dialog display state, input focus, and folder operations.
 */

(function (window) {
    'use strict';

    // Move dialog operational state
    var moveCurrentPath = ["Home"];
    var moveTargetFolder = "Home";
    var moveSourceFolder = "";
    var itemsToMove = [];
    var isCreatingFolderInMove = false;

    function openNewFolderDialog() {
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
            requestAnimationFrame(function () {
                requestAnimationFrame(function () {
                    doFocusAndSelect();
                });
            });
            setTimeout(doFocusAndSelect, 50);
            setTimeout(doFocusAndSelect, 150);
        }
    }

    function closeNewFolderDialog() {
        var dialog = document.getElementById("newFolderDialog");
        if (dialog) dialog.style.display = "none";
    }

    function openConnectQrDialog() {
        var dialog = document.getElementById("connectQrDialog");
        if (!dialog) return;
        dialog.style.display = "flex";
        if (typeof renderDialogQR === "function") renderDialogQR();
        if (typeof showConnectionInfo === "function") {
            var protoAddr = document.getElementById("connectQrDialogAddress");
            if (protoAddr && window._currentNetworkInfo) {
                protoAddr.textContent = window._currentNetworkInfo.fullUrl || "";
            }
        }
    }

    function closeConnectQrDialog() {
        var dialog = document.getElementById("connectQrDialog");
        if (dialog) dialog.style.display = "none";
    }

    // --- Rename Modal Handlers ---
    function openRenameModal() {
        if (typeof window.closePreviewModal === "function") {
            window.closePreviewModal();
        }
        var targets = (window.selectedItems || []).slice();
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
    }

    function closeRenameDialog() {
        var dialog = document.getElementById("renameDialog");
        if (dialog) dialog.style.display = "none";
    }

    // --- Move Modal Handlers ---
    function openMoveModal() {
        if (typeof window.closePreviewModal === "function") {
            window.closePreviewModal();
        }
        var targets = (window.selectedItems || []).slice();
        if (targets.length === 0 && window._contextMenuTarget) {
            targets = [window._contextMenuTarget];
        }
        if (targets.length === 0) return;

        itemsToMove = targets.slice();
        isCreatingFolderInMove = false;
        moveSourceFolder = typeof window.cleanFolderPath === "function"
            ? window.cleanFolderPath(typeof window.getCurrentFolderPath === "function" ? window.getCurrentFolderPath() : (window.currentFolderPath || ""))
            : (typeof window.getCurrentFolderPath === "function" ? window.getCurrentFolderPath() : (window.currentFolderPath || ""));

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
    }

    function closeMoveDialog() {
        itemsToMove = [];
        isCreatingFolderInMove = false;
        moveSourceFolder = "";
        var dialog = document.getElementById("moveFileDialog");
        if (dialog) dialog.style.display = "none";
    }

    function navigateMoveUp() {
        if (moveCurrentPath.length > 1) {
            moveCurrentPath.pop();
            renderMoveFolderContents();
        }
    }

    function handleNewFolderInMove() {
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
    }

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
                    var fnEscaped = typeof window.escapeHtml === "function" ? window.escapeHtml(folderItem.name) : folderItem.name;
                    row.innerHTML =
                        '<div style="display:flex;align-items:center;gap:0.5rem;min-width:0;">' +
                        '<i data-lucide="folder" style="width:16px;height:16px;color:var(--primary);"></i>' +
                        '<span style="white-space:nowrap;overflow:hidden;text-overflow:ellipsis;font-weight:600;">' + fnEscaped + '</span>' +
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

    // --- Submit Dialog Operations ---
    function submitNewFolder() {
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
        var activeDir = typeof window.getCurrentFolderPath === "function" ? window.getCurrentFolderPath() : (window.currentFolderPath || "");
        if (isCreatingFolderInMove) {
            parentPath = moveCurrentPath.length > 1 ? moveCurrentPath.slice(1).join("/") : "";
        } else {
            if (activeDir && activeDir !== "Home") {
                if (activeDir.indexOf("Home/") === 0) {
                    parentPath = activeDir.substring(5);
                } else if (activeDir !== "Home") {
                    parentPath = activeDir;
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
                            fetchFilesData().then(function (fd) { if (typeof renderFileList === "function") renderFileList(fd); });
                        }
                    }
                } else {
                    if (typeof showToast === "function") showToast(data.msg || "Failed to create folder.", 4000);
                }
            })
            .catch(function () {
                if (typeof showToast === "function") showToast("Network error creating folder.", 4000);
            });

        closeNewFolderDialog();
    }

    function submitRename() {
        if (typeof window.closePreviewModal === "function") {
            window.closePreviewModal();
        }
        var itemsToRename = (window.selectedItems || []).slice();
        if (itemsToRename.length === 0 && window._contextMenuTarget) {
            itemsToRename = [window._contextMenuTarget];
        }
        if (itemsToRename.length === 0) {
            closeRenameDialog();
            return;
        }

        var newBaseName = (document.getElementById("renameInput") || {}).value;
        if (!newBaseName) {
            closeRenameDialog();
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
                if (typeof window.clearSelection === "function") window.clearSelection();
                if (typeof window.requestSafeVisibleFilesRefresh === "function") {
                    window.requestSafeVisibleFilesRefresh(120);
                } else if (typeof fetchFilesData === "function") {
                    fetchFilesData().then(function (fd) { if (typeof renderFileList === "function") renderFileList(fd); });
                }
                return;
            }

            var oldName = itemsToRename[index];

            // Determine if the item is a folder
            var isFolder = false;
            var listEl = document.querySelector('#nasFileList [data-filename="' + oldName.replace(/"/g, '&quot;') + '"]');
            if (listEl) {
                isFolder = listEl.getAttribute("data-is-folder") === "1";
            } else if (typeof getDiskFileMetadata === "function") {
                var meta = getDiskFileMetadata(oldName, typeof window.cleanFolderPath === "function" ? window.cleanFolderPath(window._contextMenuFolderPath || window.currentFolderPath) : (window._contextMenuFolderPath || window.currentFolderPath || ""));
                if (meta) isFolder = !!(meta.isFolder || meta.is_dir);
            }

            var nameToUse = "";

            if (itemsToRename.length === 1) {
                if (isFolder) {
                    nameToUse = newBaseName;
                } else {
                    var oldDot = oldName.lastIndexOf(".");
                    var oldExt = oldDot > 0 ? oldName.substring(oldDot) : "";
                    var newDot = newBaseName.lastIndexOf(".");

                    if (newDot > 0) {
                        nameToUse = newBaseName;
                    } else {
                        nameToUse = newBaseName + oldExt;
                    }
                }
            } else {
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
            formData.append("new_name", nameToUse);
            var parentPath = typeof window.cleanFolderPath === "function" ? window.cleanFolderPath(window.currentFolderPath) : (window.currentFolderPath || "");
            if (parentPath && parentPath !== "Home") {
                formData.append("parent_path", parentPath);
            }
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
                            if (typeof saveUploadQueueToStorage === "function") saveUploadQueueToStorage();
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
        closeRenameDialog();
    }

    function submitMove() {
        var filesToMove = (itemsToMove.length > 0 ? itemsToMove : (window.selectedItems || [])).slice();
        if (filesToMove.length === 0) {
            closeMoveDialog();
            return;
        }

        var destination = moveCurrentPath.length > 1 ? moveCurrentPath.slice(1).join("/") : "";
        var sourceFolder = moveSourceFolder || (typeof window.cleanFolderPath === "function"
            ? window.cleanFolderPath(typeof window.getCurrentFolderPath === "function" ? window.getCurrentFolderPath() : (window.currentFolderPath || ""))
            : (typeof window.getCurrentFolderPath === "function" ? window.getCurrentFolderPath() : (window.currentFolderPath || "")));

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
                    if (sourceFolder) formData.append("source_path", sourceFolder);
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
                if (typeof window.clearSelection === "function") window.clearSelection();
                itemsToMove = [];
                if (typeof refreshFileList === "function") refreshFileList();
                if (typeof window.requestSafeVisibleFilesRefresh === "function") {
                    window.requestSafeVisibleFilesRefresh(120);
                } else if (typeof fetchFilesData === "function") {
                    fetchFilesData().then(function (fd) { if (typeof renderFileList === "function") renderFileList(fd); });
                }
                closeMoveDialog();
            })
            .catch(function () {
                if (typeof showToast === "function") showToast("Failed to move file(s).", 4000);
                closeMoveDialog();
            });
    }

    function deleteSelected() {
        if (typeof window.closePreviewModal === "function") {
            window.closePreviewModal();
        }
        var itemsToDelete = [];
        var target = window._contextMenuTarget || "";
        var activeSelected = window.selectedItems || [];

        if (activeSelected.length > 0) {
            if (target && activeSelected.indexOf(target) !== -1) {
                itemsToDelete = activeSelected.slice();
            } else if (!target) {
                itemsToDelete = activeSelected.slice();
            } else {
                itemsToDelete = [target];
            }
        } else if (target) {
            itemsToDelete = [target];
        }

        window._contextMenuTarget = "";
        if (itemsToDelete.length === 0) return;

        var isClipboardDelete = window.activeTab === "clipboard" || (!isNaN(itemsToDelete[0]) && !isNaN(parseFloat(itemsToDelete[0])));
        if (isClipboardDelete) {
            var completedCb = 0;
            Promise.all(itemsToDelete.map(function (cbId) {
                return fetch('/api/clipboard/delete/' + cbId, { method: 'DELETE' })
                    .then(function (res) { if (res.ok) completedCb++; });
            })).then(function () {
                if (typeof showToast === "function") showToast("Deleted " + completedCb + " clipboard item(s).", 3000);
                if (typeof window.clearSelection === "function") window.clearSelection();
                if (typeof refreshClipboardHistory === "function") refreshClipboardHistory();
            });
            return;
        }

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
                if (typeof window.clearSelection === "function") window.clearSelection();
                if (typeof refreshFileList === "function") refreshFileList();
                if (typeof window.requestSafeVisibleFilesRefresh === "function") {
                    window.requestSafeVisibleFilesRefresh(120);
                } else if (typeof fetchFilesData === "function") {
                    fetchFilesData().then(function (fd) { if (typeof renderFileList === "function") renderFileList(fd); });
                }
                return;
            }

            var filename = itemsToDelete[index];
            if (window._recentlyCreatedFolders) {
                delete window._recentlyCreatedFolders[filename];
            }

            window._cancelledFilesMap = window._cancelledFilesMap || {};
            var activeDir = typeof window.getCurrentFolderPath === "function" ? window.getCurrentFolderPath() : (window.currentFolderPath || "");
            var parentPath = (activeDir === "Home" || activeDir === "Home/" || !activeDir) ? "" : activeDir;
            var cleanParent = parentPath.replace(/^Home\/?/, "");
            var fullRelPath = cleanParent ? (cleanParent + "/" + filename) : filename;
            window._cancelledFilesMap[fullRelPath] = true;
            window._cancelledFilesMap["Home/" + fullRelPath] = true;
            window._cancelledFilesMap[filename] = true;

            if (Array.isArray(window.uploadQueue)) {
                var getCanonId = window.getCanonicalIdentity || function (p, n) {
                    var cp = typeof window.cleanFolderPath === "function" ? window.cleanFolderPath(p) : (p || "");
                    var cn = String(n || "").trim().replace(/\\/g, "/").replace(/^\/+|\/+$/g, "");
                    return cp ? (cp + "/" + cn) : cn;
                };
                var targetCanonical = getCanonId(cleanParent, filename);

                window.uploadQueue.forEach(function (qi) {
                    if (!qi) return;
                    var qiName = (qi.fileName || (qi.file && qi.file.name) || qi.name || "");
                    var qiFolder = (qi.targetDir || qi.parent_path || qi.folder || "");
                    var qiCanonical = getCanonId(qiFolder, qiName);
                    var cleanQiFolder = typeof window.cleanFolderPath === "function" ? window.cleanFolderPath(qiFolder) : qiFolder.replace(/^Home\/?/, "");

                    var isExactMatch = (qiCanonical === targetCanonical);
                    var isSubFolderMatch = (cleanQiFolder === targetCanonical || cleanQiFolder.startsWith(targetCanonical + "/"));

                    if (isExactMatch || isSubFolderMatch) {
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

            var isFolder = false;
            var listItems = document.querySelectorAll('#nasFileList .m3-list-item');
            for (var k = 0; k < listItems.length; k++) {
                var itemFn = listItems[k].getAttribute("data-filename");
                if (itemFn === filename || (typeof escapeHtml === "function" && itemFn === escapeHtml(filename))) {
                    isFolder = listItems[k].getAttribute("data-is-folder") === "1";
                    break;
                }
            }
            if (!isFolder && typeof getDiskFileMetadata === "function") {
                var foundData = getDiskFileMetadata(filename, typeof window.cleanFolderPath === "function" ? window.cleanFolderPath(window._contextMenuFolderPath || activeDir) : (window._contextMenuFolderPath || activeDir || ""));
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

            var canonicalIdentity = (typeof window.getCanonicalIdentity === 'function')
                ? window.getCanonicalIdentity(cleanParent, filename)
                : (cleanParent ? (cleanParent + '/' + filename) : filename);
            var formEntries = [];
            try {
                formData.forEach(function (value, key) {
                    formEntries.push({ key: key, value: value });
                });
            } catch (e) {
            }
            console.log('[REAL DELETE REQUEST]');
            console.log('timestamp=' + new Date().toISOString());
            console.log('currentFolder=' + activeDir);
            console.log('filename=' + filename);
            console.log('parent_path=' + cleanParent);
            console.log('canonicalIdentity=' + canonicalIdentity);
            console.log('URL=' + url);
            console.log('HTTP method=' + method);
            console.log('payload=', formEntries);
            if (typeof window.__lanvanForensicEmit === 'function') {
                window.__lanvanForensicEmit('delete_request', 'send', {
                    folder: activeDir || '',
                    name: filename,
                    identity: canonicalIdentity,
                    details: {
                        parent_path: cleanParent,
                        url: url,
                        method: method,
                        payload: formEntries
                    }
                });
            }
            if (typeof window.__lanvanForensicDumpUploadQueue === 'function') {
                window.__lanvanForensicDumpUploadQueue();
            }

            var xhr = new XMLHttpRequest();
            xhr.open(method, url);
            xhr.onload = function () {
                completed++;
                if (typeof window.triggerInstantUIUpdate === "function") window.triggerInstantUIUpdate();
                deleteNext(index + 1);
            };
            xhr.onerror = function () {
                completed++;
                if (typeof window.triggerInstantUIUpdate === "function") window.triggerInstantUIUpdate();
                deleteNext(index + 1);
            };
            xhr.send(formData);
        }

        deleteNext(0);
    }

    // --- Module Export & Window Compatibility Registration ---
    window.DialogManager = {
        openNewFolderDialog: openNewFolderDialog,
        closeNewFolderDialog: closeNewFolderDialog,
        openConnectQrDialog: openConnectQrDialog,
        closeConnectQrDialog: closeConnectQrDialog,
        openRenameModal: openRenameModal,
        closeRenameDialog: closeRenameDialog,
        closeRenameModal: closeRenameDialog,
        openMoveModal: openMoveModal,
        closeMoveDialog: closeMoveDialog,
        closeMoveModal: closeMoveDialog,
        navigateMoveUp: navigateMoveUp,
        handleNewFolderInMove: handleNewFolderInMove,
        renderMoveFolderContents: renderMoveFolderContents,
        submitNewFolder: submitNewFolder,
        submitRename: submitRename,
        submitMove: submitMove,
        deleteSelected: deleteSelected
    };

    window.openNewFolderDialog = openNewFolderDialog;
    window.closeNewFolderDialog = closeNewFolderDialog;
    window.openConnectQrDialog = openConnectQrDialog;
    window.closeConnectQrDialog = closeConnectQrDialog;
    window.openRenameModal = openRenameModal;
    window.closeRenameDialog = closeRenameDialog;
    window.closeRenameModal = closeRenameDialog;
    window.openMoveModal = openMoveModal;
    window.closeMoveDialog = closeMoveDialog;
    window.closeMoveModal = closeMoveDialog;
    window.navigateMoveUp = navigateMoveUp;
    window.handleNewFolderInMove = handleNewFolderInMove;
    window.renderMoveFolderContents = renderMoveFolderContents;
    window.submitNewFolder = submitNewFolder;
    window.submitRename = submitRename;
    window.submitMove = submitMove;
    window.deleteSelected = deleteSelected;

})(window);
