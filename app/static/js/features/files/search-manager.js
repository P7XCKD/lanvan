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
        if (menu) menu.style.display = "none";
        searchSelectedIndex = -1;
    }

    function updateAutocompleteHighlight(itemEls) {
        for (var i = 0; i < itemEls.length; i++) {
            if (i === searchSelectedIndex) {
                itemEls[i].classList.add("selected");
                itemEls[i].scrollIntoView({ block: "nearest" });
            } else {
                itemEls[i].classList.remove("selected");
            }
        }
    }

    function renderSearchAutocomplete(query) {
        if (!query) {
            hideSearchAutocomplete();
            return;
        }
        var menu = document.getElementById("searchAutocompleteMenu");
        if (!menu) return;
        menu.style.display = "block";
    }

    function clearToolbarSearch() {
        var toolbarInput = document.getElementById("toolbarSearchInput");
        var toolbarClearBtn = document.getElementById("clearToolbarSearchBtn");
        if (toolbarInput) {
            toolbarInput.value = "";
        }
        if (toolbarClearBtn) {
            toolbarClearBtn.style.display = "none";
        }
        hideSearchAutocomplete();
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
                renderSearchAutocomplete(q);
            });

            toolbarInput.addEventListener("keydown", function (e) {
                var menu = document.getElementById("searchAutocompleteMenu");
                var itemEls = menu ? menu.querySelectorAll(".search-autocomplete-item") : [];

                if (e.key === "ArrowDown" && itemEls.length > 0) {
                    e.preventDefault();
                    searchSelectedIndex = Math.min(itemEls.length - 1, searchSelectedIndex + 1);
                    updateAutocompleteHighlight(itemEls);
                } else if (e.key === "ArrowUp" && itemEls.length > 0) {
                    e.preventDefault();
                    searchSelectedIndex = Math.max(0, searchSelectedIndex - 1);
                    updateAutocompleteHighlight(itemEls);
                } else if (e.key === "Enter" && searchSelectedIndex >= 0 && itemEls[searchSelectedIndex]) {
                    e.preventDefault();
                    itemEls[searchSelectedIndex].click();
                } else if (e.key === "Escape") {
                    hideSearchAutocomplete();
                    if (this.value) {
                        clearToolbarSearch();
                    } else {
                        this.blur();
                    }
                }
            });

            // Global Ctrl+K Shortcut to Focus Search
            document.addEventListener("keydown", function (e) {
                if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
                    e.preventDefault();
                    if (toolbarInput) {
                        toolbarInput.focus();
                        toolbarInput.select();
                        if (toolbarInput.value.trim()) {
                            renderSearchAutocomplete(toolbarInput.value.trim());
                        }
                    }
                }
            });

            // Hide Autocomplete Menu on Outside Click
            document.addEventListener("click", function (e) {
                if (!e.target.closest("#toolbarSearchWrapper") && !e.target.closest("#searchAutocompleteMenu")) {
                    hideSearchAutocomplete();
                }
            });
        }
    }

    window.SearchManager = {
        setupSearch: setupSearch,
        renderSearchAutocomplete: renderSearchAutocomplete,
        hideSearchAutocomplete: hideSearchAutocomplete,
        clearToolbarSearch: clearToolbarSearch
    };

    window.setupSearch = setupSearch;
    window.renderSearchAutocomplete = renderSearchAutocomplete;
    window.hideSearchAutocomplete = hideSearchAutocomplete;
    window.clearToolbarSearch = clearToolbarSearch;

})(window);
