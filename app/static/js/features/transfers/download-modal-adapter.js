/**
 * @file download-modal-adapter.js
 * @description Download options modal dialog controller for Lanvan.
 *              Manages modal presentation for batch ZIP download and individual file downloads.
 * @module DownloadModalAdapter
 */

(function (window) {
  'use strict';

  /**
   * Close and cleanup the download options modal
   */
  function closeDownloadModal() {
    var modal = window.currentDownloadModal;
    if (modal) {
      modal.remove();
      window.currentDownloadModal = null;
    }
  }

  /**
   * Trigger batch ZIP download for all files
   */
  function downloadAsZip() {
    closeDownloadModal();
    if (typeof window.showToast === 'function') {
      window.showToast(' Preparing ZIP download...', 3000);
    }
    window.location.href = '/download-all';
  }

  /**
   * Trigger individual sequential file downloads with completion polling
   */
  async function downloadIndividually() {
    closeDownloadModal();

    try {
      var fileCards = document.querySelectorAll('.file-card .file-name');
      var fileNames = Array.prototype.slice.call(fileCards).map(function (card) {
        return card.textContent.trim();
      });

      if (fileNames.length === 0) {
        if (typeof window.showToast === 'function') {
          window.showToast(' No files found to download', 3000);
        }
        return;
      }

      if (typeof window.showToast === 'function') {
        window.showToast(' Starting intelligent sequential download of ' + fileNames.length + ' files...', 0);
      }

      var downloadCount = 0;
      var failedDownloads = [];

      function waitForDownloadCompletion(fileName, timeoutMs) {
        var limit = typeof timeoutMs === 'number' ? timeoutMs : 15000;
        return new Promise(function (resolve) {
          var startTime = Date.now();
          var resolved = false;
          var visibilityHandler, blurHandler, focusHandler;

          var cleanup = function () {
            if (visibilityHandler) document.removeEventListener('visibilitychange', visibilityHandler);
            if (blurHandler) window.removeEventListener('blur', blurHandler);
            if (focusHandler) window.removeEventListener('focus', focusHandler);
          };

          var resolveOnce = function (method) {
            if (!resolved) {
              resolved = true;
              cleanup();
              resolve(method);
            }
          };

          if (navigator.userAgent.includes('Chrome') || navigator.userAgent.includes('Edge')) {
            visibilityHandler = function () {
              if (!resolved && Date.now() - startTime > 300) {
                resolveOnce('visibility-change');
              }
            };
            document.addEventListener('visibilitychange', visibilityHandler);
          }

          var focusLost = false;
          blurHandler = function () { focusLost = true; };
          focusHandler = function () {
            if (focusLost && !resolved && Date.now() - startTime > 200) {
              resolveOnce('focus-detection');
            }
          };
          window.addEventListener('blur', blurHandler);
          window.addEventListener('focus', focusHandler);

          var adaptiveTimeout = Math.max(800, Math.min(3000, fileNames.length * 400));
          setTimeout(function () {
            resolveOnce('adaptive-timeout');
          }, adaptiveTimeout);

          setTimeout(function () {
            resolveOnce('fallback-timeout');
          }, limit);
        });
      }

      for (var i = 0; i < fileNames.length; i++) {
        try {
          var fileName = fileNames[i];
          if (typeof window.updateToastContent === 'function') {
            window.updateToastContent(' Downloading ' + fileName + '... (' + (downloadCount + 1) + '/' + fileNames.length + ')');
          }

          var link = document.createElement('a');
          link.href = '/download/' + encodeURIComponent(fileName);
          link.download = fileName;
          link.style.display = 'none';
          document.body.appendChild(link);

          var downloadStartTime = Date.now();
          link.click();
          document.body.removeChild(link);

          if (typeof window.updateToastContent === 'function') {
            window.updateToastContent(' ' + fileName + ' downloading... waiting for completion (' + (downloadCount + 1) + '/' + fileNames.length + ')');
          }

          var completionMethod = await waitForDownloadCompletion(fileName);
          var downloadTime = ((Date.now() - downloadStartTime) / 1000).toFixed(1);

          downloadCount++;

          if (window.DEBUG_MODE) {
            console.log(' Download ' + downloadCount + ': ' + fileName + ' completed via ' + completionMethod + ' in ' + downloadTime + 's');
          }

          if (typeof window.updateToastContent === 'function') {
            window.updateToastContent(' ' + fileName + ' completed (' + downloadCount + '/' + fileNames.length + ') • ' + downloadTime + 's');
          }

          if (i < fileNames.length - 1) {
            await new Promise(function (resolve) { setTimeout(resolve, 200); });
          }
        } catch (error) {
          console.error('Failed to download ' + fileNames[i] + ':', error);
          failedDownloads.push(fileNames[i]);
        }
      }

      if (failedDownloads.length === 0) {
        if (typeof window.showToast === 'function') {
          window.showToast(' Successfully downloaded all ' + downloadCount + ' files!', 5000);
        }
      } else {
        if (typeof window.showToast === 'function') {
          window.showToast(' Downloaded ' + downloadCount + ' files. Failed: ' + failedDownloads.length + ' (' + failedDownloads.join(', ') + ')', 8000);
        }
      }
    } catch (error) {
      console.error('Individual download error:', error);
      if (typeof window.showToast === 'function') {
        window.showToast(' Error during individual downloads', 5000);
      }
    }
  }

  /**
   * Display download options modal dialog
   * @param {Event} event 
   */
  function showDownloadOptions(event) {
    if (event && typeof event.preventDefault === 'function') {
      event.preventDefault();
    }

    var modal = document.createElement('div');
    modal.style.cssText = 'position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.5); display: flex; justify-content: center; align-items: center; z-index: 10000;';

    var dialog = document.createElement('div');
    dialog.style.cssText = 'background: var(--section-bg); color: var(--text-color); border: 1px solid var(--border-color); border-radius: 15px; padding: 2rem; max-width: 500px; margin: 1rem; box-shadow: 0 10px 30px rgba(0,0,0,0.3); text-align: center;';

    var zipOnClick = typeof window.downloadAsZip === 'function' ? 'onclick="downloadAsZip()"' : 'onclick="if(typeof window.DownloadModalAdapter===\'object\')window.DownloadModalAdapter.downloadAsZip();"';
    var indOnClick = typeof window.downloadIndividually === 'function' ? 'onclick="downloadIndividually()"' : 'onclick="if(typeof window.DownloadModalAdapter===\'object\')window.DownloadModalAdapter.downloadIndividually();"';
    var closeOnClick = typeof window.closeDownloadModal === 'function' ? 'onclick="closeDownloadModal()"' : 'onclick="if(window.currentDownloadModal)window.currentDownloadModal.remove();"';

    dialog.innerHTML = [
      '<h3 style="margin-top: 0; color: var(--text-color);">Choose Download Method</h3>',
      '<p style="color: var(--text-color); opacity: 0.7; margin-bottom: 2rem;">How would you like to download all files?</p>',
      '<div style="display: flex; gap: 1rem; justify-content: center; flex-wrap: wrap;">',
      '  <button ' + zipOnClick + ' style="background: #4a90e2; color: white; border: none; padding: 1rem 1.5rem; border-radius: 8px; cursor: pointer; font-size: 1rem; min-width: 180px;">',
      '     Download as ZIP<br><small style="opacity: 0.8;">Single compressed file</small>',
      '  </button>',
      '  <button ' + indOnClick + ' style="background: #27ae60; color: white; border: none; padding: 1rem 1.5rem; border-radius: 8px; cursor: pointer; font-size: 1rem; min-width: 180px;">',
      '     Download Separately<br><small style="opacity: 0.8;">Individual files</small>',
      '  </button>',
      '</div>',
      '<button ' + closeOnClick + ' style="background: #e74c3c; color: white; border: none; padding: 0.5rem 1rem; border-radius: 5px; cursor: pointer; margin-top: 1.5rem; font-size: 0.9rem;">Cancel</button>'
    ].join('\n');

    modal.appendChild(dialog);
    document.body.appendChild(modal);

    window.currentDownloadModal = modal;

    modal.addEventListener('click', function (e) {
      if (e.target === modal) {
        closeDownloadModal();
      }
    });

    document.addEventListener('keydown', function escapeHandler(e) {
      if (e.key === 'Escape') {
        closeDownloadModal();
        document.removeEventListener('keydown', escapeHandler);
      }
    });
  }

  const DownloadModalAdapter = Object.freeze({
    showDownloadOptions: showDownloadOptions,
    downloadAsZip: downloadAsZip,
    downloadIndividually: downloadIndividually,
    closeDownloadModal: closeDownloadModal
  });

  window.DownloadModalAdapter = DownloadModalAdapter;
  window.showDownloadOptions = showDownloadOptions;
  window.downloadAsZip = downloadAsZip;
  window.downloadIndividually = downloadIndividually;
  window.closeDownloadModal = closeDownloadModal;

})(window);
