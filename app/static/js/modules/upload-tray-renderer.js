/**
 * @file upload-tray-renderer.js
 * @description Declarative Notification Tray Renderer & Progress Visualizer.
 * @module UploadTrayRenderer
 */

(function (window) {
    'use strict';

    function buildTrayItemHtml(item) {
        var fn = item.fileName || item.name || "File";
        var escName = typeof escapeHtml === 'function' ? escapeHtml(fn) : fn;
        var isPaused = item.status === "paused";
        var isProcessing = item.status === "processing";
        var isCompleted = item.status === "completed";
        var isDeleted = item.status === "deleted";

        var statusClass = isCompleted ? "status-completed" : (isPaused ? "status-paused" : (isProcessing ? "status-processing" : "status-uploading"));
        var statusLabel = isCompleted ? "Completed" : (isPaused ? "Paused" : (isProcessing ? "Processing" : "Uploading"));
        var pct = typeof item.progress === 'number' ? Math.min(100, Math.max(0, Math.round(item.progress))) : (isCompleted ? 100 : 0);

        var actionControl = '';
        if (isCompleted || isDeleted) {
            actionControl = '<span class="upload-toast-cancel-text" data-upload-id="' + item.id + '" style="color:var(--text-muted); cursor:pointer;">&times;</span>';
        } else if (isPaused) {
            actionControl = '<span class="upload-toast-resume-text" data-upload-id="' + item.id + '" style="color:var(--primary); cursor:pointer; font-weight:600; margin-right:8px;">Resume</span>' +
                '<span class="upload-toast-cancel-text" data-upload-id="' + item.id + '" style="color:var(--text-muted); cursor:pointer;">&times;</span>';
        } else {
            actionControl = '<span class="upload-toast-cancel-text" data-upload-id="' + item.id + '" style="color:var(--text-muted); cursor:pointer;">Cancel</span>';
        }

        return (
            '<div class="upload-toast-item ' + statusClass + '" id="toast-item-' + item.id + '" data-upload-id="' + item.id + '">' +
            '<div class="upload-toast-item-head">' +
            '<div class="upload-toast-item-name" title="' + escName + '">' + escName + '</div>' +
            '<div class="upload-toast-actions">' + actionControl + '</div>' +
            '</div>' +
            '<div class="upload-toast-item-progress-track">' +
            '<div class="upload-toast-item-progress-fill" style="width:' + pct + '%;"></div>' +
            '</div>' +
            '<div class="upload-toast-item-sub">' + statusLabel + ' &bull; ' + pct + '%</div>' +
            '</div>'
        );
    }

    function buildHeaderActionsHtml(isAllCompleted, pausedCount, isExpanded, totalCount, isDocked) {
        var playPauseBtn = '';
        if (!isAllCompleted && totalCount > 0) {
            if (pausedCount > 0) {
                playPauseBtn = '<button class="btn-icon header-action-btn" data-action="resume-all" title="Resume All Uploads" style="width:24px;height:24px;padding:0;margin-right:4px;">' +
                    '<i data-lucide="play" style="width:14px;height:14px;"></i>' +
                    '</button>';
            } else {
                playPauseBtn = '<button class="btn-icon header-action-btn" data-action="pause-all" title="Pause All Uploads" style="width:24px;height:24px;padding:0;margin-right:4px;">' +
                    '<i data-lucide="pause" style="width:14px;height:14px;"></i>' +
                    '</button>';
            }
        }

        var chevronIcon = isExpanded ? 'chevron-down' : 'chevron-up';
        var toggleBtn = '<button class="btn-icon header-action-btn" data-action="toggle-expand" title="' + (isExpanded ? 'Collapse' : 'Expand') + '" style="width:24px;height:24px;padding:0;">' +
            '<i data-lucide="' + chevronIcon + '" style="width:14px;height:14px;"></i>' +
            '</button>';

        return playPauseBtn + toggleBtn;
    }

    function wireHeaderActions(actionsContainer) {
        if (!actionsContainer) return;
        var btnPause = actionsContainer.querySelector('[data-action="pause-all"]');
        if (btnPause) {
            btnPause.onclick = function (e) {
                e.stopPropagation();
                if (typeof window.pauseAllUploads === 'function') window.pauseAllUploads();
            };
        }
        var btnResume = actionsContainer.querySelector('[data-action="resume-all"]');
        if (btnResume) {
            btnResume.onclick = function (e) {
                e.stopPropagation();
                if (typeof window.resumeAllUploads === 'function') window.resumeAllUploads();
            };
        }
    }

    function wireTrayItemListeners(itemEl, item) {
        if (!itemEl || !item) return;
        var cancelBtn = itemEl.querySelector(".upload-toast-cancel-text");
        if (cancelBtn) {
            cancelBtn.onclick = function (e) {
                e.stopPropagation();
                if (typeof window.cancelUpload === "function") {
                    window.cancelUpload(item.id);
                }
            };
        }
        var resumeBtn = itemEl.querySelector(".upload-toast-resume-text");
        if (resumeBtn) {
            resumeBtn.onclick = function (e) {
                e.stopPropagation();
                if (typeof window.resumeUpload === "function") {
                    window.resumeUpload(item.id);
                }
            };
        }
    }

    window.UploadTrayRenderer = {
        buildTrayItemHtml: buildTrayItemHtml,
        buildHeaderActionsHtml: buildHeaderActionsHtml,
        wireHeaderActions: wireHeaderActions,
        wireTrayItemListeners: wireTrayItemListeners
    };

})(window);
