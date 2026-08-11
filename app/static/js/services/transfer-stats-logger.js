/**
 * @file transfer-stats-logger.js
 * @description Transfer Statistics and File Metadata Logging Service for Lanvan.
 * @module TransferStatsLogger
 */

(function (window) {
  'use strict';

  /**
   * File Metadata Storage
   * @param {Array<File>} files 
   * @param {number} totalSize 
   */
  function storeFileMetadata(files, totalSize) {
    if (!files || !files.length) return;
    try {
      var metadata = JSON.parse(localStorage.getItem('fileMetadata') || '{}');
      var timestamp = Date.now();

      for (var i = 0; i < files.length; i++) {
        var file = files[i];
        if (file && file.name) {
          metadata[file.name] = {
            size: file.size || 0,
            timestamp: timestamp,
            lastModified: file.lastModified || timestamp,
            type: file.type || 'unknown'
          };
        }
      }

      localStorage.setItem('fileMetadata', JSON.stringify(metadata));
      if (window.DEBUG_MODE) console.log('Stored metadata for ' + files.length + ' files');
    } catch (e) {
      console.log('Failed to store file metadata:', e);
    }
  }

  /**
   * Transfer Statistics Logging - Device-Specific Session Storage
   * @param {Object} stats 
   */
  function saveStatsToLog(stats) {
    if (!stats) return;
    try {
      // Save to device-specific session storage (clears when session ends)
      if (typeof window.saveToDeviceUploadHistory === 'function') {
        window.saveToDeviceUploadHistory(stats);
      }

      // Maintain backward compatibility with localStorage for global stats
      var logs = JSON.parse(localStorage.getItem('transferLogs') || '[]');
      logs.unshift(stats);

      // Keep only last 50 logs in global storage
      if (logs.length > 50) {
        logs.splice(50);
      }

      localStorage.setItem('transferLogs', JSON.stringify(logs));
      if (window.DEBUG_MODE) console.log('Saved transfer stats to device session:', stats.type, stats.size, stats.time);
    } catch (e) {
      console.log('Failed to save transfer stats:', e);
    }
  }

  const TransferStatsLogger = Object.freeze({
    storeFileMetadata: storeFileMetadata,
    saveStatsToLog: saveStatsToLog
  });

  window.TransferStatsLogger = TransferStatsLogger;
  window.storeFileMetadata = storeFileMetadata;
  window.saveStatsToLog = saveStatsToLog;

})(window);
