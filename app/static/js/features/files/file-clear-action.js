/**
 * @file file-clear-action.js
 * @description Encapsulates clearAllFiles action endpoint request and view update.
 * @module FileClearAction
 */

(function () {
  'use strict';

  /**
   * Clears all files via POST /clear endpoint.
   */
  async function clearAllFiles() {
    try {
      console.log(' Clearing all files...');

      const response = await fetch('/clear', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        }
      });

      if (response.ok) {
        // Update file display immediately
        if (typeof window.updateFileDisplay === 'function') {
          window.updateFileDisplay([]);
        }
        if (typeof window.showToast === 'function') {
          window.showToast(' All files cleared successfully!', 3000);
        }
        console.log(' Files cleared successfully');
      } else {
        throw new Error(`HTTP ${response.status}`);
      }
    } catch (error) {
      console.error(' Failed to clear files:', error);
      if (typeof window.showToast === 'function') {
        window.showToast(' Failed to clear files. Please try again.', 5000);
      }
    }
  }

  // Expose namespace & global API
  window.FileClearAction = {
    clearAllFiles: clearAllFiles
  };

  window.clearAllFiles = clearAllFiles;
})();
