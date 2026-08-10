/**
 * Download Manager Module
 *
 * Handles file downloads, multi-item file downloads, folder ZIP stream packing,
 * and chunked range response byte processing.
 */

(function (window) {
    'use strict';

    if (window.DownloadManager && window.DownloadManager._initialized) {
        return;
    }

    function downloadFolderAsZip(folderName) {
        if (!folderName) return;
        var link = document.createElement("a");
        link.href = "/download-folder/" + encodeURIComponent(folderName);
        link.download = folderName + ".zip";
        link.style.display = "none";
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
    }

    function getScopedFolderPath() {
        var folder = window._contextMenuFolderPath || (typeof window.getCurrentFolderPath === "function" ? window.getCurrentFolderPath() : (window.currentFolderPath || ""));
        return typeof window.cleanFolderPath === "function" ? window.cleanFolderPath(folder) : folder;
    }

    function buildScopedDownloadPath(filename) {
        if (!filename) return "";
        var cleanName = String(filename).replace(/\\/g, "/").replace(/^\/+|\/+$/g, "");
        if (cleanName.indexOf("/") !== -1) {
            return cleanName;
        }
        var folderPath = getScopedFolderPath();
        return folderPath ? (folderPath + "/" + cleanName) : cleanName;
    }

    function downloadFileByName(filename) {
        if (!filename) return;
        var scopedName = buildScopedDownloadPath(filename);
        var baseName = scopedName.split("/").pop();
        var scopedFolder = getScopedFolderPath();
        var isFolder = false;
        var listEl = document.querySelector('#nasFileList [data-filename="' + baseName.replace(/"/g, '&quot;') + '"]');
        if (listEl) {
            isFolder = listEl.getAttribute("data-is-folder") === "1";
        }
        if (!isFolder && typeof window.getDiskFileMetadata === "function") {
            var foundMeta = window.getDiskFileMetadata(baseName, scopedFolder);
            if (foundMeta && (foundMeta.isFolder || foundMeta.is_dir)) isFolder = true;
        }

        if (isFolder) {
            downloadFolderAsZip(scopedName);
            return;
        }

        var link = document.createElement("a");
        link.href = "/download/" + encodeURIComponent(scopedName);
        link.download = baseName;
        link.style.display = "none";
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        if (window._contextMenuFolderPath) {
            window._contextMenuFolderPath = "";
        }
    }

    function downloadSelected() {
        var selected = Array.isArray(window.selectedItems) ? window.selectedItems : [];
        var items = selected.slice();
        var target = window._contextMenuTarget || "";

        if (items.length === 0 && target) {
            items = [target];
        }
        window._contextMenuTarget = "";

        if (items.length === 0) return;

        var index = 0;
        function downloadNext() {
            if (index >= items.length) {
                if (typeof window.showToast === "function") {
                    window.showToast("Downloaded " + items.length + " item(s).", 3000);
                }
                if (typeof window.clearSelection === "function") {
                    window.clearSelection();
                }
                return;
            }
            var targetItem = items[index];
            var scopedItem = buildScopedDownloadPath(targetItem);
            var baseItem = scopedItem.split("/").pop();
            var scopedFolder = getScopedFolderPath();
            var isFolder = false;
            var listEl = document.querySelector('#nasFileList [data-filename="' + baseItem.replace(/"/g, '&quot;') + '"]');
            if (listEl) {
                isFolder = listEl.getAttribute("data-is-folder") === "1";
            }
            if (!isFolder && typeof window.getDiskFileMetadata === "function") {
                var foundMeta = window.getDiskFileMetadata(baseItem, scopedFolder);
                if (foundMeta && (foundMeta.isFolder || foundMeta.is_dir)) isFolder = true;
            }

            if (isFolder) {
                downloadFolderAsZip(scopedItem);
            } else {
                downloadFileByName(scopedItem);
            }

            index++;
            if (index < items.length) {
                setTimeout(downloadNext, 300);
            }
        }
        downloadNext();
    }

    function downloadSelectedAsZip() {
        var menu = document.getElementById("contextMenu");
        if (menu) menu.style.display = "none";

        var selected = Array.isArray(window.selectedItems) ? window.selectedItems : [];
        var items = selected.slice();
        var target = window._contextMenuTarget || "";

        if (items.length === 0 && target) {
            items = [target];
        }
        window._contextMenuTarget = "";

        if (items.length === 0) return;

        if (typeof window.showToast === "function") {
            window.showToast("Preparing ZIP archive...", 0);
        }

        fetch("/api/files/download-zip", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ files: items })
        })
            .then(function (res) {
                if (!res.ok) {
                    if (res.status === 404) {
                        window.location.href = "/download-all";
                        return null;
                    }
                    throw new Error("Status " + res.status);
                }

                var contentLength = res.headers.get("Content-Length");
                var totalBytes = contentLength ? parseInt(contentLength, 10) : 0;
                var receivedBytes = 0;
                var chunks = [];

                if (!res.body || !res.body.getReader) {
                    if (typeof window.showToast === "function") {
                        window.showToast("Processing ZIP download...", 0);
                    }
                    return res.blob();
                }

                var reader = res.body.getReader();

                function readChunk() {
                    return reader.read().then(function (result) {
                        if (result.done) {
                            return new Blob(chunks, { type: "application/zip" });
                        }
                        chunks.push(result.value);
                        receivedBytes += result.value.length;

                        if (typeof window.showToast === "function") {
                            var recvMB = (receivedBytes / (1024 * 1024)).toFixed(1);
                            if (totalBytes > 0) {
                                var pct = Math.min(100, Math.round((receivedBytes / totalBytes) * 100));
                                var totalMB = (totalBytes / (1024 * 1024)).toFixed(1);
                                window.showToast("Processing ZIP download: " + recvMB + " / " + totalMB + " MB (" + pct + "%)", 0);
                            } else {
                                window.showToast("Processing ZIP download: " + recvMB + " MB transferred...", 0);
                            }
                        }

                        return readChunk();
                    });
                }

                return readChunk();
            })
            .then(function (blob) {
                if (!blob) return;
                var url = URL.createObjectURL(blob);
                var a = document.createElement("a");
                a.href = url;
                a.download = items.length === 1 ? items[0] + ".zip" : "selected_files.zip";
                document.body.appendChild(a);
                a.click();
                document.body.removeChild(a);
                URL.revokeObjectURL(url);
                if (typeof window.showToast === "function") {
                    window.showToast("ZIP download started!", 3500);
                }
                if (typeof window.clearSelection === "function") {
                    window.clearSelection();
                }
            })
            .catch(function (err) {
                console.error("ZIP download error:", err);
                if (typeof window.showToast === "function") {
                    window.showToast("Error downloading ZIP archive.", 4000);
                }
            });
    }

    var DownloadManager = Object.freeze({
        _initialized: true,
        downloadSelected: downloadSelected,
        downloadSelectedAsZip: downloadSelectedAsZip,
        downloadFileByName: downloadFileByName,
        downloadFolderAsZip: downloadFolderAsZip
    });

    window.DownloadManager = DownloadManager;
    window.downloadSelected = downloadSelected;
    window.downloadSelectedAsZip = downloadSelectedAsZip;
    window.downloadFileByName = downloadFileByName;
    window.downloadFolderAsZip = downloadFolderAsZip;

})(window);
