/**
 * Dropzone Manager Module
 *
 * Handles desktop drag-and-drop file upload overlay interactions (#nasDropzone)
 * and root application container (.android-app) context menu dispatching.
 */

(function (window) {
    'use strict';

    if (window.DropzoneManager && window.DropzoneManager._initialized) {
        return;
    }

    var _isInitialized = false;

    function setupDropzone() {
        if (_isInitialized) return;

        // Context menu handling on the entire app container (.android-app)
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
                        if (typeof window.syncSelectionDOM === "function") window.syncSelectionDOM();
                        if (typeof window.updateSelectionToolbar === "function") window.updateSelectionToolbar();
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
                    if (typeof window.openRowMenu === "function") {
                        window.openRowMenu(e, filename);
                    }
                    return;
                } else {
                    // Right-clicked on empty space — show generic menu
                    if (genericOps) genericOps.style.display = "block";
                    if (itemOps) itemOps.style.display = "none";
                    if (clipboardOps) clipboardOps.style.display = "none";
                    if (typeof window.clearSelection === "function") {
                        window.clearSelection();
                    }
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
                if (typeof window.addToUploadQueue === "function") {
                    window.addToUploadQueue(Array.from(files));
                    if (typeof window.showUploadManager === "function") window.showUploadManager();
                    if (typeof window.startNextUpload === "function") window.startNextUpload();
                }
            }
        });

        _isInitialized = true;
    }

    var DropzoneManager = Object.freeze({
        _initialized: true,
        init: setupDropzone,
        setupDropzone: setupDropzone
    });

    window.DropzoneManager = DropzoneManager;
    window.setupDropzone = setupDropzone;

})(window);
