/**
 * @file clipboard-controller.js
 * @description Clipboard REST API controller and state management module for Lanvan.
 *              Handles text/image addition, retrieval, history rendering, and archive downloads.
 * @module ClipboardController
 */

(function (window) {
  'use strict';

  window.clipboardHistoryData = window.clipboardHistoryData || [];

  /**
   * Upload an image blob to clipboard storage.
   * @param {Blob} blob - Image blob data
   */
  function uploadImageToClipboard(blob) {
    const imageCount = getClipboardImageCount() + 1;
    const filename = `${imageCount}.png`;

    const formData = new FormData();
    formData.append('file', blob, filename);

    fetch('/api/clipboard/add', {
      method: 'POST',
      body: formData
    })
      .then(response => response.json())
      .then(data => {
        if (data.status === 'success') {
          if (typeof window.showToast === 'function') {
            window.showToast(` Image added to clipboard: ${filename}`, 3000);
          }
          refreshClipboardHistory();
        } else {
          if (typeof window.showToast === 'function') {
            window.showToast(` Failed to add image: ${data.msg}`, 4000);
          }
        }
      })
      .catch(error => {
        console.error('Error adding image to clipboard:', error);
        if (typeof window.showToast === 'function') {
          window.showToast(' Failed to add image to clipboard', 4000);
        }
      });
  }

  /**
   * Get total count of image items in clipboard.
   * @returns {number} Image item count.
   */
  function getClipboardImageCount() {
    const items = window.clipboardHistoryData || [];
    return items.filter(item => item && item.type === 'file' && item.content_type === 'image').length;
  }

  /**
   * Adds the entered text to clipboard history.
   */
  async function addTextToClipboard() {
    const textInput = document.getElementById('clipboardInput') || document.getElementById('clipboardTextInput');
    const addButton = document.querySelector('.clipboard-action-bar .m3-primary-btn') || document.getElementById('addTextToClipboardBtn');
    const text = textInput ? textInput.value : '';

    if (!text || !text.trim()) {
      if (typeof window.showToast === 'function') {
        window.showToast(' Please enter some text to add to clipboard', 3000);
      }
      if (textInput) textInput.focus();
      return;
    }

    if (addButton) {
      addButton.disabled = true;
      addButton.style.opacity = '0.7';
    }

    const formData = new FormData();
    formData.append('data', text);

    try {
      const response = await fetch('/api/clipboard/add', {
        method: 'POST',
        body: formData
      });
      const data = await response.json();

      if (data.status === 'success') {
        if (typeof window.showToast === 'function') {
          window.showToast(` Text added to clipboard (${data.item.size} bytes)`, 3000);
        }
        if (textInput) textInput.value = '';
        const prodInput = document.getElementById('clipboardTextInput');
        if (prodInput) prodInput.value = '';

        requestAnimationFrame(() => refreshClipboardHistory());
      } else {
        if (typeof window.showToast === 'function') {
          window.showToast(` Failed to add text: ${data.msg || data.message}`, 4000);
        }
      }
    } catch (error) {
      console.error('Error adding text to clipboard:', error);
      if (typeof window.showToast === 'function') {
        window.showToast(' Failed to add text to clipboard', 4000);
      }
    } finally {
      if (addButton) {
        addButton.disabled = false;
        addButton.style.opacity = '1';
      }
    }
  }

  /**
   * Clears the clipboard text input fields and displays a confirmation message.
   */
  function clearClipboardInput() {
    const textInput = document.getElementById('clipboardInput') || document.getElementById('clipboardTextInput');
    if (textInput) textInput.value = '';
    const prodInput = document.getElementById('clipboardTextInput');
    if (prodInput) prodInput.value = '';

    if (typeof window.showToast === 'function') {
      window.showToast(' Clipboard input cleared', 2000);
    }
  }

  /**
   * Refreshes the stored clipboard history and updates its rendered views.
   */
  async function refreshClipboardHistory() {
    try {
      const performRefresh = async () => {
        const response = await fetch('/api/clipboard/list');
        const data = await response.json();

        if (data.status === 'success') {
          window.clipboardHistoryData = data.items;
          requestAnimationFrame(() => renderClipboardHistory(data.items));
        } else {
          console.error('Failed to load clipboard history:', data.msg);
          if (typeof window.showToast === 'function') {
            window.showToast(' Failed to load clipboard history', 3000);
          }
        }
      };

      if (window.requestIdleCallback) {
        requestIdleCallback(performRefresh);
      } else {
        await performRefresh();
      }
    } catch (error) {
      console.error('Error loading clipboard history:', error);
      if (typeof window.showToast === 'function') {
        window.showToast(' Failed to load clipboard history', 3000);
      }
    }
  }

  /**
   * Renders clipboard history items in the available clipboard views.
   * @param {Array} items - Clipboard items to display.
   */
  function renderClipboardHistory(items) {
    window.clipboardHistoryData = items;

    if (typeof window.syncClipboardView === 'function') {
      window.syncClipboardView();
    }

    const legacyContainer = document.getElementById('clipboardHistoryContent');
    if (!legacyContainer) return;

    if (!items || !items.length) {
      legacyContainer.innerHTML = `
        <div style="text-align: center; color: var(--text-color); padding: 2rem;">
          <div>No clipboard items yet</div>
          <div style="font-size: 0.9rem; margin-top: 0.5rem;">Add content above to get started</div>
        </div>
      `;
      return;
    }

    legacyContainer.innerHTML = items.map(item => {
      const typeIcon = (typeof window.getClipboardItemIcon === 'function') ? window.getClipboardItemIcon(item) : '';
      const sizeText = (typeof window.formatClipboardSize === 'function')
        ? window.formatClipboardSize(item.size)
        : (item.size < 1024
          ? item.size + ' B'
          : item.size < 1024 * 1024
            ? (item.size / 1024).toFixed(1) + ' KB'
            : (item.size / (1024 * 1024)).toFixed(1) + ' MB');
      const isImage = item.type === 'file' && item.content_type === 'image';

      const imagePreview = isImage ? `
        <div style="margin: 0.5rem 0; text-align: center;">
          <img 
            src="/api/clipboard/get/${item.id}" 
            alt="${item.filename}"
            style="
              max-width: 200px; 
              max-height: 150px; 
              border-radius: 4px; 
              border: 1px solid var(--border-color);
              object-fit: cover;
              cursor: pointer;
            "
            onclick="showImagePreview('/api/clipboard/get/${item.id}', '${item.filename}')"
            title="Click to view full size"
          />
        </div>
      ` : '';

      return `
        <div style="
          background: var(--section-bg);
          border: 1px solid var(--border-color);
          border-radius: 8px;
          padding: 1rem;
          margin-bottom: 0.5rem;
          display: flex;
          justify-content: space-between;
          align-items: flex-start;
          gap: 1rem;
          color: var(--text-color);
        ">
          <div style="flex: 1;">
            <div style="display: flex; align-items: center; gap: 0.5rem; margin-bottom: 0.5rem;">
              <span style="font-size: 1.2rem;">${typeIcon}</span>
              <strong style="color: var(--text-color);">
                ${item.type === 'file' ? item.filename : `${item.content_type} content`}
              </strong>
              <span style="color: #888; font-size: 0.8rem;">(${sizeText})</span>
            </div>
            ${imagePreview}
            <div style="color: #aaa; font-size: 0.9rem; margin-bottom: 0.5rem;">
              ${isImage ? `Image dimensions and preview above` : item.preview}
            </div>
            <div style="color: #999; font-size: 0.8rem;">
              Added: ${item.timestamp}
            </div>
          </div>
          <div style="display: flex; flex-direction: column; gap: 0.3rem;">
            ${item.type === 'file' ? `
              <button onclick="downloadClipboardItem(${item.id})" style="
                background: #17a2b8;
                color: white;
                border: none;
                padding: 0.3rem 0.6rem;
                border-radius: 4px;
                cursor: pointer;
                font-size: 0.8rem;
              "> Download</button>
            ` : `
              <button onclick="copyClipboardText(${item.id})" style="
                background: #6c5ce7;
                color: white;
                border: none;
                padding: 0.3rem 0.6rem;
                border-radius: 4px;
                cursor: pointer;
                font-size: 0.8rem;
              "> Copy</button>
            `}
            <button onclick="removeClipboardItem(${item.id})" style="
              background: #dc3545;
              color: white;
              border: none;
              padding: 0.3rem 0.6rem;
              border-radius: 4px;
              cursor: pointer;
              font-size: 0.8rem;
            "> Remove</button>
          </div>
        </div>
      `;
    }).join('');
  }

  /**
   * Displays an image in the preview modal.
   * @param {string} imageSrc - Source URL of the image.
   * @param {string} filename - Filename shown in the modal and download control.
   */
  function showImagePreview(imageSrc, filename) {
    const modal = document.getElementById('previewModal');
    const titleEl = document.getElementById('previewTitle');
    const bodyEl = document.getElementById('previewBody');
    const dlBtn = document.getElementById('previewDownloadBtn');
    const streamBtn = document.getElementById('previewStreamBtn');

    if (modal && bodyEl) {
      const displayTitle = filename || 'Pasted Image';
      if (titleEl) titleEl.textContent = displayTitle;
      if (dlBtn) {
        dlBtn.href = imageSrc;
        dlBtn.download = displayTitle;
      }
      if (streamBtn) streamBtn.style.display = 'none';

      const safeTitle = typeof window.escapeHtml === 'function' ? window.escapeHtml(displayTitle) : displayTitle;
      bodyEl.innerHTML = `
        <div class="media-preview-container image-preview-wrapper" style="position:relative; width:100%; height:100%; min-height:70vh; flex:1; display:flex; align-items:center; justify-content:center; overflow:hidden;">
          <img id="lanvanZoomImage" class="media-preview-element" src="${imageSrc}" alt="${safeTitle}" style="max-width:90vw; max-height:84vh; width:auto; height:auto; object-fit:contain; border-radius:8px; display:block; margin:auto; box-shadow:0 16px 48px rgba(0,0,0,0.6); transition:transform 0.15s ease-out; cursor:grab;" />
        </div>
      `;

      modal.style.display = 'flex';
      modal.style.pointerEvents = 'auto';

      if (typeof window.setupImageZoomAndPan === 'function') {
        window.setupImageZoomAndPan();
      }
      if (typeof window.refreshLucideIcons === 'function') {
        window.refreshLucideIcons(bodyEl);
      }
    }
  }

  /**
   * Upload item from clipboard into file storage.
   * @param {number|string} itemId - Clipboard item ID
   */
  function uploadClipboardItem(itemId) {
    fetch(`/api/clipboard/upload/${itemId}`, {
      method: 'POST'
    })
      .then(response => response.json())
      .then(data => {
        if (data.status === 'success') {
          if (typeof window.showToast === 'function') {
            window.showToast(` Uploaded: ${data.filename}`, 3000);
          }
          if (typeof window.refreshFileList === 'function') {
            window.refreshFileList();
          }
        } else {
          if (typeof window.showToast === 'function') {
            window.showToast(` Upload failed: ${data.msg}`, 4000);
          }
        }
      })
      .catch(error => {
        console.error('Error uploading from clipboard:', error);
        if (typeof window.showToast === 'function') {
          window.showToast(' Failed to upload from clipboard', 4000);
        }
      });
  }

  /**
   * Downloads a clipboard item to the user's device.
   * @param {number|string} itemId - Clipboard item ID.
   */
  async function downloadClipboardItem(itemId) {
    try {
      const downloadUrl = `/api/clipboard/get/${itemId}?download=1`;
      const res = await fetch(downloadUrl);

      if (!res.ok) {
        if (typeof window.showToast === 'function') {
          window.showToast(' Failed to download clipboard item', 3000);
        }
        return;
      }

      let filename = `pasted-text-${itemId}.txt`;
      const disposition = res.headers.get('Content-Disposition');
      if (disposition && disposition.indexOf('filename=') !== -1) {
        const matches = new RegExp("filename[^;=\\n]*=((['\"]).*?\\2|[^;\\n]*)").exec(disposition);
        if (matches != null && matches[1]) {
          filename = matches[1].replace(/'/g, '').replace(/"/g, '');
        }
      }

      const blob = await res.blob();
      const blobUrl = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = blobUrl;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      setTimeout(() => {
        try { URL.revokeObjectURL(blobUrl); } catch (e) {}
      }, 1000);

      if (typeof window.showToast === 'function') {
        window.showToast(` Downloaded ${filename}`, 2000);
      }
    } catch (err) {
      console.error('Download error:', err);
      if (typeof window.showToast === 'function') {
        window.showToast(' Failed to download clipboard item', 3000);
      }
    }
  }

  /**
   * Copy clipboard text to system clipboard.
   * @param {number|string} itemId - Clipboard item ID
   */
  async function copyClipboardText(itemId) {
    try {
      const response = await fetch(`/api/clipboard/get/${itemId}`);
      const data = await response.json();

      if (data.status === 'success') {
        if (navigator.clipboard && window.isSecureContext) {
          await navigator.clipboard.writeText(data.item.data);
          if (typeof window.showToast === 'function') {
            window.showToast(' Copied to system clipboard', 2000);
          }
        } else {
          const textArea = document.createElement('textarea');
          textArea.value = data.item.data;
          textArea.style.position = 'fixed';
          textArea.style.top = '0';
          textArea.style.left = '0';
          textArea.style.width = '2em';
          textArea.style.height = '2em';
          textArea.style.padding = '0';
          textArea.style.border = 'none';
          textArea.style.outline = 'none';
          textArea.style.boxShadow = 'none';
          textArea.style.background = 'transparent';
          document.body.appendChild(textArea);
          textArea.focus();
          textArea.select();

          try {
            const successful = document.execCommand('copy');
            if (successful) {
              if (typeof window.showToast === 'function') {
                window.showToast(' Copied to system clipboard', 2000);
              }
            } else {
              if (typeof window.showToast === 'function') {
                window.showToast(' Failed to copy to system clipboard', 3000);
              }
            }
          } catch (err) {
            console.error('Fallback copy failed:', err);
            if (typeof window.showToast === 'function') {
              window.showToast(' Clipboard API not supported in this browser', 3000);
            }
          }

          document.body.removeChild(textArea);
        }
      } else {
        if (typeof window.showToast === 'function') {
          window.showToast(' Failed to copy to system clipboard', 3000);
        }
      }
    } catch (error) {
      console.error('Error copying clipboard text:', error);
      if (typeof window.showToast === 'function') {
        window.showToast(' Failed to copy to system clipboard', 3000);
      }
    }
  }

  /**
   * Removes a clipboard item from history.
   * @param {number|string} itemId - Identifier of the clipboard item to remove.
   */
  function removeClipboardItem(itemId) {
    fetch(`/api/clipboard/remove/${itemId}`, {
      method: 'DELETE'
    })
      .then(response => response.json())
      .then(data => {
        if (data.status === 'success') {
          if (typeof window.showToast === 'function') {
            window.showToast(' Clipboard item removed', 2000);
          }
          refreshClipboardHistory();
        } else {
          if (typeof window.showToast === 'function') {
            window.showToast(` Failed to remove item: ${data.msg}`, 3000);
          }
        }
      })
      .catch(error => {
        console.error('Error removing clipboard item:', error);
        if (typeof window.showToast === 'function') {
          window.showToast(' Failed to remove clipboard item', 3000);
        }
      });
  }

  /**
   * Downloads the available clipboard history as a ZIP archive.
   */
  async function downloadClipboardHistory() {
    try {
      const historyData = window.clipboardHistoryData || [];
      if (!historyData || historyData.length === 0) {
        if (typeof window.showToast === 'function') {
          window.showToast('No clipboard history to download', 3000);
        }
        return;
      }

      if (typeof window.showToast === 'function') {
        window.showToast('Downloading clipboard history ZIP archive...', 2000);
      }
      const itemIds = historyData.map(item => item.id);

      const response = await fetch('/api/clipboard/download-zip', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ item_ids: itemIds })
      });

      if (!response.ok) throw new Error('ZIP download failed');
      const blob = await response.blob();
      const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
      const filename = `Lanvan-clipboard-history-${timestamp}.zip`;
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);

      if (typeof window.showToast === 'function') {
        window.showToast(`ZIP file downloaded successfully (${historyData.length} items)`, 3000);
      }
    } catch (error) {
      console.error('Error downloading clipboard history ZIP:', error);
      if (typeof window.showToast === 'function') {
        window.showToast('Error downloading ZIP archive', 4000);
      }
    }
  }

  /**
   * Clear all clipboard items from backend storage.
   */
  function clearAllClipboardHistory() {
    fetch('/api/clipboard/clear', {
      method: 'DELETE'
    })
      .then(response => response.json())
      .then(data => {
        if (data.status === 'success') {
          if (typeof window.showToast === 'function') {
            window.showToast(data.msg, 3000);
          }
          refreshClipboardHistory();
        } else {
          if (typeof window.showToast === 'function') {
            window.showToast(` Failed to clear clipboard: ${data.msg}`, 4000);
          }
        }
      })
      .catch(error => {
        console.error('Error clearing clipboard:', error);
        if (typeof window.showToast === 'function') {
          window.showToast(' Failed to clear clipboard', 4000);
        }
      });
  }

  // Freeze immutable controller interface
  const ClipboardController = Object.freeze({
    uploadImageToClipboard: uploadImageToClipboard,
    getClipboardImageCount: getClipboardImageCount,
    addTextToClipboard: addTextToClipboard,
    clearClipboardInput: clearClipboardInput,
    refreshClipboardHistory: refreshClipboardHistory,
    renderClipboardHistory: renderClipboardHistory,
    showImagePreview: showImagePreview,
    uploadClipboardItem: uploadClipboardItem,
    downloadClipboardItem: downloadClipboardItem,
    copyClipboardText: copyClipboardText,
    removeClipboardItem: removeClipboardItem,
    downloadClipboardHistory: downloadClipboardHistory,
    clearAllClipboardHistory: clearAllClipboardHistory
  });

  window.ClipboardController = ClipboardController;

  // Preserve global backward compatibility aliases
  window.uploadImageToClipboard = window.uploadImageToClipboard || uploadImageToClipboard;
  window.getClipboardImageCount = window.getClipboardImageCount || getClipboardImageCount;
  window.addTextToClipboard = window.addTextToClipboard || addTextToClipboard;
  window.clearClipboardInput = window.clearClipboardInput || clearClipboardInput;
  window.refreshClipboardHistory = window.refreshClipboardHistory || refreshClipboardHistory;
  window.renderClipboardHistory = window.renderClipboardHistory || renderClipboardHistory;
  window.showImagePreview = window.showImagePreview || showImagePreview;
  window.uploadClipboardItem = window.uploadClipboardItem || uploadClipboardItem;
  window.downloadClipboardItem = window.downloadClipboardItem || downloadClipboardItem;
  window.copyClipboardText = window.copyClipboardText || copyClipboardText;
  window.removeClipboardItem = window.removeClipboardItem || removeClipboardItem;
  window.downloadClipboardHistory = window.downloadClipboardHistory || downloadClipboardHistory;
  window.clearAllClipboardHistory = window.clearAllClipboardHistory || clearAllClipboardHistory;

})(window);
