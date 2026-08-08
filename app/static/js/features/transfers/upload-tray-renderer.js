/**
 * @file upload-tray-renderer.js
 * @description Declarative Notification Tray Renderer & Progress Visualizer.
 * @module UploadTrayRenderer
 */

(function (window) {
    'use strict';

    function saveUploadQueueToStorage() {
        var queue = (typeof window.getUploadQueue === "function" ? window.getUploadQueue() : window.uploadQueue);
        if (!Array.isArray(queue)) return;
        var currentFolder = typeof window.getCurrentFolderPath === 'function' ? window.getCurrentFolderPath() : (window.currentFolderPath || "");
        var serialized = queue.map(function (item) {
            return {
                id: item.id,
                fileName: item.fileName || item.name,
                fileSize: item.fileSize || item.size,
                progress: item.progress,
                status: item.status,
                uploadTime: item.uploadTime,
                isFolder: item.isFolder,
                targetDir: item.targetDir || currentFolder || ""
            };
        });
        try { localStorage.setItem("lanvan_upload_queue", JSON.stringify(serialized)); } catch (e) { }
    }

    var _trayRenderScheduled = false;
    function scheduleUploadTrayRender() {
        if (_trayRenderScheduled) return;
        _trayRenderScheduled = true;
        requestAnimationFrame(function () {
            _trayRenderScheduled = false;
            renderUploadTray();
        });
    }

    function refreshLucideIcons(el) {
        if (window.lucide && typeof window.lucide.createIcons === "function") {
            window.lucide.createIcons({ nameAttr: "data-lucide", attrs: {}, nodes: el ? [el] : undefined });
        }
    }
    window.refreshLucideIcons = refreshLucideIcons;

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
            fillStyle = 'background: rgba(220, 38, 38, 0.12); width: ' + pct + '%;';
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

    function renderUploadTray() {
        window.renderUploadTray = renderUploadTray;
        var stack = document.getElementById("uploadToastStack");
        if (!stack) return;

        var rawQueue = (typeof window.getUploadQueue === "function" ? window.getUploadQueue() : window.uploadQueue);
        var queue = Array.isArray(rawQueue) ? rawQueue : [];
        var activeUploads = queue.filter(function (item) {
            return item && (item.status === "UPLOADING" || item.status === "QUEUED" || item.status === "PROCESSING" || item.status === "PAUSED" || item.status === "COMPLETED" || item.status === "DELETED");
        });

        stack.classList.add("active");

        if (!stack.__delegatedEvents) {
            stack.__delegatedEvents = true;
            stack.addEventListener("click", function (e) {
                var cancelBtn = e.target.closest(".upload-toast-cancel-text");
                if (cancelBtn) {
                    e.stopPropagation();
                    var uploadId = cancelBtn.getAttribute("data-upload-id");
                    if (uploadId && typeof window.cancelUpload === "function") {
                        window.cancelUpload(parseInt(uploadId, 10) || uploadId);
                    }
                    return;
                }
                var resumeBtn = e.target.closest(".upload-toast-resume-text");
                if (resumeBtn) {
                    e.stopPropagation();
                    var uploadId = resumeBtn.getAttribute("data-upload-id");
                    if (uploadId && typeof window.resumeUpload === "function") {
                        window.resumeUpload(parseInt(uploadId, 10) || uploadId);
                    }
                    return;
                }
            });
        }

        activeUploads.sort(function (a, b) {
            function getCategoryScore(item) {
                if (item.status === 'UPLOADING' || item.status === 'PROCESSING') return 1;
                if (item.status === 'QUEUED' || item.status === 'PAUSED') return 2;
                if (item.status === 'COMPLETED') return 3;
                if (item.status === 'DELETED') return 4;
                return 5;
            }

            var scoreA = getCategoryScore(a);
            var scoreB = getCategoryScore(b);

            if (scoreA !== scoreB) {
                return scoreA - scoreB;
            }

            if (scoreA === 3) {
                var idA = a.id || 0;
                var idB = b.id || 0;
                return idB - idA;
            }

            return (a.id || 0) - (b.id || 0);
        });

        var bodyEl = stack.querySelector(".upload-toast-body");

        var totalCount = activeUploads.length;
        var activePendingCount = activeUploads.filter(function (item) { return item.status === "UPLOADING" || item.status === "PROCESSING" || item.status === "QUEUED"; }).length;
        var pausedCount = activeUploads.filter(function (item) { return item.status === "PAUSED"; }).length;
        var completedOrDeletedCount = activeUploads.filter(function (item) { return item.status === "COMPLETED" || item.status === "DELETED"; }).length;
        var isAllCompleted = totalCount > 0 && completedOrDeletedCount === totalCount && pausedCount === 0 && activePendingCount === 0;

        if (completedOrDeletedCount > 5) {
            var activePendingItems = activeUploads.filter(function (item) {
                return item.status === "UPLOADING" || item.status === "PROCESSING" || item.status === "QUEUED" || item.status === "PAUSED";
            });
            var completedItems = activeUploads.filter(function (item) {
                return item.status === "COMPLETED" || item.status === "DELETED";
            }).slice(0, 5);
            activeUploads = activePendingItems.concat(completedItems);
        }

        if (isAllCompleted && totalCount > 0) {
            if (!window._trayAutoDismissTimer) {
                window._trayAutoDismissTimer = setTimeout(function () {
                    window._trayAutoDismissTimer = null;
                    if (window.LanvanStore) {
                        window.LanvanStore.dispatch("CLEAR_COMPLETED_UPLOADS");
                        renderUploadTray();
                    }
                }, 5000);
            }
        } else {
            if (window._trayAutoDismissTimer) {
                clearTimeout(window._trayAutoDismissTimer);
                window._trayAutoDismissTimer = null;
            }
        }

        activeUploads.forEach(function (item) {
            if (item && (item.status === 'DELETED' || item.status === 'CANCELLED') && !item._dismissTimer) {
                item._dismissTimer = setTimeout(function () {
                    if (window.LanvanStore) {
                        var curQueue = window.LanvanStore.getState().uploadQueue.filter(function (i) { return i && i.id != item.id; });
                        window.LanvanStore.dispatch("SYNC_QUEUE", { queue: curQueue });
                        renderUploadTray();
                    }
                }, 2000);
            }
        });

        saveUploadQueueToStorage();

        if (totalCount === 0 || window.uploadTrayDocked) {
            stack.classList.add("empty-state");
        } else {
            stack.classList.remove("empty-state");
        }

        var batchSummary = window.buildUploadBatchSummary
            ? window.buildUploadBatchSummary(window.uploadQueue || [])
            : { totalFiles: totalCount, isComplete: isAllCompleted, percent: 0, totalSpeed: 0, status: 'IDLE' };
        var formatted = window.formatUploadBatchStatus
            ? window.formatUploadBatchStatus(batchSummary)
            : { title: "Uploading...", subtitle: "", percent: 0, speedStr: "", status: "UPLOADING" };

        var avgPct = formatted.percent;
        var headerTitle = formatted.line1;
        var headerSubtitle = formatted.line2 || "";

        var headerTitleEl = stack.querySelector(".upload-toast-header-title");
        var headerProgressBar = stack.querySelector(".header-progress-bar");
        bodyEl = stack.querySelector(".upload-toast-body");

        if (!headerTitleEl || !bodyEl) {
            var itemsHtml = "";
            for (var i = 0; i < activeUploads.length; i++) {
                itemsHtml += buildTrayItemHtml(activeUploads[i]);
            }

            var isBodyCollapsed = !window.uploadManagerExpanded;
            var bodyClass = isBodyCollapsed ? "upload-toast-body collapsed" : "upload-toast-body";
            var headerActionsHtml = buildHeaderActionsHtml(isAllCompleted, pausedCount, window.uploadManagerExpanded, totalCount, window.uploadTrayDocked);

            var widgetHtml =
                '<div class="upload-toast-header" style="position: relative; overflow: hidden;">' +
                '<div class="header-progress-bar" style="position: absolute; top:0; left:0; bottom:0; background: rgba(59, 130, 246, 0.08); z-index: 1; transition: width 0.2s ease-out; width: ' + avgPct + '%;"></div>' +
                '<div style="position: relative; z-index: 2; display: flex; flex-direction: column; min-width: 0; flex: 1;">' +
                '<span class="upload-toast-header-title">' + headerTitle + '</span>' +
                '<div class="upload-toast-header-subtitle" style="font-size:0.72rem;color:var(--text-muted);opacity:0.85;white-space:nowrap;overflow:hidden;display:flex;align-items:center;justify-content:space-between;gap:8px;width:100%;min-height:16px;">' +
                '<span class="tray-speed-text">' + (formatted.speed || headerSubtitle || "Calculating...") + '</span>' +
                '</div>' +
                '</div>' +
                '<div class="upload-toast-header-actions" style="position: relative; z-index: 2; display: flex; align-items: center;">' +
                headerActionsHtml +
                '</div>' +
                '</div>' +
                '<div class="' + bodyClass + '">' +
                itemsHtml +
                '</div>';

            stack.innerHTML = widgetHtml;
            refreshLucideIcons(stack);

            wireHeaderActions(stack.querySelector(".upload-toast-header-actions"));

            stack.querySelector(".upload-toast-header").addEventListener("click", function (e) {
                if (!e.target.closest(".upload-toast-header-actions")) {
                    var queue = window.uploadQueue || [];
                    var hasItems = queue.some(function (item) {
                        return item && (item.status === "UPLOADING" || item.status === "QUEUED" || item.status === "PROCESSING" || item.status === "PAUSED" || item.status === "COMPLETED" || item.status === "DELETED");
                    });
                    if (!hasItems) return;

                    window.uploadManagerExpanded = !window.uploadManagerExpanded;
                    var body = stack.querySelector(".upload-toast-body");
                    if (body) {
                        if (window.uploadManagerExpanded) {
                            body.classList.remove("collapsed");
                        } else {
                            body.classList.add("collapsed");
                        }
                    }
                    var actionsEl = stack.querySelector(".upload-toast-header-actions");
                    if (actionsEl) {
                        actionsEl.innerHTML = buildHeaderActionsHtml(isAllCompleted, pausedCount, window.uploadManagerExpanded, totalCount, window.uploadTrayDocked);
                        wireHeaderActions(actionsEl);
                    }
                }
            });

            headerTitleEl = stack.querySelector(".upload-toast-header-title");
            headerProgressBar = stack.querySelector(".header-progress-bar");
            bodyEl = stack.querySelector(".upload-toast-body");

            for (var i = 0; i < activeUploads.length; i++) {
                var item = activeUploads[i];
                var itemEl = stack.querySelector("#toast-item-" + item.id);
                if (itemEl) {
                    wireTrayItemListeners(itemEl, item);
                }
            }
        }

        if (!stack._trayDOMCache) {
            stack._trayDOMCache = {
                title: stack.querySelector(".upload-toast-header-title"),
                subtitle: stack.querySelector(".upload-toast-header-subtitle"),
                speedEl: stack.querySelector(".tray-speed-text"),
                progressBar: stack.querySelector(".header-progress-bar")
            };
        }
        var trayDOM = stack._trayDOMCache;

        if (trayDOM.title && trayDOM.title.textContent !== headerTitle) {
            trayDOM.title.textContent = headerTitle;
        }
        if (trayDOM.subtitle) {
            var speedTxt = formatted.speed || headerSubtitle || ((batchSummary.state === 'UPLOADING' || batchSummary.state === 'PROCESSING') ? "Calculating..." : "");
            if (speedTxt) {
                if (trayDOM.speedEl && trayDOM.speedEl.textContent !== speedTxt) {
                    trayDOM.speedEl.textContent = speedTxt;
                }
            }
        }
        if (trayDOM.progressBar) {
            var newWidth = avgPct + "%";
            if (trayDOM.progressBar.style.width !== newWidth) {
                trayDOM.progressBar.style.width = newWidth;
            }
        }

        var actionsContainer = stack.querySelector(".upload-toast-header-actions");
        if (actionsContainer) {
            var newActionsHtml = buildHeaderActionsHtml(isAllCompleted, pausedCount, window.uploadManagerExpanded, totalCount, window.uploadTrayDocked);
            if (actionsContainer.getAttribute("data-last-html") !== newActionsHtml) {
                actionsContainer.setAttribute("data-last-html", newActionsHtml);
                actionsContainer.innerHTML = newActionsHtml;
                wireHeaderActions(actionsContainer);
                refreshLucideIcons(actionsContainer);
            }
        }

        if (bodyEl) {
            if (window.uploadManagerExpanded) {
                bodyEl.classList.remove("collapsed");
            } else {
                bodyEl.classList.add("collapsed");
            }
        }

        var activeIds = {};
        for (var i = 0; i < activeUploads.length; i++) {
            var item = activeUploads[i];
            activeIds[item.id] = true;
            var itemEl = bodyEl.querySelector("#toast-item-" + item.id);
            if (!itemEl) {
                var tempDiv = document.createElement("div");
                tempDiv.innerHTML = buildTrayItemHtml(item);
                var newItemEl = tempDiv.firstChild;
                bodyEl.appendChild(newItemEl);
                refreshLucideIcons(newItemEl);
                wireTrayItemListeners(newItemEl, item);
            } else {
                var pct = Math.round(item.progress || 0);
                var sizeStr = typeof formatSize === "function" ? formatSize(item.fileSize) : (item.fileSize + " B");

                var metaText = "";
                var fillStyle = "";
                var actionHtml = "";

                if (item.status === 'DELETED' || item.status === 'CANCELLED') {
                    metaText = sizeStr + " • " + (item.status === 'DELETED' ? 'Deleted' : 'Cancelled');
                    fillStyle = 'rgba(220, 38, 38, 0.12)';
                    actionHtml = '<span style="color: #dc2626; display: flex; align-items: center; margin-right: 8px;"><i data-lucide="' + (item.status === 'DELETED' ? 'trash-2' : 'x') + '" style="width:16px;height:16px;"></i></span>';
                } else if (item.status === 'COMPLETED' || (pct >= 100 && item.status !== 'UPLOADING' && item.status !== 'PAUSED')) {
                    var timeStr = item.uploadTime ? item.uploadTime + "s" : "completed";
                    metaText = sizeStr + " • Completed (" + timeStr + ")";
                    fillStyle = 'rgba(24, 128, 56, 0.08)';
                    pct = 100;
                    actionHtml = '<span style="color: var(--green); display: inline-flex; align-items: center; justify-content: center; margin-right: 8px;"><i data-lucide="check" style="width:16px;height:16px;"></i></span>';
                } else if (item.status === 'QUEUED') {
                    metaText = sizeStr + " • Queued";
                    fillStyle = 'transparent';
                    pct = 0;
                } else {
                    metaText = sizeStr + " • " + pct + "%";
                    fillStyle = 'rgba(59, 130, 246, 0.08)';
                }

                var metaEl = itemEl.querySelector(".upload-toast-meta");
                if (metaEl && metaEl.textContent !== metaText) metaEl.textContent = metaText;

                var progressFill = itemEl.querySelector(".toast-progress-bar");
                if (progressFill) {
                    var newWidth = pct + "%";
                    if (progressFill.style.width !== newWidth) progressFill.style.width = newWidth;
                    if (progressFill.style.background !== fillStyle) progressFill.style.background = fillStyle;
                }

                if (item.status === 'COMPLETED' || item.status === 'DELETED') {
                    var itemActionsContainer = itemEl.querySelector(".upload-toast-actions");
                    if (itemActionsContainer && itemActionsContainer.querySelector(".upload-toast-cancel-text")) {
                        itemActionsContainer.innerHTML = actionHtml;
                        refreshLucideIcons(itemActionsContainer);
                    }
                    wireTrayItemListeners(itemEl, item);
                }

                if (bodyEl.children[i] !== itemEl) {
                    bodyEl.appendChild(itemEl);
                }
            }
        }

        var existingItems = bodyEl.querySelectorAll(".upload-toast");
        for (var j = 0; j < existingItems.length; j++) {
            var itemEl = existingItems[j];
            var idAttr = itemEl.getAttribute("id");
            if (idAttr) {
                var itemId = parseInt(idAttr.replace("toast-item-", ""));
                if (!activeIds[itemId]) {
                    itemEl.remove();
                }
            }
        }

        refreshLucideIcons(stack);
    }

    var uploadTrayInterval = null;
    function startUploadTrayPolling() {
        if (uploadTrayInterval) return;
        uploadTrayInterval = setInterval(function () {
            var queue = window.uploadQueue || [];
            var activeCount = queue.filter(function (item) {
                return item.status === "UPLOADING" || item.status === "QUEUED" || item.status === "PROCESSING" || item.status === "PAUSED";
            }).length;
            if (activeCount === 0) {
                renderUploadTray();
                clearInterval(uploadTrayInterval);
                uploadTrayInterval = null;
            } else {
                renderUploadTray();
            }
        }, 500);
    }

    window.UploadTrayRenderer = {
        render: renderUploadTray,
        renderUploadTray: renderUploadTray,
        scheduleUploadTrayRender: scheduleUploadTrayRender,
        saveUploadQueueToStorage: saveUploadQueueToStorage,
        startUploadTrayPolling: startUploadTrayPolling,
        buildTrayItemHtml: buildTrayItemHtml,
        buildHeaderActionsHtml: buildHeaderActionsHtml,
        wireHeaderActions: wireHeaderActions,
        wireTrayItemListeners: wireTrayItemListeners
    };

    window.renderUploadTray = renderUploadTray;
    window.scheduleUploadTrayRender = scheduleUploadTrayRender;
    window.saveUploadQueueToStorage = saveUploadQueueToStorage;
    window.startUploadTrayPolling = startUploadTrayPolling;
    window.buildTrayItemHtml = buildTrayItemHtml;
    window.buildHeaderActionsHtml = buildHeaderActionsHtml;
    window.wireHeaderActions = wireHeaderActions;
    window.wireTrayItemListeners = wireTrayItemListeners;

})(window);
