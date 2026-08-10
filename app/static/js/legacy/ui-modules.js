/**
 * @file ui-modules.js
 * @description Layout control and UI component layer for Lanvan. Coordinates Toast notifications,
 *              download progress animation sequences, file grid populating, and settings menus.
 * @module UIControllers
 * @dependency main-app.js, file-utils.js
 */
window.DOM_CACHE = window.DOM_CACHE || {};
var DOM_CACHE = window.DOM_CACHE;


//  Store file metadata for downloads (fixes "unknown size" issue)
function storeFileMetadata(files, totalSize) {
  const metadata = JSON.parse(localStorage.getItem('fileMetadata') || '{}');

  for (let file of files) {
    metadata[file.name] = {
      size: file.size,
      sizeFormatted: (file.size / (1024 * 1024)).toFixed(2) + ' MB',
      type: file.type || 'unknown',
      uploadDate: new Date().toISOString(),
      timestamp: Date.now()
    };
  }

  //  PERFORMANCE: Optimize metadata cleanup with for...in loop
  const thirtyDaysAgo = Date.now() - (30 * 24 * 60 * 60 * 1000);
  for (const filename in metadata) {
    if (metadata[filename].timestamp < thirtyDaysAgo) {
      delete metadata[filename];
    }
  }

  localStorage.setItem('fileMetadata', JSON.stringify(metadata));
}








// Page router extracted to features/navigation/page-router.js

//  Save toggle state when user changes it
document.addEventListener('DOMContentLoaded', () => {
  const aesToggle = document.getElementById('enableEncryption');
  if (!aesToggle) return;

  const isHTTP = location.protocol === 'http:';

  //  NEW LOGIC: Allow AES over HTTP only with HTTP-Safe mode
  if (isHTTP) {
    // For HTTP, enable AES toggle but show warning about HTTP-Safe requirement
    aesToggle.disabled = false;
    const toggleContainer = aesToggle.closest('.toggle-switch').parentElement;
    toggleContainer.style.opacity = '1';
    toggleContainer.title = 'AES over HTTP requires HTTP-Safe Mode for security. Enable both toggles for secure encryption.';

    // Restore saved state
    const saved = localStorage.getItem('aes_enabled');
    if (saved !== null) {
      aesToggle.checked = saved === '1';
    }
  } else {
    // For HTTPS, restore saved state and enable toggle
    aesToggle.disabled = false;
    const saved = localStorage.getItem('aes_enabled');
    if (saved !== null) {
      aesToggle.checked = saved === '1';
    }
  }

  // Save state on change (for both HTTP and HTTPS)
  aesToggle.addEventListener('change', () => {
    localStorage.setItem('aes_enabled', aesToggle.checked ? '1' : '0');

    //  HTTP-Safe mode is now automatic - no toggle needed
    if (isHTTP && aesToggle.checked) {
      console.log(' HTTP-Safe mode automatically enabled for HTTP connection');
      showToast(' HTTP-Safe mode automatically enabled for secure encryption!', 4000);
    }
  });

  //  HTTP-Safe mode is now automatic - no toggle management needed

  // Theme management extracted to features/ui/theme-manager.js
});

//  HTTP-Safe mode is now automatic - no toggle management needed



//  FOLDER UPLOAD FUNCTIONALITY
// Expose on window so all scripts (main-app.js, app-init.js) share the same state
window.currentUploadMode = 'files';
var currentUploadMode = window.currentUploadMode;

// Modern toggle function for single button mode switching
function toggleUploadMode() {
  const toggleBtn = document.getElementById('uploadModeToggle');
  const dropZoneText = document.getElementById('dropZoneText');

  if (currentUploadMode === 'files') {
    window.currentUploadMode = 'folder';
    currentUploadMode = 'folder';
    if (toggleBtn) {
      toggleBtn.innerHTML = ' Folders';
      toggleBtn.title = 'Currently in Folders mode - Click to switch to Files';
    }
    if (dropZoneText) dropZoneText.textContent = ' Drag & Drop folders here or click to select';
  } else {
    window.currentUploadMode = 'files';
    currentUploadMode = 'files';
    if (toggleBtn) {
      toggleBtn.innerHTML = ' Files';
      toggleBtn.title = 'Currently in Files mode - Click to switch to Folders';
    }
    if (dropZoneText) dropZoneText.textContent = ' Drag & Drop files here or click to select';
  }
}

// NEW: Beautiful Sliding Toggle Function
function toggleUploadModeNew() {
  const slider = document.getElementById('uploadModeSlider');
  const filesLabel = document.getElementById('filesLabel');
  const foldersLabel = document.getElementById('foldersLabel');
  const dropZoneText = document.getElementById('dropZoneText');

  if (slider && slider.checked) {
    window.currentUploadMode = 'folder';
    currentUploadMode = 'folder';
    if (filesLabel) filesLabel.classList.remove('active');
    if (foldersLabel) foldersLabel.classList.add('active');
    if (dropZoneText) dropZoneText.textContent = ' Drag & Drop folders here or click to select';
  } else {
    window.currentUploadMode = 'files';
    currentUploadMode = 'files';
    if (foldersLabel) foldersLabel.classList.remove('active');
    if (filesLabel) filesLabel.classList.add('active');
    if (dropZoneText) dropZoneText.textContent = ' Drag & Drop files here or click to select';
  }
}

// Initialize the toggle on page load
document.addEventListener('DOMContentLoaded', function () {
  const oldButton = document.getElementById('uploadModeToggle');
  if (oldButton && oldButton.parentElement) {
    oldButton.parentElement.style.display = 'none';
  }

  const newSliderContainer = document.getElementById('newSliderContainer');
  if (newSliderContainer) {
    newSliderContainer.style.display = 'flex';
  }
});

function handleDropZoneClick() {
  // Check the slider DOM state as primary source of truth
  const slider = document.getElementById('uploadModeSlider');
  const isFolder = (slider && slider.checked) ||
    window.currentUploadMode === 'folder' ||
    (typeof currentUploadMode !== 'undefined' && currentUploadMode === 'folder');

  if (isFolder) {
    const folderInput = document.getElementById('folderInput') || document.getElementById('hiddenFolderInput');
    if (folderInput) {
      // Re-assert folder attributes to ensure browser opens folder picker
      folderInput.setAttribute('webkitdirectory', '');
      folderInput.setAttribute('directory', '');
      folderInput.setAttribute('mozdirectory', '');
      folderInput.value = '';
      folderInput.click();
    }
  } else {
    const fileInput = document.getElementById('fileInput');
    if (fileInput) {
      fileInput.value = '';
      fileInput.click();
    }
  }
}
window.handleDropZoneClick = handleDropZoneClick;

// Main file upload handler
window.handleFiles = function (files) {
  console.count("handleFiles");
  console.trace("handleFiles");
  const fileInputEl = document.getElementById('fileInput');
  if (fileInputEl && typeof getEventListeners === 'function') {
    console.log('[INSTRUMENTATION] getEventListeners(fileInput):', getEventListeners(fileInputEl));
  }
  if (!files || !files.length) return;
  // Ensure we only process valid File objects
  const validFiles = Array.from(files).filter(f => f && typeof f === 'object' && typeof f.name === 'string');
  if (validFiles.length === 0) return;

  console.log(' handleFiles called with:', validFiles.length, 'files');

  console.log(' Adding files to upload queue...');
  addToUploadQueue(validFiles);

  showUploadManager();
  startNextUpload();
};

/**
 * Programmatically open the file or folder picker.
 * Called from onclick handlers in app-init.js empty-state drop zones.
 * @param {string} type - 'file' or 'folder'
 */
function handleFileSelection(type) {
  if (type === 'folder') {
    const folderInput = document.getElementById('folderInput') || document.getElementById('hiddenFolderInput');
    if (folderInput) {
      folderInput.setAttribute('webkitdirectory', '');
      folderInput.setAttribute('directory', '');
      folderInput.setAttribute('mozdirectory', '');
      folderInput.value = '';
      folderInput.click();
    }
  } else {
    // Default to file picker
    const fileInput = document.getElementById('fileInput');
    if (fileInput) {
      fileInput.value = '';
      fileInput.click();
    }
  }
}

// Export to window so main-app.js and other scripts can call it directly
window.handleFileSelection = handleFileSelection;



async function loadFolders() {
  try {
    const response = await fetch('/api/folders');
    const result = await response.json();

    if (result.status === 'success') {
      displayFolders(result.folders);
    }
  } catch (error) {
    console.error('Error loading folders:', error);
  }
}

function displayFolders(folders) {
  const folderGrid = document.getElementById('folderGrid');
  const folderCount = document.getElementById('folderCount');

  if (!folderGrid) return;

  if (folders.length === 0) {
    folderGrid.innerHTML = '<p style="color: var(--text-color); text-align: center; padding: 2rem;">No folders uploaded yet.</p>';
    if (folderCount) folderCount.textContent = '(0)';
    return;
  }

  if (folderCount) folderCount.textContent = `(${folders.length})`;

  function escapeHtml(text) {
    if (!text) return '';
    return text
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  folderGrid.innerHTML = folders.map(folder => {
    const escName = escapeHtml(folder.name);
    const attrEscName = escName.replace(/'/g, '&#39;').replace(/"/g, '&quot;');
    const encodedName = encodeURIComponent(folder.name);
    return `
    <div class="file-card">
      <div class="file-icon"></div>
      <div class="file-name" title="${escName}">${escName}</div>
      <div class="file-size">${folder.file_count} files • ${folder.size_formatted}</div>
      <div class="file-actions">
        <a href="/download-folder/${encodedName}" class="download-btn"> Download</a>
        <button onclick="deleteFolder('${attrEscName}')" class="download-btn" style="background-color: #e74c3c;"></button>
      </div>
    </div>
  `;
  }).join('');
}

async function deleteFolder(folderName) {
  try {
    const response = await fetch(`/delete-folder/${encodeURIComponent(folderName)}`, { method: 'POST' });
    const result = await response.json();

    if (result.status === 'success') {
      showToast(` Folder "${folderName}" deleted successfully!`, 3000);
      loadFolders(); // Refresh folder list
    } else {
      showToast(` Failed to delete folder: ${result.msg}`, 4000);
    }
  } catch (error) {
    console.error('Error deleting folder:', error);
    showToast(' Error deleting folder!', 4000);
  }
}

// Load folders when page loads
document.addEventListener('DOMContentLoaded', function () {
  setTimeout(loadFolders, 1000);
});

// Mark that the main page loaded successfully (for loading page optimization)
try {
  sessionStorage.setItem('Lanvan_page_loaded_successfully', Date.now().toString());
  // Also set a flag that resources are working
  sessionStorage.setItem('Lanvan_resources_ready', 'true');
} catch (e) {
  // Ignore storage errors
}
