/**
 * Lanvan Pure Projection Engine (projection-layer.js)
 * Pure Function: (storeState, diskFiles) => viewModel
 * Merges server disk files and active upload queue items for currentFolder with ZERO side effects.
 */

(function (window) {
    'use strict';

    function cleanFolderPath(path) {
        if (!path) return "";
        var cleaned = String(path).replace(/\\/g, "/").replace(/^Home \(Root\)\/?/, "").replace(/^Home\/?/, "");
        cleaned = cleaned.replace(/^\/+|\/+$/g, "");
        return (cleaned === "Home (Root)" || cleaned === "Home" || cleaned === "Home/") ? "" : cleaned;
    }

    function formatSize(bytes) {
        if (!bytes || bytes === 0) return '0 B';
        var k = 1024;
        var sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
        var i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
    }

    function ProjectionLayer() {}

    ProjectionLayer.prototype.buildCurrentFolderViewModel = function (storeState, diskFiles) {
        var startTime = performance.now();
        var currentFolder = cleanFolderPath(storeState ? storeState.currentFolder : "");
        var rawDiskFiles = Array.isArray(diskFiles) ? diskFiles : [];
        var uploadQueue = storeState && Array.isArray(storeState.uploadQueue) ? storeState.uploadQueue : [];
        var pendingOps = storeState && storeState.pendingOps ? storeState.pendingOps : {};

        var normalizedDiskFiles = [];
        var taggedPath = rawDiskFiles.__folderPath !== undefined ? cleanFolderPath(rawDiskFiles.__folderPath) : currentFolder;

        // 1. Process Server Disk Files (strictly matching target folder scope)
        if (taggedPath === currentFolder) {
            for (var i = 0; i < rawDiskFiles.length; i++) {
                var df = rawDiskFiles[i];
                if (!df) continue;
                var fileName = typeof df === 'string' ? df : df.name;
                if (!fileName) continue;

                // Check pending delete status
                var isPendingDelete = Object.keys(pendingOps).some(function (opId) {
                    var op = pendingOps[opId];
                    return op && op.type === 'DELETE' && op.fileName === fileName;
                });
                if (isPendingDelete) continue;

                var isFolderVal = false;
                if (typeof df === 'string') {
                    var cachedRepo = window.FileRepository ? window.FileRepository.getFolderCache(currentFolder) : [];
                    var matchRepo = cachedRepo.find(function (c) {
                        return c && typeof c === 'object' && c.name === fileName && (c.isFolder || c.is_dir || c.is_folder);
                    });
                    isFolderVal = !!matchRepo || !!(window._recentlyCreatedFolders && window._recentlyCreatedFolders[fileName]);
                } else {
                    isFolderVal = !!(df.isFolder || df.is_dir || df.is_folder || (window._recentlyCreatedFolders && window._recentlyCreatedFolders[fileName]));
                }

                normalizedDiskFiles.push({
                    name: fileName,
                    size: typeof df === 'string' ? '--' : (df.size || '--'),
                    mtime: typeof df === 'string' ? 0 : (df.mtime || 0),
                    isFolder: isFolderVal,
                    uploading: false,
                    uploadProgress: 100,
                    uploadStatus: 'completed'
                });
            }
        }

        // 2. Process Upload Queue Items
        var activeFolderMap = {};
        var activeNameMap = activeFolderMap;
        for (var j = 0; j < uploadQueue.length; j++) {
            var item = uploadQueue[j];
            if (!item) continue;
            var itemName = item.fileName || (item.file && item.file.name) || item.name;
            if (!itemName) continue;

            var targetDir = cleanFolderPath(item.targetDir || item.parent_path || "");
            var status = String(item.status || 'QUEUED').toLowerCase();
            if (status === 'deleted') continue;
            var itemPct = Math.round(item.progress || 0);
            var fileSize = item.fileSize || (item.file && item.file.size) || 0;

            if (targetDir === currentFolder) {
                // Direct file in active viewport (skip if item itself is marked as folder)
                if (item.isFolder || (item.file && item.file.isFolder)) continue;

                var existingItem = normalizedDiskFiles.find(function (f) {
                    return f && !f.isFolder && f.name.trim().toLowerCase() === itemName.trim().toLowerCase();
                });

                if (status === 'cancelled') {
                    continue;
                }

                if (status === 'queued' || status === 'uploading' || status === 'processing' || status === 'paused') {
                    if (existingItem) {
                        existingItem.uploading = true;
                        existingItem.uploadProgress = itemPct;
                        existingItem.uploadStatus = status;
                        existingItem.uploadId = item.id;
                    } else {
                        normalizedDiskFiles.push({
                            name: itemName,
                            size: formatSize(fileSize),
                            mtime: Math.floor(Date.now() / 1000),
                            isFolder: false,
                            uploading: true,
                            uploadProgress: itemPct,
                            uploadStatus: status,
                            uploadId: item.id
                        });
                    }
                }
            } else if (targetDir.startsWith(currentFolder ? (currentFolder + "/") : "")) {
                // Subfolder upload batch: calculate synthetic root folder row
                var relPath = currentFolder ? targetDir.substring(currentFolder.length + 1) : targetDir;
                var subFolder = relPath.split("/")[0];
                if (subFolder && subFolder !== currentFolder) {
                    if (!activeFolderMap[subFolder]) {
                        activeFolderMap[subFolder] = {
                            name: subFolder,
                            totalBytes: 0,
                            uploadedBytes: 0,
                            hasUploading: false,
                            items: []
                        };
                    }
                    var bytesDone = (status === 'completed') ? fileSize : (item.bytesUploaded || 0);
                    activeFolderMap[subFolder].totalBytes += fileSize;
                    activeFolderMap[subFolder].uploadedBytes += bytesDone;
                    if (status === 'uploading' || status === 'processing' || status === 'queued') {
                        activeFolderMap[subFolder].hasUploading = true;
                    }
                    activeFolderMap[subFolder].items.push(item);
                }
            }
        }

        // 3. Synthesize Synthetic Root Folder Rows for Active Batches
        Object.keys(activeFolderMap).forEach(function (subFolderName) {
            var sFolder = activeFolderMap[subFolderName];
            var existingFolder = normalizedDiskFiles.find(function (f) {
                return f && f.isFolder && f.name.trim().toLowerCase() === subFolderName.trim().toLowerCase();
            });

            var folderProgress = sFolder.totalBytes > 0 ? Math.round((sFolder.uploadedBytes / sFolder.totalBytes) * 100) : 0;
            if (existingFolder) {
                if (sFolder.hasUploading) {
                    existingFolder.uploading = true;
                    existingFolder.uploadProgress = folderProgress;
                    existingFolder.uploadStatus = 'uploading';
                }
            } else {
                normalizedDiskFiles.push({
                    name: subFolderName,
                    size: formatSize(sFolder.totalBytes),
                    mtime: Math.floor(Date.now() / 1000),
                    isFolder: true,
                    uploading: sFolder.hasUploading,
                    uploadProgress: folderProgress,
                    uploadStatus: sFolder.hasUploading ? 'uploading' : (folderProgress >= 100 ? 'completed' : 'queued')
                });
            }
        });

        // 4. Strict Deduplication: Prefer folder entries over file entries if names match
        var deduplicatedFiles = [];
        var seenNameKeys = {};
        normalizedDiskFiles.forEach(function (f) {
            if (!f || !f.name) return;
            var key = f.name.trim().toLowerCase();
            if (!seenNameKeys[key]) {
                seenNameKeys[key] = f;
                deduplicatedFiles.push(f);
            } else if (f.isFolder && !seenNameKeys[key].isFolder) {
                var idx = deduplicatedFiles.indexOf(seenNameKeys[key]);
                if (idx !== -1) {
                    deduplicatedFiles[idx] = f;
                    seenNameKeys[key] = f;
                }
            }
        });

        // 5. Sort: Folders first (by name), then files (by name)
        deduplicatedFiles.sort(function (a, b) {
            if (a.isFolder !== b.isFolder) {
                return a.isFolder ? -1 : 1;
            }
            return String(a.name).localeCompare(String(b.name));
        });

        var execDuration = (performance.now() - startTime).toFixed(2);
        console.log("🔍 [TRACE @ projection-layer.js:160] Projection Complete | Exec: " + execDuration + "ms | Items: " + deduplicatedFiles.length + " | Visible: [" + deduplicatedFiles.map(function(d){ return d.name + (d.isFolder ? '(dir)' : '(file)'); }).join(", ") + "]");

        return deduplicatedFiles;
    };

    var projectionInstance = new ProjectionLayer();
    projectionInstance.projectViewModel = projectionInstance.buildCurrentFolderViewModel;
    window.ProjectionLayer = projectionInstance;

})(window);
