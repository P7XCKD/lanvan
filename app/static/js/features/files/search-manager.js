/**
 * @file search-manager.js
 * @description Toolbar search input manager & keyboard shortcut controller.
 * @module SearchManager
 */

(function (window) {
    'use strict';

    function noop() {}

    function clearToolbarSearch() {
        var toolbarInput = document.getElementById("toolbarSearchInput");
        var toolbarClearBtn = document.getElementById("clearToolbarSearchBtn");
        if (toolbarInput) {
            toolbarInput.value = "";
        }
        if (toolbarClearBtn) {
            toolbarClearBtn.style.display = "none";
        }
        if (typeof window.renderFileList === "function") {
            window.renderFileList();
        }
        if (toolbarInput) {
            try { toolbarInput.focus(); } catch (e) {}
        }
    }

    function setupSearch() {
        var toolbarInput = document.getElementById("toolbarSearchInput");
        var toolbarClearBtn = document.getElementById("clearToolbarSearchBtn");

        if (toolbarInput) {
            toolbarInput.addEventListener("input", function () {
                var q = this.value.trim();
                if (toolbarClearBtn) toolbarClearBtn.style.display = q ? "inline-flex" : "none";
                if (typeof window.renderFileList === "function") window.renderFileList();
            });

            toolbarInput.addEventListener("keydown", function (e) {
                if (e.key === "Escape") {
                    if (this.value) {
                        clearToolbarSearch();
                    } else {
                        this.blur();
                    }
                }
            });

            // Global Ctrl+K / Cmd+K Shortcut to Focus Search Input
            document.addEventListener("keydown", function (e) {
                if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
                    e.preventDefault();
                    if (toolbarInput) {
                        toolbarInput.focus();
                        toolbarInput.select();
                    }
                }
            });
        }
    }

    window.SearchManager = {
        setupSearch: setupSearch,
        renderSearchAutocomplete: noop,
        hideSearchAutocomplete: noop,
        clearToolbarSearch: clearToolbarSearch
    };

    window.setupSearch = setupSearch;
    window.renderSearchAutocomplete = noop;
    window.hideSearchAutocomplete = noop;
    window.clearToolbarSearch = clearToolbarSearch;

})(window);
