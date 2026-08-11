/**
 * @file auto-refresh-controller.js
 * @description Auto-Refresh Polling Controller for Lanvan.
 *              Manages cross-device file synchronization polling, upload-pause triggers,
 *              and visibility state handling.
 * @module AutoRefreshController
 */

(function (window) {
  'use strict';

  var autoRefreshInterval = null;
  var lastFileCount = 0;
  var autoRefreshActive = true;

  /**
   * Start auto-refresh polling for cross-device file sync
   */
  function startAutoRefresh() {
    if (window.DEBUG_MODE) console.log('Starting auto-refresh for cross-device file sync...');

    // Initial file count setup
    var fileGrid = document.querySelector('.file-grid');
    if (fileGrid) {
      lastFileCount = fileGrid.querySelectorAll('.file-card').length;
    }

    // Immediate file count refresh to ensure accuracy
    if (typeof window.refreshFileCountOnly === 'function') {
      window.refreshFileCountOnly();
    }

    // Ensure any existing interval is cleared before starting a new one
    if (autoRefreshInterval) {
      clearInterval(autoRefreshInterval);
      autoRefreshInterval = null;
    }

    // Set up polling every 5 seconds to check for file changes
    autoRefreshInterval = setInterval(async function () {
      if (!autoRefreshActive || document.hidden) return;

      // Only refresh files when file section is active, not when in clipboard mode
      var currentSection = window.currentActiveSection || 'file';
      if (currentSection !== 'file') {
        if (window.DEBUG_MODE) console.log('Skipping file refresh - clipboard section is active');
        return;
      }

      // Skip auto-refresh file count comparison while active uploads are transferring
      var queue = Array.isArray(window.uploadQueue) ? window.uploadQueue : [];
      var hasActiveUploads = queue.some(function (i) {
        return i && (i.status === 'UPLOADING' || i.status === 'QUEUED' || i.status === 'PROCESSING');
      });
      if (hasActiveUploads) {
        return;
      }

      try {
        if (typeof window.getCurrentFileListEndpoint !== 'function') return;
        var endpoint = window.getCurrentFileListEndpoint();
        var response = await fetch(endpoint);
        if (!response.ok) return;

        var data = await response.json();
        var files = data.files || [];
        var currentFileCount = files.length;

        // Only update if file count changed (indicating new uploads/deletions)
        if (currentFileCount !== lastFileCount) {
          if (window.DEBUG_MODE) console.log('File count changed: ' + lastFileCount + ' → ' + currentFileCount + ', auto-loading...');
          // Route through canonical pipeline: API → Repository → Scheduler → Projection → Renderer
          if (typeof window.refreshFileList === 'function') {
            window.refreshFileList('auto_refresh');
          }

          if (currentFileCount > lastFileCount) {
            if (window.DEBUG_MODE) console.log((currentFileCount - lastFileCount) + ' new file(s) auto-loaded from other device(s)');
          } else if (currentFileCount < lastFileCount) {
            if (window.DEBUG_MODE) console.log((lastFileCount - currentFileCount) + ' file(s) removed from other device(s)');
          }
        } else {
          // Even if file count is same, ensure display is current
          if (typeof window.updateFileCount === 'function') {
            window.updateFileCount(currentFileCount);
          }
        }
      } catch (error) {
        console.error('Auto-refresh failed:', error);
      }
    }, 5000);
  }

  /**
   * Stop auto-refresh polling completely
   */
  function stopAutoRefresh() {
    autoRefreshActive = false;
    if (autoRefreshInterval) {
      clearInterval(autoRefreshInterval);
      autoRefreshInterval = null;
      if (window.DEBUG_MODE) console.log('Auto-refresh stopped');
    }
  }

  /**
   * Pause auto-refresh polling temporarily
   */
  function pauseAutoRefresh() {
    autoRefreshActive = false;
    if (window.DEBUG_MODE) console.log('⏸ Auto-refresh paused');
  }

  /**
   * Resume auto-refresh polling
   */
  function resumeAutoRefresh() {
    autoRefreshActive = true;
    if (window.DEBUG_MODE) console.log('▶ Auto-refresh resumed');
  }

  /**
   * Pause auto-refresh when user starts an upload
   */
  function handleUploadStart() {
    pauseAutoRefresh();
  }

  /**
   * Resume auto-refresh when all uploads complete (after a 2s safety delay)
   */
  function handleUploadEnd() {
    var queue = Array.isArray(window.uploadQueue) ? window.uploadQueue : [];
    var hasUploadsInProgress = queue.some(function (item) {
      return item && ['UPLOADING', 'QUEUED', 'PAUSED'].includes(item.status);
    });
    if (hasUploadsInProgress) {
      if (window.DEBUG_MODE) console.log('Skipping auto-refresh resume: paused or active uploads exist in queue');
      return;
    }

    setTimeout(function () {
      var currentQueue = Array.isArray(window.uploadQueue) ? window.uploadQueue : [];
      var hasUploadsInProgress2 = currentQueue.some(function (item) {
        return item && ['UPLOADING', 'QUEUED', 'PAUSED'].includes(item.status);
      });
      if (!hasUploadsInProgress2) {
        resumeAutoRefresh();
      }
    }, 2000);
  }

  const AutoRefreshController = Object.freeze({
    startAutoRefresh: startAutoRefresh,
    stopAutoRefresh: stopAutoRefresh,
    pauseAutoRefresh: pauseAutoRefresh,
    resumeAutoRefresh: resumeAutoRefresh,
    handleUploadStart: handleUploadStart,
    handleUploadEnd: handleUploadEnd
  });

  window.AutoRefreshController = AutoRefreshController;
  window.startAutoRefresh = startAutoRefresh;
  window.stopAutoRefresh = stopAutoRefresh;
  window.pauseAutoRefresh = pauseAutoRefresh;
  window.resumeAutoRefresh = resumeAutoRefresh;
  window.handleUploadStart = handleUploadStart;
  window.handleUploadEnd = handleUploadEnd;

})(window);
