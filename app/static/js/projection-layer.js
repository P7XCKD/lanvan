/**
 * Lanvan Unidirectional Architecture: Projection Layer
 * Only ProjectionLayer may create VisibleFiles[]. Violation of this rule is a bug.
 * Pure function: Transforms Store State and Repository Disk Files into a ViewModel.
 */

(function (window) {
    'use strict';

    function cleanProjectionFolderPath(path) {
        if (!path) return "";
        var cleaned = String(path).replace(/\\/g, "/").replace(/^Home \(Root\)\/?/, "").replace(/^Home\/?/, "");
        cleaned = cleaned.replace(/^\/+|\/+$/g, "");
        if (cleaned === "Home (Root)" || cleaned === "Home" || cleaned === "Home/") return "";
        return cleaned;
    }

    function getRelativeItemDir(itemDir, normCurrentDir) {
        var cleanItem = cleanProjectionFolderPath(itemDir);
        var cleanCurrent = cleanProjectionFolderPath(normCurrentDir);
        if (!cleanCurrent) return cleanItem;
        if (cleanItem === cleanCurrent) return "";
        if (cleanItem.startsWith(cleanCurrent + "/")) {
            return cleanItem.substring(cleanCurrent.length + 1);
        }
        return null;
    }

    function formatProjectionSize(bytes) {
        if (bytes === 0 || !bytes) return '0 B';
        var k = 1024;
        var sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
        var i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
    }

    function ProjectionLayer() {}

    ProjectionLayer.prototype.buildCurrentFolderViewModel = function (storeState, diskFiles) {
        var currentFolder = cleanProjectionFolderPath(storeState ? storeState.currentFolder : "");
        var rawDiskFiles = diskFiles || [];
        var uploadQueue = (storeState && storeState.uploadQueue) ? storeState.uploadQueue : [];
        var pendingOps = (storeState && storeState.pendingOps) ? storeState.pendingOps : {};

        // 1. Normalize Disk Files (and validate target folder scope if tagged)
        var normalizedDiskFiles = [];
        var hasFolderTag = rawDiskFiles && rawDiskFiles.__folderPath !== undefined;
        var targetFolderOfDiskFiles = hasFolderTag ? cleanProjectionFolderPath(rawDiskFiles.__folderPath) : "";

        if (!hasFolderTag && currentFolder) {
            console.error("  [PROJECTION GUARD] Rejected unscoped disk files while projecting subfolder '" + currentFolder + "'. Disk files must carry __folderPath.");
            rawDiskFiles = [];
        }

        if (targetFolderOfDiskFiles === currentFolder) {
            for (var i = 0; i < rawDiskFiles.length; i++) {
                var df = rawDiskFiles[i];
                if (!df) continue;
                var fn = typeof df === "string" ? df : df.name;
                if (!fn) continue;
                normalizedDiskFiles.push({
                    name: fn,
                    size: typeof df === "string" ? "--" : (df.size || "--"),
                    mtime: typeof df === "string" ? 0 : (df.mtime || 0),
                    isFolder: typeof df === "string" ? false : !!df.isFolder,
                    targetDir: targetFolderOfDiskFiles
                });
            }
        } else {
            console.warn("  [PROJECTION GUARD] Suppressed rawDiskFiles from wrong folder! Raw disk files folder: '" + targetFolderOfDiskFiles + "' | currentFolder: '" + currentFolder + "'");
        }

        // 2. Filter out items pending deletion
        normalizedDiskFiles = normalizedDiskFiles.filter(function (f) {
            var isPendingDelete = Object.keys(pendingOps).some(function (opId) {
                var op = pendingOps[opId];
                return op && op.type === 'DELETE' && op.fileName === f.name;
            });
            return !isPendingDelete;
        });

        // 3. Process active uploads & synthetic root folders for current view
        var activeUploads = [];
        var activeFolderMap = {};

        uploadQueue.forEach(function (item) {
            if (!item) return;
            var itemName = item.fileName || (item.file && item.file.name) || item.name;
            if (!itemName) return;

            var rawDir = item.targetDir || item.parent_path || item.folder || "";
            var relDir = getRelativeItemDir(rawDir, currentFolder);
            if (relDir === null) return; // Belongs to a completely different folder view!

            var fileSize = item.fileSize || (item.file && item.file.size) || 0;

            if (relDir === "") {
                // Direct file in current view
                var existingItem = normalizedDiskFiles.find(function (f) {
                    return f && !f.isFolder && f.name.trim().toLowerCase() === itemName.trim().toLowerCase();
                });

                var status = String(item.status || '').toLowerCase();
                var itemPct = Math.round(item.progress || 0);

                if (status === 'queued' || status === 'uploading' || status === 'processing' || status === 'paused') {
                    if (existingItem) {
                        existingItem.uploading = true;
                        existingItem.uploadProgress = itemPct;
                        existingItem.uploadStatus = status;
                        existingItem.uploadId = item.id;
                    } else {
                        activeUploads.push({
                            name: itemName,
                            size: formatProjectionSize(fileSize),
                            mtime: Math.floor(Date.now() / 1000),
                            isFolder: false,
                            uploading: true,
                            uploadProgress: itemPct,
                            uploadStatus: status,
                            uploadId: item.id
                        });
                    }
                } else if (status === 'completed') {
                    if (existingItem) {
                        existingItem.uploading = false;
                        existingItem.uploadProgress = 100;
                        existingItem.uploadStatus = 'completed';
                    } else {
                        // Newly completed upload not yet in disk files API response
                        var alreadyInDisk = normalizedDiskFiles.find(function (f) { return f && f.name === itemName; });
                        if (!alreadyInDisk) {
                            normalizedDiskFiles.push({
                                name: itemName,
                                size: formatProjectionSize(fileSize),
                                mtime: Math.floor(Date.now() / 1000),
                                isFolder: false,
                                uploading: false,
                                uploadProgress: 100,
                                uploadStatus: 'completed'
                            });
                        }
                    }
                }
            } else if (['queued', 'uploading', 'processing', 'paused', 'completed', 'cancelled'].indexOf(String(item.status).toLowerCase()) !== -1) {
                // Subfolder upload batch in current view
                var rootFolder = relDir.split("/")[0];
                if (rootFolder) {
                    if (!activeFolderMap[rootFolder]) {
                        activeFolderMap[rootFolder] = {
                            totalBytes: 0,
                            uploadedBytes: 0,
                            hasUploading: false,
                            hasPaused: false,
                            hasCancelled: false,
                            allCompleted: true,
                            items: []
                        };
                    }
                    var itemStatus = String(item.status).toLowerCase();
                    var bytesDone = (itemStatus === 'completed') ? fileSize : (item.bytesUploaded || 0);
                    activeFolderMap[rootFolder].totalBytes += fileSize;
                    activeFolderMap[rootFolder].uploadedBytes += bytesDone;
                    if (itemStatus === 'uploading' || itemStatus === 'processing' || itemStatus === 'queued') {
                        activeFolderMap[rootFolder].allCompleted = false;
                    }
                    if (itemStatus === 'cancelled') {
                        activeFolderMap[rootFolder].hasCancelled = true;
                        activeFolderMap[rootFolder].allCompleted = false;
                    }
                    if (itemStatus === 'uploading' || itemStatus === 'processing') {
                        activeFolderMap[rootFolder].hasUploading = true;
                    }
                    if (itemStatus === 'paused') {
                        activeFolderMap[rootFolder].hasPaused = true;
                    }
                    activeFolderMap[rootFolder].items.push(item);
                }
            }
        });

        // 4. Synthesize active folder rows
        Object.keys(activeFolderMap).forEach(function (folderName) {
            var finfo = activeFolderMap[folderName];
            if (!finfo.allCompleted || finfo.hasCancelled) {
                var folderPct = finfo.totalBytes > 0 ? Math.min(99, Math.round((finfo.uploadedBytes / finfo.totalBytes) * 100)) : 0;
                var existingFolder = normalizedDiskFiles.find(function (f) { return f && f.name === folderName && f.isFolder; });
                var folderStatus = finfo.hasUploading ? 'uploading' : (finfo.hasPaused ? 'paused' : (finfo.hasCancelled ? 'cancelled' : 'queued'));
                if (existingFolder) {
                    existingFolder.uploading = true;
                    existingFolder.uploadProgress = folderPct;
                    existingFolder.uploadStatus = folderStatus;
                    existingFolder.uploadId = finfo.items[0] ? finfo.items[0].id : null;
                } else {
                    var alreadyInActive = activeUploads.find(function (f) { return f.name === folderName && f.isFolder; });
                    if (!alreadyInActive) {
                        activeUploads.push({
                            name: folderName,
                            size: formatProjectionSize(finfo.uploadedBytes) + " / " + formatProjectionSize(finfo.totalBytes),
                            mtime: Math.floor(Date.now() / 1000),
                            isFolder: true,
                            uploading: true,
                            uploadProgress: folderPct,
                            uploadStatus: folderStatus,
                            uploadId: finfo.items[0] ? finfo.items[0].id : null
                        });
                    }
                }
            }
        });

        // 5. Deduplicate and merge active uploads + remaining unique disk files
        var activeNameMap = {};
        activeUploads.forEach(function (au) {
            if (au && au.name) {
                var k = (au.isFolder ? "folder:" : "file:") + au.name.trim().toLowerCase();
                activeNameMap[k] = true;
            }
        });

        var filteredDiskFiles = normalizedDiskFiles.filter(function (nf) {
            if (!nf || !nf.name) return false;
            var k = (nf.isFolder ? "folder:" : "file:") + nf.name.trim().toLowerCase();
            return !activeNameMap[k];
        });

        var visibleFiles = activeUploads.concat(filteredDiskFiles);

        // 6. Development Invariant Assertions (Assert dynamically merged active queue items)
        activeUploads.forEach(function (item) {
            var qi = uploadQueue.find(function (q) {
                var qName = q.fileName || (q.file && q.file.name) || q.name;
                return qName === item.name;
            });
            if (qi) {
                var itemDir = cleanProjectionFolderPath(qi.targetDir || qi.parent_path || qi.folder || "");
                if (itemDir !== currentFolder) {
                    console.error("  [PROJECTION ASSERTION FAILED] File from wrong folder projected! File: '" + item.name + "' | Item targetDir: '" + itemDir + "' | currentFolder: '" + currentFolder + "'");
                }
            }
        });

        return {
            currentFolder: currentFolder,
            visibleFiles: visibleFiles,
            activeUploads: activeUploads,
            selection: ((storeState && storeState.selection) ? storeState.selection : []).slice(),
            timestamp: Date.now()
        };
    };

    var projectionInstance = new ProjectionLayer();
    window.ProjectionLayer = ProjectionLayer;
    window.projectionLayer = projectionInstance;

    // DevTools hook
    if (window.__LANVAN_DEVTOOLS__) {
        window.__LANVAN_DEVTOOLS__.dumpProjection = function () {
            var vm = projectionInstance.buildCurrentFolderViewModel(
                window.LanvanStore ? window.LanvanStore.state : {},
                window.FileRepository ? window.FileRepository.getFolderCache() : []
            );
            console.log("=== LANVAN PROJECTION VIEW MODEL ===", vm);
            return vm;
        };
    }

})(window);
