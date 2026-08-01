/**
 * @file preview-modal.js
 * @description Preview Modal presentation layer for images, videos, audio, documents, and code text files.
 * @module PreviewModal
 */

(function (window) {
    'use strict';

    if (window.PreviewModal) {
        return;
    }

    function setupImageZoomAndPan() {
        var img = document.getElementById("lanvanZoomImage");
        if (!img) return;

        var scale = 1;
        var isPanning = false;
        var startX = 0, startY = 0;
        var translateX = 0, translateY = 0;

        img.addEventListener("wheel", function (e) {
            e.preventDefault();
            var delta = e.deltaY > 0 ? -0.15 : 0.15;
            scale = Math.min(Math.max(0.5, scale + delta), 4);
            if (scale === 1) {
                translateX = 0;
                translateY = 0;
            }
            img.style.transform = "translate(" + translateX + "px, " + translateY + "px) scale(" + scale + ")";
            img.style.cursor = scale > 1 ? "grab" : "default";
        }, { passive: false });

        img.addEventListener("mousedown", function (e) {
            if (scale <= 1) return;
            isPanning = true;
            startX = e.clientX - translateX;
            startY = e.clientY - translateY;
            img.style.cursor = "grabbing";
        });

        window.addEventListener("mousemove", function (e) {
            if (!isPanning) return;
            translateX = e.clientX - startX;
            translateY = e.clientY - startY;
            img.style.transform = "translate(" + translateX + "px, " + translateY + "px) scale(" + scale + ")";
        });

        window.addEventListener("mouseup", function () {
            if (isPanning) {
                isPanning = false;
                img.style.cursor = scale > 1 ? "grab" : "default";
            }
        });
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

        if (imageExts.indexOf(ext) !== -1) {
            bodyEl.innerHTML = '<div class="image-preview-wrapper" style="position:relative; width:100%; height:100%; min-height:70vh; flex:1; display:flex; align-items:center; justify-content:center; overflow:hidden; background:rgba(18,20,26,0.5); border-radius:14px; padding:1.5rem;">' +
                '<img id="lanvanZoomImage" src="' + downloadUrl + '" alt="' + escName + '" style="max-width:90vw; max-height:84vh; width:auto; height:auto; object-fit:contain; border-radius:8px; display:block; margin:auto; box-shadow:0 16px 48px rgba(0,0,0,0.6); transition:transform 0.15s ease-out; cursor:grab;" />' +
                '</div>';
            modal.style.display = "flex";
            if (typeof window.refreshLucideIcons === 'function') window.refreshLucideIcons(bodyEl);
            setupImageZoomAndPan();
        } else if (videoExts.indexOf(ext) !== -1) {
            bodyEl.innerHTML = '<div style="width:100%; height:100%; min-height:70vh; flex:1; display:flex; align-items:center; justify-content:center; background:rgba(18,20,26,0.5); border-radius:14px; padding:1.5rem;">' +
                '<video src="' + downloadUrl + '" controls autoplay playsinline preload="auto" tabindex="0" style="max-width:90vw; max-height:84vh; width:auto; height:auto; object-fit:contain; border-radius:8px; outline:none; background:transparent; box-shadow:0 16px 48px rgba(0,0,0,0.6);"></video>' +
                '</div>';
            modal.style.display = "flex";
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
            if (typeof window.refreshLucideIcons === 'function') window.refreshLucideIcons(bodyEl);
        } else if (ext === "pdf") {
            bodyEl.style.padding = "0";
            bodyEl.innerHTML = '<div style="width:100%; height:100%; min-height:70vh; flex:1; background:rgba(18,20,26,0.5); border-radius:14px; overflow:hidden;">' +
                '<iframe src="' + downloadUrl + '" style="width:100%; height:100%; border:none; display:block;"></iframe>' +
                '</div>';
            modal.style.display = "flex";
        } else if (docExts.indexOf(ext) !== -1) {
            bodyEl.innerHTML = '<div style="width:100%; text-align:center; color:var(--text-color); padding:1rem;">Rendering Word document...</div>';
            modal.style.display = "flex";

            function renderDocCardFallback() {
                bodyEl.innerHTML = '<div style="display:flex; flex-direction:column; align-items:center; justify-content:center; gap:1.4rem; width:100%; height:100%; min-height:70vh; flex:1; padding:2.5rem; background:rgba(18, 20, 26, 0.5); border-radius:14px; color:#fff; text-align:center;">' +
                    '<div class="avatar-icon avatar-doc" style="width:84px; height:84px; border-radius:24px; background:rgba(239, 68, 68, 0.14); display:flex; align-items:center; justify-content:center; box-shadow:0 8px 24px rgba(239,68,68,0.15);">' +
                    '<i data-lucide="file-text" style="width:42px; height:42px; color:#ef4444;"></i>' +
                    '</div>' +
                    '<div style="font-weight:700; font-size:1.4rem; color:#ffffff; text-align:center; word-break:break-all; max-width:600px;">' + escName + '</div>' +
                    '<div style="font-size:0.95rem; color:rgba(255,255,255,0.75); text-align:center; max-width:440px;">No in-app preview available for this document format.</div>' +
                    '<a href="' + downloadUrl + '?download=1" download class="gdrive-doc-fallback-btn">' +
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
                '<a href="' + downloadUrl + '?download=1" download class="gdrive-doc-fallback-btn">' +
                '<i data-lucide="download" style="width:18px; height:18px;"></i> Download File' +
                '</a>' +
                '</div>';
            modal.style.display = "flex";
            modal.style.pointerEvents = "auto";
            if (typeof window.refreshLucideIcons === 'function') window.refreshLucideIcons(bodyEl);
        }
    }

    function openFilePreviewTarget() {
        var selected = window.prototypeSelectedItems || [];
        var target = window._contextMenuTarget || (selected.length > 0 ? selected[0] : "");
        window._contextMenuTarget = "";
        if (target) {
            openFilePreview(target);
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

        if (e.key === " " || e.code === "Space") {
            e.preventDefault();
            if (video.paused) video.play(); else video.pause();
        } else if (e.key === "ArrowLeft") {
            e.preventDefault();
            video.currentTime = Math.max(0, video.currentTime - 5);
        } else if (e.key === "ArrowRight") {
            e.preventDefault();
            video.currentTime = Math.min(video.duration || 0, video.currentTime + 5);
        }
    });

    var PreviewModal = Object.freeze({
        open: openFilePreview,
        close: closePreviewModal,
        openTarget: openFilePreviewTarget
    });

    window.PreviewModal = PreviewModal;
    window.openFilePreview = openFilePreview;
    window.closePreviewModal = closePreviewModal;
    window.openFilePreviewTarget = openFilePreviewTarget;

})(window);
