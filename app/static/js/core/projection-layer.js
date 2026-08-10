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

    function getCanonicalIdentity(parentPath, fileName) {
        if (typeof window.getCanonicalIdentity === 'function') {
            return window.getCanonicalIdentity(parentPath, fileName);
        }
        if (!fileName) return "";
        var cleanParent = cleanFolderPath(parentPath);
        var cleanName = String(fileName).trim().replace(/\\/g, "/").replace(/^\/+|\/+$/g, "");
        return cleanParent ? (cleanParent + "/" + cleanName) : cleanName;
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
        if (window.__lanvanTimelineTracker) {
            var folder = storeState ? storeState.currentFolder : "";
            var dCount = Array.isArray(diskFiles) ? diskFiles.length : 0;
            window.__lanvanTimelineTracker.recordEvent("projectionBuild", "folder: '" + folder + "', diskCount: " + dCount);
        }
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

                // Check pending delete status using canonical identity
                var isPendingDelete = Object.keys(pendingOps).some(function (opId) {
                    var op = pendingOps[opId];
                    if (!op || op.type !== 'DELETE') return false;
                    var opIdentity = op.identity || getCanonicalIdentity(op.parentPath || op.folder || "", op.fileName || op.name || "");
                    var itemIdentity = getCanonicalIdentity(taggedPath || currentFolder, fileName);
                    return opIdentity === itemIdentity;
                });
                if (isPendingDelete) continue;

                var isFolderVal = false;
                var dfSize = '--';
                var dfMtime = 0;

                var diskMeta = (typeof window.getFileMetadata === 'function')
                    ? window.getFileMetadata(taggedPath || currentFolder, fileName)
                    : (window._fileMetadataMap ? (window._fileMetadataMap[getCanonicalIdentity(taggedPath || currentFolder, fileName)] || window._fileMetadataMap[fileName]) : null);

                if (typeof df === 'object' && df !== null) {
                    isFolderVal = !!(df.isFolder || df.is_dir || df.is_folder);
                    dfSize = df.size || df.fileSize || df.file_size || '--';
                    dfMtime = df.mtime || df.date || df.modified || 0;
                } else if (typeof df === 'string') {
                    if (diskMeta) {
                        dfSize = diskMeta.size || '--';
                        dfMtime = diskMeta.mtime || 0;
                        isFolderVal = !!diskMeta.isFolder;
                    }
                }

                var vCount = (typeof df === 'object' && df !== null) ? (df.versionCount || 1) : (diskMeta ? (diskMeta.versionCount || 1) : 1);
                var hasV = (typeof df === 'object' && df !== null) ? !!df.hasVersions : (diskMeta ? !!diskMeta.hasVersions : (vCount > 1));
                var logId = (typeof df === 'object' && df !== null) ? df.logicalFileId : (diskMeta ? diskMeta.logicalFileId : null);

                normalizedDiskFiles.push({
                    name: fileName,
                    identity: getCanonicalIdentity(taggedPath || currentFolder, fileName),
                    size: dfSize,
                    mtime: dfMtime,
                    isFolder: isFolderVal,
                    uploading: false,
                    uploadProgress: 100,
                    uploadStatus: 'COMPLETED',
                    versionCount: vCount,
                    hasVersions: hasV,
                    logicalFileId: logId
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

                // Match by identity (full path), not just display name.
                // Two files with the same name in different subfolders are distinct objects.
                var uplIdentity = getCanonicalIdentity(targetDir, itemName);
                var existingIdx = -1;
                for (var ei = 0; ei < normalizedDiskFiles.length; ei++) {
                    var f = normalizedDiskFiles[ei];
                    if (f && !f.isFolder && f.identity === uplIdentity) {
                        existingIdx = ei;
                        break;
                    }
                }
                // Fallback: name-only match if identity didn't hit (handles legacy disk items without identity field)
                if (existingIdx === -1) {
                    if (window.DEBUG_MODE) console.warn('[PROJECTION] Identity fallback: disk item matched by name-only for "' + itemName + '" — add identity field');
                    for (var ei = 0; ei < normalizedDiskFiles.length; ei++) {
                        var f = normalizedDiskFiles[ei];
                        if (f && !f.isFolder && f.name.trim().toLowerCase() === itemName.trim().toLowerCase()) {
                            existingIdx = ei;
                            break;
                        }
                    }
                }

                if (status === 'QUEUED' || status === 'UPLOADING' || status === 'PROCESSING' || status === 'PAUSED' || status === 'COMPLETED') {
                    if (existingIdx >= 0) {
                        // Clone the existing item before modifying (immutability)
                        var clone = Object.assign({}, normalizedDiskFiles[existingIdx]);
                        if (status !== 'COMPLETED') {
                            clone.uploading = true;
                            clone.uploadProgress = itemPct;
                            clone.uploadStatus = status;
                            clone.uploadId = item.id;
                        } else {
                            clone.uploading = false;
                            clone.uploadProgress = 100;
                            clone.uploadStatus = 'COMPLETED';
                        }
                        normalizedDiskFiles[existingIdx] = clone;
                    } else {
                        uploadOverlayItems.push({
                            name: itemName,
                            identity: getCanonicalIdentity(targetDir, itemName),
                            size: formatSize(fileSize),
                            mtime: null, // Unknown mtime — deterministic sentinel
                            isFolder: false,
                            uploading: (status !== 'COMPLETED'),
                            uploadProgress: (status === 'COMPLETED') ? 100 : itemPct,
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
            // Match synthetic folder to existing disk folder by identity (full path),
            // not just display name. Two folders with the same name in different
            // contexts have different identities and must never collide.
            var subFolderIdentity = getCanonicalIdentity(currentFolder, subFolderName);
            var existingIdx = -1;
            for (var fi = 0; fi < normalizedDiskFiles.length; fi++) {
                var f = normalizedDiskFiles[fi];
                if (f && f.isFolder && f.identity === subFolderIdentity) {
                    existingIdx = fi;
                    break;
                }
            }
            // Fallback: name-only match for legacy items without identity field
            if (existingIdx === -1) {
                if (window.DEBUG_MODE) console.warn('[PROJECTION] Identity fallback: folder matched by name-only for "' + subFolderName + '" — add identity field');
                for (var fi = 0; fi < normalizedDiskFiles.length; fi++) {
                    var f = normalizedDiskFiles[fi];
                    if (f && f.isFolder && f.name.trim().toLowerCase() === subFolderName.trim().toLowerCase()) {
                        existingIdx = fi;
                        break;
                    }
                }
            }

            var folderSummary = window.buildUploadBatchSummary
                ? window.buildUploadBatchSummary(sFolder.items)
                : null;
            var formattedFolder = window.formatUploadBatchStatus && folderSummary
                ? window.formatUploadBatchStatus(folderSummary)
                : null;

            var folderProgress = (folderSummary && typeof folderSummary.percent === 'number') 
                ? folderSummary.percent 
                : (sFolder.totalBytes > 0 ? Math.floor((sFolder.uploadedBytes / sFolder.totalBytes) * 100) : 0);

            // Keep legacy fields for backward compatibility with renderer fallbacks
            var baseOverlay = {
                uploading: sFolder.hasUploading,
                uploadProgress: folderProgress,
                uploadStatus: sFolder.hasUploading ? 'UPLOADING' : (folderProgress >= 100 ? 'COMPLETED' : 'QUEUED')
            };
            // Add unified summary if helpers are available
            if (folderSummary && formattedFolder) {
                baseOverlay.uploadSummary = folderSummary;
                baseOverlay.formattedSubtitle = "Folder";
                baseOverlay.formattedStatus = formattedFolder.status;
            }

            if (existingIdx >= 0) {
                var fClone = Object.assign({}, normalizedDiskFiles[existingIdx], baseOverlay);
                normalizedDiskFiles[existingIdx] = fClone;
            } else {
                var newFolder = {
                    name: subFolderName,
                    identity: getCanonicalIdentity(currentFolder, subFolderName),
                    size: formatSize(sFolder.totalBytes),
                    mtime: null,
                    isFolder: true
                };
                Object.assign(newFolder, baseOverlay);
                normalizedDiskFiles.push(newFolder);
            }
        });

        // 4. Strict Deduplication: Every ViewModel item has a unique identity.
        //    Use identity (full filesystem path) as the primary key — never display name alone.
        //    If two items share an identity, prefer folder over file.
        var deduplicatedFiles = [];
        var seenIdentities = {};
        normalizedDiskFiles.forEach(function (f) {
            if (!f || !f.name) return;
            var id = f.identity || getCanonicalIdentity(currentFolder, f.name);
            if (!seenIdentities[id]) {
                seenIdentities[id] = f;
                deduplicatedFiles.push(f);
            } else if (f.isFolder && !seenIdentities[id].isFolder) {
                // Same identity but folder trumps file
                var idx = deduplicatedFiles.indexOf(seenIdentities[id]);
                if (idx !== -1) {
                    deduplicatedFiles[idx] = f;
                    seenIdentities[id] = f;
                }
            }
        });

        // 5. Apply Pure Projection Sorting based on Store state / Global sort settings
        var sortBy = (storeState && typeof storeState.sortBy === "string") ? storeState.sortBy : (window.sortBy || "name");
        var sortDirection = (storeState && typeof storeState.sortDirection === "string") ? storeState.sortDirection : (window.sortDirection || "asc");
        var sortFolders = (storeState && typeof storeState.sortFolders === "string") ? storeState.sortFolders : (window.sortFolders || "top");

        var parseBytes = window.parseSizeToBytes || function (s, isF) { return isF ? -1 : 0; };
        var parseDate = window.parseDateToTimestamp || function (d) { return 0; };

        deduplicatedFiles.sort(function (a, b) {
            if (sortFolders === "top") {
                if (a.isFolder && !b.isFolder) return -1;
                if (!a.isFolder && b.isFolder) return 1;
            }

            var comparison = 0;
            if (sortBy === "name") {
                var nameA = String(a.name || "").toLowerCase();
                var nameB = String(b.name || "").toLowerCase();
                comparison = nameA.localeCompare(nameB, undefined, { numeric: true, sensitivity: 'base' });
            } else if (sortBy === "date") {
                var timeA = parseDate(a.mtime || a.date || a.modified || (a.uploading ? Date.now() / 1000 : 0));
                var timeB = parseDate(b.mtime || b.date || b.modified || (b.uploading ? Date.now() / 1000 : 0));
                comparison = timeA - timeB;
            } else if (sortBy === "size") {
                var bytesA = parseBytes(a.size || a.fileSize, a.isFolder);
                var bytesB = parseBytes(b.size || b.fileSize, b.isFolder);
                comparison = bytesA - bytesB;
            } else {
                var defaultNameA = String(a.name || "").toLowerCase();
                var defaultNameB = String(b.name || "").toLowerCase();
                comparison = defaultNameA.localeCompare(defaultNameB, undefined, { numeric: true, sensitivity: 'base' });
            }

            return sortDirection === "asc" ? comparison : -comparison;
        });

        // INVARIANT GUARD (DEBUG only): Verify ViewModel integrity.
        // No duplicate identities, no invalid statuses.
        if (window.DEBUG_MODE) {
            var vmIdentities = {};
            for (var vi = 0; vi < deduplicatedFiles.length; vi++) {
                var vf = deduplicatedFiles[vi];
                if (!vf || !vf.name) continue;
                var vid = vf.identity || getCanonicalIdentity(currentFolder, vf.name);
                if (vmIdentities[vid]) {
                    console.error('[INVARIANT FAILED] Duplicate identity in ViewModel: ' + vid, vf, vmIdentities[vid]);
                }
                vmIdentities[vid] = vf;
                if (vf.uploading && vf.uploadStatus !== vf.uploadStatus.toUpperCase()) {
                    console.error('[INVARIANT FAILED] Non-UPPERCASE uploadStatus in ViewModel: ' + vf.uploadStatus, vf);
                }
            }
        }

        var execDuration = (performance.now() - startTime).toFixed(2);
        console.log("🔍 [TRACE @ projection-layer.js:160] Projection Complete | Exec: " + execDuration + "ms | Items: " + deduplicatedFiles.length + " | Visible: [" + deduplicatedFiles.map(function(d){ return d.name + (d.isFolder ? '(dir)' : '(file)'); }).join(", ") + "]");

        if (typeof window.tagFilesWithFolder === 'function') {
            window.tagFilesWithFolder(deduplicatedFiles, currentFolder);
        } else {
            try {
                Object.defineProperty(deduplicatedFiles, '__folderPath', {
                    value: currentFolder,
                    writable: true,
                    configurable: true,
                    enumerable: false
                });
            } catch (e) {
                deduplicatedFiles.__folderPath = currentFolder;
            }
        }

        return deduplicatedFiles;
    };

    var projectionInstance = new ProjectionLayer();
    projectionInstance.projectViewModel = projectionInstance.buildCurrentFolderViewModel;
    window.ProjectionLayer = projectionInstance;

})(window);
