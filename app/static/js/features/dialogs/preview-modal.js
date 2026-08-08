/**
 * Preview Modal Module
 *
 * Comprehensive presentation & interactive controller for the file preview dialog.
 * Renders images (with 1x/2x double-click zoom, mousewheel zoom, drag pan), videos, audio,
 * PDFs, Office documents (via docx.js), and plain-text code files.
 * Manages right-click context menu, video stream link copying, toast notifications,
 * and keyboard navigation (Escape, Spacebar, Arrow keys).
 */

(function (window) {
    'use strict';

    if (window.PreviewModal && window.PreviewModal._isFullEngine) {
        return;
    }

    var currentImageScale = 1;
    var currentImageTransX = 0;
    var currentImageTransY = 0;
    var isDraggingImage = false;
    var dragStartX = 0;
    var dragStartY = 0;

    function updateImageTransform() {
        var img = document.getElementById("lanvanZoomImage");
        var label = document.getElementById("zoomPercentLabel");
        if (!img) return;
        img.style.transform = "translate(" + currentImageTransX + "px, " + currentImageTransY + "px) scale(" + currentImageScale + ")";
        if (label) label.textContent = Math.round(currentImageScale * 100) + "%";
        img.style.cursor = currentImageScale > 1 ? (isDraggingImage ? "grabbing" : "grab") : "grab";
    }

    function zoomPreviewImage(delta) {
        currentImageScale = Math.max(0.5, Math.min(4, currentImageScale + delta));
        if (currentImageScale === 1) {
            currentImageTransX = 0;
            currentImageTransY = 0;
        }
        updateImageTransform();
    }

    function resetPreviewImageZoom() {
        currentImageScale = 1;
        currentImageTransX = 0;
        currentImageTransY = 0;
        updateImageTransform();
    }

    function setupImageZoomAndPan() {
        currentImageScale = 1;
        currentImageTransX = 0;
        currentImageTransY = 0;
        isDraggingImage = false;

        var img = document.getElementById("lanvanZoomImage");
        var wrapper = img ? img.parentElement : null;
        if (!img || !wrapper) return;

        // Mouse Wheel Zoom
        wrapper.addEventListener("wheel", function (e) {
            e.preventDefault();
            var zoomDelta = e.deltaY < 0 ? 0.2 : -0.2;
            zoomPreviewImage(zoomDelta);
        }, { passive: false });

        // Double Click to Toggle 1x / 2x Zoom
        img.addEventListener("dblclick", function (e) {
            e.stopPropagation();
            if (currentImageScale > 1.2) {
                resetPreviewImageZoom();
            } else {
                currentImageScale = 2;
                updateImageTransform();
            }
        });

        // Mouse Drag to Pan Image
        img.addEventListener("mousedown", function (e) {
            if (e.button !== 0) return;
            isDraggingImage = true;
            dragStartX = e.clientX - currentImageTransX;
            dragStartY = e.clientY - currentImageTransY;
            img.style.cursor = "grabbing";
            e.preventDefault();
        });

        window.addEventListener("mousemove", function (e) {
            if (!isDraggingImage) return;
            currentImageTransX = e.clientX - dragStartX;
            currentImageTransY = e.clientY - dragStartY;
            updateImageTransform();
        });

        window.addEventListener("mouseup", function () {
            if (isDraggingImage) {
                isDraggingImage = false;
                updateImageTransform();
            }
        });

        // Touch double-tap and drag zoom on mobile
        var lastTapTime = 0;
        img.addEventListener("touchend", function (e) {
            var currentTime = new Date().getTime();
            var tapLength = currentTime - lastTapTime;
            if (tapLength < 300 && tapLength > 0) {
                e.preventDefault();
                if (currentImageScale > 1) {
                    resetPreviewImageZoom();
                } else {
                    currentImageScale = 2.2;
                    updateImageTransform();
                }
            }
            lastTapTime = currentTime;
        });

        img.addEventListener("touchstart", function (e) {
            if (e.touches.length === 1 && currentImageScale > 1) {
                isDraggingImage = true;
                dragStartX = e.touches[0].clientX - currentImageTransX;
                dragStartY = e.touches[0].clientY - currentImageTransY;
            }
        }, { passive: true });

        img.addEventListener("touchmove", function (e) {
            if (isDraggingImage && e.touches.length === 1 && currentImageScale > 1) {
                e.preventDefault();
                currentImageTransX = e.touches[0].clientX - dragStartX;
                currentImageTransY = e.touches[0].clientY - dragStartY;
                updateImageTransform();
            }
        }, { passive: false });
    }

    function closePreviewModal() {
        var modal = document.getElementById("previewModal");
        if (modal) {
            modal.style.display = "none";
            modal.style.pointerEvents = "none";
            var bodyEl = document.getElementById("previewBody");
            if (bodyEl) {
                var mediaEls = bodyEl.querySelectorAll("video, audio, iframe");
                for (var i = 0; i < mediaEls.length; i++) {
                    try {
                        if (typeof mediaEls[i].pause === "function") mediaEls[i].pause();
                        mediaEls[i].removeAttribute("src");
                        if (typeof mediaEls[i].load === "function") mediaEls[i].load();
                    } catch (e) { }
                }
                bodyEl.innerHTML = "";
            }
            window.currentPreviewFilename = "";
            var ctxMenu = document.getElementById("previewContextMenu");
            if (ctxMenu) ctxMenu.style.display = "none";
        }
    }

    function openFilePreview(filename) {
        if (!filename) return;
        if (window.selectedItems && window.selectedItems.length > 1) return;
        window.currentPreviewFilename = filename;
        var modal = document.getElementById("previewModal");
        var titleEl = document.getElementById("previewTitle");
        var bodyEl = document.getElementById("previewBody");
        var dlBtn = document.getElementById("previewDownloadBtn");
        if (!modal || !bodyEl) return;

        var downloadUrl = "/download/" + encodeURIComponent(filename);
        if (titleEl) titleEl.textContent = filename;
        if (dlBtn) {
            dlBtn.href = downloadUrl + "?download=1";
            dlBtn.download = filename;
        }

        var ext = filename.split(".").pop().toLowerCase();
        var escName = typeof window.escapeHtml === 'function' ? window.escapeHtml(filename) : filename;

        var imageExts = ["jpg", "jpeg", "png", "gif", "webp", "svg", "bmp"];
        var videoExts = ["mp4", "webm", "mov", "mkv", "avi"];
        var audioExts = ["mp3", "wav", "ogg", "flac", "m4a", "aac"];
        var textExts = ["txt", "json", "py", "js", "css", "html", "md", "csv", "log", "xml", "yaml", "yml"];
        var docExts = ["doc", "docx", "ppt", "pptx", "xls", "xlsx", "rtf", "odt"];

        bodyEl.innerHTML = "";
        bodyEl.style.padding = "";

        var streamBtn = document.getElementById("previewStreamBtn");
        if (streamBtn) {
            if (videoExts.indexOf(ext) !== -1) {
                streamBtn.style.display = "inline-flex";
            } else {
                streamBtn.style.display = "none";
            }
        }

        var historyBtn = document.getElementById("previewHistoryBtn");
        if (historyBtn) {
            var hasV = false;
            var lfId = null;
            var baseN = filename ? filename.split("/").pop().split("\\").pop() : "";
            if (window._fileMetadataMap) {
                var meta = window._fileMetadataMap[filename] || window._fileMetadataMap[baseN];
                if (meta) {
                    hasV = !!meta.hasVersions;
                    lfId = meta.logicalFileId;
                }
            }
            if (!lfId) lfId = "lf_" + baseN;
            historyBtn.style.display = hasV ? "inline-flex" : "none";
            if (hasV && typeof window.refreshLucideIcons === "function") {
                window.refreshLucideIcons(historyBtn);
            }
            historyBtn.onclick = function () {
                if (window.LanvanVersionHistoryPanel) {
                    window.LanvanVersionHistoryPanel.open(lfId, baseN);
                }
            };
        }

        if (imageExts.indexOf(ext) !== -1) {
            bodyEl.innerHTML = '<div class="media-preview-container image-preview-wrapper" style="position:relative; width:100%; height:100%; min-height:70vh; flex:1; display:flex; align-items:center; justify-content:center; overflow:hidden;">' +
                '<img id="lanvanZoomImage" class="media-preview-element" src="' + downloadUrl + '" alt="' + escName + '" style="max-width:90vw; max-height:84vh; width:auto; height:auto; object-fit:contain; border-radius:8px; display:block; margin:auto; box-shadow:0 16px 48px rgba(0,0,0,0.6); transition:transform 0.15s ease-out; cursor:grab;" />' +
                '</div>';
            modal.style.display = "flex";
            modal.style.pointerEvents = "auto";
            if (typeof window.refreshLucideIcons === 'function') window.refreshLucideIcons(bodyEl);
            setupImageZoomAndPan();
        } else if (videoExts.indexOf(ext) !== -1) {
            bodyEl.innerHTML = '<div class="media-preview-container video-preview-wrapper" style="width:100%; height:100%; min-height:70vh; flex:1; display:flex; align-items:center; justify-content:center;">' +
                '<video class="media-preview-element" src="' + downloadUrl + '" controls autoplay playsinline preload="auto" tabindex="0" style="max-width:90vw; max-height:84vh; width:auto; height:auto; object-fit:contain; border-radius:8px; outline:none; background:transparent; box-shadow:0 16px 48px rgba(0,0,0,0.6);"></video>' +
                '</div>';
            modal.style.display = "flex";
            modal.style.pointerEvents = "auto";
            var vid = bodyEl.querySelector("video");
            if (vid) vid.focus();
        } else if (audioExts.indexOf(ext) !== -1) {
            bodyEl.innerHTML = '<div style="display:flex; flex-direction:column; align-items:center; justify-content:center; gap:1.4rem; width:100%; height:100%; min-height:70vh; flex:1; padding:2.5rem; background:rgba(18,20,26,0.5); border-radius:14px; text-align:center;">' +
                '<div class="avatar-icon avatar-audio" style="width:84px; height:84px; border-radius:24px; background:rgba(168, 85, 247, 0.15); display:flex; align-items:center; justify-content:center; box-shadow:0 8px 24px rgba(168,85,247,0.2);">' +
                '<i data-lucide="music" style="width:42px; height:42px; color:#c084fc;"></i>' +
                '</div>' +
                '<div style="font-weight:700; color:#ffffff; font-size:1.35rem; text-align:center; word-break:break-all; max-width:600px;">' + escName + '</div>' +
                '<audio src="' + downloadUrl + '" controls autoplay style="width:100%; max-width:460px; outline:none; border-radius:30px;"></audio>' +
                '</div>';
            modal.style.display = "flex";
            modal.style.pointerEvents = "auto";
            if (typeof window.refreshLucideIcons === 'function') window.refreshLucideIcons(bodyEl);
        } else if (ext === "pdf") {
            bodyEl.style.padding = "0";
            bodyEl.innerHTML = '<div style="width:100%; height:100%; min-height:70vh; flex:1; background:rgba(18,20,26,0.5); border-radius:14px; overflow:hidden;">' +
                '<iframe src="' + downloadUrl + '" style="width:100%; height:100%; border:none; display:block;"></iframe>' +
                '</div>';
            modal.style.display = "flex";
            modal.style.pointerEvents = "auto";
        } else if (docExts.indexOf(ext) !== -1) {
            bodyEl.innerHTML = '<div style="width:100%; text-align:center; color:var(--text-color); padding:1rem;">Rendering Word document...</div>';
            modal.style.display = "flex";
            modal.style.pointerEvents = "auto";

            function renderDocCardFallback() {
                bodyEl.innerHTML = '<div style="display:flex; flex-direction:column; align-items:center; justify-content:center; gap:1.4rem; width:100%; height:100%; min-height:70vh; flex:1; padding:2.5rem; background:rgba(18, 20, 26, 0.5); border-radius:14px; color:#fff; text-align:center;">' +
                    '<div class="avatar-icon avatar-doc" style="width:84px; height:84px; border-radius:24px; background:rgba(239, 68, 68, 0.14); display:flex; align-items:center; justify-content:center; box-shadow:0 8px 24px rgba(239,68,68,0.15);">' +
                    '<i data-lucide="file-text" style="width:42px; height:42px; color:#ef4444;"></i>' +
                    '</div>' +
                    '<div style="font-weight:700; font-size:1.4rem; color:#ffffff; text-align:center; word-break:break-all; max-width:600px;">' + escName + '</div>' +
                    '<div style="font-size:0.95rem; color:rgba(255,255,255,0.75); text-align:center; max-width:440px;">No in-app preview available for this document format.</div>' +
                    '<a href="' + downloadUrl + '?download=1" download class="lv-doc-fallback-btn">' +
                    '<i data-lucide="download" style="width:18px; height:18px;"></i> Download File' +
                    '</a>' +
                    '</div>';
                if (typeof window.refreshLucideIcons === 'function') window.refreshLucideIcons(bodyEl);
            }

            fetch(downloadUrl)
                .then(function (res) { return res.arrayBuffer(); })
                .then(function (buffer) {
                    if (window.docx && window.docx.renderAsync) {
                        bodyEl.innerHTML = '<div id="docxRenderTarget" style="width:100%; max-height:85vh; overflow-y:auto; padding:1.5rem; display:flex; flex-direction:column; align-items:center; background:rgba(18,20,26,0.5); border-radius:14px;"></div>';
                        var target = document.getElementById("docxRenderTarget");
                        window.docx.renderAsync(buffer, target, null, {
                            inBase64Output: false,
                            className: "docx",
                            ignoreWidth: false,
                            ignoreHeight: false,
                            ignoreMargins: false,
                            breakPages: true
                        })
                            .then(function () {
                                console.log("[DOCX-PREVIEW] Successfully rendered docx document!");
                            })
                            .catch(function (err) {
                                console.error("[DOCX-PREVIEW] Render error:", err);
                                renderDocCardFallback();
                            });
                    } else {
                        renderDocCardFallback();
                    }
                })
                .catch(renderDocCardFallback);
        } else if (textExts.indexOf(ext) !== -1) {
            bodyEl.innerHTML = '<div style="width:100%; text-align:center; color:var(--text-color); padding:1rem;">Loading content...</div>';
            modal.style.display = "flex";
            modal.style.pointerEvents = "auto";
            fetch(downloadUrl)
                .then(function (res) { return res.text(); })
                .then(function (text) {
                    bodyEl.innerHTML = '<div style="width:100%; height:100%; min-height:70vh; flex:1; background:rgba(18,20,26,0.5); border-radius:14px; padding:1.5rem;">' +
                        '<pre style="max-height:68vh; width:100%; overflow:auto; background:var(--card-bg); padding:1rem; border-radius:8px; white-space:pre-wrap; word-break:break-word; text-align:left; font-family:monospace; color:var(--text-color); font-size:0.85rem; margin:0; border:1px solid var(--border-color);"></pre>' +
                        '</div>';
                    var pre = bodyEl.querySelector("pre");
                    if (pre) pre.textContent = text;
                })
                .catch(function () {
                    bodyEl.innerHTML = '<div style="color:var(--danger); padding:1rem;">Failed to load text preview.</div>';
                });
        } else {
            bodyEl.innerHTML = '<div style="display:flex; flex-direction:column; align-items:center; justify-content:center; gap:1.4rem; width:100%; height:100%; min-height:70vh; flex:1; padding:2.5rem; background:rgba(18,20,26,0.5); border-radius:14px; color:#fff; text-align:center;">' +
                '<div class="avatar-icon avatar-doc" style="width:84px; height:84px; border-radius:24px; background:rgba(239, 68, 68, 0.14); display:flex; align-items:center; justify-content:center; box-shadow:0 8px 24px rgba(239,68,68,0.15);">' +
                '<i data-lucide="file" style="width:42px; height:42px; color:#ef4444;"></i>' +
                '</div>' +
                '<div style="font-weight:700; color:#ffffff; font-size:1.4rem; text-align:center; word-break:break-all; max-width:600px;">' + escName + '</div>' +
                '<div style="font-size:0.95rem; color:rgba(255,255,255,0.75); text-align:center; max-width:440px;">No in-app preview available for this file type.</div>' +
                '<a href="' + downloadUrl + '?download=1" download class="lv-doc-fallback-btn">' +
                '<i data-lucide="download" style="width:18px; height:18px;"></i> Download File' +
                '</a>' +
                '</div>';
            modal.style.display = "flex";
            modal.style.pointerEvents = "auto";
            if (typeof window.refreshLucideIcons === 'function') window.refreshLucideIcons(bodyEl);
        }
    }

    function openFilePreviewTarget() {
        var selected = window.selectedItems || [];
        var target = window._contextMenuTarget || (selected.length > 0 ? selected[0] : "");
        window._contextMenuTarget = "";
        if (target) {
            openFilePreview(target);
        }
    }

    function copyVideoStreamUrl(filename) {
        var fn = filename || window.currentPreviewFilename || (window._contextMenuTarget || (window.selectedItems && window.selectedItems[0]));
        if (!fn) return;
        var fullUrl = window.location.origin + "/download/" + encodeURIComponent(fn);

        var copied = false;
        if (typeof window.fallbackCopyTextToClipboard === "function") {
            copied = window.fallbackCopyTextToClipboard(fullUrl);
        }
        if (!copied && navigator.clipboard && navigator.clipboard.writeText) {
            navigator.clipboard.writeText(fullUrl).catch(function () {
                if (typeof window.fallbackCopyTextToClipboard === "function") {
                    window.fallbackCopyTextToClipboard(fullUrl);
                }
            });
        }

        if (typeof window.showToast === "function") {
            window.showToast('Stream link copied to clipboard!', 3000);
        }

        var streamBtn = document.getElementById("previewStreamBtn");
        if (streamBtn) {
            var origHtml = streamBtn.innerHTML;
            streamBtn.innerHTML = '<i data-lucide="check" style="width:16px;height:16px;color:#4ade80;"></i><span>Copied!</span>';
            if (typeof window.refreshLucideIcons === "function") window.refreshLucideIcons(streamBtn);
            setTimeout(function () {
                streamBtn.innerHTML = origHtml;
                if (typeof window.refreshLucideIcons === "function") window.refreshLucideIcons(streamBtn);
            }, 2000);
        }
    }

    function downloadPreviewFile(filename) {
        var menu = document.getElementById("previewContextMenu");
        if (menu) menu.style.display = "none";
        var fn = filename || window.currentPreviewFilename;
        if (!fn) return;
        var a = document.createElement("a");
        a.href = "/download/" + encodeURIComponent(fn) + "?download=1";
        a.download = fn;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
    }

    function showPreviewContextMenu(x, y, filename) {
        var menu = document.getElementById("previewContextMenu");
        if (!menu) {
            menu = document.createElement("div");
            menu.id = "previewContextMenu";
            menu.className = "context-menu";
            menu.style.cssText = "position:fixed; z-index:20000; min-width:190px; padding:6px 0; border-radius:12px; background:var(--card-bg, #1e2026); border:1px solid var(--border-color, rgba(255,255,255,0.15)); box-shadow:0 12px 36px rgba(0,0,0,0.5); display:none;";
            document.body.appendChild(menu);

            document.addEventListener("click", function () {
                menu.style.display = "none";
            });
        }

        var escFn = typeof window.escapeHtml === 'function' ? window.escapeHtml(filename) : filename;
        var ext = filename.split(".").pop().toLowerCase();
        var videoExts = ["mp4", "webm", "mov", "mkv", "avi", "3gp", "m4v", "ts", "flv"];
        var isVideo = videoExts.indexOf(ext) !== -1;

        var html = '';
        if (isVideo) {
            html += '<div class="menu-item" onclick="copyVideoStreamUrl(\'' + escFn + '\')" style="display:flex; align-items:center; gap:10px; padding:9px 16px; cursor:pointer; font-size:0.9rem; font-weight:500; color:var(--text-color, #fff); border-radius:6px; margin:0 4px; transition:background 0.15s ease;">' +
                '<i data-lucide="tv" style="width:16px; height:16px; color:var(--primary, #3b82f6);"></i> Copy Stream Link' +
                '</div>';
        }
        html += '<div class="menu-item" onclick="downloadPreviewFile(\'' + escFn + '\')" style="display:flex; align-items:center; gap:10px; padding:9px 16px; cursor:pointer; font-size:0.9rem; font-weight:500; color:var(--text-color, #fff); border-radius:6px; margin:0 4px; transition:background 0.15s ease;">' +
            '<i data-lucide="download" style="width:16px; height:16px; color:var(--primary, #3b82f6);"></i> Download' +
            '</div>';

        menu.innerHTML = html;
        menu.style.display = "block";

        var menuWidth = menu.offsetWidth || 190;
        var menuHeight = menu.offsetHeight || 100;
        var posX = Math.min(x, window.innerWidth - menuWidth - 10);
        var posY = Math.min(y, window.innerHeight - menuHeight - 10);

        menu.style.left = posX + "px";
        menu.style.top = posY + "px";

        if (window.refreshLucideIcons) {
            window.refreshLucideIcons(menu);
        }
    }

    // Keyboard controls for preview modal: Escape closes, Space/Arrows control video
    document.addEventListener("keydown", function (e) {
        var modal = document.getElementById("previewModal");
        if (!modal || modal.style.display === "none") return;

        if (e.key === "Escape" || e.key === "Esc") {
            e.preventDefault();
            closePreviewModal();
            return;
        }

        if (document.activeElement && (document.activeElement.tagName === "INPUT" || document.activeElement.tagName === "TEXTAREA")) {
            return;
        }

        var video = modal.querySelector("video");
        if (!video) return;

        if (e.key === "ArrowLeft") {
            e.preventDefault();
            e.stopPropagation();
            video.currentTime = Math.max(0, video.currentTime - 10);
        } else if (e.key === "ArrowRight") {
            e.preventDefault();
            e.stopPropagation();
            video.currentTime = Math.min(video.duration || 0, video.currentTime + 10);
        } else if ((e.key === " " || e.code === "Space") && document.activeElement !== video) {
            e.preventDefault();
            e.stopPropagation();
            if (video.paused) { video.play(); } else { video.pause(); }
        } else if (e.key === " " || e.code === "Space") {
            e.preventDefault();
            e.stopPropagation();
        }
    });

    // Preview modal event listeners setup
    function initPreviewModalListeners() {
        var previewModalEl = document.getElementById("previewModal");
        if (previewModalEl) {
            previewModalEl.addEventListener("dblclick", function (e) {
                if (e.target.tagName !== "PRE" && e.target.tagName !== "CODE" && e.target.tagName !== "INPUT" && e.target.tagName !== "TEXTAREA") {
                    e.preventDefault();
                    e.stopPropagation();
                }
            });
            previewModalEl.addEventListener("contextmenu", function (e) {
                e.preventDefault();
                e.stopPropagation();
                var fn = window.currentPreviewFilename;
                if (!fn) {
                    var titleEl = document.getElementById("previewTitle");
                    if (titleEl) fn = titleEl.textContent.trim();
                }
                if (fn) {
                    showPreviewContextMenu(e.clientX, e.clientY, fn);
                }
            });
        }
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", initPreviewModalListeners);
    } else {
        initPreviewModalListeners();
    }

    var PreviewModal = Object.freeze({
        _isFullEngine: true,
        open: openFilePreview,
        close: closePreviewModal,
        openTarget: openFilePreviewTarget,
        updateImageTransform: updateImageTransform,
        zoomPreviewImage: zoomPreviewImage,
        resetPreviewImageZoom: resetPreviewImageZoom,
        setupImageZoomAndPan: setupImageZoomAndPan,
        copyVideoStreamUrl: copyVideoStreamUrl,
        downloadPreviewFile: downloadPreviewFile,
        showPreviewContextMenu: showPreviewContextMenu
    });

    window.PreviewModal = PreviewModal;
    window.openFilePreview = openFilePreview;
    window.closePreviewModal = closePreviewModal;
    window.openFilePreviewTarget = openFilePreviewTarget;
    window.updateImageTransform = updateImageTransform;
    window.zoomPreviewImage = zoomPreviewImage;
    window.resetPreviewImageZoom = resetPreviewImageZoom;
    window.setupImageZoomAndPan = setupImageZoomAndPan;
    window.copyVideoStreamUrl = copyVideoStreamUrl;
    window.downloadPreviewFile = downloadPreviewFile;
    window.showPreviewContextMenu = showPreviewContextMenu;

})(window);
