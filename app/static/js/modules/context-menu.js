/**
 * @file context-menu.js
 * @description Context Menu presentation, positioning, rendering, and keyboard/outside-click dismiss.
 * @module ContextMenu
 * 
 * Rules:
 * - Owns ONLY presentation (DOM creation, positioning, lifecycle, keyboard handling).
 * - Action triggers (delete, rename, download, share) dispatch to existing window handlers.
 */

(function (window) {
    'use strict';

    if (window.ContextMenu) {
        return;
    }

    function closeContextMenu() {
        var menu = document.getElementById("contextMenu");
        if (menu) {
            menu.style.display = "none";
        }
    }

    function openRowMenu(event, filename) {
        if (!event) return;
        event.stopPropagation();

        if (typeof window.isItemUploading === 'function' && window.isItemUploading(filename)) {
            if (event.preventDefault) event.preventDefault();
            closeContextMenu();
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
        // If filename is NOT currently part of selectedItems, select ONLY filename.
        // If filename IS ALREADY in selectedItems (multi-selection), PRESERVE ALL selected items!
        if (filename && typeof window.selectedItems !== 'undefined') {
            var alreadySelected = Array.isArray(window.selectedItems) && window.selectedItems.indexOf(filename) !== -1;
            if (!alreadySelected) {
                window.selectedItems = [filename];
            }
            // Sync visual DOM selection state across list items and quick cards
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

        // Check if target item is a folder
        var isTargetFolder = false;
        var targetName = filename || (window.selectedItems && window.selectedItems[0]) || "";
        if (targetName) {
            var listEl = document.querySelector('#nasFileList [data-filename="' + targetName.replace(/"/g, '&quot;') + '"]');
            if (listEl) {
                isTargetFolder = listEl.getAttribute("data-is-folder") === "1";
            } else if (typeof window.getDiskFileMetadata === 'function') {
                var meta = window.getDiskFileMetadata(targetName);
                if (meta) isTargetFolder = !!meta.isFolder;
            }
        }

        var selectedCount = (window.selectedItems && window.selectedItems.length) || 1;
        var isSingle = selectedCount <= 1;

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

        // Show/Hide "History" option if single item and target file has version history
        var historyItem = document.getElementById("historyMenuItem");
        if (historyItem) {
            var hasV = false;
            var baseN = targetName ? targetName.split("/").pop().split("\\").pop() : "";
            if (window._fileMetadataMap) {
                var meta = window._fileMetadataMap[targetName] || window._fileMetadataMap[baseN];
                if (meta) {
                    hasV = !!meta.hasVersions;
                }
            }
            historyItem.style.display = (isSingle && !isTargetFolder && hasV) ? "flex" : "none";
            if (hasV && typeof window.refreshLucideIcons === "function") {
                window.refreshLucideIcons(historyItem);
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
    }

    function handleOpenVersionHistoryFromMenu() {
        closeContextMenu();
        var targetName = window._contextMenuTarget || (window.selectedItems && window.selectedItems[0]);
        if (!targetName) return;
        var baseN = targetName.split("/").pop().split("\\").pop();
        var meta = window._fileMetadataMap && (window._fileMetadataMap[targetName] || window._fileMetadataMap[baseN]);
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

})(window);
