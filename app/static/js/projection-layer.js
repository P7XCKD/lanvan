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

    /**
     * PROJECTION CONTRACT:
     * Pure function: (storeState, diskFiles) => ViewModel
     * - Never mutates inputs (clones before modifying)
     * - Never reads global state (all data via parameters)
     * - Deterministic: same inputs always produce same output
     * - Date.now() is NEVER used for mtime (use 0 as sentinel)
     */
    ProjectionLayer.prototype.buildCurrentFolderViewModel = function (storeState, diskFiles) {
        var startTime = performance.now();
        var currentFolder = cleanFolderPath(storeState ? storeState.currentFolder : "");
        var rawDiskFiles = Array.isArray(diskFiles) ? diskFiles : [];
        var uploadQueue = storeState && Array.isArray(storeState.uploadQueue) ? storeState.uploadQueue : [];
        var pendingOps = storeState && storeState.pendingOps ? storeState.pendingOps : {};

        // Normalize status to UPPERCASE for comparison (Store uses UPPERCASE now)
        function normStatus(s) {
            if (!s) return 'QUEUED';
            return String(s).toUpperCase();
        }

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
                    // Use the diskFiles parameter itself for folder detection — already a Repository snapshot
                    // No global window.FileRepository read needed
                    isFolderVal = false;
                } else {
                    isFolderVal = !!(df.isFolder || df.is_dir || df.is_folder);
                }

                normalizedDiskFiles.push({
                    name: fileName,
                    size: typeof df === 'string' ? '--' : (df.size || '--'),
                    mtime: typeof df === 'string' ? 0 : (df.mtime || 0),
                    isFolder: isFolderVal,
                    uploading: false,
                    uploadProgress: 100,
                    uploadStatus: 'COMPLETED'
                });
            }
        }

        // 2. Process Upload Queue Items — NEVER mutate normalizedDiskFiles items in-place
        var uploadOverlayItems = []; // New array for overlay items, merged after
        var activeFolderMap = {};
        for (var j = 0; j < uploadQueue.length; j++) {
            var item = uploadQueue[j];
            if (!item) continue;
            var itemName = item.fileName || (item.file && item.file.name) || item.name;
            if (!itemName) continue;

            var targetDir = cleanFolderPath(item.targetDir || item.parent_path || "");
            var status = normStatus(item.status);
            if (status === 'DELETED' || status === 'CANCELLED') continue;
            var itemPct = Math.round(item.progress || 0);
            var fileSize = item.fileSize || (item.file && item.file.size) || 0;

            if (targetDir === currentFolder) {
                // Direct file in active viewport (skip if item itself is marked as folder)
                if (item.isFolder || (item.file && item.file.isFolder)) continue;

                var existingIdx = -1;
                for (var ei = 0; ei < normalizedDiskFiles.length; ei++) {
                    var f = normalizedDiskFiles[ei];
                    if (f && !f.isFolder && f.name.trim().toLowerCase() === itemName.trim().toLowerCase()) {
                        existingIdx = ei;
                        break;
                    }
                }

                if (status === 'QUEUED' || status === 'UPLOADING' || status === 'PROCESSING' || status === 'PAUSED') {
                    if (existingIdx >= 0) {
                        // Clone the existing item before modifying (immutability)
                        var clone = Object.assign({}, normalizedDiskFiles[existingIdx]);
                        clone.uploading = true;
                        clone.uploadProgress = itemPct;
                        clone.uploadStatus = status;
                        clone.uploadId = item.id;
                        normalizedDiskFiles[existingIdx] = clone;
                    } else {
                        uploadOverlayItems.push({
                            name: itemName,
                            size: formatSize(fileSize),
                            mtime: 0, // Sentinel: unknown mtime (deterministic)
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
                    var bytesDone = (status === 'COMPLETED') ? fileSize : (item.bytesUploaded || 0);
                    activeFolderMap[subFolder].totalBytes += fileSize;
                    activeFolderMap[subFolder].uploadedBytes += bytesDone;
                    if (status === 'UPLOADING' || status === 'PROCESSING' || status === 'QUEUED') {
                        activeFolderMap[subFolder].hasUploading = true;
                    }
                    activeFolderMap[subFolder].items.push(item);
                }
            }
        }

        // Append overlay items (uploads without existing disk file)
        for (var oi = 0; oi < uploadOverlayItems.length; oi++) {
            normalizedDiskFiles.push(uploadOverlayItems[oi]);
        }

        // 3. Synthesize Synthetic Root Folder Rows for Active Batches
        Object.keys(activeFolderMap).forEach(function (subFolderName) {
            var sFolder = activeFolderMap[subFolderName];
            var existingIdx = -1;
            for (var fi = 0; fi < normalizedDiskFiles.length; fi++) {
                var f = normalizedDiskFiles[fi];
                if (f && f.isFolder && f.name.trim().toLowerCase() === subFolderName.trim().toLowerCase()) {
                    existingIdx = fi;
                    break;
                }
            }

            var folderProgress = sFolder.totalBytes > 0 ? Math.round((sFolder.uploadedBytes / sFolder.totalBytes) * 100) : 0;
            if (existingIdx >= 0) {
                if (sFolder.hasUploading) {
                    var fClone = Object.assign({}, normalizedDiskFiles[existingIdx]);
                    fClone.uploading = true;
                    fClone.uploadProgress = folderProgress;
                    fClone.uploadStatus = 'UPLOADING';
                    normalizedDiskFiles[existingIdx] = fClone;
                }
            } else {
                normalizedDiskFiles.push({
                    name: subFolderName,
                    size: formatSize(sFolder.totalBytes),
                    mtime: 0, // Sentinel: unknown mtime (deterministic)
                    isFolder: true,
                    uploading: sFolder.hasUploading,
                    uploadProgress: folderProgress,
                    uploadStatus: sFolder.hasUploading ? 'UPLOADING' : (folderProgress >= 100 ? 'COMPLETED' : 'QUEUED')
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
