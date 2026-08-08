/**
 * Upload Engine
 *
 * Coordinates upload scheduling, queue item state transitions (pause,
 * resume, cancel), backend cancellation network cleanup, and UI synchronization.
 *
 * All state mutations flow through LanvanStore to maintain a single source
 * of truth across the unidirectional render pipeline.
 */

(function (window) {
  'use strict';

  /**
   * Retrieves an upload item record from the active upload queue by ID.
   *
   * @param {string} uploadId Unique identifier for the upload item.
   * @returns {Object|null} Upload queue item object or null if not found.
   */
  function getQueueItem(uploadId) {
    if (!window.uploadQueue) return null;
    return window.uploadQueue.find(function (item) {
      return item && item.id === uploadId;
    }) || null;
  }

  /**
   * Pauses an active upload transfer item or entire synthetic folder batch.
   *
   * @param {string} uploadId Unique identifier for the target upload item.
   */
  function pauseUploadItem(uploadId) {
    var item = getQueueItem(uploadId);
    if (!item) return;

    var folder = window.getItemFolder ? window.getItemFolder(item) : "";
    if (folder) {
      var idsToPause = [];
      window.uploadQueue.forEach(function (queueItem) {
        if (!queueItem) return;
        var itemFolder = window.getItemFolder ? window.getItemFolder(queueItem) : "";
        if (itemFolder === folder && (queueItem.status === 'UPLOADING' || queueItem.status === 'QUEUED')) {
          if (queueItem.xhr) { try { queueItem.xhr.abort(); } catch (abortErr) { } }
          idsToPause.push(queueItem.id);
        }
      });
      for (var p = 0; p < idsToPause.length; p++) {
        if (window.LanvanStore) {
          window.LanvanStore.dispatch('UPDATE_UPLOAD_STATUS', { id: idsToPause[p], status: 'PAUSED' });
        }
      }
    } else if (item.status === 'UPLOADING' || item.status === 'QUEUED') {
      if (item.xhr) { try { item.xhr.abort(); } catch (abortErr) { } }
      if (window.LanvanStore) {
        window.LanvanStore.dispatch('UPDATE_UPLOAD_STATUS', { id: uploadId, status: 'PAUSED' });
      }
    }
  }

  /**
   * Resumes a previously paused upload transfer item or entire synthetic folder batch.
   *
   * @param {string} uploadId Unique identifier for the target upload item.
   */
  function resumeUploadItem(uploadId) {
    var item = getQueueItem(uploadId);
    if (!item) return;

    var folder = window.getItemFolder ? window.getItemFolder(item) : "";
    if (folder) {
      var itemsToResume = [];
      window.uploadQueue.forEach(function (queueItem) {
        if (!queueItem) return;
        var itemFolder = window.getItemFolder ? window.getItemFolder(queueItem) : "";
        if (itemFolder === folder && queueItem.status === 'PAUSED') {
          itemsToResume.push(queueItem);
        }
      });
      for (var r = 0; r < itemsToResume.length; r++) {
        var resumeItem = itemsToResume[r];
        if (window.LanvanStore) {
          window.LanvanStore.dispatch('UPDATE_UPLOAD_STATUS', { id: resumeItem.id, status: 'UPLOADING' });
        }
        if (typeof window.uploadLargeFileChunked === 'function') {
          window.uploadLargeFileChunked(resumeItem);
        }
      }
    } else if (item.status === 'PAUSED') {
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

  /**
   * Cancels an upload transfer, aborting active HTTP requests and purging staging backend artifacts.
   *
   * @param {string} uploadId Unique identifier for the target upload item.
   */
  function cancelUploadItem(uploadId) {
    var item = getQueueItem(uploadId);
    if (!item) return;

    if (item.xhr) { try { item.xhr.abort(); } catch (abortErr) { } }

    var fileName = window.getItemName ? window.getItemName(item) : "";
    var targetDir = window.getItemFolder ? window.getItemFolder(item) : "";
    if (fileName && fileName !== 'Unknown') {
      var formData = new FormData();
      formData.append("filename", fileName);
      if (targetDir) formData.append("parent_path", targetDir);
      fetch("/api/cancel-upload", { method: "POST", body: formData }).catch(function () { });
    }

    // Dispatch cancellation through Store to remove item and update state generation
    if (window.LanvanStore) {
      window.LanvanStore.dispatch('CANCEL_UPLOAD', { id: uploadId });
    }

    if (typeof window.triggerInstantUIUpdate === 'function') {
      window.triggerInstantUIUpdate();
    }
  }

    // Expose public API on the global window object for procedural callers (cancel buttons, tray controls, etc.)
  window.LanvanUploadEngine = {
    getQueueItem: getQueueItem,
    pauseUploadItem: pauseUploadItem,
    resumeUploadItem: resumeUploadItem,
    cancelUploadItem: cancelUploadItem
  };

})(typeof window !== 'undefined' ? window : this);
