/**
 * Lanvan Upload Transfer Engine Module (upload-engine.js)
 * Manages window.uploadQueue single source of truth, chunking, pause/resume/cancel transitions.
 */

(function (window) {
  'use strict';

  // Authoritative State Repository — Store is the single source of truth.
  // Do NOT reassign window.uploadQueue; read from Store directly.

  function getQueueItem(uploadId) {
    if (!window.uploadQueue) return null;
    return window.uploadQueue.find(function (item) {
      return item && item.id === uploadId;
    }) || null;
  }

  function pauseUploadItem(uploadId) {
    var item = getQueueItem(uploadId);
    if (!item) return;

    var folder = window.getItemFolder ? window.getItemFolder(item) : "";
    if (folder) {
      var idsToPause = [];
      window.uploadQueue.forEach(function (i) {
        if (!i) return;
        var f = window.getItemFolder ? window.getItemFolder(i) : "";
        if (f === folder && (i.status === 'UPLOADING' || i.status === 'QUEUED' || i.status === 'UPLOADING' || i.status === 'QUEUED')) {
          if (i.xhr) { try { i.xhr.abort(); } catch (e) { } }
          idsToPause.push(i.id);
        }
      });
      for (var p = 0; p < idsToPause.length; p++) {
        if (window.LanvanStore) {
          window.LanvanStore.dispatch('UPDATE_UPLOAD_STATUS', { id: idsToPause[p], status: 'PAUSED' });
        }
      }
    } else if (item.status === 'UPLOADING' || item.status === 'QUEUED' || item.status === 'UPLOADING' || item.status === 'QUEUED') {
      if (item.xhr) { try { item.xhr.abort(); } catch (e) { } }
      if (window.LanvanStore) {
        window.LanvanStore.dispatch('UPDATE_UPLOAD_STATUS', { id: uploadId, status: 'PAUSED' });
      }
    }
  }

  function resumeUploadItem(uploadId) {
    var item = getQueueItem(uploadId);
    if (!item) return;

    var folder = window.getItemFolder ? window.getItemFolder(item) : "";
    if (folder) {
      var idsToResume = [];
      window.uploadQueue.forEach(function (i) {
        if (!i) return;
        var f = window.getItemFolder ? window.getItemFolder(i) : "";
        if (f === folder && (i.status === 'PAUSED' || i.status === 'PAUSED')) {
          idsToResume.push(i);
        }
      });
      for (var r = 0; r < idsToResume.length; r++) {
        var ri = idsToResume[r];
        if (window.LanvanStore) {
          window.LanvanStore.dispatch('UPDATE_UPLOAD_STATUS', { id: ri.id, status: 'UPLOADING' });
        }
        if (typeof window.uploadLargeFileChunked === 'function') {
          window.uploadLargeFileChunked(ri);
        }
      }
    } else if (item.status === 'PAUSED' || item.status === 'PAUSED') {
      if (window.LanvanStore) {
        window.LanvanStore.dispatch('UPDATE_UPLOAD_STATUS', { id: uploadId, status: 'UPLOADING' });
      }
      if (typeof window.uploadLargeFileChunked === 'function') {
        window.uploadLargeFileChunked(item);
      }
    }

    if (typeof window.triggerInstantUIUpdate === 'function') {
      window.triggerInstantUIUpdate();
    }
  }

  function cancelUploadItem(uploadId) {
    var item = getQueueItem(uploadId);
    if (!item) return;

    if (item.xhr) { try { item.xhr.abort(); } catch (e) { } }

    var fileName = window.getItemName ? window.getItemName(item) : "";
    var targetDir = window.getItemFolder ? window.getItemFolder(item) : "";
    if (fileName && fileName !== 'Unknown') {
      var formData = new FormData();
      formData.append("filename", fileName);
      if (targetDir) formData.append("parent_path", targetDir);
      fetch("/api/cancel-upload", { method: "POST", body: formData }).catch(function () { });
    }

    // Dispatch through Store — single source of truth for queue mutations.
    // Store validates transition, removes from queue, increments generation.
    if (window.LanvanStore) {
      window.LanvanStore.dispatch('CANCEL_UPLOAD', { id: uploadId });
    }

    if (typeof window.triggerInstantUIUpdate === 'function') {
      window.triggerInstantUIUpdate();
    }
  }

  // Export module API
  window.LanvanUploadEngine = {
    getQueueItem: getQueueItem,
    pauseUploadItem: pauseUploadItem,
    resumeUploadItem: resumeUploadItem,
    cancelUploadItem: cancelUploadItem
  };

})(typeof window !== 'undefined' ? window : this);
