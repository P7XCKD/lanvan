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



// Progress styling utilities for visual feedback
function setProgressColor(color) {
  try {
    // Use cached DOM element instead of repeated getElementById
    let progressBar = DOM_CACHE.toastProgress;
    if (!progressBar) {
      progressBar = document.getElementById('toast-progress');
      if (progressBar) DOM_CACHE.toastProgress = progressBar;
    }
    if (!progressBar) return; // Safe guard for guest devices

    if (color === 'blue') {
      progressBar.style.background = 'linear-gradient(90deg, #2196F3, #42A5F5)';
    } else if (color === 'green') {
      progressBar.style.background = 'linear-gradient(90deg, #4CAF50, #66BB6A)';
    } else {
      progressBar.style.background = color;
    }
  } catch (err) {
    console.log('Progress color update skipped on this device');
  }
}




// Switch button dropdown and navigation logic (inlined to avoid 404 issues)
function showSwitchDropdown(event, dropdownId) {
  event.stopPropagation();
  const dropdown = document.getElementById(dropdownId);
  if (dropdown.style.display === 'block') {
    dropdown.style.display = 'none';
  } else {
    dropdown.style.display = 'block';
    // Hide dropdown if clicked outside
    document.addEventListener('click', function handler(e) {
      if (!dropdown.contains(e.target)) {
        dropdown.style.display = 'none';
        document.removeEventListener('click', handler);
      }
    });
  }
}
function switchToPage(page) {
  // Hide all switch dropdowns before switching
  var dropdowns = [
    document.getElementById('switchDropdownMain'),
    document.getElementById('switchDropdownClipboard')
  ];
  dropdowns.forEach(function (dd) {
    if (dd) dd.style.display = 'none';
  });

  // Get the sections by ID
  const fileTransferSection = document.getElementById('fileTransferSection');
  const fileListSection = document.getElementById('fileListSection');
  const clipboardSection = document.getElementById('clipboardSection');

  // If target section is missing, perform standard redirect instead of dynamic toggle
  if (page === 'clipboard' && !clipboardSection) {
    window.location.href = '/clipboard';
    return;
  }
  if (page === 'file' && (!fileTransferSection || !fileListSection)) {
    window.location.href = '/';
    return;
  }

  // Update active tab state immediately (0ms delay)
  document.documentElement.setAttribute('data-active-tab', page);
  if (typeof window.switchView === 'function') {
    window.switchView(page);
  }

  if (page === 'clipboard') {
    currentActiveSection = 'clipboard';
    if (fileTransferSection) fileTransferSection.style.opacity = '1';
    if (fileListSection) fileListSection.style.opacity = '1';
    if (clipboardSection) clipboardSection.style.opacity = '1';
    history.pushState({ page: 'clipboard' }, 'Lanvan - Clipboard', '/clipboard');
    document.title = 'Lanvan - Clipboard';
  } else if (page === 'file') {
    currentActiveSection = 'file';
    if (fileTransferSection) fileTransferSection.style.opacity = '1';
    if (fileListSection) fileListSection.style.opacity = '1';
    if (clipboardSection) clipboardSection.style.opacity = '1';
    history.pushState({ page: 'file' }, 'Lanvan - File Transfer', '/');
    document.title = 'Lanvan - File Transfer';
  }

  // Trigger any necessary updates for the visible section
  setTimeout(() => {
    if (page === 'file') {
      // When switching back to file section, refresh the file list to show any new files
      if (typeof refreshFileList === 'function') {
        refreshFileList();
      } else if (typeof updateFileList === 'function') {
        updateFileList();
      }
    } else if (page === 'clipboard') {
      if (typeof refreshClipboardHistory === 'function') {
        refreshClipboardHistory();
      }
    }
  }, 150); // Slight delay to ensure sections are visible

  // Show a brief toast notification
  if (typeof showToast === 'function') {
    const sectionName = page === 'clipboard' ? 'Clipboard' : 'File Transfer';
    showToast(` Switched to ${sectionName}`, 1500);
  }
}

if (!window.__popstateWired) {
  window.__popstateWired = true;
  window.addEventListener('popstate', function (event) {
    if (event.state && event.state.page) {
      // Switch to the page without updating history (since we're handling popstate)
      const targetPage = event.state.page;

      // Update current active section tracker
      currentActiveSection = targetPage;
      console.log(` Browser navigation - active section: ${currentActiveSection}`);

      const fileTransferSection = document.getElementById('fileTransferSection');
      const fileListSection = document.getElementById('fileListSection');
      const clipboardSection = document.getElementById('clipboardSection');

      if (targetPage === 'clipboard') {
        document.title = 'Lanvan - Clipboard';
      } else {
        document.title = 'Lanvan - File Transfer';
      }

      // Delegate all view switching to switchView (single source of truth)
      if (typeof window.switchView === 'function') {
        window.switchView(targetPage);
      }
    }
  });
}

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

  //  Dark Mode Toggle Functionality
  // --- 3-Way Theme Preference Initializer ---
  window.applyThemePreference = function (themePref) {
    // Migrate legacy settings if themePref is not set
    if (!themePref) {
      themePref = localStorage.getItem('theme_preference');
      if (themePref === null) {
        const legacyDark = localStorage.getItem('dark_mode_enabled');
        if (legacyDark !== null) {
          themePref = legacyDark === '1' ? 'dark' : 'light';
        } else {
          themePref = 'system';
        }
        localStorage.setItem('theme_preference', themePref);
      }
    }

    let isDarkMode = false;
    if (themePref === 'dark') {
      isDarkMode = true;
    } else if (themePref === 'light') {
      isDarkMode = false;
    } else {
      isDarkMode = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
    }

    applyDarkMode(isDarkMode);

    // Update settings radio buttons
    const themeLightRadio = document.getElementById('themeLight');
    const themeDarkRadio = document.getElementById('themeDark');
    const themeSystemRadio = document.getElementById('themeSystem');

    if (themeLightRadio && themeDarkRadio && themeSystemRadio) {
      themeLightRadio.checked = themePref === 'light';
      themeDarkRadio.checked = themePref === 'dark';
      themeSystemRadio.checked = themePref === 'system';
    }

    // Keep legacy checkboxes in sync
    if (DOM_CACHE.darkModeToggle) {
      DOM_CACHE.darkModeToggle.checked = isDarkMode;
    }
    const settingsToggle = document.getElementById("darkThemeSettingToggle");
    if (settingsToggle) {
      settingsToggle.checked = isDarkMode;
    }

    // Dynamic label/icon/description updates
    const themeIcon = document.getElementById('themeSettingIcon');
    const themeTitle = document.getElementById('themeSettingTitle');
    const themeDesc = document.getElementById('themeSettingDesc');

    if (themeIcon && themeTitle && themeDesc) {
      if (themePref === 'light') {
        themeIcon.setAttribute('data-lucide', 'sun');
        themeTitle.textContent = 'Light Theme';
        themeDesc.textContent = 'Use clean light mode interface';
      } else if (themePref === 'dark') {
        themeIcon.setAttribute('data-lucide', 'moon');
        themeTitle.textContent = 'Dark Theme';
        themeDesc.textContent = 'Use sleek dark mode interface';
      } else {
        themeIcon.setAttribute('data-lucide', 'monitor');
        themeTitle.textContent = 'System Theme';
        themeDesc.textContent = "Follow device's theme settings";
      }
      if (window.refreshLucideIcons) {
        window.refreshLucideIcons(themeIcon ? themeIcon.parentElement : null);
      } else if (window.lucide && typeof window.lucide.createIcons === 'function') {
        window.lucide.createIcons();
      }
    }

    // Sync header toggle icon
    const headerToggleBtn = document.querySelector('button[onclick="toggleDarkMode()"]');
    if (headerToggleBtn) {
      const iconEl = headerToggleBtn.querySelector('i');
      if (iconEl) {
        let iconName = 'monitor';
        if (themePref === 'light') iconName = 'sun';
        else if (themePref === 'dark') iconName = 'moon';
        iconEl.setAttribute('data-lucide', iconName);
        if (window.refreshLucideIcons) {
          window.refreshLucideIcons(headerToggleBtn);
        } else if (window.lucide && typeof window.lucide.createIcons === 'function') {
          window.lucide.createIcons();
        }
      }
    }
  };

  // Run initialization
  window.applyThemePreference(null);

  // Listen for system theme changes dynamically
  if (window.matchMedia) {
    window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', (e) => {
      const themePref = localStorage.getItem('theme_preference') || 'system';
      if (themePref === 'system') {
        applyDarkMode(e.matches);
      }
    });
  }

  //  Apply Dark Mode Function
  function applyDarkMode(isDarkMode) {
    if (isDarkMode) {
      document.documentElement.setAttribute('data-theme', 'dark');
    } else {
      document.documentElement.setAttribute('data-theme', 'light');
    }

    // Update dark mode toggle text based on current mode
    const darkModeLabel = document.getElementById('darkModeLabel');
    if (darkModeLabel) {
      if (isDarkMode) {
        darkModeLabel.innerHTML = '<b> Dark Mode</b>';
      } else {
        darkModeLabel.innerHTML = '<b> Light Mode</b>';
      }
    }

    // Update protocol status hover colors for dark mode
    // Guard with typeof in case another DOMContentLoaded fires first
    if (typeof updateProtocolStatusHover === 'function') {
      updateProtocolStatusHover(isDarkMode);
    }

    // Fix any remaining hardcoded colors dynamically
    fixRemainingColors(isDarkMode);
  }

  // Fix remaining hardcoded colors that CSS might miss
  function fixRemainingColors(isDarkMode) {
    if (isDarkMode) {
      // Fix any elements with hardcoded #333 color
      const darkTextElements = document.querySelectorAll('[style*="color: #333"], [style*="color:#333"], [style*="color: #666"], [style*="color:#666"], [style*="color: #999"], [style*="color:#999"]');
      darkTextElements.forEach(el => {
        el.style.color = 'var(--text-color)';
      });

      // Fix any white background divs
      const whiteBgElements = document.querySelectorAll('[style*="background: #fff"], [style*="background-color: #fff"], [style*="background: #f8f9fa"], [style*="background: white"]');
      whiteBgElements.forEach(el => {
        el.style.backgroundColor = 'var(--section-bg)';
        el.style.color = 'var(--text-color)';
      });

      // Fix file names and clipboard items specifically
      const fileNameElements = document.querySelectorAll('.file-name, .upload-file-name');
      fileNameElements.forEach(el => {
        el.style.color = 'var(--text-color)';
      });

      // Fix clipboard items
      const clipboardElements = document.querySelectorAll('#clipboardHistoryContent div');
      clipboardElements.forEach(el => {
        if (el.style.color && (el.style.color.includes('#333') || el.style.color.includes('#666') || el.style.color.includes('#999'))) {
          el.style.color = 'var(--text-color)';
        }
      });

      // Fix labels and other text elements
      const textElements = document.querySelectorAll('label, span:not(.slider), .file-name, strong');
      textElements.forEach(el => {
        // Skip the mDNS hint text to preserve green color
        if (el.id === 'qrHintText' && el.innerHTML.includes('mDNS:')) {
          return;
        }
        if (!el.classList.contains('slider') && !el.classList.contains('toggle-text')) {
          if (el.style.color && (el.style.color.includes('#333') || el.style.color.includes('#666'))) {
            el.style.color = 'var(--text-color)';
          }
        }
      });
    } else {
      // Reset to light mode colors
      const allElements = document.querySelectorAll('*');
      allElements.forEach(el => {
        if (el.style.color && el.style.color.includes('var(--text-color)')) {
          el.style.color = '';
        }
        if (el.style.backgroundColor && el.style.backgroundColor.includes('var(--')) {
          el.style.backgroundColor = '';
        }
      });
    }
  }

  // Update protocol status hover behavior for dark mode
  function updateProtocolStatusHover(isDarkMode) {
    const protocolStatus = DOM_CACHE.protocolStatus;
    if (protocolStatus) {
      if (isDarkMode) {
        protocolStatus.onmouseover = function () { this.style.backgroundColor = '#1e40af'; };
        protocolStatus.onmouseout = function () { this.style.backgroundColor = 'var(--protocol-bg)'; };
      } else {
        protocolStatus.onmouseover = function () { this.style.backgroundColor = '#d0e9f7'; };
        protocolStatus.onmouseout = function () { this.style.backgroundColor = 'var(--protocol-bg)'; };
      }
    }
  }
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

async function uploadFolder(files) {
  if (files.length === 0) {
    showToast(' No files selected!', 3000);
    return;
  }

  const folderGroups = new Map();
  const standaloneFiles = [];

  for (let file of files) {
    if (file.webkitRelativePath) {
      const parts = file.webkitRelativePath.split('/');
      const rootFolder = parts[0];
      if (!folderGroups.has(rootFolder)) {
        folderGroups.set(rootFolder, []);
      }
      folderGroups.get(rootFolder).push(file);
    } else {
      standaloneFiles.push(file);
    }
  }

  if (standaloneFiles.length > 0) {
    if (typeof addToUploadQueue === 'function') addToUploadQueue(standaloneFiles);
  }

  for (let [folderName, folderFiles] of folderGroups) {
    if (typeof addToUploadQueue === 'function') addToUploadQueue(folderFiles);
  }

  if (typeof showUploadManager === 'function') showUploadManager();
  if (typeof startNextUpload === 'function') startNextUpload();
}

async function uploadSingleFolder(folderName, files) {
  const formData = new FormData();
  formData.append('folder_name', folderName);

  const currentDir = (typeof window.getCurrentFolderPath === 'function') ? window.getCurrentFolderPath() : '';
  if (currentDir) {
    formData.append('parent_path', currentDir);
  }

  for (let file of files) {
    const relativePath = file.webkitRelativePath || file.name;
    const pathWithoutRoot = relativePath.includes('/') ? relativePath.substring(relativePath.indexOf('/') + 1) : file.name;
    formData.append('files', file, pathWithoutRoot);
  }

  try {
    const response = await fetch('/upload-folder', {
      method: 'POST',
      body: formData
    });

    const result = await response.json();

    if (result.status === 'success') {
      showToast(` Folder "${folderName}" uploaded successfully! (${result.files_uploaded.length} files)`, 4000);
      if (typeof refreshFileListManually === 'function') {
        refreshFileListManually();
      }
      if (typeof window.requestSafeVisibleFilesRefresh === 'function') {
        window.requestSafeVisibleFilesRefresh(120);
      } else if (typeof fetchFilesData === 'function' && typeof renderFileList === 'function') {
        fetchFilesData().then(function (fd) { renderFileList(fd); });
      }
      if (typeof loadFolders === 'function') loadFolders();
      return { success: true, folderName, fileCount: result.files_uploaded.length };
    } else {
      showToast(` Upload failed: ${result.msg}`, 4000);
      return { success: false, folderName, error: result.msg };
    }
  } catch (error) {
    console.error('Folder upload error:', error);
    showToast(` Folder "${folderName}" upload failed!`, 4000);
    return { success: false, folderName, error: error.message };
  }
}

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
