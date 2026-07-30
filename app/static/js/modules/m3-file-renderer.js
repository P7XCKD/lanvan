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
        if (uploadStatus === 'COMPLETED' || (pct >= 100 && uploadStatus !== 'UPLOADING' && uploadStatus !== 'PAUSED')) {
            isUploading = false;
        }

        var dateText = dateStr || "--";
        var subtitleText = subtitle || (isFolder ? "Folder" : "File");
        if (isUploading) {
            var statusLabel = uploadStatus === 'PAUSED' ? 'Paused' : (uploadStatus === 'QUEUED' ? 'Queued' : 'Uploading');
            subtitleText = pct + "% • " + statusLabel;
        }

        var displaySize = isFolder ? "-" : sizeStr;
        var progressBarHtml = isUploading
            ? '<div class="row-progress-bar" style="position:absolute; top:0; bottom:0; left:0; background:rgba(59, 130, 246, 0.08); width:' + pct + '%; transition:width 0.25s ease-out; pointer-events:none; z-index:1;"></div>'
            : '';

        var actionsHtml = '';
        if (isUploading) {
            var playPauseBtn = '';
            var svgPlay = '<svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor" stroke="none"><polygon points="5 3 19 12 5 21 5 3"></polygon></svg>';
            var svgPause = '<svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor" stroke="none"><rect x="6" y="4" width="4" height="16"></rect><rect x="14" y="4" width="4" height="16"></rect></svg>';
            var svgClose = '<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>';

            if (uploadStatus === 'PAUSED') {
                playPauseBtn = '<button class="btn-icon" title="Resume upload" data-action="resume-upload" data-upload-id="' + uploadId + '" style="display:inline-flex;align-items:center;justify-content:center;">' +
                    svgPlay +
                    '</button>';
            } else {
                playPauseBtn = '<button class="btn-icon" title="Pause upload" data-action="pause-upload" data-upload-id="' + uploadId + '" style="display:inline-flex;align-items:center;justify-content:center;">' +
                    svgPause +
                    '</button>';
            }
            actionsHtml = playPauseBtn +
                '<button class="btn-icon" title="Cancel upload" data-action="cancel-upload" data-upload-id="' + uploadId + '" style="display:inline-flex;align-items:center;justify-content:center;">' +
                svgClose +
                '</button>';
        } else {
            actionsHtml =
                '<button class="btn-icon hover-btn" title="Download" data-action="download" data-filename="' + escName + '" data-is-folder="' + (isFolder ? '1' : '0') + '">' +
                '<i data-lucide="download" style="width:16px;height:16px;"></i>' +
                '</button>' +
                (isFolder ? '' :
                    '<button class="btn-icon hover-btn" title="Rename" data-action="rename" data-filename="' + escName + '">' +
                    '<i data-lucide="edit-2" style="width:16px;height:16px;"></i>' +
                    '</button>'
                ) +
                '<button class="btn-icon" title="More actions" data-action="menu" data-filename="' + escName + '">' +
                '<i data-lucide="more-vertical" style="width:16px;height:16px;"></i>' +
                '</button>';
        }

        var displayDate = isUploading ? (uploadStatus === 'PAUSED' ? 'Paused' : (uploadStatus === 'QUEUED' ? 'Queued' : 'Uploading')) : dateText;

        return (
            '<div class="m3-list-item' + (isUploading ? ' uploading' : '') + '" data-filename="' + escName + '" data-is-folder="' + (isFolder ? '1' : '0') + '" style="' + (isUploading ? 'position:relative; overflow:hidden;' : '') + '">' +
            progressBarHtml +
            '<div class="file-name-cell" style="position:relative; z-index:2;">' +
            '<div class="avatar-icon ' + itemInfo.avatarClass + '"><i data-lucide="' + itemInfo.iconName + '"></i></div>' +
            '<div class="item-main">' +
            '<div class="item-title">' + escName + '</div>' +
            '<div class="item-subtitle">' + subtitleText + '</div>' +
            '</div>' +
            '</div>' +
            '<div class="item-date" style="position:relative; z-index:2;">' + displayDate + '</div>' +
            '<div class="item-size" style="position:relative; z-index:2;">' + displaySize + '</div>' +
            '<div class="row-actions" style="position:relative; z-index:2;">' +
            actionsHtml +
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
