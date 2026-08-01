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
        var subtitleText = subtitle ? subtitle : (isFolder ? "Folder" : "File");
        if (!isFolder && isUploading && (!subtitle || subtitle === "File" || subtitle.indexOf("%") !== -1)) {
            var statusLabel = uploadStatus === 'PAUSED' ? 'Paused' : (uploadStatus === 'QUEUED' ? 'Queued' : 'Uploading');
            subtitleText = pct + "% • " + statusLabel;

            // Format ETA for list row subtitles using the UploadETA module
            if (uploadStatus === 'UPLOADING' && window.UploadETA) {
                var queue = window.uploadQueue || [];
                var qItem = null;
                if (uploadId) {
                    qItem = queue.find(function (q) { return q && (q.id == uploadId || q.uploadId == uploadId); });
                }
                if (!qItem && name) {
                    var targetBase = name.split("/").pop().split("\\").pop();
                    var matches = queue.filter(function (q) {
                        if (!q) return false;
                        var qName = q.fileName || q.name || (q.file ? q.file.name : "");
                        return qName === name || (qName && qName.split("/").pop().split("\\").pop() === targetBase);
                    });
                    if (matches.length === 1) qItem = matches[0];
                }
                if (qItem) {
                    var etaStr = window.UploadETA.format(qItem);
                    if (etaStr) subtitleText += " • ETA " + etaStr;
                }
            }
        }

        var displaySize = isFolder ? "-" : sizeStr;
        var progressBarHtml = isUploading
            ? '<div class="row-progress-bar" style="position:absolute; top:0; bottom:0; left:0; width:100%; height:100%; background:rgba(59, 130, 246, 0.08); transform:scaleX(' + (pct / 100) + '); transform-origin:left center; transition:transform 0.25s ease-out, width 0.25s ease-out; pointer-events:none; z-index:1;"></div>'
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

        var formattedDate = (typeof formatLastModified === 'function' && !isUploading && dateText && dateText !== '--') ? formatLastModified(dateText) : { display: dateText || "--", tooltip: dateText || "" };
        var displayDate = isUploading ? (uploadStatus === 'PAUSED' ? 'Paused' : (uploadStatus === 'QUEUED' ? 'Queued' : 'Uploading')) : formattedDate.display;
        var dateTooltip = isUploading ? "" : (formattedDate.tooltip || formattedDate.display);

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
            '<div class="item-date" style="position:relative; z-index:2;" title="' + (typeof escapeHtml === 'function' ? escapeHtml(dateTooltip) : dateTooltip) + '">' + (typeof escapeHtml === 'function' ? escapeHtml(displayDate) : displayDate) + '</div>' +
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
            var statusText = uploadStatus === 'PAUSED' ? 'Paused' : (uploadStatus === 'QUEUED' ? 'Queued' : 'Uploading');
            progressBarHtml =
                '<div class="glass-b4-body" style="position: absolute; top: 39px; bottom: 0; left: 0; right: 0; display: flex; align-items: center; justify-content: center; background: rgba(0, 0, 0, 0.22); backdrop-filter: blur(4px); z-index: 10;">' +
                '<div class="b4-badge" style="background: rgba(255, 255, 255, 0.95); border-radius: 12px; padding: 12px 20px; box-shadow: 0 4px 16px rgba(0,0,0,0.15); display: flex; flex-direction: column; align-items: center; justify-content: center; min-width: 100px;">' +
                '<div class="b4-num" style="font-size: 1.35rem; font-weight: 800; color: var(--primary, #2563eb); line-height: 1.1;">' + displayPct + '%</div>' +
                '<div class="b4-sub" style="font-size: 0.68rem; font-weight: 600; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.5px; margin-top: 2px;">' + statusText + '</div>' +
                '</div>' +
                '<div class="b4-bottom-strip" style="position: absolute; bottom: 0; left: 0; right: 0; height: 3px; background: rgba(0,0,0,0.08); overflow: hidden;">' +
                '<div style="width: ' + displayPct + '%; height: 100%; background: var(--primary, #3b82f6); transition: width 0.2s ease-out;"></div>' +
                '</div>' +
                '</div>';
        }

        var previewHtml = '';
        if (isFolder) {
            previewHtml = '<div class="grid-card-preview folder-preview-box" style="background: rgba(59, 130, 246, 0.08); display: flex !important; align-items: center !important; justify-content: center !important; text-align: center; width: 100%; height: calc(100% - 39px); position: absolute; top: 39px; left: 0; right: 0; bottom: 0;">' +
                '<div style="display: inline-flex; align-items: center; justify-content: center; width: 48px; height: 48px; margin: auto;">' +
                '<i data-lucide="folder" style="width: 48px; height: 48px; min-width: 48px; min-height: 48px; color: var(--primary, #2563eb); stroke-width: 1.5; display: block; margin: auto;"></i>' +
                '</div>' +
                '</div>';
        } else if (itemInfo.avatarClass === 'avatar-image') {
            if (isUploading) {
                previewHtml = '<div class="grid-card-preview" style="background:var(--card-bg);">' +
                    '<div class="doc-preview-sheet" style="display:flex;align-items:center;justify-content:center;">' +
                    '<i data-lucide="image" style="width:36px;height:36px;color:var(--primary,#3b82f6);opacity:0.4;"></i>' +
                    '</div>' +
                    '</div>';
            } else {
                var downloadUrl = "/download/" + encodeURIComponent(name);
                previewHtml = '<div class="grid-card-preview" style="padding:0;margin:0;background:var(--card-bg);">' +
                    '<img src="' + downloadUrl + '" alt="' + escName + '" style="width:100%;height:100%;object-fit:cover;object-position:center;display:block;" onerror="this.style.display=\'none\';" />' +
                    '</div>';
            }
        } else if (itemInfo.avatarClass === 'avatar-video') {
            if (isUploading) {
                previewHtml = '<div class="grid-card-preview" style="background:var(--card-bg);">' +
                    '<div class="doc-preview-sheet" style="display:flex;align-items:center;justify-content:center;">' +
                    '<i data-lucide="video" style="width:36px;height:36px;color:var(--primary,#3b82f6);opacity:0.4;"></i>' +
                    '</div>' +
                    '</div>';
            } else {
                var downloadUrl = "/download/" + encodeURIComponent(name);
                previewHtml = '<div class="grid-card-preview video-preview-box" style="position:absolute;top:39px;left:0;right:0;bottom:0;width:100%;height:calc(100% - 39px);padding:0;margin:0;background:#0f172a;overflow:hidden;">' +
                    '<video src="' + downloadUrl + '#t=0.5" preload="metadata" style="width:100%;height:100%;object-fit:cover;object-position:center;display:block;pointer-events:none;" muted controlsList="nodownload no-fullscreen noremoteplayback" disablePictureInPicture></video>' +
                    '<div class="video-play-badge" style="position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);z-index:10;margin:0;">' +
                    '<i data-lucide="play" style="width:20px;height:20px;fill:currentColor;margin:0;"></i>' +
                    '</div>' +
                    '</div>';
            }
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

        var subtitleHtml = (isFolder && subtitle && subtitle !== "Folder")
            ? '<div class="item-subtitle" style="font-size:0.7rem; color:var(--text-muted); white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">' + subtitle + '</div>'
            : '';

        return (
            '<div class="m3-list-item' + (isUploading ? ' uploading' : '') + '" data-filename="' + escName + '" data-is-folder="' + (isFolder ? '1' : '0') + '" style="position:relative; overflow:hidden;">' +
            '<div class="grid-card-head" style="position:relative; z-index:20; background:var(--card-bg, #ffffff);">' +
            '<div class="avatar-icon ' + itemInfo.avatarClass + '"><i data-lucide="' + itemInfo.iconName + '"></i></div>' +
            '<div style="display:flex; flex-direction:column; min-width:0; flex:1;">' +
            '<div class="item-title" title="' + escName + '">' + escName + '</div>' +
            subtitleHtml +
            '</div>' +
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
