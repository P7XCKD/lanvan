/**
 * @file selection-manager.js
 * @description Store-backed selection state manager & toolbar renderer.
 * @module SelectionManager
 */

(function (window) {
    'use strict';

    function updateSelectionToolbar() {
        var defaultContent = document.getElementById("toolbarDefaultContent");
        var selectionContent = document.getElementById("toolbarSelectionContent");
        if (!defaultContent || !selectionContent) return;

        var selected = window.prototypeSelectedItems || [];

        if (selected.length > 0) {
            defaultContent.style.display = "none";
            selectionContent.style.display = "flex";
            var isGrid = document.getElementById("nasFileList") && document.getElementById("nasFileList").classList.contains("grid-mode");
            selectionContent.innerHTML =
                '<div style="display:flex;align-items:center;gap:0.5rem;font-size:0.85rem;font-weight:700;color:var(--primary);">' +
                '<button class="btn-icon" onclick="clearSelection()" title="Clear selection" style="width:32px;height:32px;color:var(--primary);">' +
                '<i data-lucide="x" style="width:18px;height:18px;"></i></button>' +
                "<span>" +
                selected.length +
                " selected</span></div>" +
                '<div style="display:flex;align-items:center;gap:0.35rem;">' +
                '<button class="btn-icon" onclick="openRenameModal()" title="Rename" style="width:34px;height:34px;color:var(--primary);"><i data-lucide="pencil" style="width:16px;height:16px;"></i></button>' +
                '<button class="btn-icon" onclick="downloadSelected()" title="Download individually" style="width:34px;height:34px;color:var(--primary);"><i data-lucide="download" style="width:16px;height:16px;"></i></button>' +
                (selected.length > 1
                    ? '<button class="btn-icon" onclick="downloadSelectedAsZip()" title="Download as ZIP" style="width:34px;height:34px;color:var(--primary);"><i data-lucide="file-archive" style="width:16px;height:16px;"></i></button>'
                    : "") +
                '<button class="btn-icon" onclick="openMoveModal()" title="Move selected" style="width:34px;height:34px;color:var(--primary);"><i data-lucide="folder-input" style="width:16px;height:16px;"></i></button>' +
                '<button class="btn-icon" onclick="deleteSelected()" title="Delete selected" style="width:34px;height:34px;color:var(--danger);"><i data-lucide="trash-2" style="width:16px;height:16px;"></i></button>' +
                '<div class="view-switcher-pill" style="margin-left:0.5rem;">' +
                '<button id="listViewBtn" class="view-switcher-btn' + (isGrid ? '' : ' active') + '" onclick="setViewMode(\'list\')" title="List View"><i data-lucide="menu" style="width:16px;height:16px;"></i></button>' +
                '<button id="gridViewBtn" class="view-switcher-btn' + (isGrid ? ' active' : '') + '" onclick="setViewMode(\'grid\')" title="Grid View"><i data-lucide="layout-grid" style="width:16px;height:16px;"></i></button>' +
                '</div>' +
                "</div>";
        } else {
            defaultContent.style.display = "flex";
            selectionContent.style.display = "none";
            selectionContent.innerHTML = "";
        }
        if (window.lucide) lucide.createIcons();
    }

    function clearSelection() {
        window.prototypeSelectedItems = [];
        var items = document.querySelectorAll("#nasFileList .m3-list-item.selected");
        for (var i = 0; i < items.length; i++) {
            items[i].classList.remove("selected");
        }
        updateSelectionToolbar();
    }

    window.SelectionManager = {
        updateSelectionToolbar: updateSelectionToolbar,
        clearSelection: clearSelection
    };

    window.updateSelectionToolbar = updateSelectionToolbar;
    window.clearSelection = clearSelection;

})(window);
