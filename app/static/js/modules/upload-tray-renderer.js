/**
 * @file upload-tray-renderer.js
 * @description Declarative Notification Tray Renderer & Progress Visualizer.
 * @module UploadTrayRenderer
 */

(function (window) {
    'use strict';

    function buildTrayItemHtml(item) {
        var pct = Math.round(typeof window.getItemProgress === "function" ? window.getItemProgress(item) : (item.progress || 0));
        var rawName = typeof window.getItemName === "function" ? window.getItemName(item) : (item.fileName || item.name || "File");
        var name = typeof escapeHtml === "function" ? escapeHtml(rawName) : rawName;
        var rawSize = typeof window.getItemSize === "function" ? window.getItemSize(item) : (item.fileSize || 0);
        var sizeStr = typeof formatSize === "function" ? formatSize(rawSize) : (rawSize + " B");

        var metaText = "";
        var fillStyle = "";
        var actionHtml = "";

        if (item.status === 'DELETED' || item.status === 'CANCELLED' || item.status === 'FAILED') {
            var label = item.status === 'DELETED' ? 'Deleted' : (item.status === 'FAILED' ? 'Failed' : 'Cancelled');
            metaText = sizeStr + " • " + label;
            fillStyle = 'background: rgba(220, 38, 38, 0.06); width: 100%;';
            actionHtml = '<span style="color: #dc2626; font-size:0.75rem; font-weight:600; margin-right: 8px;">' + label + '</span>';
        } else if (item.status === 'COMPLETED' || (pct >= 100 && item.status !== 'UPLOADING' && item.status !== 'PAUSED')) {
            var timeStr = item.uploadTime ? item.uploadTime + "s" : "completed";
            metaText = sizeStr + " • Completed (" + timeStr + ")";
            fillStyle = 'background: rgba(24, 128, 56, 0.08); width: 100%;';
            actionHtml = '<span style="color: var(--green); display: inline-flex; align-items: center; justify-content: center; margin-right: 8px;"><svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"></polyline></svg></span>';
        } else if (item.status === 'PAUSED') {
            metaText = sizeStr + " • " + pct + "% (Paused)";
            fillStyle = 'background: rgba(234, 179, 8, 0.12); width: ' + pct + '%;';
            actionHtml = '<button type="button" class="upload-toast-resume-text" data-upload-id="' + item.id + '" title="Resume upload" style="background:none; border:none; color:var(--primary, #3b82f6); cursor:pointer; font-weight:500; font-size:0.8rem; margin-right:8px; padding:2px 4px;">' +
                '<span>Resume</span>' +
                '</button>' +
                '<button type="button" class="upload-toast-cancel-text" data-upload-id="' + item.id + '" title="Cancel upload">' +
                '<span>Cancel</span>' +
                '</button>';
        } else if (item.status === 'QUEUED') {
            metaText = sizeStr + " • Queued";
            fillStyle = 'background: transparent; width: 0%;';
            actionHtml = '<button type="button" class="upload-toast-cancel-text" data-upload-id="' + item.id + '" title="Cancel upload">' +
                '<span>Cancel</span>' +
                '</button>';
        } else {
            metaText = sizeStr + " • " + pct + "%";
            fillStyle = 'background: rgba(59, 130, 246, 0.08); width: ' + pct + '%;';
            actionHtml = '<button type="button" class="upload-toast-cancel-text" data-upload-id="' + item.id + '" title="Cancel upload">' +
                '<span>Cancel</span>' +
                '</button>';
        }

        var completedClass = (item.status === 'COMPLETED') ? ' completed-toast' : (item.status === 'DELETED' ? ' deleted-toast' : '');
        var cursorStyle = (item.status === 'COMPLETED' || item.status === 'DELETED') ? ' cursor: pointer;' : '';
        var itemTargetDir = item.targetDir || "";

        return '<div class="upload-toast' + completedClass + '" id="toast-item-' + item.id + '" style="position:relative; overflow:hidden;' + cursorStyle + '" data-target-dir="' + (typeof escapeHtml === "function" ? escapeHtml(itemTargetDir) : itemTargetDir) + '" data-filename="' + name + '">' +
            '<div class="toast-progress-bar" style="position:absolute; top:0; bottom:0; left:0; ' + fillStyle + ' transition:width 0.2s ease-out; pointer-events:none; z-index:1;"></div>' +
            '<div class="upload-toast-top" style="position:relative; z-index:2; width:100%;">' +
            '<div class="upload-toast-title">' +
            '<span class="upload-toast-filename" title="' + name + '">' + name + "</span>" +
            '<span class="upload-toast-meta">' + metaText + "</span>" +
            "</div>" +
            '<div class="upload-toast-actions">' +
            actionHtml +
            "</div>" +
            "</div>" +
            "</div>";
    }

    function buildHeaderActionsHtml(isAllCompleted, pausedCount, expanded, totalCount, docked) {
        var toggleHtml = "";
        var actionBtnHtml = "";

        var svgChevronDown = '<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="6 9 12 15 18 9"></polyline></svg>';
        var svgChevronUp = '<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="18 15 12 9 6 15"></polyline></svg>';
        var svgPlay = '<svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor" stroke="none"><polygon points="5 3 19 12 5 21 5 3"></polygon></svg>';
        var svgPause = '<svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor" stroke="none"><rect x="6" y="4" width="4" height="16"></rect><rect x="14" y="4" width="4" height="16"></rect></svg>';
        var svgClose = '<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>';
        var svgPlus = '<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="12" y1="5" x2="12" y2="19"></line><line x1="5" y1="12" x2="19" y2="12"></line></svg>';

        if (totalCount > 0) {
            var chevronSvg = expanded ? svgChevronDown : svgChevronUp;
            var chevronBtn = '<button type="button" class="upload-toast-header-btn header-expand-btn" title="Toggle detailed list" style="display:inline-flex; align-items:center; justify-content:center;">' +
                chevronSvg +
                '</button>';

            if (isAllCompleted) {
                toggleHtml = chevronBtn;
            } else {
                var playPauseBtn = "";
                if (pausedCount > 0) {
                    playPauseBtn = '<button type="button" class="upload-toast-header-btn header-playpause-btn" title="Resume all uploads" data-action="resume" style="display:inline-flex; align-items:center; justify-content:center;">' +
                        svgPlay +
                        '</button>';
                } else {
                    playPauseBtn = '<button type="button" class="upload-toast-header-btn header-playpause-btn" title="Pause all uploads" data-action="pause" style="display:inline-flex; align-items:center; justify-content:center;">' +
                        svgPause +
                        '</button>';
                }
                toggleHtml = playPauseBtn + chevronBtn;
            }
            actionBtnHtml = '<button type="button" class="upload-toast-header-btn close-panel-btn" title="Cancel all uploads and close" style="display:inline-flex; align-items:center; justify-content:center;">' +
                svgClose +
                '</button>';
        } else {
            actionBtnHtml = '<button type="button" class="upload-toast-header-btn open-menu-btn" title="Upload or Create" style="display:inline-flex; align-items:center; justify-content:center;">' +
                svgPlus +
                '</button>';
        }

        return toggleHtml + actionBtnHtml;
    }

    function wireHeaderActions(actionsContainer) {
        if (!actionsContainer) return;
        var playPauseBtn = actionsContainer.querySelector(".header-playpause-btn");
        if (playPauseBtn) {
            playPauseBtn.addEventListener("click", function (e) {
                e.stopPropagation();
                var action = this.getAttribute("data-action");
                if (action === "pause") {
                    if (typeof window.pauseAllUploads === 'function') window.pauseAllUploads();
                } else {
                    if (typeof window.resumeAllUploads === 'function') window.resumeAllUploads();
                }
            });
        }
        var expandBtn = actionsContainer.querySelector(".header-expand-btn");
        if (expandBtn) {
            expandBtn.addEventListener("click", function (e) {
                e.stopPropagation();
                window.uploadManagerExpanded = !window.uploadManagerExpanded;
                if (typeof window.renderUploadTray === "function") {
                    window.renderUploadTray();
                } else if (typeof renderUploadTray === "function") {
                    renderUploadTray();
                }
            });
        }
        var expandDockBtn = actionsContainer.querySelector(".header-expand-dock-btn");
        if (expandDockBtn) {
            expandDockBtn.addEventListener("click", function (e) {
                e.stopPropagation();
                window.uploadManagerExpanded = !window.uploadManagerExpanded;
                if (typeof window.renderUploadTray === "function") {
                    window.renderUploadTray();
                } else if (typeof renderUploadTray === "function") {
                    renderUploadTray();
                }
            });
        }
        var closeBtn = actionsContainer.querySelector(".close-panel-btn");
        if (closeBtn) {
            closeBtn.addEventListener("click", function (e) {
                e.stopPropagation();
                if (window.uploadQueue) {
                    var hasActive = window.uploadQueue.some(function (i) {
                        return i.status === 'UPLOADING' || i.status === 'QUEUED' || i.status === 'PROCESSING' || i.status === 'PAUSED';
                    });
                    if (!hasActive) {
                        if (window._trayAutoDismissTimer) {
                            clearTimeout(window._trayAutoDismissTimer);
                            window._trayAutoDismissTimer = null;
                        }
                        if (window.LanvanStore) {
                            window.LanvanStore.dispatch("CLEAR_COMPLETED_UPLOADS");
                        }
                        if (typeof window.triggerInstantUIUpdate === "function") {
                            window.triggerInstantUIUpdate();
                        }
                        if (typeof window.renderUploadTray === "function") {
                            window.renderUploadTray();
                        } else if (typeof renderUploadTray === "function") {
                            renderUploadTray();
                        }
                        return;
                    }
                }
                if (typeof window.cancelAllUploads === "function") {
                    window.cancelAllUploads();
                }
            });
        }
        var openMenuBtn = actionsContainer.querySelector(".open-menu-btn");
        if (openMenuBtn) {
            openMenuBtn.addEventListener("click", function (e) {
                e.stopPropagation();
                var rect = this.getBoundingClientRect();
                if (typeof window.showGenericContextMenu === "function") {
                    window.showGenericContextMenu(rect.left - 120, rect.top - 110);
                }
            });
        }
    }


    function wireTrayItemListeners(el, item) {
        if (!el || !item) return;
        var cancelBtn = el.querySelector(".upload-toast-cancel-text");
        if (cancelBtn && !cancelBtn.__cancelWired) {
            cancelBtn.__cancelWired = true;
            cancelBtn.addEventListener("click", function (e) {
                e.stopPropagation();
                if (typeof window.cancelUpload === "function") {
                    window.cancelUpload(item.id);
                }
            });
        }
        var resumeBtn = el.querySelector(".upload-toast-resume-text");
        if (resumeBtn && !resumeBtn.__resumeWired) {
            resumeBtn.__resumeWired = true;
            resumeBtn.addEventListener("click", function (e) {
                e.stopPropagation();
                if (typeof window.resumeUpload === "function") {
                    window.resumeUpload(item.id);
                }
            });
        }
        if (item.status === 'COMPLETED' && !el.__navWired) {
            el.__navWired = true;
            el.style.cursor = "pointer";
            el.addEventListener("click", function (e) {
                if (e.target.closest("button") || e.target.closest(".upload-toast-actions")) return;
                if (typeof window.navigateToPathAndSelect === "function") {
                    window.navigateToPathAndSelect(item.targetDir || "", item.fileName || item.name || "");
                }
            });
        }
    }

    window.UploadTrayRenderer = {
        buildTrayItemHtml: buildTrayItemHtml,
        buildHeaderActionsHtml: buildHeaderActionsHtml,
        wireHeaderActions: wireHeaderActions,
        wireTrayItemListeners: wireTrayItemListeners
    };

    window.buildTrayItemHtml = buildTrayItemHtml;
    window.buildHeaderActionsHtml = buildHeaderActionsHtml;
    window.wireHeaderActions = wireHeaderActions;
    window.wireTrayItemListeners = wireTrayItemListeners;

})(window);
