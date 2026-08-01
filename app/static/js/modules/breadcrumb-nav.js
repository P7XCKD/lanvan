/**
 * @file breadcrumb-nav.js
 * @description Breadcrumb navigation renderer & click handler manager.
 * @module BreadcrumbNav
 */

(function (window) {
    'use strict';

    function renderBreadcrumbs() {
        var container = document.getElementById("breadcrumbsContainer");
        if (!container) return;
        container.innerHTML = "";

        var currentPath = typeof window.currentFolderPath !== 'undefined' ? window.currentFolderPath : "Home";

        // Always start from "Home", then show current subfolder path parts
        var fullParts = ["Home"];
        if (currentPath && currentPath !== "Home" && currentPath !== "") {
            var subParts = currentPath.split("/");
            fullParts = fullParts.concat(subParts);
        }

        for (var i = 0; i < fullParts.length; i++) {
            if (i > 0) {
                var sep = document.createElement("span");
                sep.className = "breadcrumb-separator";
                sep.innerHTML = '<i data-lucide="chevron-right" style="width:16px;height:16px;"></i>';
                container.appendChild(sep);
            }
            var bItem = document.createElement("span");
            bItem.className = "breadcrumb-item";
            bItem.textContent = fullParts[i];
            if (i < fullParts.length - 1) {
                // Clickable — navigate to that level
                (function (idx) {
                    bItem.onclick = function () {
                        var targetPath = (idx === 0) ? "" : fullParts.slice(1, idx + 1).join("/");
                        if (typeof window.navigateToFolder === "function") {
                            window.navigateToFolder(targetPath);
                        } else if (window.LanvanStore) {
                            window.LanvanStore.dispatch("SET_CURRENT_FOLDER", { folderPath: targetPath });
                        }
                        if (typeof window.clearSelection === "function") {
                            window.clearSelection();
                        } else {
                            window.selectedItems = [];
                            window.prototypeSelectedItems = window.selectedItems;
                        }
                        if (typeof updateSelectionToolbar === "function") updateSelectionToolbar();
                    };
                })(i);
                bItem.style.cursor = "pointer";
            }
            container.appendChild(bItem);
        }

        if (typeof lucide !== "undefined" && typeof lucide.createIcons === "function") {
            lucide.createIcons();
        }
    }

    window.BreadcrumbNav = {
        renderBreadcrumbs: renderBreadcrumbs
    };

    window.renderBreadcrumbs = renderBreadcrumbs;

})(window);
