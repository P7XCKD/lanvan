/**
 * @file m3-file-renderer.js
 * @description Declarative M3 List Item & Grid Card HTML Builder.
 * @module M3FileRenderer
 */

(function (window) {
    'use strict';

    function buildListItem(name, info, size, dateStr, subtitle, isFolder, isUploading, uploadProgress, uploadId, uploadStatus) {
        var escName = typeof escapeHtml === 'function' ? escapeHtml(name) : name;
        var fn = name || "";
        var itemInfo = info;
        if (!itemInfo || !itemInfo.iconName) {
            var ext = fn.split(".").pop().toLowerCase();
            itemInfo = typeof getFileTypeInfo === 'function' ? getFileTypeInfo(fn, ext) : { avatarClass: 'avatar-doc', iconName: 'file-text' };
        }
        var pct = typeof uploadProgress === 'number' ? Math.min(100, Math.max(0, uploadProgress)) : 0;
        var hasActiveUpload = !!(isUploading);
        var sizeStr = size || "--";
        var progressBarHtml = '';
        var subtitleHtml = '';

        if (isFolder && subtitle) {
            subtitleHtml = '<div class="item-subtitle">' + subtitle + '</div>';
        }

        if (hasActiveUpload) {
            var statusText = pct > 0 ? 'Uploading' : 'Queued';
            progressBarHtml =
                '<div class="upload-row-progress">' +
                '<div class="upload-row-progress-label">' + statusText + ' &bull; ' + pct + '%</div>' +
                '<div class="progress-bar-container">' +
                '<div class="progress-bar-fill" style="width: ' + pct + '%;"></div>' +
                '</div>' +
                '</div>';
        }

        return (
            '<div class="m3-list-item' + (isUploading ? ' uploading' : '') + '" data-filename="' + escName + '" data-is-folder="' + (isFolder ? '1' : '0') + '">' +
            '<div class="file-name-cell">' +
            '<div class="avatar-icon ' + itemInfo.avatarClass + '"><i data-lucide="' + itemInfo.iconName + '"></i></div>' +
            '<div class="item-main">' +
            '<div class="item-title">' + escName + '</div>' +
            subtitleHtml +
            progressBarHtml +
            '</div>' +
            '</div>' +
            '<div class="item-date">' + (dateStr || '--') + '</div>' +
            '<div class="item-size">' + sizeStr + '</div>' +
            '<div class="row-actions">' +
            '<button class="btn-icon" title="More actions" data-action="menu" data-filename="' + escName + '">' +
            '<i data-lucide="more-vertical"></i>' +
            '</button>' +
            '</div>' +
            '</div>'
        );
    }

    function buildGridItem(name, info, size, dateStr, subtitle, isFolder, isUploading, uploadProgress, uploadId, uploadStatus) {
        var escName = typeof escapeHtml === 'function' ? escapeHtml(name) : name;
        var fn = name || "";
        var itemInfo = info;
        if (!itemInfo || !itemInfo.iconName) {
            var ext = fn.split(".").pop().toLowerCase();
            itemInfo = typeof getFileTypeInfo === 'function' ? getFileTypeInfo(fn, ext) : { avatarClass: 'avatar-doc', iconName: 'file-text' };
        }
        var hasActiveUpload = !!(isUploading);
        var pct = typeof uploadProgress === 'number' ? Math.min(100, Math.max(0, uploadProgress)) : 0;

        var progressBarHtml = '';
        if (hasActiveUpload) {
            var displayPct = Math.round(pct);
            var statusText = 'Uploading';
            progressBarHtml =
                '<div class="glass-b4-body" style="position: absolute; bottom: 0; left: 0; right: 0; padding: 8px; background: rgba(255, 255, 255, 0.85); backdrop-filter: blur(8px); z-index: 10;">' +
                '<div style="display: flex; justify-content: space-between; font-size: 0.7rem; color: var(--text-muted); margin-bottom: 2px;">' +
                '<span>' + statusText + '</span><span>' + displayPct + '%</span>' +
                '</div>' +
                '<div style="height: 3px; background: rgba(0,0,0,0.1); border-radius: 2px; overflow: hidden;">' +
                '<div style="width: ' + displayPct + '%; height: 100%; background: var(--primary, #3b82f6);"></div>' +
                '</div>' +
                '</div>';
        }

        var previewHtml = '';
        if (itemInfo.avatarClass === 'avatar-image') {
            var downloadUrl = "/download/" + encodeURIComponent(name);
            previewHtml = '<div class="grid-card-preview" style="padding:0;margin:0;background:var(--card-bg);width:100%;height:100%;">' +
                '<img src="' + downloadUrl + '" alt="' + escName + '" style="width:100%;height:100%;object-fit:cover;object-position:center;display:block;" onerror="this.style.display=\'none\';" />' +
                '</div>';
        } else if (itemInfo.avatarClass === 'avatar-video') {
            var downloadUrl = "/download/" + encodeURIComponent(name);
            previewHtml = '<div class="grid-card-preview video-preview-box" style="padding:0;margin:0;background:#0f172a;width:100%;height:100%;">' +
                '<video src="' + downloadUrl + '#t=0.5" preload="metadata" style="width:100%;height:100%;object-fit:cover;object-position:center;display:block;" muted></video>' +
                '<div class="video-play-badge" style="position:absolute;z-index:3;">' +
                '<i data-lucide="play" style="width:20px;height:20px;fill:currentColor;"></i>' +
                '</div>' +
                '</div>';
        } else {
            previewHtml = '<div class="grid-card-preview" style="background:var(--card-bg);">' +
                '<div class="doc-preview-sheet">' +
                '<div class="doc-preview-line title"></div>' +
                '<div class="doc-preview-line"></div>' +
                '<div class="doc-preview-line short"></div>' +
                '<div style="flex:1;"></div>' +
                '<i data-lucide="file-text" style="width:24px;height:24px;color:#d93025;"></i>' +
                '</div>' +
                '</div>';
        }

        return (
            '<div class="m3-list-item' + (isUploading ? ' uploading' : '') + '" data-filename="' + escName + '" data-is-folder="' + (isFolder ? '1' : '0') + '" style="position:relative; overflow:hidden;">' +
            '<div class="grid-card-head" style="position:relative; z-index:20; background:var(--card-bg, #ffffff);">' +
            '<div class="avatar-icon ' + itemInfo.avatarClass + '"><i data-lucide="' + itemInfo.iconName + '"></i></div>' +
            '<div class="item-title" title="' + escName + '">' + escName + '</div>' +
            '<button class="btn-icon" title="More actions" data-action="menu" data-filename="' + escName + '" style="width:24px;height:24px;padding:0;flex-shrink:0;">' +
            '<i data-lucide="more-vertical" style="width:14px;height:14px;"></i>' +
            '</button>' +
            '</div>' +
            previewHtml +
            progressBarHtml +
            '</div>'
        );
    }

    window.M3FileRenderer = {
        buildListItem: buildListItem,
        buildGridItem: buildGridItem
    };

    window.buildListItem = buildListItem;
    window.buildGridItem = buildGridItem;

})(window);
