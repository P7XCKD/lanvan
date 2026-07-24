/**
 * Defensive Data Contract Helpers for Lanvan Upload System
 * Standardized getters to prevent TypeError exceptions across data sources.
 */

(function (window) {
  'use strict';

  function getItemSize(item) {
    if (!item) return 0;
    if (typeof item.fileSize === 'number' && !isNaN(item.fileSize)) {
      return item.fileSize;
    }
    if (item.file && typeof item.file.size === 'number' && !isNaN(item.file.size)) {
      return item.file.size;
    }
    if (typeof item.size === 'number' && !isNaN(item.size)) {
      return item.size;
    }
    return 0;
  }

  function getItemName(item) {
    if (!item) return 'Unknown';
    if (item.fileName && typeof item.fileName === 'string') {
      return item.fileName;
    }
    if (item.file && item.file.name && typeof item.file.name === 'string') {
      return item.file.name;
    }
    if (item.name && typeof item.name === 'string') {
      return item.name;
    }
    return 'Unknown';
  }

  function getItemProgress(item) {
    if (!item || typeof item.progress !== 'number' || isNaN(item.progress)) {
      return 0;
    }
    return Math.min(100, Math.max(0, item.progress));
  }

  function getItemFolder(item) {
    if (!item) return '';
    var folder = item.targetDir || item.parent_path || item.folder || '';
    if (folder === 'Home' || folder === 'Home/') {
      return '';
    }
    return folder;
  }

  // Export helpers globally
  window.getItemSize = getItemSize;
  window.getItemName = getItemName;
  window.getItemProgress = getItemProgress;
  window.getItemFolder = getItemFolder;

})(typeof window !== 'undefined' ? window : this);
