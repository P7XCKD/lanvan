/**
 * @file file-staging-buffer.js
 * @description Input File Staging Buffer & Auto-Upload Dispatcher for Lanvan.
 *              Handles clearing file selection UI, displaying file selection summaries,
 *              and dispatching staged files to the core upload queue.
 * @module FileStagingBuffer
 */

(function (window) {
  'use strict';

  /**
   * Clear file selection UI inputs and preview areas
   */
  function clearFileSelection() {
    var domCache = window.DOM_CACHE || {};
    var fileInput = domCache.fileInput || document.getElementById('fileInput');
    var preview = domCache.preview || document.getElementById('preview');

    // Clear the file input (safe - doesn't affect active uploads)
    if (fileInput) {
      fileInput.value = '';
    }

    // Clear the preview area (safe - only affects UI)
    if (preview) {
      preview.innerHTML = '';
    }

    console.log(' File selection UI cleared (upload queue preserved)');
  }

  /**
   * Display summary for selected files and trigger auto-upload
   * @param {FileList|Array<File>} files 
   */
  function displaySelectedFiles(files) {
    if (!files) return;

    // For multiple files, show preview if updatePreview helper exists
    if (typeof window.updatePreview === 'function') {
      window.updatePreview(files);
    }

    // Show helpful message for multiple files
    var totalSize = Array.from(files).reduce(function (sum, file) {
      return sum + (file ? file.size || 0 : 0);
    }, 0);
    var totalSizeMB = (totalSize / 1024 / 1024).toFixed(1);

    if (typeof window.showToast === 'function') {
      window.showToast(' ' + files.length + ' files selected (' + totalSizeMB + ' MB total) - Auto-upload triggered', 3000);
    }

    // Actually trigger auto-upload
    autoUpload(files);
  }

  /**
   * Dispatch selected files to upload queue and trigger queue execution
   * @param {FileList|Array<File>} files 
   */
  function autoUpload(files) {
    console.log(' autoUpload called with files:', files ? files.length : 'no files', files);

    if (!files || !files.length) {
      console.log(' No files to upload');
      return;
    }

    // Deduplication: Check for rapid duplicate selections
    if (typeof window.shouldProcessFileSelection === 'function') {
      if (!window.shouldProcessFileSelection(files)) {
        return;
      }
    }

    // Perform periodic memory cleanup if available
    if (typeof window.performMemoryCleanup === 'function') {
      window.performMemoryCleanup();
    }

    var domCache = window.DOM_CACHE || {};
    var aesToggle = domCache.aesToggle || document.getElementById('enableEncryption');
    var isAESEnabled = aesToggle && aesToggle.checked;
    var isHTTPS = location.protocol === 'https:';

    console.log(' Upload settings:', { isAESEnabled: isAESEnabled, isHTTPS: isHTTPS });
    console.log(' AES enabled - streaming encryption supports any file size');

    if (isAESEnabled && !isHTTPS) {
      console.log(' AES over HTTP - HTTP-Safe mode provides security');
    }

    // Log current upload queue state before adding new files
    var queue = Array.isArray(window.uploadQueue) ? window.uploadQueue : [];
    var currentActiveUploads = queue.filter(function (item) {
      return item && item.status === 'UPLOADING';
    }).length;

    console.log(' Current upload state: ' + currentActiveUploads + ' active uploads, adding ' + files.length + ' new files');

    // Add files to upload manager
    if (typeof window.addToUploadQueue === 'function') {
      window.addToUploadQueue(Array.from(files));
    }

    // Clear the file input and preview after adding to queue
    clearFileSelection();

    // Start uploading new files if possible
    if (typeof window.startNextUpload === 'function') {
      window.startNextUpload();
    }

    // Show feedback to user about adding files to active queue
    if (typeof window.showToast === 'function') {
      if (currentActiveUploads > 0) {
        window.showToast(' Added ' + files.length + ' file(s) to upload queue. ' + currentActiveUploads + ' uploads currently active.', 3000);
      } else {
        var optimalConcurrency = (typeof window.getOptimalConcurrency === 'function')
          ? window.getOptimalConcurrency()
          : 2;
        var filesToStart = Math.min(optimalConcurrency, files.length);

        if (filesToStart > 1) {
          window.showToast(' Starting smart concurrent upload of ' + files.length + ' file(s) (' + filesToStart + ' concurrent)...', 3000);
        } else {
          window.showToast(' Starting upload of ' + files.length + ' file(s)...', 3000);
        }
      }
    }
  }

  const FileStagingBuffer = Object.freeze({
    clearFileSelection: clearFileSelection,
    displaySelectedFiles: displaySelectedFiles,
    autoUpload: autoUpload
  });

  window.FileStagingBuffer = FileStagingBuffer;
  window.clearFileSelection = clearFileSelection;
  window.displaySelectedFiles = displaySelectedFiles;
  window.autoUpload = autoUpload;

})(window);
