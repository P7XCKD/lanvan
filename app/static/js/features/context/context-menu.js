/**
 * Context Menu
 *
 * Owns presentation-layer concerns for the right-click context menu:
 * DOM creation, positioning, lifecycle, and keyboard/outside-click dismiss.
 * Action triggers (delete, rename, download, share) delegate to existing
 * window handlers rather than implementing business logic directly.
 */

(function (window) {
    'use strict';

    if (window.ContextMenu) {
        return;
    }

    /**
     * Hides the context menu when it is present.
     */
    function closeContextMenu() {
        var menu = document.getElementById("contextMenu");
        if (menu) {
            menu.style.display = "none";
        }
    }

    /**
     * Finds an upload queue item matching a filename or path.
     * @param {string} filename - The filename, path, or queue identifier to match.
     * @return {Object|null} The matching upload queue item, or `null` when no match is found.
     */
    function getUploadQueueItem(filename) {
        if (!filename) return null;
        var state = window.LanvanStore ? window.LanvanStore.getState() : null;
        var queue = (state && state.uploadQueue) ? state.uploadQueue : (window.uploadQueue || []);
        var targetBase = String(filename).split("/").pop().split("\\").pop().trim().toLowerCase();
        for (var i = 0; i < queue.length; i++) {
            var item = queue[i];
            if (!item) continue;
            var names = [
                item.id,
                item.uploadId,
                item.fileName,
                item.name,
                item.file ? item.file.name : "",
                item.relativePath,
                typeof window.getItemName === "function" ? window.getItemName(item) : ""
            ];
            for (var j = 0; j < names.length; j++) {
                var n = names[j];
                if (!n) continue;
                var nStr = String(n).trim().toLowerCase();
                var nBase = nStr.split("/").pop().split("\\").pop();
                if (nStr === String(filename).trim().toLowerCase() || nBase === targetBase) {
                    return item;
                }
            }
        }
        return null;
    }

    /**
     * Pauses the upload associated with the selected context-menu item.
     */
    function handlePauseFromMenu() {
        closeContextMenu();
        var fn = window._contextMenuTarget;
        var qItem = getUploadQueueItem(fn);
        var targetId = qItem ? (qItem.id || qItem.uploadId) : fn;
        if (typeof window.pauseUpload === 'function') {
            window.pauseUpload(targetId);
        } else if (window.UploadEngine && typeof window.UploadEngine.pauseUploadItem === 'function') {
            window.UploadEngine.pauseUploadItem(targetId);
        }
    }

    /**
     * Resumes the upload associated with the selected context-menu target.
     */
    function handleResumeFromMenu() {
        closeContextMenu();
        var fn = window._contextMenuTarget;
        var qItem = getUploadQueueItem(fn);
        var targetId = qItem ? (qItem.id || qItem.uploadId) : fn;
        if (typeof window.resumeUpload === 'function') {
            window.resumeUpload(targetId);
        } else if (window.UploadEngine && typeof window.UploadEngine.resumeUploadItem === 'function') {
            window.UploadEngine.resumeUploadItem(targetId);
        }
    }

    /**
     * Cancels the upload associated with the selected context-menu item.
     */
    function handleCancelFromMenu() {
        closeContextMenu();
        var fn = window._contextMenuTarget;
        var qItem = getUploadQueueItem(fn);
        var targetId = qItem ? (qItem.id || qItem.uploadId) : fn;
        if (typeof window.cancelUpload === 'function') {
            window.cancelUpload(targetId);
        } else if (window.UploadEngine && typeof window.UploadEngine.cancelUploadItem === 'function') {
            window.UploadEngine.cancelUploadItem(targetId);
        }
    }

    /**
     * Opens the context menu for a file-list item and configures actions based on its state, type, and selection.
     * @param {MouseEvent} event - The event that triggered the context menu.
     * @param {string} filename - The target item's filename or path.
     */
    function openRowMenu(event, filename) {
        if (!event) return;
        event.stopPropagation();

        var menu = document.getElementById("contextMenu");
        var genericOps = document.getElementById("genericMenuOptions");
        var itemOps = document.getElementById("itemMenuOptions");
        if (!menu) return;

        if (genericOps) genericOps.style.display = "none";
        if (itemOps) itemOps.style.display = "block";

        window._contextMenuTarget = filename;
        window._contextMenuFolderPath = typeof window.getCurrentFolderPath === "function"
            ? window.getCurrentFolderPath()
            : (window.currentFolderPath || "");

        // Smart Selection Logic for Right-Click Context Menu:
        if (filename && typeof window.selectedItems !== 'undefined') {
            var alreadySelected = Array.isArray(window.selectedItems) && window.selectedItems.indexOf(filename) !== -1;
            if (!alreadySelected) {
                window.selectedItems = [filename];
            }
            var items = document.querySelectorAll("#nasFileList .m3-list-item, .quick-card");
            for (var i = 0; i < items.length; i++) {
                var itemFn = items[i].getAttribute("data-filename");
                if (itemFn && window.selectedItems.indexOf(itemFn) !== -1) {
                    items[i].classList.add("selected");
                } else {
                    items[i].classList.remove("selected");
                }
            }
            if (typeof window.updateSelectionToolbar === "function") {
                window.updateSelectionToolbar();
            }
        }

        var qItem = getUploadQueueItem(filename);
        var isUploading = false;
        if (qItem && (qItem.status === 'UPLOADING' || qItem.status === 'QUEUED' || qItem.status === 'PROCESSING' || qItem.status === 'PAUSED')) {
            isUploading = true;
        } else if (typeof window.isItemUploading === 'function' && window.isItemUploading(filename)) {
            isUploading = true;
        }

        var pauseItem = document.getElementById("pauseMenuItem");
        var resumeItem = document.getElementById("resumeMenuItem");
        var cancelItem = document.getElementById("cancelMenuItem");
        var renameItem = document.getElementById("renameMenuItem");
        var previewItem = document.getElementById("previewMenuItem");
        var historyItem = document.getElementById("historyMenuItem");
        var copyStreamLinkItem = document.getElementById("copyStreamLinkMenuItem");
        var downloadItem = document.getElementById("downloadMenuItem");
        var downloadZipItem = document.getElementById("downloadZipMenuItem");
        var moveItem = document.getElementById("moveMenuItem");
        var deleteItem = document.getElementById("deleteMenuItem");

        if (isUploading) {
            var qItem = getUploadQueueItem(filename);
            var isPaused = qItem && qItem.status === 'PAUSED';

            if (pauseItem) pauseItem.style.display = isPaused ? "none" : "flex";
            if (resumeItem) resumeItem.style.display = isPaused ? "flex" : "none";
            if (cancelItem) cancelItem.style.display = "flex";

            if (renameItem) renameItem.style.display = "none";
            if (previewItem) previewItem.style.display = "none";
            if (historyItem) historyItem.style.display = "none";
            if (copyStreamLinkItem) copyStreamLinkItem.style.display = "none";
            if (downloadItem) downloadItem.style.display = "none";
            if (downloadZipItem) downloadZipItem.style.display = "none";
            if (moveItem) moveItem.style.display = "none";
            if (deleteItem) deleteItem.style.display = "none";
        } else {
            if (pauseItem) pauseItem.style.display = "none";
            if (resumeItem) resumeItem.style.display = "none";
            if (cancelItem) cancelItem.style.display = "none";

            if (downloadItem) downloadItem.style.display = "flex";
            if (moveItem) moveItem.style.display = "flex";
            if (deleteItem) deleteItem.style.display = "flex";

            // Check if target item is a folder
            var isTargetFolder = false;
            var targetName = filename || (window.selectedItems && window.selectedItems[0]) || "";
            if (targetName) {
                var listEl = document.querySelector('#nasFileList [data-filename="' + targetName.replace(/"/g, '&quot;') + '"]');
                if (listEl) {
                    isTargetFolder = listEl.getAttribute("data-is-folder") === "1";
                } else if (typeof window.getDiskFileMetadata === 'function') {
                    var meta = window.getDiskFileMetadata(targetName, window._contextMenuFolderPath || "");
                    if (meta) isTargetFolder = !!meta.isFolder;
                }
            }

            var selectedCount = (window.selectedItems && window.selectedItems.length) || 1;
            var isSingle = selectedCount <= 1;

            if (renameItem) renameItem.style.display = "flex";

            // Preview item: HIDE if target is a folder OR if multiple items selected
            if (previewItem) previewItem.style.display = (isSingle && !isTargetFolder) ? "flex" : "none";

            var downloadText = document.getElementById("downloadMenuText");
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
            if (copyStreamLinkItem) {
                var ext = filename ? filename.split(".").pop().toLowerCase() : "";
                var videoExts = ["mp4", "webm", "mov", "mkv", "avi", "3gp", "m4v", "ts", "flv"];
                if (isSingle && videoExts.indexOf(ext) !== -1) {
                    copyStreamLinkItem.style.display = "flex";
                } else {
                    copyStreamLinkItem.style.display = "none";
                }
            }

            // Show/Hide "History" option if single item and target file has version history
            if (historyItem) {
                var hasV = false;
                var baseN = targetName ? targetName.split("/").pop().split("\\").pop() : "";
                var curFolder = typeof window.cleanFolderPath === "function" ? window.cleanFolderPath(window._contextMenuFolderPath || window.currentFolderPath) : (window._contextMenuFolderPath || window.currentFolderPath || "");
                var meta = typeof window.getFileMetadata === 'function' ? window.getFileMetadata(curFolder, baseN) : null;
                if (meta) {
                    hasV = !!meta.hasVersions;
                }
                historyItem.style.display = (isSingle && !isTargetFolder && hasV) ? "flex" : "none";
            }
        }

        if (typeof window.refreshLucideIcons === "function") {
            window.refreshLucideIcons(menu);
        }

        // Position at cursor, only reposition if menu won't fit
        var top = event.clientY;
        var left = event.clientX;
        if (top + 100 > window.innerHeight) top = window.innerHeight - 105;
        if (left + 190 > window.innerWidth) left = window.innerWidth - 200;
        menu.style.left = left + "px";
        menu.style.top = top + "px";
        menu.style.display = "block";
    }

    function handleOpenVersionHistoryFromMenu() {
        closeContextMenu();
        var targetName = window._contextMenuTarget || (window.selectedItems && window.selectedItems[0]);
        if (!targetName) return;
        var baseN = targetName.split("/").pop().split("\\").pop();
        var curFolder = typeof window.cleanFolderPath === "function" ? window.cleanFolderPath(window._contextMenuFolderPath || window.currentFolderPath) : (window._contextMenuFolderPath || window.currentFolderPath || "");
        var meta = typeof window.getFileMetadata === 'function' ? window.getFileMetadata(curFolder, baseN) : null;
        var lfId = meta ? meta.logicalFileId : ("lf_" + baseN);
        if (window.LanvanVersionHistoryPanel) {
            window.LanvanVersionHistoryPanel.open(lfId, baseN);
        }
    }

    // Dismiss listeners
    document.addEventListener("mousedown", function (e) {
        var menu = document.getElementById("contextMenu");
        if (menu && menu.style.display === "block") {
            if (!menu.contains(e.target)) {
                menu.style.display = "none";
            }
        }
    });

    document.addEventListener("keydown", function (e) {
        if (e.key === "Escape") {
            closeContextMenu();
        }
    });

    var ContextMenu = Object.freeze({
        openRowMenu: openRowMenu,
        close: closeContextMenu
    });

    window.ContextMenu = ContextMenu;
    window.openRowMenu = openRowMenu;
    window.closeContextMenu = closeContextMenu;
    window.handleOpenVersionHistoryFromMenu = handleOpenVersionHistoryFromMenu;
    window.handlePauseFromMenu = handlePauseFromMenu;
    window.handleResumeFromMenu = handleResumeFromMenu;
    window.handleCancelFromMenu = handleCancelFromMenu;

})(window);
