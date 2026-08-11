/**
 * @file file-summary-counter.js
 * @description Header File Summary Counter display resolver and endpoint helper for Lanvan.
 * @module FileSummaryCounter
 */

(function (window) {
  'use strict';

  /**
   * Dedicated function to update file count display in UI (#fileCount)
   * @param {number} fileCount 
   */
  function updateFileCount(fileCount) {
    var fileCountEl = document.getElementById('fileCount');
    if (fileCountEl) {
      if (fileCount > 0) {
        fileCountEl.textContent = '(' + fileCount + ' file' + (fileCount === 1 ? '' : 's') + ')';
      } else {
        fileCountEl.textContent = '';
      }
    }
    if (window.DEBUG_MODE) console.log('File count updated: ' + fileCount + ' files');
  }

  /**
   * Helper to build the correct file listing endpoint for the current folder
   * @returns {string} Endpoint URL
   */
  function getCurrentFileListEndpoint() {
    var rawFolder = (typeof window.getCurrentFolderPath === 'function')
      ? window.getCurrentFolderPath()
      : (window.currentFolderPath || '');
    var folder = (rawFolder === 'Home' || rawFolder === 'Home/') ? '' : rawFolder;
    if (folder) {
      return '/api/folders/' + encodeURIComponent(folder) + '/files';
    }
    return '/api/files';
  }

  /**
   * Refresh only the file count from server without re-rendering the full display
   */
  async function refreshFileCountOnly() {
    try {
      var response = await fetch(getCurrentFileListEndpoint());
      if (!response.ok) {
        console.warn('Failed to refresh file count: HTTP ' + response.status);
        return;
      }

      var data = await response.json();
      var count = data.files_data ? data.files_data.length : (data.files ? data.files.length : 0);
      updateFileCount(count);
      if (typeof window.lastFileCount !== 'undefined') {
        window.lastFileCount = count;
      }

      if (window.DEBUG_MODE) console.log('File count refreshed: ' + count + ' files');
    } catch (error) {
      console.error('Failed to refresh file count:', error);
    }
  }

  const FileSummaryCounter = Object.freeze({
    updateFileCount: updateFileCount,
    getCurrentFileListEndpoint: getCurrentFileListEndpoint,
    refreshFileCountOnly: refreshFileCountOnly
  });

  window.FileSummaryCounter = FileSummaryCounter;
  window.updateFileCount = updateFileCount;
  window.getCurrentFileListEndpoint = getCurrentFileListEndpoint;
  window.refreshFileCountOnly = refreshFileCountOnly;

})(window);
