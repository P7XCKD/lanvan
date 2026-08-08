/**
 * Lanvan File List View Module (file-list-view.js)
 * Manages file list rendering (#nasFileList), subfolder synthesis, and row progress updates.
 */

(function (window) {
  'use strict';

  function updateRowProgress(row, item) {
    if (!row || !item) return;
    var progress = Math.round(window.getItemProgress ? window.getItemProgress(item) : (item.progress || 0));
    var subtitleCell = row.querySelector('.item-subtitle');
    if (subtitleCell) {
      subtitleCell.textContent = progress + "% • " + (item.status === 'PAUSED' ? 'Paused' : 'Uploading');
    }
    var dateCell = row.querySelector('.item-date');
    if (dateCell) {
      dateCell.textContent = item.status === 'PAUSED' ? 'Paused' : 'Uploading';
    }
    var bar = row.querySelector('.row-progress-bar');
    if (bar) {
      bar.style.transform = "scaleX(" + (progress / 100) + ")";
    }
  }

  // Export module API
  window.LanvanFileListView = {
    updateRowProgress: updateRowProgress
  };

})(typeof window !== 'undefined' ? window : this);
