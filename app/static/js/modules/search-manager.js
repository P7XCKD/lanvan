/**
 * @file search-manager.js
 * @description Search input debouncer & autocomplete UI manager.
 * @module SearchManager
 */

(function (window) {
    'use strict';

    var searchSelectedIndex = -1;

    function hideSearchAutocomplete() {
        var menu = document.getElementById("searchAutocompleteMenu");
        if (menu) {
            menu.style.display = "none";
            menu.innerHTML = "";
        }
        searchSelectedIndex = -1;
    }

    function renderSearchAutocomplete(query) {
        var menu = document.getElementById("searchAutocompleteMenu");
        if (!menu) return;

        var q = (query || "").trim().toLowerCase();
        if (!q) {
            hideSearchAutocomplete();
            return;
        }

        var path = (typeof window.LanvanStore !== 'undefined' && window.LanvanStore.getState) ? window.LanvanStore.getState().currentFolder : (window.currentFolderPath || "");
        var allItems = (window.FileRepository && typeof window.FileRepository.getFolderCache === 'function') ? window.FileRepository.getFolderCache(path) : [];
        var matches = allItems.filter(function (item) {
            if (!item || !item.name) return false;
            return item.name.toLowerCase().indexOf(q) !== -1;
        }).slice(0, 4);

        if (matches.length === 0) {
            menu.innerHTML =
                '<div class="search-autocomplete-header">Search Suggestions</div>' +
                '<div style="padding: 0.75rem 0.65rem; font-size: 0.8rem; color: var(--text-muted); text-align: center;">No matching files or folders</div>';
            menu.style.display = "block";
            searchSelectedIndex = -1;
            return;
        }

        var html = '<div class="search-autocomplete-header">Quick Results</div>';
        for (var i = 0; i < matches.length; i++) {
            var item = matches[i];
            var name = item.name;
            var isFolder = !!item.isFolder;
            var itemType = isFolder ? "folder" : (typeof getFileItemType === "function" ? getFileItemType({ name: name }) : "file");

            var iconName = "file-text";
            var labelType = "FILE";

            if (isFolder) {
                iconName = "folder";
                labelType = "FOLDER";
            } else if (itemType === "image") {
                iconName = "image";
                labelType = "IMAGE";
            } else if (itemType === "video") {
                iconName = "video";
                labelType = "VIDEO";
            } else if (itemType === "audio") {
                iconName = "music";
                labelType = "AUDIO";
            } else if (itemType === "archive") {
                iconName = "archive";
                labelType = "ARCHIVE";
            } else if (itemType === "doc") {
                iconName = "file-text";
                labelType = "DOCUMENT";
            }

            var sizeStr = item.size && item.size !== "--" ? item.size : "";
            var subText = labelType + (sizeStr ? " • " + sizeStr : "") + " • Home";
            var escName = typeof escapeHtml === "function" ? escapeHtml(name) : name;

            html +=
                '<div class="search-autocomplete-item" data-index="' + i + '" data-filename="' + escName + '" data-is-folder="' + (isFolder ? "true" : "false") + '">' +
                '<div class="search-autocomplete-icon type-' + itemType + '">' +
                '<i data-lucide="' + iconName + '" style="width: 18px; height: 18px;"></i>' +
                '</div>' +
                '<div class="search-autocomplete-details">' +
                '<div class="search-autocomplete-title">' + escName + '</div>' +
                '<div class="search-autocomplete-sub">' + (typeof escapeHtml === "function" ? escapeHtml(subText) : subText) + '</div>' +
                '</div>' +
                '</div>';
        }

        menu.innerHTML = html;
        menu.style.display = "block";
        searchSelectedIndex = -1;

        if (window.lucide && typeof window.lucide.createIcons === "function") {
            window.lucide.createIcons();
        }
    }

    window.SearchManager = {
        renderSearchAutocomplete: renderSearchAutocomplete,
        hideSearchAutocomplete: hideSearchAutocomplete
    };

    window.renderSearchAutocomplete = renderSearchAutocomplete;
    window.hideSearchAutocomplete = hideSearchAutocomplete;

})(window);
