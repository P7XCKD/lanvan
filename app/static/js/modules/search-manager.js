/**
 * @file search-manager.js
 * @description Search input debouncer & autocomplete UI manager.
 * @module SearchManager
 */

(function (window) {
    'use strict';

    function hideSearchAutocomplete() {
        var menu = document.getElementById("searchAutocompleteMenu");
        if (menu) {
            menu.style.display = "none";
            menu.innerHTML = "";
        }
    }

    function renderSearchAutocomplete(query) {
        hideSearchAutocomplete();
    }

    window.SearchManager = {
        renderSearchAutocomplete: renderSearchAutocomplete,
        hideSearchAutocomplete: hideSearchAutocomplete
    };

    window.renderSearchAutocomplete = renderSearchAutocomplete;
    window.hideSearchAutocomplete = hideSearchAutocomplete;

})(window);
