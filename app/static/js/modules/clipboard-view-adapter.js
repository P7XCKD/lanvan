/**
 * Clipboard View Adapter
 *
 * Manages rendering of production clipboard items into the #clipboardHistory DOM container,
 * clipboard item selection toggling, batch/individual downloads, deletion, and input handlers.
 */

(function (window) {
    'use strict';

    /**
     * Sync clipboard history view from production #clipboardHistoryContent DOM.
     */
    function syncClipboardView() {
        var clipboardContainer = document.getElementById("clipboardHistory");
        if (!clipboardContainer) return;

        var items = window.clipboardHistoryData || [];

        if (!Array.isArray(items) || items.length === 0) {
            clipboardContainer.innerHTML =
                '<div style="grid-column: 1 / -1; width: 100%; display: flex; flex-direction: column; align-items: center; justify-content: center; text-align: center; padding: 3rem 1rem; color: var(--text-muted);">' +
                '<i data-lucide="clipboard-x" style="width: 44px; height: 44px; margin-bottom: 0.75rem; stroke-width: 1.5; opacity: 0.7;"></i>' +
                '<div style="font-weight: 600; font-size: 0.95rem; color: var(--text-color);">No clipboard items yet</div>' +
                '<div style="font-size: 0.8rem; margin-top: 0.35rem;">Add content above to get started</div>' +
                '</div>';
            if (window.lucide) lucide.createIcons();
            return;
        }

        var html = "";
        for (var i = 0; i < items.length; i++) {
            var item = items[i];
            var isFile = item.type === "file";
            var isImage = isFile && item.content_type === "image";
            var sizeStr = item.size ? (typeof formatFileSize === 'function' ? formatFileSize(item.size) : item.size) : "";
            var subtitle = sizeStr || "";
            var itemId = item.id;

            var copyAction =
                '<button class="btn-icon" onclick="event.stopPropagation();copyClipboardText(' + itemId + ');" title="Copy text / link" style="width:28px;height:28px;padding:0;">' +
                '<i data-lucide="copy" style="width:15px;height:15px;"></i></button>';

            var downloadAction =
                '<button class="btn-icon" onclick="event.stopPropagation();downloadClipboardItem(' + itemId + ');" title="Download item" style="width:28px;height:28px;padding:0;">' +
                '<i data-lucide="download" style="width:15px;height:15px;"></i></button>';

            var removeAction =
                '<button class="btn-icon" onclick="event.stopPropagation();removeClipboardItem(' + itemId + ');" title="Delete item" style="width:28px;height:28px;padding:0;color:var(--danger);">' +
                '<i data-lucide="trash-2" style="width:15px;height:15px;"></i></button>';

            var fnEscape = typeof window.escapeHtml === 'function' ? window.escapeHtml : function(s){ return s; };

            if (isImage) {
                var imgTitle = "Pasted Image";
                if (item.filename && !item.filename.startsWith("clipboard-image") && !item.filename.startsWith("Pasted_Image")) {
                    imgTitle = item.filename;
                }

                var isSelected = Array.isArray(window.selectedItems) && (window.selectedItems.indexOf(itemId) !== -1 || window.selectedItems.indexOf(String(itemId)) !== -1);
                var selectedClass = isSelected ? " selected" : "";

                html +=
                    '<div class="clipboard-grid-card' + selectedClass + '" data-clipboard-id="' + itemId + '" onclick="toggleClipboardSelection(event, ' + itemId + ')">' +
                    '<div class="clipboard-card-head">' +
                    '<div style="display:flex;align-items:center;gap:0.5rem;min-width:0;flex:1;">' +
                    '<div class="avatar-icon avatar-image" style="width:32px;height:32px;border-radius:8px;flex-shrink:0;"><i data-lucide="image" style="width:16px;height:16px;"></i></div>' +
                    '<div style="display:flex;flex-direction:column;min-width:0;flex:1;">' +
                    '<span style="font-weight:600;font-size:0.85rem;color:var(--text-color);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;user-select:text;">' + fnEscape(imgTitle) + '</span>' +
                    '<span style="font-size:0.7rem;color:var(--text-muted);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;user-select:text;">' + fnEscape(subtitle) + '</span>' +
                    '</div>' +
                    '</div>' +
                    '<div style="display:flex;align-items:center;gap:0.15rem;flex-shrink:0;" onclick="event.stopPropagation()">' +
                    downloadAction +
                    removeAction +
                    '</div>' +
                    '</div>' +
                    '<div class="clipboard-card-body" style="cursor:pointer;" onclick="event.stopPropagation(); showImagePreview(\'/api/clipboard/get/' + itemId + '\', \'' + fnEscape(imgTitle) + '\')">' +
                    '<img src="/api/clipboard/get/' + itemId + '" alt="' + fnEscape(imgTitle) + '" style="width:100%;height:100%;object-fit:cover;display:block;" />' +
                    '</div>' +
                    '</div>';
            } else {
                var isUrl = item.content_type === "url";
                var avatarClass = isFile ? "avatar-doc" : (isUrl ? "avatar-audio" : "avatar-doc");
                var iconName = isFile ? "file-text" : (isUrl ? "link" : "file-text");
                var displayTitle = isFile ? (item.filename || "File") : (isUrl ? "URL" : "Text");
                var fullText = item.data || item.preview || "";

                var isSelected = Array.isArray(window.selectedItems) && (window.selectedItems.indexOf(itemId) !== -1 || window.selectedItems.indexOf(String(itemId)) !== -1);
                var selectedClass = isSelected ? " selected" : "";

                html +=
                    '<div class="clipboard-grid-card' + selectedClass + '" data-clipboard-id="' + itemId + '" onclick="toggleClipboardSelection(event, ' + itemId + ')">' +
                    '<div class="clipboard-card-head">' +
                    '<div style="display:flex;align-items:center;gap:0.5rem;min-width:0;flex:1;">' +
                    '<div class="avatar-icon ' + avatarClass + '"><i data-lucide="' + iconName + '"></i></div>' +
                    '<div style="display:flex;flex-direction:column;min-width:0;flex:1;">' +
                    '<span style="font-weight:600;font-size:0.85rem;color:var(--text-color);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;user-select:text;">' + fnEscape(displayTitle) + '</span>' +
                    '<span style="font-size:0.7rem;color:var(--text-muted);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;user-select:text;">' + fnEscape(subtitle) + '</span>' +
                    '</div>' +
                    '</div>' +
                    '<div style="display:flex;align-items:center;gap:0.15rem;flex-shrink:0;" onclick="event.stopPropagation()">' +
                    copyAction +
                    downloadAction +
                    removeAction +
                    '</div>' +
                    '</div>' +
                    '<div class="clipboard-card-body text-card-body">' +
                    '<div class="clipboard-text-body">' + fnEscape(fullText) + '</div>' +
                    '</div>' +
                    '</div>';
            }
        }
        clipboardContainer.innerHTML = html;
        if (window.lucide) lucide.createIcons();
    }

    function toggleClipboardSelection(event, itemId) {
        if (event && event.target && (event.target.closest("button") || event.target.tagName === "BUTTON" || event.target.tagName === "A")) {
            return;
        }

        var idStr = String(itemId);
        if (!Array.isArray(window.selectedItems)) {
            window.selectedItems = [];
        }

        var idx = window.selectedItems.indexOf(idStr);
        if (idx === -1) {
            idx = window.selectedItems.indexOf(itemId);
        }

        if (idx !== -1) {
            window.selectedItems.splice(idx, 1);
        } else {
            window.selectedItems.push(idStr);
        }

        if (typeof syncSelectionDOM === "function") syncSelectionDOM();
        if (typeof updateSelectionToolbar === "function") updateSelectionToolbar();
    }

    function downloadSelectedClipboard() {
        var selected = window.selectedItems || [];
        if (selected.length === 0) return;

        if (selected.length === 1) {
            var singleId = selected[0];
            window.open('/api/clipboard/get/' + singleId + '?download=1', '_blank');
            if (typeof window.clearSelection === 'function') window.clearSelection();
        } else {
            fetch('/api/clipboard/download-zip', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ item_ids: selected })
            })
            .then(function (res) {
                if (!res.ok) throw new Error('ZIP download failed');
                return res.blob();
            })
            .then(function (blob) {
                var url = window.URL.createObjectURL(blob);
                var a = document.createElement('a');
                a.href = url;
                a.download = 'clipboard_selection.zip';
                document.body.appendChild(a);
                a.click();
                a.remove();
                window.URL.revokeObjectURL(url);
                if (typeof window.clearSelection === 'function') window.clearSelection();
                if (typeof showToast === 'function') showToast('Downloaded ' + selected.length + ' clipboard items as ZIP', 3000);
            })
            .catch(function (err) {
                console.error('Clipboard ZIP error:', err);
                if (typeof showToast === 'function') showToast('Error downloading ZIP archive', 4000);
            });
        }
    }

    function handleClipboardMenuDownload() {
        var menu = document.getElementById("contextMenu");
        if (menu) menu.style.display = "none";

        var selected = window.selectedItems || [];
        var target = window._contextClipboardTarget;

        if (selected.length > 0) {
            downloadSelectedClipboard();
        } else if (target) {
            window.open('/api/clipboard/get/' + target + '?download=1', '_blank');
        }
    }

    function handleClipboardMenuDelete() {
        var menu = document.getElementById("contextMenu");
        if (menu) menu.style.display = "none";

        var selected = window.selectedItems || [];
        var target = window._contextClipboardTarget;

        if (selected.length > 0) {
            if (typeof window.deleteSelected === 'function') {
                window.deleteSelected();
            }
        } else if (target) {
            fetch('/api/clipboard/delete/' + target, { method: 'DELETE' })
                .then(function (res) {
                    if (res.ok) {
                        if (typeof showToast === "function") showToast("Deleted 1 clipboard item.", 3000);
                        if (typeof refreshClipboardHistory === "function") refreshClipboardHistory();
                    }
                });
        }
    }

    function addClipboardItem() {
        var protoInput = document.getElementById("clipboardInput");
        var prodInput = document.getElementById("clipboardTextInput");
        if (!protoInput) return;

        var text = protoInput.value.trim();
        if (!text) return;

        if (prodInput) prodInput.value = text;
        if (typeof addTextToClipboard === "function") {
            addTextToClipboard();
        }
        protoInput.value = "";
    }

    function clearClipboardInput() {
        var input = document.getElementById("clipboardInput");
        if (input) {
            input.value = "";
            input.focus();
        }
    }

    function copyToClipboard(text) {
        if (navigator.clipboard) {
            navigator.clipboard.writeText(text);
        }
    }

    window.ClipboardViewAdapter = {
        syncClipboardView: syncClipboardView,
        toggleClipboardSelection: toggleClipboardSelection,
        downloadSelectedClipboard: downloadSelectedClipboard,
        handleClipboardMenuDownload: handleClipboardMenuDownload,
        handleClipboardMenuDelete: handleClipboardMenuDelete,
        addClipboardItem: addClipboardItem,
        clearClipboardInput: clearClipboardInput,
        copyToClipboard: copyToClipboard
    };

    window.syncClipboardView = syncClipboardView;
    window.toggleClipboardSelection = toggleClipboardSelection;
    window.downloadSelectedClipboard = downloadSelectedClipboard;
    window.handleClipboardMenuDownload = handleClipboardMenuDownload;
    window.handleClipboardMenuDelete = handleClipboardMenuDelete;
    window.addClipboardItem = addClipboardItem;
    window.clearClipboardInput = clearClipboardInput;
    window.copyToClipboard = copyToClipboard;

})(window);
