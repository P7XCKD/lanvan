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
        // Render autocomplete results if query exists
        if (!query) {
            hideSearchAutocomplete();
            return;
        }
        var menu = document.getElementById("searchAutocompleteMenu");
        if (!menu) return;
        
        // Autocomplete menu query matching
        menu.style.display = "block";
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

            window.clearToolbarSearch = function () {
                if (toolbarInput) {
                    toolbarInput.value = "";
                    if (toolbarClearBtn) toolbarClearBtn.style.display = "none";
                    hideSearchAutocomplete();
                    if (typeof window.fetchFilesData === "function") {
                        window.fetchFilesData().then(function (fd) {
                            if (typeof window.renderFileList === "function") window.renderFileList(fd);
                        });
                    }
                    toolbarInput.focus();
                }
            };

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

        var searchInput = document.getElementById("searchInput");
        var clearBtn = document.getElementById("clearSearchBtn");
        if (!searchInput) return;

        var lastFiles = [];

        searchInput.addEventListener("input", function () {
            var query = this.value.trim().toLowerCase();
            if (clearBtn) clearBtn.classList.toggle("visible", !!query);

            if (!query) {
                if (typeof window.renderFileList === "function") window.renderFileList(lastFiles);
                var panel = document.getElementById("searchResultsPanel");
                if (panel) panel.classList.remove("active");
                return;
            }

            var results = lastFiles.filter(function (f) {
                return f.toLowerCase().indexOf(query) !== -1;
            });
            renderSearchResults(results, query);
        });

        if (clearBtn) {
            clearBtn.addEventListener("click", function () {
                searchInput.value = "";
                searchInput.focus();
                if (typeof window.renderFileList === "function") window.renderFileList(lastFiles);
                var panel = document.getElementById("searchResultsPanel");
                if (panel) panel.classList.remove("active");
                clearBtn.classList.remove("visible");
            });
        }
    }

    function renderSearchResults(results, query) {
        var panel = document.getElementById("searchResultsPanel");
        if (!panel) return;

        panel.classList.add("active");

        var escapeHtml = (typeof window.escapeHtml === 'function') ? window.escapeHtml : function(s){ return s; };
        var getFileTypeInfo = (typeof window.getFileTypeInfo === 'function') ? window.getFileTypeInfo : function() { return { avatarClass: 'default', iconName: 'file' }; };

        if (results.length === 0) {
            panel.innerHTML =
                '<div class="search-results-list"><div class="search-results-empty">No matches found for "' +
                escapeHtml(query) +
                '".</div></div>';
            return;
        }

        var html = '<div class="search-results-list">';
        for (var i = 0; i < results.length; i++) {
            var name = results[i];
            var ext = name.split(".").pop().toLowerCase();
            var info = getFileTypeInfo(name, ext);
            html +=
                '<div class="search-result-item" data-filename="' +
                escapeHtml(name) +
                '">' +
                '<div class="search-result-main">' +
                '<div class="search-result-icon ' +
                info.avatarClass +
                '"><i data-lucide="' +
                info.iconName +
                '" style="width:18px;height:18px;"></i></div>' +
                '<div class="search-result-copy">' +
                '<div class="search-result-name">' +
                escapeHtml(name) +
                "</div>" +
                '<div class="search-result-meta">File</div>' +
                "</div>" +
                "</div>" +
                '<div class="search-result-badge">File</div>' +
                "</div>";
        }
        html += "</div>";
        panel.innerHTML = html;

        var items = panel.querySelectorAll(".search-result-item");
        for (var j = 0; j < items.length; j++) {
            items[j].addEventListener("click", function () {
                var fname = this.getAttribute("data-filename");
                var listItem = document.querySelector(
                    '#nasFileList [data-filename="' + fname.replace(/"/g, '"') + '"]'
                );
                if (listItem) listItem.scrollIntoView({ behavior: "smooth", block: "center" });
                panel.classList.remove("active");
            });
        }
        if (window.lucide) lucide.createIcons();
    }

    function clearToolbarSearch() {
        if (typeof window.clearToolbarSearch === "function") {
            window.clearToolbarSearch();
        }
    }

    window.SearchManager = {
        setupSearch: setupSearch,
        renderSearchAutocomplete: renderSearchAutocomplete,
        hideSearchAutocomplete: hideSearchAutocomplete,
        renderSearchResults: renderSearchResults,
        clearToolbarSearch: function() {
            if (typeof window.clearToolbarSearch === "function") {
                window.clearToolbarSearch();
            }
        }
    };

    window.setupSearch = setupSearch;
    window.renderSearchAutocomplete = renderSearchAutocomplete;
    window.hideSearchAutocomplete = hideSearchAutocomplete;
    window.clearToolbarSearch = function() {
        var toolbarInput = document.getElementById("toolbarSearchInput");
        var toolbarClearBtn = document.getElementById("clearToolbarSearchBtn");
        if (toolbarInput) {
            toolbarInput.value = "";
            if (toolbarClearBtn) toolbarClearBtn.style.display = "none";
            hideSearchAutocomplete();
            if (typeof window.fetchFilesData === "function") {
                window.fetchFilesData().then(function (fd) {
                    if (typeof window.renderFileList === "function") window.renderFileList(fd);
                });
            }
            toolbarInput.focus();
        }
    };

})(window);
