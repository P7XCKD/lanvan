/**
 * @file clipboard-paste-modal.js
 * @description Clipboard Modal presentation controller and image/text paste event receiver for Lanvan.
 * @module ClipboardPasteModal
 */

(function (window) {
  'use strict';

  /**
   * Open clipboard modal dialog and set focus to input
   */
  function openClipboardModal() {
    var modal = document.getElementById('clipboardModal');
    if (!modal) return;
    modal.style.display = 'flex';

    if (typeof window.refreshClipboardHistory === 'function') {
      window.refreshClipboardHistory();
    }

    setTimeout(function () {
      var textInput = document.getElementById('clipboardTextInput');
      if (textInput) textInput.focus();
    }, 100);

    document.addEventListener('keydown', function escapeHandler(e) {
      if (e.key === 'Escape') {
        closeClipboardModal();
        document.removeEventListener('keydown', escapeHandler);
      }
    });

    modal.addEventListener('click', function (e) {
      if (e.target === modal) {
        closeClipboardModal();
      }
    });

    if (window.DEBUG_MODE) console.log('Clipboard modal opened');
  }

  /**
   * Close clipboard modal dialog
   */
  function closeClipboardModal() {
    var modal = document.getElementById('clipboardModal');
    if (modal) modal.style.display = 'none';
  }

  /**
   * Handle paste events in text area or input fields
   * @param {ClipboardEvent} event 
   */
  function handleClipboardPaste(event) {
    if (window.DEBUG_MODE) console.log('Paste event detected');

    var clipboardData = event.clipboardData || window.clipboardData;
    if (!clipboardData) {
      if (window.DEBUG_MODE) console.log('No clipboard data available');
      return;
    }

    var files = clipboardData.files;
    if (files && files.length > 0) {
      if (window.DEBUG_MODE) console.log('Files detected in clipboard:', files.length);
      event.preventDefault();

      Array.prototype.slice.call(files).forEach(function (file) {
        if (file.type && file.type.startsWith('image/')) {
          if (window.DEBUG_MODE) console.log('Image file detected:', file.type);
          handleImagePaste(file);
        } else {
          if (window.DEBUG_MODE) console.log('Non-image file detected:', file.type);
          if (typeof window.showToast === 'function') {
            window.showToast('File detected, but only images are supported', 3000);
          }
        }
      });
      return;
    }

    var items = clipboardData.items;
    if (items) {
      for (var i = 0; i < items.length; i++) {
        var item = items[i];
        if (window.DEBUG_MODE) console.log('Clipboard item type:', item.type);

        if (item.type && item.type.indexOf('image') !== -1) {
          event.preventDefault();
          var blob = item.getAsFile();
          if (blob) {
            if (window.DEBUG_MODE) console.log('Image blob detected from clipboard items');
            handleImagePaste(blob);
            return;
          }
        }
      }
    }

    var textData = clipboardData.getData('text/plain');
    if (textData && window.DEBUG_MODE) {
      console.log('Text data detected, length:', textData.length);
    }
  }

  /**
   * Handle image paste from clipboard (uploads blob to /api/clipboard/add)
   * @param {Blob|File} blob 
   */
  function handleImagePaste(blob) {
    if (!blob) return;
    if (window.DEBUG_MODE) console.log('Image pasted from clipboard, size:', blob.size);
    if (typeof window.showToast === 'function') {
      window.showToast(' Processing pasted image...', 2000);
    }

    var timestamp = new Date().toISOString().replace(/[:.]/g, '-');
    var filename = 'clipboard-image-' + timestamp + '.png';

    var formData = new FormData();
    formData.append('file', blob, filename);

    fetch('/api/clipboard/add', {
      method: 'POST',
      body: formData
    })
      .then(function (response) { return response.json(); })
      .then(function (data) {
        if (data.status === 'success') {
          if (typeof window.showToast === 'function') {
            window.showToast(' Image added to clipboard: ' + filename, 3000);
          }
          if (typeof window.refreshClipboardHistory === 'function') {
            window.refreshClipboardHistory();
          }
        } else {
          if (typeof window.showToast === 'function') {
            window.showToast(' Failed to add image: ' + (data.msg || 'Unknown error'), 4000);
          }
        }
      })
      .catch(function (error) {
        console.error('Error adding image to clipboard:', error);
        if (typeof window.showToast === 'function') {
          window.showToast(' Failed to add image to clipboard', 4000);
        }
      });
  }

  // Global document paste listener for Clipboard view (Industry Standard Event Propagation Marking)
  document.addEventListener('paste', function (event) {
    if (event.defaultPrevented || event._handled) {
      return;
    }

    var activeEl = document.activeElement;
    var isClipInput = activeEl && (activeEl.id === 'clipboardInput' || activeEl.id === 'clipboardTextInput');
    var isClipView = window.activeTab === 'clipboard' || (document.getElementById('clipboardView') && document.getElementById('clipboardView').style.display !== 'none');

    if (isClipInput || isClipView) {
      var clipboardData = event.clipboardData || window.clipboardData;
      if (!clipboardData) return;

      var targetImage = null;

      if (clipboardData.files && clipboardData.files.length > 0) {
        for (var i = 0; i < clipboardData.files.length; i++) {
          if (clipboardData.files[i].type && clipboardData.files[i].type.startsWith('image/')) {
            targetImage = clipboardData.files[i];
            break;
          }
        }
      }

      if (!targetImage && clipboardData.items) {
        for (var j = 0; j < clipboardData.items.length; j++) {
          var item = clipboardData.items[j];
          if (item.type && item.type.startsWith('image/')) {
            var blob = item.getAsFile();
            if (blob) {
              targetImage = blob;
              break;
            }
          }
        }
      }

      if (targetImage) {
        event._handled = true;
        event.preventDefault();
        if (typeof event.stopImmediatePropagation === 'function') {
          event.stopImmediatePropagation();
        }
        handleImagePaste(targetImage);
      }
    }
  }, true);

  const ClipboardPasteModal = Object.freeze({
    openClipboardModal: openClipboardModal,
    closeClipboardModal: closeClipboardModal,
    handleClipboardPaste: handleClipboardPaste,
    handleImagePaste: handleImagePaste
  });

  window.ClipboardPasteModal = ClipboardPasteModal;
  window.openClipboardModal = openClipboardModal;
  window.closeClipboardModal = closeClipboardModal;
  window.handleClipboardPaste = handleClipboardPaste;
  window.handleImagePaste = handleImagePaste;

})(window);
