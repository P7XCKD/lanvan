/**
 * @file quick-access.js
 * @description Renders Quick Access recent files section in home folder view.
 * @module QuickAccess
 */

(function (window) {
    'use strict';

    if (window.QuickAccess) {
        return;
    }

    function renderQuickAccess(files) {
        var container = document.getElementById("quickAccessContainer");
        if (!container) return;

        // Hide Recents (Quick Access) on mobile screens OR inside a subfolder OR on Recent view
        var tab = window.activeTab || "file";
        var activeFolder = (typeof window.getCurrentFolderPath === "function")
            ? window.getCurrentFolderPath()
            : (typeof window.currentFolderPath !== "undefined" ? window.currentFolderPath : "");
        if (window.innerWidth <= 550 || (activeFolder && activeFolder !== "Home" && activeFolder !== "") || tab === "recent") {
            container.style.display = "none";
            return;
        }
        container.style.display = ""; // Reset display

        if (!files || files.length === 0) {
            container.innerHTML = "";
            return;
        }

        // Take up to 4 recent files
        var recentFiles = files.slice(0, 4);
        var html = "";
        for (var i = 0; i < recentFiles.length; i++) {
            var item = recentFiles[i];
            var name = typeof item === "string" ? item : (item.name || item.filename || "");
            var ext = name.split(".").pop().toLowerCase();
            var info = typeof window.getFileTypeInfo === 'function'
                ? window.getFileTypeInfo(name, ext)
                : { avatarClass: 'avatar-doc', iconName: 'file-text' };
            var escName = typeof window.escapeHtml === 'function' ? window.escapeHtml(name) : name;
            var sizeBytes = typeof item === "object" && typeof item.size === "number" ? item.size : 0;
            var formattedSize = sizeBytes > 0 ? (typeof window.formatBytes === 'function' ? window.formatBytes(sizeBytes) : (typeof window.formatSize === 'function' ? window.formatSize(sizeBytes) : "")) : "";
            var typeLabel = ext ? ext.toUpperCase() : "FILE";
            var subtitle = formattedSize ? (typeLabel + " - " + formattedSize) : typeLabel;

            html +=
                '<div class="quick-card" data-filename="' + escName + '">' +
                '<div class="quick-icon ' + info.avatarClass + '"><i data-lucide="' + info.iconName + '"></i></div>' +
                '<div class="quick-copy" style="flex:1;min-width:0;">' +
                '<div class="quick-title" title="' + escName + '">' + escName + '</div>' +
                '<div class="quick-subtitle">' + subtitle + '</div>' +
                '</div>' +
                '<div class="quick-hover-actions" style="display:flex;align-items:center;gap:4px;flex-shrink:0;">' +
                '<button class="btn-icon" data-action="download" data-filename="' + escName + '" title="Download" style="width:24px;height:24px;padding:0;display:flex;align-items:center;justify-content:center;background:transparent;border:none;color:var(--text-muted);cursor:pointer;">' +
                '<i data-lucide="download" style="width:14px;height:14px;"></i>' +
                '</button>' +
                '<button class="btn-icon" data-action="menu" data-filename="' + escName + '" title="More actions" style="width:24px;height:24px;padding:0;display:flex;align-items:center;justify-content:center;background:transparent;border:none;color:var(--text-muted);cursor:pointer;">' +
                '<i data-lucide="more-vertical" style="width:14px;height:14px;"></i>' +
                '</button>' +
                '</div>' +
                '</div>';
        }
        container.innerHTML = html;

        if (typeof window.refreshLucideIcons === 'function') {
            window.refreshLucideIcons(container);
        }

        // Action Handlers
        var downloadBtns = container.querySelectorAll('button[data-action="download"]');
        for (var d = 0; d < downloadBtns.length; d++) {
            downloadBtns[d].addEventListener("click", function (e) {
                e.stopPropagation();
                var fname = this.getAttribute("data-filename");
                if (fname) {
                    var link = document.createElement("a");
                    link.href = "/download/" + encodeURIComponent(fname);
                    link.download = fname;
                    document.body.appendChild(link);
                    link.click();
                    document.body.removeChild(link);
                }
            });
        }

        var menuBtns = container.querySelectorAll('button[data-action="menu"]');
        for (var m = 0; m < menuBtns.length; m++) {
            menuBtns[m].addEventListener("click", function (e) {
                e.stopPropagation();
                var fname = this.getAttribute("data-filename");
                if (fname && typeof window.openRowMenu === "function") {
                    window.openRowMenu(e, fname);
                }
            });
        }

        // Click card to select
        var cards = container.querySelectorAll(".quick-card");
        for (var k = 0; k < cards.length; k++) {
            cards[k].addEventListener("click", function (e) {
                if (e.target.closest("button")) return;
                var fname = this.getAttribute("data-filename");
                if (!fname) return;
                var current = Array.isArray(window.selectedItems) ? window.selectedItems.slice() : [];
                var idx = current.indexOf(fname);
                if (idx > -1) {
                    current.splice(idx, 1);
                } else {
                    current = [fname];
                }
                window.selectedItems = current;
                if (typeof window.updateSelectionToolbar === "function") {
                    window.updateSelectionToolbar();
                }
            });
        }

        if (typeof window.refreshLucideIcons === 'function') {
            window.refreshLucideIcons(container);
        }
    }

    var QuickAccess = Object.freeze({
        render: renderQuickAccess
    });

    window.QuickAccess = QuickAccess;
    window.renderQuickAccess = renderQuickAccess;

})(window);
