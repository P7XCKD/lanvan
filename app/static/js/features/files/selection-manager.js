/**
 * Selection Manager
 *
 * Manages item selection state, selection toolbar controls, clipboard/file tab mode detection,
 * and bulk operations (rename, move, download, delete).
 */

(function (window) {
    'use strict';

    function detectSelectionRepresentation(selected) {
        if (!Array.isArray(selected) || selected.length === 0) return 'empty';
        var hasObject = false;
        var hasRelativePath = false;
        var hasBasename = false;
        var hasCanonical = false;
        var hasOther = false;
        for (var i = 0; i < selected.length; i++) {
            var v = selected[i];
            if (v && typeof v === 'object') {
                hasObject = true;
                continue;
            }
            if (typeof v !== 'string') {
                hasOther = true;
                continue;
            }
            var s = v.trim();
            if (!s) {
                hasOther = true;
                continue;
            }
            if (s.indexOf('/') !== -1 || s.indexOf('\\') !== -1) {
                if (typeof window.getCanonicalIdentity === 'function') {
                    var can = window.getCanonicalIdentity('', s);
                    hasCanonical = hasCanonical || (can === s.replace(/\\/g, '/').replace(/^\/+|\/+$/g, ''));
                }
                hasRelativePath = true;
            } else {
                hasBasename = true;
            }
        }
        var flags = [];
        if (hasObject) flags.push('object');
        if (hasCanonical) flags.push('canonical identity');
        if (hasRelativePath) flags.push('relative path');
        if (hasBasename) flags.push('basename');
        if (hasOther) flags.push('other');
        if (flags.length === 1) return flags[0];
        return 'mixed(' + flags.join(', ') + ')';
    }

    function logRealSelection(eventName) {
        try {
            var timestamp = new Date().toISOString();
            var currentFolder = typeof window.getCurrentFolderPath === 'function' ? window.getCurrentFolderPath() : (window.currentFolderPath || '');
            var selected = Array.isArray(window.selectedItems) ? window.selectedItems.slice() : [];
            var selector = '#nasFileList .m3-list-item.selected, .quick-card.selected, #clipboardHistory .clipboard-grid-card.selected';
            var selectedEls = document.querySelectorAll(selector);
            var details = [];
            for (var i = 0; i < selectedEls.length; i++) {
                var el = selectedEls[i];
                var name = el.getAttribute('data-filename') || '';
                var clipId = el.getAttribute('data-clipboard-id') || '';
                var parentPath = el.getAttribute('data-parent-path') || currentFolder || '';
                var idName = name || clipId;
                var identity = idName
                    ? (typeof window.getCanonicalIdentity === 'function' ? window.getCanonicalIdentity(parentPath, idName) : idName)
                    : '';
                console.log('name=' + name + ' data-filename=' + name + ' data-clipboard-id=' + clipId + ' parentPath=' + parentPath + ' identity=' + identity);
                details.push({
                    name: name,
                    dataFilename: name,
                    dataClipboardId: clipId,
                    parentPath: parentPath,
                    identity: identity
                });
            }

            var representation = detectSelectionRepresentation(selected);
            console.log('[REAL SELECTION]');
            console.log('timestamp=' + timestamp);
            console.log('currentFolder=' + currentFolder);
            console.log('selectedItems=', selected);
            console.log('representation=' + representation);

            if (typeof window.__lanvanForensicEmit === 'function') {
                window.__lanvanForensicEmit('selection', eventName || 'selection_changed', {
                    folder: currentFolder,
                    details: {
                        selectedItems: selected,
                        representation: representation,
                        selectedDomItems: details
                    }
                });
            }
        } catch (err) {
        }
    }

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
        logRealSelection('updateSelectionToolbar');
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

    function isItemUploading(filename) {
        if (!filename) return false;
        var lastRenderedFiles = window.lastRenderedFiles;
        if (lastRenderedFiles && lastRenderedFiles.length > 0) {
            var r = lastRenderedFiles.find(function (f) {
                return f && (f.name === filename || (typeof f === 'string' && f === filename));
            });
            var activeStatus = r && (r.uploadStatus === 'UPLOADING' || r.uploadStatus === 'QUEUED' ||
                r.uploadStatus === 'PROCESSING' || r.uploadStatus === 'PAUSED');
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

    window.SelectionManager = {
        updateSelectionToolbar: updateSelectionToolbar,
        clearSelection: clearSelection,
        selectAll: selectAll,
        initMarqueeSelection: initMarqueeSelection,
        handleListItemClick: handleListItemClick,
        isItemUploading: isItemUploading
    };

    window.updateSelectionToolbar = updateSelectionToolbar;
    window.clearSelection = clearSelection;
    window.selectAll = selectAll;
    window.handleListItemClick = handleListItemClick;

})(window);
