/**
 * Selection Manager
 *
 * Manages item selection state, selection toolbar controls, clipboard/file tab mode detection,
 * and bulk operations (rename, move, download, delete).
 */

(function (window) {
    'use strict';

    function isClipboardTabActive() {
        var attr = document.documentElement.getAttribute("data-active-tab");
        if (attr) return attr === "clipboard";
        if (window.activeTab) return window.activeTab === "clipboard";
        var clipView = document.getElementById("clipboardView");
        if (clipView) {
            return window.getComputedStyle(clipView).display !== "none";
        }
        return false;
    }

    function syncSelectionDOM() {
        var selected = window.selectedItems || [];
        var items = document.querySelectorAll("#nasFileList .m3-list-item, .quick-card, #clipboardHistory .clipboard-grid-card");
        for (var i = 0; i < items.length; i++) {
            var key = items[i].getAttribute("data-filename") || items[i].getAttribute("data-clipboard-id");
            if (key && (selected.indexOf(key) !== -1 || selected.indexOf(Number(key)) !== -1)) {
                items[i].classList.add("selected");
            } else {
                items[i].classList.remove("selected");
            }
        }
    }

    function updateSelectionToolbar() {
        syncSelectionDOM();
        var defaultContent = document.getElementById("toolbarDefaultContent");
        var selectionContent = document.getElementById("toolbarSelectionContent");
        if (!defaultContent || !selectionContent) return;

        var selected = window.selectedItems || [];

        if (selected.length > 0) {
            defaultContent.style.display = "none";
            selectionContent.style.display = "flex";
            var isClipboardMode = isClipboardTabActive() || (!isNaN(selected[0]) && !isNaN(parseFloat(selected[0])));
            
            if (isClipboardMode) {
                selectionContent.innerHTML =
                    '<div style="display:flex;align-items:center;gap:0.5rem;font-size:0.85rem;font-weight:700;color:var(--primary);">' +
                    '<button class="btn-icon" onclick="clearSelection()" title="Clear selection" style="width:32px;height:32px;color:var(--primary);">' +
                    '<i data-lucide="x" style="width:18px;height:18px;"></i></button>' +
                    "<span>" +
                    selected.length +
                    " selected</span></div>" +
                    '<div style="display:flex;align-items:center;gap:0.35rem;">' +
                    '<button class="btn-icon" onclick="downloadSelectedClipboard()" title="' + (selected.length > 1 ? 'Download all as ZIP' : 'Download item') + '" style="width:34px;height:34px;color:var(--primary);"><i data-lucide="download" style="width:16px;height:16px;"></i></button>' +
                    '<button class="btn-icon" onclick="deleteSelected()" title="Delete selected" style="width:34px;height:34px;color:var(--danger);"><i data-lucide="trash-2" style="width:16px;height:16px;"></i></button>' +
                    "</div>";
            } else {
                var isGrid = document.getElementById("nasFileList") && document.getElementById("nasFileList").classList.contains("grid-mode");
                selectionContent.innerHTML =
                    '<div style="display:flex;align-items:center;gap:0.35rem;flex-wrap:wrap;">' +
                    '<button class="btn-icon" onclick="clearSelection()" title="Clear selection" style="width:30px;height:30px;color:var(--primary);">' +
                    '<i data-lucide="x" style="width:16px;height:16px;"></i></button>' +
                    '<span style="font-size:0.8rem;font-weight:700;color:var(--primary);white-space:nowrap;">' +
                    selected.length +
                    " selected</span></div>" +
                    '<div style="display:flex;align-items:center;gap:0.25rem;flex-wrap:wrap;">' +
                    '<button class="btn-icon" onclick="openRenameModal()" title="Rename" style="width:32px;height:32px;color:var(--primary);"><i data-lucide="pencil" style="width:15px;height:15px;"></i></button>' +
                    '<button class="btn-icon" onclick="downloadSelected()" title="Download individually" style="width:32px;height:32px;color:var(--primary);"><i data-lucide="download" style="width:15px;height:15px;"></i></button>' +
                    (selected.length > 1
                        ? '<button class="btn-icon" onclick="downloadSelectedAsZip()" title="Download as ZIP" style="width:32px;height:32px;color:var(--primary);"><i data-lucide="file-archive" style="width:15px;height:15px;"></i></button>'
                        : "") +
                    '<button class="btn-icon" onclick="openMoveModal()" title="Move selected" style="width:32px;height:32px;color:var(--primary);"><i data-lucide="folder-input" style="width:15px;height:15px;"></i></button>' +
                    '<button class="btn-icon" onclick="deleteSelected()" title="Delete selected" style="width:32px;height:32px;color:var(--danger);"><i data-lucide="trash-2" style="width:15px;height:15px;"></i></button>' +
                    "</div>";
            }
        } else {
            defaultContent.style.display = "flex";
            selectionContent.style.display = "none";
            selectionContent.innerHTML = "";
        }
        if (window.lucide) lucide.createIcons();
    }

    function clearSelection() {
        window.selectedItems = [];
        // Keep backward-compat alias so older callers using window.prototypeSelectedItems still work
        window.prototypeSelectedItems = window.selectedItems;
        syncSelectionDOM();
        updateSelectionToolbar();
    }

    // --- Production-Grade Marquee Selection System ---
    function initMarqueeSelection() {
        var DRAG_THRESHOLD = 5;
        var startX = 0;
        var startY = 0;
        var currentX = 0;
        var currentY = 0;
        var isMarqueeActive = false;
        var rafPending = false;
        var cachedItems = [];
        var marqueeBox = null;

        function getMarqueeElement() {
            if (!marqueeBox) {
                marqueeBox = document.createElement("div");
                marqueeBox.className = "drag-selection-marquee";
                marqueeBox.style.cssText = "position:fixed; border:1px solid #3b82f6; background:rgba(59, 130, 246, 0.18); border-radius:4px; z-index:9999; pointer-events:none; display:none;";
                document.body.appendChild(marqueeBox);
            }
            return marqueeBox;
        }

        function cacheItemRectangles() {
            var selector = isClipboardTabActive()
                ? "#clipboardHistory .clipboard-grid-card"
                : "#nasFileList .m3-list-item, .quick-card";
            var elements = document.querySelectorAll(selector);
            cachedItems = [];
            for (var i = 0; i < elements.length; i++) {
                var key = elements[i].getAttribute("data-filename") || elements[i].getAttribute("data-clipboard-id");
                if (key) {
                    cachedItems.push({
                        name: key,
                        rect: elements[i].getBoundingClientRect()
                    });
                }
            }
        }

        function updateMarqueeFrame() {
            rafPending = false;
            if (!isMarqueeActive) return;

            var box = getMarqueeElement();
            box.style.display = "block";

            var rectLeft = Math.min(startX, currentX);
            var rectTop = Math.min(startY, currentY);
            var rectWidth = Math.abs(currentX - startX);
            var rectHeight = Math.abs(currentY - startY);

            box.style.left = rectLeft + "px";
            box.style.top = rectTop + "px";
            box.style.width = rectWidth + "px";
            box.style.height = rectHeight + "px";

            // Fast 60 FPS hit test against cached item rects
            var nextSelection = [];
            for (var i = 0; i < cachedItems.length; i++) {
                var item = cachedItems[i];
                var r = item.rect;
                var overlaps = !(rectLeft > r.right ||
                    rectLeft + rectWidth < r.left ||
                    rectTop > r.bottom ||
                    rectTop + rectHeight < r.top);
                if (overlaps) {
                    nextSelection.push(item.name);
                }
            }

            // Atomic store update: replace selection array directly to trigger window setter
            window.selectedItems = nextSelection;
            updateSelectionToolbar();
        }

        function suppressNextClick(e) {
            e.stopPropagation();
            e.preventDefault();
            window.removeEventListener("click", suppressNextClick, true);
        }

        document.addEventListener("pointerdown", function (e) {
            // Only primary pointer (left click / touch)
            if (e.button !== 0 && e.pointerType === "mouse") return;
            // Ignore click on interactive buttons, inputs, links, context menus or sidebar
            if (e.target.closest("button, a, input, select, textarea, .custom-context-menu, [data-action], .sidebar-item, .brand-logo")) return;
            // Only activate if inside fileView, clipboardView, or clipboardHistory
            if (!e.target.closest("#fileView") && !e.target.closest("#clipboardView") && !e.target.closest("#clipboardHistory") && !e.target.closest("#fileListSection")) return;

            startX = e.clientX;
            startY = e.clientY;
            currentX = e.clientX;
            currentY = e.clientY;
            isMarqueeActive = false;

            function onPointerMove(ev) {
                currentX = ev.clientX;
                currentY = ev.clientY;
                var dx = currentX - startX;
                var dy = currentY - startY;

                if (!isMarqueeActive && Math.sqrt(dx * dx + dy * dy) >= DRAG_THRESHOLD) {
                    isMarqueeActive = true;
                    if (window.getSelection) window.getSelection().removeAllRanges();
                    cacheItemRectangles();
                }

                if (isMarqueeActive) {
                    ev.preventDefault();
                    if (window.getSelection) window.getSelection().removeAllRanges();

                    if (!rafPending) {
                        rafPending = true;
                        requestAnimationFrame(updateMarqueeFrame);
                    }
                }
            }

            function onPointerUp(ev) {
                window.removeEventListener("pointermove", onPointerMove, true);
                window.removeEventListener("pointerup", onPointerUp, true);
                window.removeEventListener("pointercancel", onPointerUp, true);

                if (window.getSelection) window.getSelection().removeAllRanges();
                if (marqueeBox) {
                    marqueeBox.style.display = "none";
                }

                if (isMarqueeActive) {
                    // Instantly register capture-phase click suppressor to consume the upcoming click
                    window.addEventListener("click", suppressNextClick, true);
                    // Fallback cleanup of suppressor after 200ms if no click fires
                    setTimeout(function () {
                        window.removeEventListener("click", suppressNextClick, true);
                    }, 200);
                    isMarqueeActive = false;
                }
            }

            window.addEventListener("pointermove", onPointerMove, true);
            window.addEventListener("pointerup", onPointerUp, true);
            window.addEventListener("pointercancel", onPointerUp, true);
        });
    }

    function selectAll() {
        var isClipboardMode = isClipboardTabActive();
        var selector = isClipboardMode
            ? "#clipboardHistory .clipboard-grid-card"
            : "#nasFileList .m3-list-item";
        var items = document.querySelectorAll(selector);
        var allSelected = [];
        for (var i = 0; i < items.length; i++) {
            var key = items[i].getAttribute("data-filename") || items[i].getAttribute("data-clipboard-id");
            if (key) {
                allSelected.push(key);
                items[i].classList.add("selected");
            }
        }
        window.selectedItems = allSelected;
        if (window.LanvanStore && typeof window.LanvanStore.dispatch === "function") {
            window.LanvanStore.dispatch({ type: 'SET_SELECTION', payload: allSelected });
        }
        updateSelectionToolbar();
    }

    document.addEventListener("keydown", function (e) {
        if (document.activeElement && (
            document.activeElement.tagName === "INPUT" ||
            document.activeElement.tagName === "TEXTAREA" ||
            document.activeElement.isContentEditable
        )) {
            return;
        }

        var modal = document.getElementById("lanvanPreviewModal");
        if (modal && modal.style.display !== "none" && modal.style.display !== "") {
            return;
        }

        if ((e.ctrlKey || e.metaKey) && (e.key === "a" || e.key === "A" || e.keyCode === 65)) {
            e.preventDefault();
            e.stopPropagation();
            selectAll();
        } else if (e.key === "Delete" || e.key === "Del") {
            if (window.selectedItems && window.selectedItems.length > 0) {
                e.preventDefault();
                if (typeof window.deleteSelected === "function") {
                    window.deleteSelected();
                }
            }
        } else if (e.key === "F2") {
            if (window.selectedItems && window.selectedItems.length > 0) {
                e.preventDefault();
                if (typeof window.openRenameModal === "function") {
                    window.openRenameModal();
                }
            }
        } else if (e.key === "Escape" || e.keyCode === 27) {
            if (window.selectedItems && window.selectedItems.length > 0) {
                e.preventDefault();
                clearSelection();
            }
        }
    });

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", initMarqueeSelection);
    } else {
        initMarqueeSelection();
    }

    window.SelectionManager = {
        updateSelectionToolbar: updateSelectionToolbar,
        clearSelection: clearSelection,
        selectAll: selectAll,
        initMarqueeSelection: initMarqueeSelection
    };

    window.updateSelectionToolbar = updateSelectionToolbar;
    window.clearSelection = clearSelection;
    window.selectAll = selectAll;

})(window);
