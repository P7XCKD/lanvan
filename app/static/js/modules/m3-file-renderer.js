/**
 * @file m3-file-renderer.js
 * @description Declarative M3 List Item & Grid Card HTML Builder.
 * @module M3FileRenderer
 */

(function (window) {
    'use strict';

    function buildListItem(item, viewMode) {
        var fn = typeof item === "string" ? item : item.name;
        var info = typeof getFileTypeInfo === 'function' ? getFileTypeInfo(fn, item.isFolder) : { avatarClass: 'avatar-file', iconName: 'file-text' };
        var escName = typeof escapeHtml === 'function' ? escapeHtml(fn) : fn;
        var isUploading = !!(item.uploading && item.status !== 'completed');
        var pct = typeof item.progress === 'number' ? Math.min(100, Math.max(0, item.progress)) : 0;
        var statusLabel = (item.status || 'uploading').toLowerCase();
        var isFolder = !!item.isFolder;

        var sizeStr = item.size ? item.size : "--";

        if (viewMode === 'grid') {
            return buildGridItem(item, escName, info, isUploading, pct, statusLabel, isFolder, sizeStr);
        }

        var isPaused = item.status === 'paused';
        var isProcessing = item.status === 'processing';
        var hasActiveUpload = isUploading || isPaused || isProcessing;

        var progressBarHtml = '';
        if (hasActiveUpload) {
            var displayPct = isProcessing ? 100 : Math.round(pct);
            var statusText = isProcessing ? 'Processing' : (isPaused ? 'Paused' : 'Uploading');
            var statusIcon = isPaused ? 'play' : 'pause';
            var statusAction = isPaused ? 'resume-upload' : 'pause-upload';

            progressBarHtml =
                '<div class="upload-row-progress" style="margin-top: 6px; padding: 4px 8px; background: rgba(59, 130, 246, 0.06); border-radius: 6px;">' +
                '<div style="display: flex; justify-content: space-between; align-items: center; font-size: 0.75rem; color: var(--text-muted); margin-bottom: 3px;">' +
                '<span><span id="status-' + item.id + '">' + statusText + '</span> &bull; <span id="progress-text-' + item.id + '">' + displayPct + '%</span></span>' +
                '<div style="display: flex; gap: 4px;">' +
                '<button class="btn-icon" data-action="' + statusAction + '" data-upload-id="' + item.id + '" title="' + (isPaused ? 'Resume' : 'Pause') + '" style="width: 20px; height: 20px; padding: 0;">' +
                '<i data-lucide="' + statusIcon + '" style="width: 12px; height: 12px;"></i>' +
                '</button>' +
                '<button class="btn-icon" data-action="cancel-upload" data-upload-id="' + item.id + '" title="Cancel" style="width: 20px; height: 20px; padding: 0;">' +
                '<i data-lucide="x" style="width: 12px; height: 12px;"></i>' +
                '</button>' +
                '</div>' +
                '</div>' +
                '<div class="progress-bar-container" style="height: 4px; background: rgba(0, 0, 0, 0.1); border-radius: 2px; overflow: hidden;">' +
                '<div id="progress-fill-' + item.id + '" class="progress-bar-fill" style="width: ' + displayPct + '%; height: 100%; background: var(--primary, #3b82f6); transition: width 0.2s ease;"></div>' +
                '</div>' +
                '</div>';
        }

        return (
            '<div class="m3-list-item' + (isUploading ? ' uploading' : '') + '" data-filename="' + escName + '" data-is-folder="' + (isFolder ? '1' : '0') + '">' +
            '<div class="avatar-icon ' + info.avatarClass + '"><i data-lucide="' + info.iconName + '"></i></div>' +
            '<div class="item-details">' +
            '<div class="item-title">' + escName + '</div>' +
            '<div class="item-subtitle">' + sizeStr + '</div>' +
            progressBarHtml +
            '</div>' +
            '<div class="item-actions">' +
            '<button class="btn-icon" title="More actions" data-action="menu" data-filename="' + escName + '">' +
            '<i data-lucide="more-vertical"></i>' +
            '</button>' +
            '</div>' +
            '</div>'
        );
    }

    function buildGridItem(item, escName, info, isUploading, pct, statusLabel, isFolder, sizeStr) {
        var name = typeof item === "string" ? item : item.name;
        var isPaused = item.status === 'paused';
        var isProcessing = item.status === 'processing';
        var hasActiveUpload = isUploading || isPaused || isProcessing;

        var progressBarHtml = '';
        if (hasActiveUpload) {
            var displayPct = isProcessing ? 100 : Math.round(pct);
            var statusText = isProcessing ? 'Processing' : (isPaused ? 'Paused' : 'Uploading');
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
        if (info.avatarClass === 'avatar-image') {
            var downloadUrl = "/download/" + encodeURIComponent(name);
            previewHtml = '<div class="grid-card-preview" style="padding:0;margin:0;background:var(--card-bg);width:100%;height:100%;">' +
                '<img src="' + downloadUrl + '" alt="' + escName + '" style="width:100%;height:100%;object-fit:cover;object-position:center;display:block;" onerror="this.style.display=\'none\';" />' +
                '</div>';
        } else if (info.avatarClass === 'avatar-video') {
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
            '<div class="avatar-icon ' + info.avatarClass + '"><i data-lucide="' + info.iconName + '"></i></div>' +
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
