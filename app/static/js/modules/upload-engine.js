/**
 * Lanvan Upload Transfer Engine Module (upload-engine.js)
 * Manages window.uploadQueue single source of truth, chunking, pause/resume/cancel transitions.
 */

(function (window) {
  'use strict';

  // Authoritative State Repository
  if (!window.uploadQueue && window.LanvanStore) {
    window.uploadQueue = window.LanvanStore.getState().uploadQueue;
  }

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
      window.uploadQueue.forEach(function (i) {
        if (!i) return;
        var f = window.getItemFolder ? window.getItemFolder(i) : "";
        if (f === folder && (i.status === 'uploading' || i.status === 'queued')) {
          i.status = 'paused';
          if (i.xhr) { try { i.xhr.abort(); } catch (e) { } }
        }
      });
    } else if (item.status === 'uploading' || item.status === 'queued') {
      item.status = 'paused';
      if (item.xhr) { try { item.xhr.abort(); } catch (e) { } }
    }

  }

  function resumeUploadItem(uploadId) {
    var item = getQueueItem(uploadId);
    if (!item) return;

    var folder = window.getItemFolder ? window.getItemFolder(item) : "";
    if (folder) {
      window.uploadQueue.forEach(function (i) {
        if (!i) return;
        var f = window.getItemFolder ? window.getItemFolder(i) : "";
        if (f === folder && i.status === 'paused') {
          i.status = 'uploading';
          if (typeof window.uploadLargeFileChunked === 'function') {
            window.uploadLargeFileChunked(i);
          }
        }
      });
    } else if (item.status === 'paused') {
      item.status = 'uploading';
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

    item.status = 'cancelled';
    item.error = 'Cancelled by user';

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
