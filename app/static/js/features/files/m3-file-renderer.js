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
                var queue = Array.isArray(window.uploadQueue) ? window.uploadQueue : [];
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
        var progressBarHtml = (isUploading && !isFolder)
            ? '<div class="row-progress-bar" style="position:absolute; top:0; bottom:0; left:0; width:100%; height:100%; background:rgba(59, 130, 246, 0.08); transform:scaleX(' + (pct / 100) + '); transform-origin:left center; transition:transform 0.25s ease-out, width 0.25s ease-out; pointer-events:none; z-index:1;"></div>'
            : '';

        var actionsHtml = '';
        if (isUploading && !isFolder) {
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

        var formattedDate = (typeof formatLastModified === 'function' && (!isUploading || isFolder) && dateText && dateText !== '--') ? formatLastModified(dateText) : { display: dateText || "--", tooltip: dateText || "" };
        var displayDate = (isUploading && !isFolder) ? (uploadStatus === 'PAUSED' ? 'Paused' : (uploadStatus === 'QUEUED' ? 'Queued' : 'Uploading')) : formattedDate.display;

        var dateTooltip = isUploading ? "" : (formattedDate.tooltip || formattedDate.display);

        var hasVersions = false;
        var versionCount = 1;
        if (window._fileMetadataMap && window._fileMetadataMap[name]) {
            hasVersions = !!window._fileMetadataMap[name].hasVersions;
            versionCount = window._fileMetadataMap[name].versionCount || 1;
        }
        var versionBadgeHtml = hasVersions
            ? '<span class="version-pill-badge" title="Version ' + versionCount + ' (Has version history)" style="font-size:0.72rem; font-weight:700; padding:2px 8px; border-radius:12px; margin-left:8px; background:var(--primary-bg, rgba(37,99,235,0.12)); color:var(--primary, #2563eb); border:1px solid var(--primary-border, rgba(37,99,235,0.3)); vertical-align:middle; display:inline-flex; align-items:center; letter-spacing:0.02em;">v' + versionCount + '</span>'
            : '';

        return (
            '<div class="m3-list-item' + (isUploading ? ' uploading' : '') + '" data-filename="' + escName + '" data-is-folder="' + (isFolder ? '1' : '0') + '" style="' + (isUploading ? 'position:relative; overflow:hidden;' : '') + '">' +
            progressBarHtml +
            '<div class="file-name-cell" style="position:relative; z-index:2;">' +
            '<div class="avatar-icon ' + itemInfo.avatarClass + '"><i data-lucide="' + itemInfo.iconName + '"></i></div>' +
            '<div class="item-main">' +
            '<div class="item-title">' + escName + versionBadgeHtml + '</div>' +
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
        if (hasActiveUpload && !isFolder) {
            var displayPct = Math.round(pct);
            var statusText = uploadStatus === 'PAUSED' ? 'Paused' : (uploadStatus === 'QUEUED' ? 'Queued' : 'Uploading');
            progressBarHtml =
                '<div class="glass-b4-body">' +
                '<div class="b4-badge">' +
                '<div class="b4-num">' + displayPct + '%</div>' +
                '<div class="b4-sub">' + statusText + '</div>' +
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

        var hasVersions = false;
        var versionCount = 1;
        if (window._fileMetadataMap && window._fileMetadataMap[name]) {
            hasVersions = !!window._fileMetadataMap[name].hasVersions;
            versionCount = window._fileMetadataMap[name].versionCount || 1;
        }
        var versionBadgeHtml = hasVersions
            ? '<span class="version-pill-badge" title="Version ' + versionCount + ' (Has version history)" style="font-size:0.68rem; font-weight:700; padding:1px 6px; border-radius:10px; margin-left:6px; background:var(--primary-bg, rgba(37,99,235,0.12)); color:var(--primary, #2563eb); border:1px solid var(--primary-border, rgba(37,99,235,0.3)); vertical-align:middle; display:inline-flex; align-items:center; letter-spacing:0.02em;">v' + versionCount + '</span>'
            : '';

        return (
            '<div class="m3-list-item' + (isUploading ? ' uploading' : '') + '" data-filename="' + escName + '" data-is-folder="' + (isFolder ? '1' : '0') + '" style="position:relative; overflow:hidden;">' +
            '<div class="grid-card-head" style="position:relative; z-index:20; background:var(--card-bg, #ffffff);">' +
            '<div class="avatar-icon ' + itemInfo.avatarClass + '"><i data-lucide="' + itemInfo.iconName + '"></i></div>' +
            '<div style="display:flex; flex-direction:column; min-width:0; flex:1;">' +
            '<div class="item-title" title="' + escName + '">' + escName + versionBadgeHtml + '</div>' +
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

    // --- Private Renderer State ---
    var lastRenderedFiles = [];
    var _lastRenderSignature = null;
    var _renderHasPainted = false;

    function getDiskFileMetadata(filename, folderPath) {
        if (!filename) return null;
        var path = folderPath || (typeof window.lanvanStore !== 'undefined' && window.lanvanStore.getState ? window.lanvanStore.getState().currentFolder : (window.currentFolderPath || ""));
        var cache = (window.FileRepository && typeof window.FileRepository.getFolderCache === 'function')
            ? window.FileRepository.getFolderCache(path)
            : [];
        var match = (cache || []).find(function (f) {
            if (!f) return false;
            var fn = typeof f === 'string' ? f : f.name;
            return fn && fn.trim().toLowerCase() === String(filename).trim().toLowerCase();
        });
        if (match) {
            if (typeof match === 'object') {
                return Object.assign({}, match, {
                    isFolder: !!(match.isFolder || match.is_dir || match.is_folder || (window._recentlyCreatedFolders && window._recentlyCreatedFolders[filename]))
                });
            } else if (typeof match === 'string') {
                var isF = !!(window._recentlyCreatedFolders && window._recentlyCreatedFolders[match]);
                return { name: match, size: "--", mtime: 0, isFolder: isF };
            }
        }
        return match || null;
    }

    function syncFileTableHeadWidth() {
        var head = document.getElementById("fileTableHead");
        var list = document.getElementById("nasFileList");
        if (!head || !list) return;

        var mode = document.documentElement.getAttribute("data-view-mode") || (list.classList.contains("grid-mode") ? "grid" : "list");
        if (mode === "grid") {
            head.style.removeProperty("padding-right");
            return;
        }

        var scrollbarWidth = list.offsetWidth - list.clientWidth;
        head.style.setProperty("padding-right", (12 + Math.max(0, scrollbarWidth)) + "px", "important");
    }

    function getFileTypeInfo(name, ext) {
        var imageExts = ["png", "jpg", "jpeg", "gif", "webp", "svg", "bmp", "ico"];
        var videoExts = ["mp4", "mov", "avi", "mkv", "webm", "flv", "wmv"];
        var audioExts = ["mp3", "wav", "ogg", "flac", "aac", "m4a"];
        var archiveExts = ["zip", "rar", "7z", "tar", "gz", "bz2"];
        var docExts = ["pdf", "doc", "docx", "xls", "xlsx", "ppt", "pptx", "txt", "md", "csv"];

        if (imageExts.indexOf(ext) !== -1) return { avatarClass: "avatar-image", iconName: "image" };
        if (videoExts.indexOf(ext) !== -1) return { avatarClass: "avatar-video", iconName: "video" };
        if (audioExts.indexOf(ext) !== -1) return { avatarClass: "avatar-audio", iconName: "music" };
        if (archiveExts.indexOf(ext) !== -1) return { avatarClass: "avatar-archive", iconName: "archive" };
        if (docExts.indexOf(ext) !== -1) return { avatarClass: "avatar-doc", iconName: "file-text" };
        return { avatarClass: "avatar-doc", iconName: "file" };
    }

    function attachListItemHandlers(container, files, filesData) {
        var items = container.querySelectorAll(".m3-list-item");
        for (var i = 0; i < items.length; i++) {
            (function (item, index) {
                var name = files[index];
                var itemData = (filesData || [])[index] || {};
                var folderFlag = item.getAttribute("data-is-folder") === "1" || !!itemData.isFolder;

                var touchStartPos = null;
                var isLongPress = false;
                var longPressTimer = null;

                item.addEventListener("touchstart", function (e) {
                    if (e.touches.length > 1) return;
                    touchStartPos = { x: e.touches[0].clientX, y: e.touches[0].clientY };
                    isLongPress = false;

                    longPressTimer = setTimeout(function () {
                        isLongPress = true;
                        if (typeof handleListItemClick === "function") {
                            handleListItemClick(item, index, files, { isLongPress: true });
                        }
                    }, 400);
                }, { passive: true });

                item.addEventListener("touchmove", function (e) {
                    if (touchStartPos && e.touches.length === 1) {
                        var dx = Math.abs(e.touches[0].clientX - touchStartPos.x);
                        var dy = Math.abs(e.touches[0].clientY - touchStartPos.y);
                        if (dx > 10 || dy > 10) {
                            if (longPressTimer) clearTimeout(longPressTimer);
                        }
                    }
                }, { passive: true });

                item.addEventListener("touchend", function (e) {
                    if (longPressTimer) clearTimeout(longPressTimer);
                    if (isLongPress) {
                        e.preventDefault();
                        e.stopPropagation();
                        window._justHandledTouchSelection = true;
                        setTimeout(function () { window._justHandledTouchSelection = false; }, 350);
                    }
                });

                item.addEventListener("click", function (e) {
                    if (window._justFinishedMarqueeDrag || window._justHandledTouchSelection) {
                        e.stopPropagation();
                        e.preventDefault();
                        return;
                    }
                    if (e.target.closest("button")) return;

                    var currentSelection = window.selectedItems || [];

                    if (e.ctrlKey || e.metaKey || e.shiftKey || currentSelection.length > 0) {
                        e.preventDefault();
                        e.stopPropagation();
                        if (typeof handleListItemClick === "function") {
                            handleListItemClick(item, index, files, e);
                        }
                        return;
                    }

                    if (folderFlag) {
                        if (typeof navigateIntoFolder === "function") navigateIntoFolder(name);
                        return;
                    }

                    if ((itemData.uploading || (typeof isItemUploading === "function" && isItemUploading(name)))) {
                        return;
                    }

                    e.preventDefault();
                    e.stopPropagation();
                    if (typeof handleListItemClick === "function") {
                        handleListItemClick(item, index, files, e);
                    }
                    if (typeof window.openFilePreview === "function") {
                        window.openFilePreview(name);
                    }
                });

                item.addEventListener("contextmenu", function (e) {
                    if (e.target.closest("button")) return;
                    if (!folderFlag && (itemData.uploading || (typeof isItemUploading === "function" && isItemUploading(name)))) {
                        e.preventDefault();
                        e.stopPropagation();
                        return;
                    }
                    e.preventDefault();
                    if (typeof openRowMenu === "function") openRowMenu(e, name);
                });

                item.addEventListener("dblclick", function (e) {
                    if (e.target.closest("button")) return;
                    var currentSelection = window.selectedItems || [];
                    if (currentSelection.length > 0) {
                        e.preventDefault();
                        e.stopPropagation();
                        return;
                    }
                    if (folderFlag) {
                        if (typeof navigateIntoFolder === "function") navigateIntoFolder(name);
                        return;
                    }
                    if (itemData.uploading || (typeof isItemUploading === "function" && isItemUploading(name))) return;
                    if (typeof window.openFilePreview === "function") window.openFilePreview(name);
                });

                var cancelBtn = item.querySelector('[data-action="cancel-upload"]');
                if (cancelBtn) {
                    cancelBtn.addEventListener("click", function (e) {
                        e.stopPropagation();
                        var uploadId = cancelBtn.getAttribute("data-upload-id");
                        if (uploadId && typeof window.cancelUpload === "function") {
                            window.cancelUpload(parseInt(uploadId));
                        }
                    });
                }

                var playPauseBtn = item.querySelector('[data-action="pause-upload"], [data-action="resume-upload"]');
                if (playPauseBtn) {
                    playPauseBtn.addEventListener("click", function (e) {
                        e.stopPropagation();
                        var uploadId = playPauseBtn.getAttribute("data-upload-id");
                        var action = playPauseBtn.getAttribute("data-action");
                        if (uploadId) {
                            var parsedId = parseInt(uploadId);
                            if (action === "pause-upload" && typeof window.pauseUpload === "function") {
                                window.pauseUpload(parsedId);
                            } else if (action === "resume-upload" && typeof window.resumeUpload === "function") {
                                window.resumeUpload(parsedId);
                            }
                        }
                    });
                }

                var dlBtn = item.querySelector('[data-action="download"]');
                if (dlBtn) {
                    dlBtn.addEventListener("click", function (e) {
                        e.stopPropagation();
                        var fname = dlBtn.getAttribute("data-filename");
                        var isF = dlBtn.getAttribute("data-is-folder") === "1";
                        if (isF) {
                            if (typeof downloadFolderAsZip === "function") downloadFolderAsZip(fname);
                        } else {
                            if (typeof downloadFileByName === "function") downloadFileByName(fname);
                        }
                    });
                }

                var renameBtn = item.querySelector('[data-action="rename"]');
                if (renameBtn) {
                    renameBtn.addEventListener("click", function (e) {
                        e.stopPropagation();
                        var fname = renameBtn.getAttribute("data-filename");
                        window.selectedItems = [fname];
                        window._contextMenuTarget = fname;
                        if (typeof window.openRenameModal === "function") window.openRenameModal();
                    });
                }

                var menuBtn = item.querySelector('[data-action="menu"]');
                if (menuBtn) {
                    menuBtn.addEventListener("click", function (e) {
                        e.stopPropagation();
                        var fname = menuBtn.getAttribute("data-filename");
                        if (typeof openRowMenu === "function") openRowMenu(e, fname);
                    });
                }
            })(items[i], i);
        }
    }

    function renderFileList(files, renderReason) {
        if (window.__lanvanTimelineTracker) {
            var fCount = Array.isArray(files) ? files.length : (files ? 1 : 0);
            window.__lanvanTimelineTracker.recordEvent("renderView", "reason: " + renderReason + ", filesArg: " + fCount);
        }
        if (typeof window.__logF5Trace === "function") {
            window.__logF5Trace("5. After renderFileList() entry");
        }
        var curFolder = window.currentFolderPath || (typeof window.getCurrentFolderPath === "function" ? window.getCurrentFolderPath() : "");
        var cleanFolderPathFn = window.cleanFolderPath || function(p) { return p || ""; };
        var getTaggedFolderPathFn = window.getTaggedFolderPath || function() { return null; };
        var tagFilesWithFolderFn = window.tagFilesWithFolder || function(f, p) { return f; };

        var normCurrentDir = cleanFolderPathFn(curFolder);
        var reason = renderReason || "render_view";
        var container = document.getElementById("nasFileList");
        var filePanelMeta = document.getElementById("filePanelMeta");
        if (!container) return;
        var activeTab = document.documentElement.dataset.activeTab || (window.activeTab || 'file');
        if (activeTab !== 'file') {
            if (files) lastRenderedFiles = files;
            return;
        }

        if (files) {
            var taggedFolderPath = getTaggedFolderPathFn(files);

            if (taggedFolderPath !== null) {
                if (taggedFolderPath !== normCurrentDir) {
                    console.warn("[CACHE GUARD] Incoming payload belongs to '" + taggedFolderPath + "' but active view is '" + normCurrentDir + "'. Rendering active folder cache instead.");
                    files = window.FileRepository ? window.FileRepository.getFolderCache(normCurrentDir) : tagFilesWithFolderFn([], normCurrentDir);
                }
            } else {
                if (normCurrentDir !== "") {
                    console.warn("[CACHE GUARD] Rejecting untagged payload while viewing subfolder '" + normCurrentDir + "'. Rendering active folder cache instead.");
                    files = window.FileRepository ? window.FileRepository.getFolderCache(normCurrentDir) : tagFilesWithFolderFn([], normCurrentDir);
                } else {
                    files = tagFilesWithFolderFn(files, "");
                }
            }
            lastRenderedFiles = files;
        }

        var fileSource = "explicit_arg";
        if (!files || (Array.isArray(files) && files.length === 0)) {
            var cachedRepoFiles = window.FileRepository ? window.FileRepository.getFolderCache(normCurrentDir) : [];
            if (cachedRepoFiles && cachedRepoFiles.length > 0) {
                files = cachedRepoFiles;
                fileSource = "folder_cache_" + (normCurrentDir || "root");
            } else if (!files) {
                files = tagFilesWithFolderFn([], normCurrentDir);
                fileSource = "empty_folder_init";
            }
        }
        if (files) {
            if (getTaggedFolderPathFn(files) === null) {
                files = tagFilesWithFolderFn(files, normCurrentDir);
            }
            lastRenderedFiles = files;
        }

        var quickContainer = document.getElementById("quickAccessContainer");
        if (quickContainer) {
            if ((normCurrentDir && normCurrentDir !== "") || !files || files.length === 0) {
                quickContainer.style.display = "none";
            } else {
                quickContainer.style.display = "";
            }
        }

        if (typeof window.renderBreadcrumbs === "function") window.renderBreadcrumbs();

        var normalizedFiles = [];
        if (files && files.length > 0) {
            for (var i = 0; i < files.length; i++) {
                var item = files[i];
                if (!item) continue;
                var fn = typeof item === "string" ? item : item.name;
                if (!fn) continue;

                var meta = (typeof item === "string") ? getDiskFileMetadata(item) : item;

                if (fileSource.startsWith("fallback_")) {
                    console.error("  [ASSERTION FAILED] Fallback cache used during subfolder view! File: '" + fn + "' | Source: " + fileSource + " | CurrentFolder: '" + normCurrentDir + "'");
                    console.error("   WHO: renderFileList | FROM: " + fileSource + " | WHY: files parameter was undefined/null during render!");
                }

                var isFolderFlag = false;
                if (meta) {
                    isFolderFlag = !!(meta.isFolder || meta.is_dir || meta.is_folder);
                } else if (typeof item === "object") {
                    isFolderFlag = !!(item.isFolder || item.is_dir || item.is_folder);
                } else if (window._recentlyCreatedFolders && window._recentlyCreatedFolders[fn]) {
                    isFolderFlag = true;
                }

                normalizedFiles.push({
                    name: fn,
                    size: meta ? meta.size : "--",
                    mtime: meta ? meta.mtime : 0,
                    isFolder: isFolderFlag
                });
            }
        }

        var viewModel;
        if (reason === 'scheduler' && Array.isArray(files) && files.length > 0 && files[0].hasOwnProperty('uploading')) {
            viewModel = files;
        } else {
            var storeState = window.LanvanStore ? Object.assign({}, window.LanvanStore.state) : { currentFolder: normCurrentDir, pendingOps: {} };
            var liveUploadQueue = Array.isArray(window.uploadQueue) ? window.uploadQueue : [];
            storeState.currentFolder = normCurrentDir;
            storeState.uploadQueue = liveUploadQueue;
            var curSortBy = window.sortBy || "name";
            var curSortDir = window.sortDirection || "asc";
            var curSortFold = window.sortFolders || "top";

            storeState.sortBy = curSortBy;
            storeState.sortDirection = curSortDir;
            storeState.sortFolders = curSortFold;
            if (!storeState.pendingOps) {
                storeState.pendingOps = {};
            }
            var projectionEngine = window.projectionLayer || (typeof window.ProjectionLayer === 'function' ? new window.ProjectionLayer() : window.ProjectionLayer);
            viewModel = projectionEngine ? projectionEngine.buildCurrentFolderViewModel(storeState, files) : normalizedFiles;

            var traceId = Math.random().toString(36).substring(2, 7);
            console.log("🛠️ [TRACE @" + traceId + " @ m3-file-renderer.js] renderFileList triggered | Reason: " + reason + " | Folder: '" + (normCurrentDir || "Home") + "'");
            console.log("   ↳ Disk Payload: " + (files ? files.length : 0) + " items | Active Queue: " + liveUploadQueue.length + " items");
            console.log("✨ [TRACE @" + traceId + " @ m3-file-renderer.js] View Model Ready | Visible Count: " + (Array.isArray(viewModel) ? viewModel.length : 0) + " | Files: [" + (Array.isArray(viewModel) ? viewModel.map(function (f) { return f.name + (f.isFolder ? '(dir)' : '(file)'); }).join(", ") : "?") + "]");
        }

        normalizedFiles = Array.isArray(viewModel) ? viewModel : (viewModel.visibleFiles || []);
        var activeUploads = (viewModel && Array.isArray(viewModel.activeUploads)) ? viewModel.activeUploads : [];
        var originalFilesForQuickAccess = normalizedFiles.slice();

        activeUploads.forEach(function (item) {
            if (!item || !item.name) return;
            var qi = (window.uploadQueue || []).find(function (q) { return q && window.getItemName(q) === item.name; });
            if (qi) {
                var itemDir = cleanFolderPathFn(window.getItemFolder(qi));
                if (itemDir !== normCurrentDir) {
                    console.error("  [ASSERTION FAILED] Queue item from wrong folder rendered! File: '" + item.name + "' | Item targetDir: '" + itemDir + "' | currentFolder: '" + normCurrentDir + "'");
                }
            }
        });

        var curTypeFilter = window.typeFilter || "all";
        if (curTypeFilter !== "all") {
            normalizedFiles = normalizedFiles.filter(function (f) {
                return typeof getFileItemType === "function" ? getFileItemType(f) === curTypeFilter : true;
            });
        }

        var toolbarSearchInputEl = document.getElementById("toolbarSearchInput");
        var searchQuery = toolbarSearchInputEl ? toolbarSearchInputEl.value.trim().toLowerCase() : "";
        if (searchQuery) {
            var universalSource = (window.FileRepository && typeof window.FileRepository.getAllCachedFiles === "function")
                ? window.FileRepository.getAllCachedFiles()
                : normalizedFiles;
            normalizedFiles = universalSource.filter(function (f) {
                if (!f) return false;
                var nameStr = typeof f === "string" ? f : f.name;
                if (!nameStr) return false;
                return nameStr.toLowerCase().indexOf(searchQuery) !== -1;
            });
        }

        var curSortBy = window.sortBy || "name";
        var curSortDirection = window.sortDirection || "asc";
        var curSortFolders = window.sortFolders || "top";

        normalizedFiles.sort(function (a, b) {
            if (curSortFolders === "top") {
                if (a.isFolder && !b.isFolder) return -1;
                if (!a.isFolder && b.isFolder) return 1;
            }

            var comparison = 0;
            if (curSortBy === "name") {
                var nameA = String(a.name || "").toLowerCase();
                var nameB = String(b.name || "").toLowerCase();
                comparison = nameA.localeCompare(nameB, undefined, { numeric: true, sensitivity: 'base' });
            } else if (curSortBy === "date") {
                var parseDate = window.parseDateToTimestamp || function (d) { return typeof d === 'number' ? d : 0; };
                var timeA = parseDate(a.mtime || a.date || a.modified || (a.uploading ? Date.now() / 1000 : 0));
                var timeB = parseDate(b.mtime || b.date || b.modified || (b.uploading ? Date.now() / 1000 : 0));
                comparison = timeA - timeB;
            } else if (curSortBy === "size") {
                var parseBytes = window.parseSizeToBytes || function () { return 0; };
                var bytesA = parseBytes(a.size || a.fileSize, a.isFolder);
                var bytesB = parseBytes(b.size || b.fileSize, b.isFolder);
                comparison = bytesA - bytesB;
            }

            return curSortDirection === "asc" ? comparison : -comparison;
        });

        var savedViewModeForSignature = "grid";
        try {
            savedViewModeForSignature = localStorage.getItem("lanvan_view_mode") || "grid";
        } catch (e) { }

        var renderSignature = [
            normCurrentDir,
            savedViewModeForSignature,
            curTypeFilter,
            searchQuery,
            curSortBy,
            curSortDirection,
            curSortFolders,
            normalizedFiles.map(function (f) {
                if (!f) return "";
                return [
                    f.name || "",
                    f.isFolder ? 1 : 0,
                    f.uploading ? 1 : 0,
                    f.uploadStatus || "",
                    f.size || "",
                    f.mtime || 0
                ].join("|");
            }).join("||")
        ].join("::");

        var isStillShowingLoadingShell = false;
        try {
            isStillShowingLoadingShell = !!container.querySelector(".loading-shell") ||
                /Loading files\.\.\./i.test(container.textContent || "");
        } catch (e) { }

        if (_renderHasPainted && _lastRenderSignature === renderSignature && !isStillShowingLoadingShell) {
            return;
        }
        _lastRenderSignature = renderSignature;

        if (typeof updateSortCheckmarks === "function") updateSortCheckmarks();
        if (typeof updateSortHeaderArrows === "function") updateSortHeaderArrows();

        if (filePanelMeta) {
            var folderCount = 0;
            var fileCount = 0;
            if (Array.isArray(normalizedFiles)) {
                for (var fIdx = 0; fIdx < normalizedFiles.length; fIdx++) {
                    if (normalizedFiles[fIdx] && normalizedFiles[fIdx].isFolder) {
                        folderCount++;
                    } else {
                        fileCount++;
                    }
                }
            }
            var parts = [];
            if (fileCount > 0) {
                parts.push(fileCount + " file" + (fileCount === 1 ? "" : "s"));
            }
            if (folderCount > 0) {
                parts.push(folderCount + " folder" + (folderCount === 1 ? "" : "s"));
            }
            filePanelMeta.textContent = parts.length > 0 ? parts.join(", ") : "";
        }

        var hasFiles = normalizedFiles && normalizedFiles.length > 0;
        if (typeof updateExplorerLayoutState === "function") {
            updateExplorerLayoutState({
                hasFiles: hasFiles,
                viewMode: savedViewModeForSignature
            });
        }

        if (!hasFiles) {
            container.style.display = "flex";
            container.style.flexDirection = "column";
            container.style.alignItems = "stretch";
            container.style.justifyContent = "stretch";
            container.style.flex = "1";
            container.style.height = "100%";
            window.selectedItems = [];
            window._contextMenuTarget = "";

            var queue = Array.isArray(window.uploadQueue) ? window.uploadQueue : [];
            var activeUploadsCount = queue.filter(function (item) {
                return item.status === "UPLOADING" || item.status === "QUEUED" || item.status === "PROCESSING" || item.status === "PAUSED";
            }).length;

            if (searchQuery) {
                container.innerHTML =
                    '<div class="empty-dropzone-wrapper" style="grid-column: 1 / -1; width:100%; height:100%; flex:1; display:flex; flex-direction:column; align-items:center; justify-content:center; text-align:center; padding:0; margin:auto;">' +
                    '<div class="avatar-icon" style="width:64px;height:64px;border-radius:18px;margin-bottom:1rem;background:var(--toggle-bg);color:var(--text-muted);display:flex;align-items:center;justify-content:center;">' +
                    '<i data-lucide="search-x" style="width:32px;height:32px;"></i></div>' +
                    '<div style="font-size:1.05rem; font-weight:600; color:var(--text-color); margin-bottom:0.25rem;">No files matching "' + (typeof escapeHtml === "function" ? escapeHtml(searchQuery) : searchQuery) + '"</div>' +
                    '<div style="font-size:0.82rem; color:var(--text-muted); margin-bottom:1rem;">Check spelling or try searching for another term.</div>' +
                    '<button class="filter-chip" onclick="clearToolbarSearch()" style="display:inline-flex; align-items:center; gap:0.35rem; font-size:0.8rem; font-weight:700; border:1px solid var(--border-color); background:var(--card-bg); color:var(--primary); border-radius:999px; padding:0.4rem 0.9rem; cursor:pointer;">Clear search</button>' +
                    '</div>';
            } else if (curTypeFilter !== "all") {
                container.innerHTML =
                    '<div class="empty-dropzone-wrapper" style="grid-column: 1 / -1; width:100%; height:100%; flex:1; display:flex; flex-direction:column; align-items:center; justify-content:center; text-align:center; padding:0; margin:auto;">' +
                    '<div class="avatar-icon" style="width:64px;height:64px;border-radius:18px;margin-bottom:1rem;background:var(--toggle-bg);color:var(--text-muted);display:flex;align-items:center;justify-content:center;">' +
                    '<i data-lucide="file-x" style="width:32px;height:32px;"></i></div>' +
                    '<div style="font-size:1.05rem; font-weight:600; color:var(--text-color); margin-bottom:0.25rem;">No ' + (typeof escapeHtml === "function" ? escapeHtml(curTypeFilter) : curTypeFilter) + ' files found</div>' +
                    '<div style="font-size:0.82rem; color:var(--text-muted); margin-bottom:1rem;">No files match the active type filter.</div>' +
                    '<button class="filter-chip" onclick="clearTypeFilter(event)" style="display:inline-flex; align-items:center; gap:0.35rem; font-size:0.8rem; font-weight:700; border:1px solid var(--border-color); background:var(--card-bg); color:var(--primary); border-radius:999px; padding:0.4rem 0.9rem; cursor:pointer;">Clear filter</button>' +
                    '</div>';
            } else if (activeUploadsCount > 0) {
                container.innerHTML =
                    '<div class="empty-dropzone-wrapper" style="grid-column: 1 / -1; width:100%; height:100%; flex:1; display:flex; flex-direction:column; align-items:center; justify-content:center; text-align:center; padding:0; margin:auto;">' +
                    '<div class="empty-dropzone-target" style="display:inline-flex; flex-direction:column; align-items:center; justify-content:center; padding:1.5rem 2.5rem; border-radius:16px; cursor:pointer; transition:background-color 0.2s ease;" onclick="if(typeof handleFileSelection===\'function\'){handleFileSelection(\'file\');}else{var fi=document.getElementById(\'fileInput\');if(fi){fi.value=\'\';fi.click();}}">' +
                    '<div class="avatar-icon avatar-folder" style="width:72px;height:72px;border-radius:18px;margin-bottom:1rem;">' +
                    '<i data-lucide="upload-cloud" style="width:34px;height:34px;"></i></div>' +
                    '<div style="font-size:1.05rem; font-weight:500; color:var(--text-color); margin-bottom:0.25rem;">Uploading ' + activeUploadsCount + ' file' + (activeUploadsCount === 1 ? '' : 's') + '...</div>' +
                    '<div style="font-size:0.8rem; color:var(--text-muted);">Files will appear here when upload completes. Click to add more.</div>' +
                    '</div>' +
                    '</div>';
            } else {
                container.innerHTML =
                    '<div class="empty-dropzone-wrapper" style="grid-column: 1 / -1; width:100%; height:100%; flex:1; display:flex; flex-direction:column; align-items:center; justify-content:center; text-align:center; padding:0; margin:auto;">' +
                    '<div class="empty-dropzone-target" style="display:inline-flex; flex-direction:column; align-items:center; justify-content:center; padding:1.5rem 2.5rem; border-radius:16px; cursor:pointer; transition:background-color 0.2s ease;" onclick="if(typeof handleFileSelection===\'function\'){handleFileSelection(\'file\');}else{var fi=document.getElementById(\'fileInput\');if(fi){fi.value=\'\';fi.click();}}">' +
                    '<div class="avatar-icon avatar-folder" style="width:72px;height:72px;border-radius:18px;margin-bottom:1rem;">' +
                    '<i data-lucide="folder-open" style="width:34px;height:34px;"></i></div>' +
                    '<div style="font-size:1.05rem; font-weight:500; color:var(--text-color); margin-bottom:0.25rem;">Drop files here</div>' +
                    '<div style="font-size:0.8rem; color:var(--text-muted);">or right-click to upload / create folders.</div>' +
                    '</div>' +
                    '</div>';
            }
            _renderHasPainted = true;
            if (typeof window.refreshLucideIcons === "function") window.refreshLucideIcons(container);
            if (typeof updateSelectionToolbar === "function") updateSelectionToolbar();
            try {
                if (typeof renderQuickAccess === "function") {
                    renderQuickAccess(originalFilesForQuickAccess.filter(function (f) { return !f.isFolder && !f.uploading; }));
                }
            } catch (e) {
                console.error("[LANVAN UI] Quick access render failed during empty-state paint:", e);
            }
            return;
        }

        container.classList.remove("empty-state");
        container.style.display = "";
        container.style.flexDirection = "";
        container.style.alignItems = "";
        container.style.justifyContent = "";
        container.style.flex = "";
        container.style.minHeight = "";
        container.style.height = "";
        var isGrid = container.classList.contains("grid-mode");
        var html = "";
        for (var i = 0; i < normalizedFiles.length; i++) {
            var fileData = normalizedFiles[i];
            if (typeof fileData === 'string') {
                fileData = { name: fileData };
            }
            var name = fileData.name || "";
            if (!name) continue;

            var repoCache = window.FileRepository ? window.FileRepository.getFolderCache(normCurrentDir) : [];
            if ((!fileData.size && !fileData.mtime && !fileData.modified) && repoCache.length > 0) {
                var cachedMatch = repoCache.find(function (c) {
                    return c && typeof c === 'object' && c.name === name;
                });
                if (cachedMatch) {
                    fileData = Object.assign({}, cachedMatch, fileData);
                }
            }

            var isFolderItem = !!(fileData.isFolder || fileData.is_dir || fileData.is_folder);
            var ext = name.split(".").pop().toLowerCase();
            var info = isFolderItem
                ? { avatarClass: "avatar-folder", iconName: "folder" }
                : getFileTypeInfo(name, ext);
            var rawSize = fileData.size || fileData.size_formatted || fileData.formatted_size;
            if (!rawSize && typeof fileData.size_bytes === 'number') {
                rawSize = typeof formatSize === "function" ? formatSize(fileData.size_bytes) : fileData.size_bytes;
            }
            if (!rawSize && typeof fileData.fileSize === 'number') {
                rawSize = typeof formatSize === "function" ? formatSize(fileData.fileSize) : fileData.fileSize;
            }
            var size = isFolderItem ? "-" : (rawSize || "--");
            var rawDate = fileData.modified || fileData.date || fileData.dateStr || fileData.modified_formatted || fileData.mtime || "--";
            var dateStr = typeof formatLastModified === 'function' ? formatLastModified(rawDate) : rawDate;
            var locationText = (searchQuery && fileData.location) ? ("in " + fileData.location) : "";
            var subtitle = isFolderItem
                ? (locationText ? "Folder • " + locationText : (fileData.formattedSubtitle || "Folder"))
                : (locationText ? locationText : "File");
            if (isGrid) {
                html += buildGridItem(
                    name,
                    info,
                    size,
                    dateStr,
                    subtitle,
                    isFolderItem,
                    !!fileData.uploading,
                    fileData.uploadProgress || 0,
                    fileData.uploadId,
                    fileData.uploadStatus
                );
            } else {
                html += buildListItem(
                    name,
                    info,
                    size,
                    dateStr,
                    subtitle,
                    isFolderItem,
                    !!fileData.uploading,
                    fileData.uploadProgress || 0,
                    fileData.uploadId,
                    fileData.uploadStatus
                );
            }
        }
        _renderHasPainted = true;
        var existingPreviews = {};
        var existingItems = container.querySelectorAll(".m3-list-item");
        for (var k = 0; k < existingItems.length; k++) {
            var fn = existingItems[k].getAttribute("data-filename");
            var prev = existingItems[k].querySelector(".grid-card-preview");
            if (fn && prev) {
                var vid = prev.querySelector("video");
                var img = prev.querySelector("img");
                var isVidReady = vid && vid.readyState >= 2 && vid.networkState !== 3;
                var isImgReady = img && img.complete && img.naturalWidth > 0;
                if (isVidReady || isImgReady) {
                    existingPreviews[fn] = prev;
                }
            }
        }

        var prevChildCount = container.children.length;
        var stackTrace = (new Error()).stack || "";
        var callerLine = stackTrace.split("\n")[2] || "";
        console.log("[DOM-WRITE-TRACE] 💥 DOM WRITE TO #" + (container.id || "nasFileList") + "\n" +
            "   Timestamp: " + performance.now().toFixed(1) + "ms\n" +
            "   File: m3-file-renderer.js\n" +
            "   Function: renderFileList\n" +
            "   Caller: " + callerLine.trim() + "\n" +
            "   Target Element: #" + (container.id || "nasFileList") + "\n" +
            "   Previous Child Count: " + prevChildCount + "\n" +
            "   HTML Length: " + html.length + "\n" +
            "   Reason: " + (renderReason || "file_render") + "\n" +
            "   Call Stack:\n" + stackTrace);

        var oldDomItems = Array.prototype.slice.call(container.querySelectorAll(".m3-list-item")).map(function (el) { return el.getAttribute("data-filename") || el.textContent.trim(); });
        container.innerHTML = html;
        var newDomItems = Array.prototype.slice.call(container.querySelectorAll(".m3-list-item")).map(function (el) { return el.getAttribute("data-filename") || el.textContent.trim(); });

        console.log("[DOM-WRITE-TRACE] ✅ New Child Count: " + container.children.length + " | Visible List Items: [" + newDomItems.join(", ") + "]");

        var newItems = container.querySelectorAll(".m3-list-item");
        for (var n = 0; n < newItems.length; n++) {
            var itemFn = newItems[n].getAttribute("data-filename");
            var oldPrev = existingPreviews[itemFn];
            var newPrev = newItems[n].querySelector(".grid-card-preview");
            if (oldPrev && newPrev) {
                newPrev.parentNode.replaceChild(oldPrev, newPrev);
            }
        }

        attachListItemHandlers(container, normalizedFiles.map(function (f) { return f.name; }), normalizedFiles);

        var validNames = normalizedFiles.map(function (f) { return f.name; });
        var selItems = window.selectedItems || [];
        if (Array.isArray(selItems)) {
            var filteredSel = selItems.filter(function (name) {
                return validNames.indexOf(name) !== -1 && !(typeof isItemUploading === "function" && isItemUploading(name));
            });
            window.selectedItems = filteredSel;
            var renderedItems = container.querySelectorAll(".m3-list-item");
            for (var s = 0; s < renderedItems.length; s++) {
                var itemFn = renderedItems[s].getAttribute("data-filename");
                if (itemFn && filteredSel.indexOf(itemFn) !== -1) {
                    renderedItems[s].classList.add("selected");
                } else {
                    renderedItems[s].classList.remove("selected");
                }
            }
        }
        if (typeof updateSelectionToolbar === "function") updateSelectionToolbar();

        try {
            if (typeof renderQuickAccess === "function") {
                renderQuickAccess(originalFilesForQuickAccess.filter(function (f) { return !f.isFolder && !f.uploading; }));
            }
        } catch (e) {
            console.error("[LANVAN UI] Quick access render failed during file-list paint:", e);
        }

        if (typeof window.refreshLucideIcons === "function") window.refreshLucideIcons(container);
        syncFileTableHeadWidth();
    }

    // Expose FileListRenderer module namespace and backward-compatibility globals
    window.FileListRenderer = {
        buildListItem: buildListItem,
        buildGridItem: buildGridItem,
        getDiskFileMetadata: getDiskFileMetadata,
        renderFileList: renderFileList,
        syncFileTableHeadWidth: syncFileTableHeadWidth,
        getFileTypeInfo: getFileTypeInfo,
        attachListItemHandlers: attachListItemHandlers,
        getLastRenderedFiles: function() { return lastRenderedFiles; }
    };

    window.M3FileRenderer = window.FileListRenderer;
    window.buildListItem = buildListItem;
    window.buildGridItem = buildGridItem;
    window.renderFileList = renderFileList;
    window.syncFileTableHeadWidth = syncFileTableHeadWidth;
    window.getFileTypeInfo = getFileTypeInfo;

    // Maintain window.lastRenderedFiles accessor proxy
    Object.defineProperty(window, 'lastRenderedFiles', {
        get: function() { return lastRenderedFiles; },
        set: function(val) { lastRenderedFiles = Array.isArray(val) ? val : []; },
        configurable: true
    });

})(window);
