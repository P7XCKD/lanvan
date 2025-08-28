/* Single Function Extraction - generateFileListHash */
/* Ultra-safe: zero external dependencies */

/**
 * Generate a hash string from a file list for deduplication
 * @param {FileList|Array} files - Files to generate hash from
 * @returns {string} Hash string
 */
function generateFileListHash(files) {
  if (!files || files.length === 0) return '';
  return Array.from(files).map(f => `${f.name}_${f.size}_${f.lastModified}`).join('|');
}

/**
 * Generate an offline QR code pattern on a canvas
 * @param {string} text - Text to encode in QR pattern
 * @param {HTMLCanvasElement} canvas - Canvas element to draw on
 * @returns {string|boolean} Data URL of the QR code or false if blocked
 */
function generateOfflineQR(text, canvas) {
  // Skip computation if uploads are blocked to prevent UI blocking
  if (window._qrBlocked) {
    console.log('⏸️ QR computation blocked during upload');
    return false;
  }
  
  // Create a simple grid-based QR code for offline use
  const ctx = canvas.getContext('2d');
  canvas.width = 200;
  canvas.height = 200;
  
  // Simple pattern generation (basic QR-like appearance)
  const size = 20;
  const cellSize = canvas.width / size;
  
  // Generate pattern based on text hash
  let hash = 0;
  for (let i = 0; i < text.length; i++) {
    hash = ((hash << 5) - hash + text.charCodeAt(i)) & 0xffffffff;
  }
  
  ctx.fillStyle = '#ffffff';
  ctx.fillRect(0, 0, canvas.width, canvas.height);
  
  ctx.fillStyle = '#000000';
  
  // Create QR-like pattern
  for (let y = 0; y < size; y++) {
    for (let x = 0; x < size; x++) {
      // Position markers (corners)
      if ((x < 7 && y < 7) || (x >= size-7 && y < 7) || (x < 7 && y >= size-7)) {
        if ((x < 6 && y < 6 && (x === 0 || x === 5 || y === 0 || y === 5)) ||
            (x >= size-6 && y < 6 && (x === size-6 || x === size-1 || y === 0 || y === 5)) ||
            (x < 6 && y >= size-6 && (x === 0 || x === 5 || y === size-6 || y === size-1))) {
          ctx.fillRect(x * cellSize, y * cellSize, cellSize, cellSize);
        }
        if ((x >= 2 && x <= 4 && y >= 2 && y <= 4) ||
            (x >= size-5 && x <= size-3 && y >= 2 && y <= 4) ||
            (x >= 2 && x <= 4 && y >= size-5 && y <= size-3)) {
          ctx.fillRect(x * cellSize, y * cellSize, cellSize, cellSize);
        }
      } else {
        // Data pattern based on hash
        const pos = y * size + x;
        if (((hash >> (pos % 32)) & 1) === 1) {
          ctx.fillRect(x * cellSize, y * cellSize, cellSize, cellSize);
        }
      }
    }
  }
  
  return canvas.toDataURL();
}

/**
 * Get system resource usage information
 * @returns {Object} Resource usage data
 */
function getSystemResourceUsage() {
  const usage = {
    memory: 50, // Default fallback
    connection: 'unknown'
  };
  
  try {
    // Check memory if available
    if (navigator.deviceMemory) {
      const totalMemory = navigator.deviceMemory * 1024; // Convert to MB
      usage.memory = Math.min(100, (4096 / totalMemory) * 100); // Estimate usage
    }
    
    // Check connection type if available
    if (navigator.connection) {
      usage.connection = navigator.connection.effectiveType || 'unknown';
      usage.downlink = navigator.connection.downlink || 0;
    }
  } catch (e) {
    console.log('Resource monitoring not available');
  }
  
  return usage;
}

/**
 * Format time duration in seconds to human readable format
 * @param {number} seconds - Time in seconds
 * @returns {string} Formatted time string (e.g., "45s", "2m", "1h")
 */
function formatTime(seconds) {
  if (seconds < 60) return Math.round(seconds) + 's';
  if (seconds < 3600) return Math.round(seconds / 60) + 'm';
  return Math.round(seconds / 3600) + 'h';
}

/**
 * Format file size in bytes to human readable format
 * @param {number} bytes - File size in bytes
 * @returns {string} Formatted size string (e.g., "1.5 MB", "256 KB")
 */
function formatFileSize(bytes) {
  if (bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
}

/**
 * Format transfer speed in bytes per second to human readable format
 * @param {number} bytesPerSecond - Speed in bytes per second
 * @returns {string} Formatted speed string (e.g., "1.2 MB/s", "500 KB/s")
 */
function formatSpeed(bytesPerSecond) {
  if (bytesPerSecond === 0) return '0 B/s';
  const k = 1024;
  const sizes = ['B/s', 'KB/s', 'MB/s', 'GB/s'];
  const i = Math.floor(Math.log(bytesPerSecond) / Math.log(k));
  return parseFloat((bytesPerSecond / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
}

/**
 * Escape HTML special characters to prevent XSS
 * @param {string} text - Text to escape
 * @returns {string} HTML-escaped text
 */
function escapeHtml(text) {
  const map = {
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#039;'
  };
  return text.replace(/[&<>"']/g, m => map[m]);
}

/**
 * Format clipboard item size to human readable format
 * @param {number} bytes - Size in bytes
 * @returns {string} Formatted size string (e.g., "1.5 MB", "256.0 KB")
 */
function formatClipboardSize(bytes) {
  if (bytes < 1024) return bytes + ' B';
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
}

/**
 * Get status display text for upload status
 * @param {string} status - Upload status code
 * @returns {string} Human readable status text
 */
function getStatusDisplay(status) {
  const statusMap = {
    'queued': 'Queued',
    'uploading': 'Uploading',
    'completed': '✅ Complete',
    'error': '❌ Error', 
    'cancelled': '⏸️ Cancelled'
  };
  return statusMap[status] || status;
}

/**
 * Get device memory in MB with fallback
 * @returns {number} Device memory in MB
 */
function getDeviceMemory() {
  try {
    return navigator.deviceMemory ? navigator.deviceMemory * 1024 : 2048; // Default to 2GB if unknown
  } catch (e) {
    return 2048; // Conservative default
  }
}

/**
 * Check if browser is in incognito/private mode
 * @returns {boolean} True if incognito mode detected
 */
function checkIncognitoMode() {
  try {
    // Simple incognito detection
    return !window.indexedDB || !window.localStorage;
  } catch (e) {
    return true; // Assume incognito if checks fail
  }
}

/**
 * Get browser information from user agent string
 * @param {string} userAgent - User agent string
 * @returns {Object} Browser name and version info
 */
function getBrowserInfo(userAgent) {
  if (userAgent.includes('Firefox')) {
    return { name: 'Firefox', version: 'Unknown' };
  } else if (userAgent.includes('Chrome') && !userAgent.includes('Edge')) {
    return { name: 'Chrome', version: 'Unknown' };
  } else if (userAgent.includes('Safari') && !userAgent.includes('Chrome')) {
    return { name: 'Safari', version: 'Unknown' };
  } else if (userAgent.includes('Edge')) {
    return { name: 'Edge', version: 'Unknown' };
  } else {
    return { name: 'Unknown', version: 'Unknown' };
  }
}

/**
 * Update HTTP security warning display
 */
function updateHttpSecurityWarning() {
  // HTTP-Safe mode is automatic when AES is enabled over HTTP
  console.log('🛡️ HTTP-Safe mode: automatic when AES enabled over HTTP');
}

/**
 * Get appropriate icon for clipboard item type
 * @param {Object} item - Clipboard item with type and content_type
 * @returns {string} Emoji icon for the item type
 */
function getClipboardItemIcon(item) {
  if (item.type === 'file') {
    switch (item.content_type) {
      case 'image': return '🖼️';
      case 'text': return '📄';
      case 'document': return '📋';
      default: return '📁';
    }
  } else {
    switch (item.content_type) {
      case 'image_base64': return '🖼️';
      case 'url': return '🔗';
      default: return '📝';
    }
  }
}

/**
 * Get control buttons HTML for upload item
 * @param {Object} uploadItem - Upload item with status and id
 * @returns {string} HTML string for control buttons
 */
function getControlButtons(uploadItem) {
  switch (uploadItem.status) {
    case 'uploading':
      return `<button class="upload-control-btn cancel" onclick="cancelUpload(${uploadItem.id})" title="Cancel upload">Cancel</button>`;
    case 'queued':
      return `<button class="upload-control-btn cancel" onclick="cancelUpload(${uploadItem.id})" title="Cancel upload">Cancel</button>`;
    case 'completed':
      return ``; // No individual remove button for completed uploads
    case 'error':
      return ``; // No cancel button for error state
    case 'cancelled':
      return ``; // No cancel button for already cancelled uploads
    default:
      return `<button class="upload-control-btn cancel" onclick="cancelUpload(${uploadItem.id})" title="Cancel upload">Cancel</button>`;
  }
}

/**
 * Determine if new upload item should be inserted before existing item
 * @param {Object} newItem - New upload item to insert
 * @param {Object} existingItem - Existing upload item in queue
 * @returns {boolean} True if new item should come before existing item
 */
function shouldInsertBefore(newItem, existingItem) {
  // Priority 1: Incomplete/Failed uploads first
  const newIncomplete = ['failed', 'paused'].includes(newItem.status);
  const existingIncomplete = ['failed', 'paused'].includes(existingItem.status);
  
  if (newIncomplete && !existingIncomplete) return true;
  if (!newIncomplete && existingIncomplete) return false;
  
  // Priority 2: AES files get priority within same completion status
  if (newItem.isAESEnabled && !existingItem.isAESEnabled) return true;
  if (!newItem.isAESEnabled && existingItem.isAESEnabled) return false;
  
  // Priority 3: Smaller files first
  return newItem.fileSize < existingItem.fileSize;
}

// Function to establish a WebSocket connection for clipboard-only mode
function connectClipboardWS() {
  const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws';
  const wsUrl = `${protocol}://${window.location.host}/ws/clipboard`;
  let ws = new WebSocket(wsUrl);

  ws.onopen = () => {
    // Refresh clipboard history when WebSocket (re)connects
    if (typeof refreshClipboardHistory === 'function') {
      setTimeout(() => refreshClipboardHistory(), 50); // Reduced from 100ms for responsiveness
    }
  };

  ws.onmessage = (event) => {
    if (event.data === 'refresh') {
      if (typeof refreshClipboardHistory === 'function') refreshClipboardHistory();
    }
  };
}

// Function to establish a WebSocket connection for regular clipboard mode
function connectRegularClipboardWS() {
  // Only connect if clipboard section exists
  const clipboardSection = document.getElementById('clipboardSection');
  if (!clipboardSection) return;

  const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws';
  const wsUrl = `${protocol}://${window.location.host}/ws/clipboard`;
  let clipboardWS = new WebSocket(wsUrl);

  clipboardWS.onopen = () => {
    log.network('Regular mode clipboard WebSocket connected');
    // Refresh clipboard history when WebSocket (re)connects
    if (typeof refreshClipboardHistory === 'function') {
      setTimeout(() => refreshClipboardHistory(), 50); // Reduced from 100ms for responsiveness
    }
  };

  clipboardWS.onmessage = (event) => {
    if (event.data === 'refresh') {
      log.debug('Clipboard update received via WebSocket');
      if (typeof refreshClipboardHistory === 'function') refreshClipboardHistory();
    }
  };

  clipboardWS.onclose = () => {
    log.warn('Clipboard WebSocket disconnected, will reconnect...');
    // Try to reconnect after reduced delay if disconnected
    setTimeout(connectRegularClipboardWS, 1000); // Reduced from 2000ms
  };
}

// Function to manage a safety net for upload progress updates
function startProgressUpdateSafetyNet() {
  if (progressUpdateInterval) return; // Already running

  progressUpdateInterval = setInterval(() => {
    // Include ALL uploads that should show progress (uploading OR processing)
    const activeUploads = uploadQueue.filter(item => 
      (item.status === 'uploading' || item.status === 'processing') && 
      item.progress !== undefined && item.progress < 100
    );

    // Force update uploads that might be stuck due to processing delays
    activeUploads.forEach(uploadItem => {
      const timeSinceUpdate = uploadItem.lastProgressUpdate ? (Date.now() - uploadItem.lastProgressUpdate) : 5000;
      // More aggressive: force update every 800ms for ultra-responsive feel
      if (timeSinceUpdate > 800) {
        // Only log if critically stuck for more than 30 seconds to reduce spam
        if (timeSinceUpdate > 30000) {
          console.warn(`⚠️ Upload critically stuck for ${uploadItem.fileName} (${(timeSinceUpdate/1000).toFixed(1)}s), forcing update`);
        }
        updateUploadItem(uploadItem, true); // Force update flag
      }
    });

    // Keep safety net running if ANY uploads exist (not just active ones)
    const anyUploads = uploadQueue.filter(item => 
      !['completed', 'cancelled', 'error'].includes(item.status)
    );

    if (anyUploads.length === 0) {
      clearInterval(progressUpdateInterval);
      progressUpdateInterval = null;
      console.log('🔄 Safety net stopped - no active uploads');
    }
  }, 300); // Check every 300ms for ultra-responsive feel
}

/**
 * Function to determine if a file selection should be processed
 * @param {FileList|Array} files - Files from the file input
 * @returns {boolean} True if file selection should be processed
 */
function shouldProcessFileSelection(files) {
  const now = Date.now();
  const fileHash = generateFileListHash(files);

  // Check if this is a duplicate selection within debounce period
  if (now - lastFileSelectionTime < FILE_SELECTION_DEBOUNCE && fileHash === lastFileSelectionHash) {
    console.log('🔄 Duplicate file selection ignored (debounced)');
    return false;
  }

  // Update last selection time and hash
  lastFileSelectionTime = now;
  lastFileSelectionHash = fileHash;
  return true;
}

/**
 * Function to determine optimal concurrency for uploads
 */
function getOptimalConcurrency() {
  // Get average network speed from recent samples
  if (networkSpeedSamples.length === 0) {
    return LANVAN_CONFIG.CONCURRENT.NETWORK_MEDIUM;
  }

  const avgSpeed = networkSpeedSamples.reduce((a, b) => a + b, 0) / networkSpeedSamples.length;

  // Detect device capability
  const isLowEndDevice = detectGuestDevice();
  const deviceMemory = getDeviceMemory();

  // Base concurrency on network speed
  let optimal;
  if (avgSpeed > 10) {
    optimal = LANVAN_CONFIG.CONCURRENT.NETWORK_FAST;
  } else if (avgSpeed > 5) {
    optimal = LANVAN_CONFIG.CONCURRENT.NETWORK_MEDIUM;
  } else {
    optimal = LANVAN_CONFIG.CONCURRENT.NETWORK_SLOW;
  }

  // Reduce for low-end devices
  if (isLowEndDevice || deviceMemory < 4096) {
    optimal = Math.min(optimal, 2);
  }

  // Cap at maximum
  return Math.min(optimal, LANVAN_CONFIG.CONCURRENT.MAX_UPLOADS);
}

// Function to handle the end of an upload
function endUpload() {
  activeUploads = Math.max(0, activeUploads - 1);
  log.upload(`Upload ended (${activeUploads}/${currentMaxConcurrent} active)`);

  // Resume auto-refresh when all uploads complete
  if (activeUploads === 0) {
    handleUploadEnd();
  }
}

// Function to show the upload manager
function showUploadManager() {
  const manager = document.getElementById('uploadManager');
  if (manager && !isUploadManagerVisible) {
    manager.style.display = 'block';
    isUploadManagerVisible = true;

    // 🔔 Show helpful toast when upload manager first appears
    showToast('📤 Upload Manager opened - Track your file uploads here!', 3000);
  }
}

// Function to toggle the visibility of device logs
function toggleDeviceLogs() {
  // Open device logs in modal format
  const modal = document.getElementById('deviceLogsModal');
  modal.style.display = 'flex';

  // Populate logs data
  populateDeviceLogsModal();

  // Close on escape key
  document.addEventListener('keydown', function escapeHandler(e) {
    if (e.key === 'Escape') {
      closeDeviceLogsModal();
      document.removeEventListener('keydown', escapeHandler);
    }
  });

  // Close on background click
  modal.addEventListener('click', (e) => {
    if (e.target === modal) {
      closeDeviceLogsModal();
    }
  });
}

// Function to populate the device logs modal
function populateDeviceLogsModal() {
  const logsSection = document.getElementById('deviceLogsSection');
  const logsContent = document.getElementById('deviceLogsContent');
  const logsStats = document.getElementById('deviceLogsStats');
  const logsPagination = document.getElementById('deviceLogsPagination');

  // Show logs in modal
  try {
    const deviceUploadLogs = getDeviceUploadHistory();

    if (deviceUploadLogs.length === 0) {
      logsContent.innerHTML = `
        <div style="text-align: center; color: var(--text-color); opacity: 0.6; padding: 2rem;">
          <div style="font-size: 3rem; margin-bottom: 1rem;">📊</div>
          <div style="font-size: 1.1rem; color: var(--text-color) !important;">No device logs for this session yet</div>
          <div style="font-size: 0.9rem; margin-top: 0.5rem; color: var(--text-color) !important; opacity: 0.7;">Upload some files to see activity logs here</div>
          <div style="font-size: 0.85rem; margin-top: 1rem; color: var(--text-color) !important; opacity: 0.7;">
            📱 Logs are device-specific and clear when you close the browser
          </div>
        </div>
      `;
      logsStats.innerHTML = '';
      logsPagination.style.display = 'none';
    } else {
      // Generate logs stats
      const totalFiles = deviceUploadLogs.length;
      const totalSizeBytes = deviceUploadLogs.reduce((sum, log) => {
        const sizeMB = parseFloat(log.size?.replace(/[^\d.-]/g, '') || '0');
        return sum + sizeMB;
      }, 0);
      const sessionStartTime = deviceUploadLogs[deviceUploadLogs.length - 1]?.timestamp;
      const sessionEndTime = deviceUploadLogs[0]?.timestamp;

      logsStats.innerHTML = `
        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 1rem;">
          <div><strong>📊 Total Entries:</strong> ${totalFiles}</div>
          <div><strong>💾 Total Data:</strong> ${totalSizeBytes.toFixed(1)} MB</div>
          <div><strong>📱 Device Session:</strong> ${getCurrentDeviceId().substring(0, 8)}...</div>
          <div><strong>⏰ Session Started:</strong> ${sessionStartTime || 'Unknown'}</div>
        </div>
      `;

      // Display logs with pagination (grouped by batch)
      displayDeviceLogsWithPagination(deviceUploadLogs, logsContent, logsPagination);
    }
  } catch (error) {
    console.error('Error populating device logs modal:', error);
  }
}

/**
 * Function to update network speed and adapt concurrency
 * @param {number} speedMBps - Speed in MB/s
 */
function updateNetworkSpeed(speedMBps) {
  networkSpeedSamples.push(speedMBps);

  // Keep only recent samples
  if (networkSpeedSamples.length > LANVAN_CONFIG.CONCURRENT.SPEED_SAMPLE_SIZE) {
    networkSpeedSamples.shift();
  }

  // Adapt concurrency every N uploads
  totalUploadsProcessed++;
  if (totalUploadsProcessed % LANVAN_CONFIG.CONCURRENT.ADAPTATION_INTERVAL === 0) {
    const newOptimal = getOptimalConcurrency();
    if (newOptimal !== currentMaxConcurrent) {
      console.log(`📊 Adaptive concurrency: ${currentMaxConcurrent} → ${newOptimal} (avg speed: ${(networkSpeedSamples.reduce((a, b) => a + b, 0) / networkSpeedSamples.length).toFixed(1)} MB/s)`);
      currentMaxConcurrent = newOptimal;
      lastConcurrencyAdjustment = Date.now();

      // Update UI to reflect new concurrency
      updateUploadManager();

      // Start additional uploads if we increased concurrency
      if (newOptimal > activeUploads) {
        setTimeout(() => {
          startNextUpload();
        }, 100);
      }
    }
  }
}

// Function to create an upload item
function createUploadItem(file, uploadId) {
  // Check if AES encryption is enabled
  const isAESEnabled = isEncryptionEnabled && document.getElementById('enableEncryption').checked;

  return {
    id: uploadId,
    file: file,
    fileName: file.name,
    fileSize: file.size,
    status: 'queued', // queued, uploading, completed, error, cancelled
    progress: 0,
    uploadedBytes: 0,
    startTime: null,
    speed: 0,
    timeRemaining: 0,
    xhr: null,
    error: null,
    isAESEnabled: isAESEnabled, // Store AES encryption state
    uploadedChunks: 0, // For resume functionality
    totalChunks: 0, // For chunked uploads
    // 📊 Statistics tracking
    resumeCount: 0
  };
}

// Function to close settings menu when clicking outside
function closeSettingsOnOutsideClick(event) {
  const settingsMenu = document.getElementById('settingsMenu');
  const settingsBtn = document.getElementById('settingsBtn');

  if (!settingsMenu.contains(event.target) && !settingsBtn.contains(event.target)) {
    settingsMenu.style.display = 'none';
    document.removeEventListener('click', closeSettingsOnOutsideClick);
  }
}

// Function to get the current device ID
function getCurrentDeviceId() {
  let deviceId = sessionStorage.getItem('lanvan_device_id');
  if (!deviceId) {
    // Try to get actual device information
    const deviceInfo = getDeviceInfo();
    const timestamp = Date.now();
    const randomId = Math.random().toString(36).substring(2, 8);

    // Create readable device ID with actual device name if available
    deviceId = `${deviceInfo.name}_${timestamp}_${randomId}`;
    sessionStorage.setItem('lanvan_device_id', deviceId);

    console.log(`📱 New device session created: ${deviceInfo.displayName}`);
  }
  return deviceId;
}

// Function to get device information
function getDeviceInfo() {
  // Try multiple methods to get device name
  let deviceName = 'Unknown_Device';
  let displayName = 'Unknown Device';

  try {
    // Method 1: Try to get hostname if available (some browsers)
    if (typeof window.clientInformation !== 'undefined' && window.clientInformation.platform) {
      const platform = window.clientInformation.platform;
      deviceName = platform.replace(/\s+/g, '_');
    }

    // Method 2: Use navigator userAgent to detect device type
    const userAgent = navigator.userAgent;
    const browserInfo = getBrowserInfo(userAgent);

    // Method 3: Try to detect common device patterns
    if (userAgent.includes('Windows')) {
      if (userAgent.includes('Windows NT 10')) deviceName = 'Windows_PC';
      else if (userAgent.includes('Windows NT 6')) deviceName = 'Windows_Legacy';
      displayName = deviceName.replace('_', ' ');
    } else if (userAgent.includes('Mac')) {
      if (userAgent.includes('iPhone')) {
        deviceName = 'iPhone';
        displayName = 'iPhone';
      } else if (userAgent.includes('iPad')) {
        deviceName = 'iPad';
        displayName = 'iPad';
      } else {
        deviceName = 'Mac';
        displayName = 'Mac';
      }
    } else if (userAgent.includes('Android')) {
      deviceName = 'Android_Device';
      displayName = 'Android Device';
    } else if (userAgent.includes('Linux')) {
      deviceName = 'Linux_PC';
      displayName = 'Linux PC';
    }

    // Add browser info to make it more specific
    deviceName = `${deviceName}_${browserInfo.name}`;
    displayName = `${displayName} (${browserInfo.name})`;

  } catch (error) {
    console.log('Could not detect device info, using fallback');
    deviceName = 'Unknown_Device';
    displayName = 'Unknown Device';
  }

  return {
    name: deviceName,
    displayName: displayName
  };
}

// Function to save upload stats to device history
function saveToDeviceUploadHistory(stats) {
  try {
    const deviceId = getCurrentDeviceId();
    const sessionKey = `uploadHistory_${deviceId}`;
    const deviceHistory = getDeviceUploadHistory();

    // Add device/session info to stats
    const enhancedStats = {
      ...stats,
      deviceId: deviceId,
      sessionTimestamp: Date.now()
    };

    deviceHistory.unshift(enhancedStats); // Add to beginning (newest first)

    // Keep unlimited history for this session (no limit since it's session-specific)
    // Session will auto-clear when browser closes

    sessionStorage.setItem(sessionKey, JSON.stringify(deviceHistory));
    console.log(`📱 Saved to device history (${deviceId}):`, stats.type, stats.size, stats.time);
  } catch (e) {
    console.log('⚠️ Failed to save to device upload history:', e);
  }
}

/**
 * Function to display device logs with pagination
 * @param {Array} logs - Array of log objects to display
 * @param {HTMLElement} contentElement - Element to display log content
 * @param {HTMLElement} paginationElement - Element to display pagination controls
 */
function displayDeviceLogsWithPagination(logs, contentElement, paginationElement) {
  const itemsPerPage = 10;

  // Sort logs by timestamp (newest first) for individual file display
  const sortedLogs = logs.sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp));
  const totalPages = Math.ceil(sortedLogs.length / itemsPerPage);
  let currentPage = 1;

  function renderPage(page) {
    const startIndex = (page - 1) * itemsPerPage;
    const endIndex = startIndex + itemsPerPage;
    const pageItems = sortedLogs.slice(startIndex, endIndex);

    let historyHTML = '';
    pageItems.forEach((log, index) => {
      const globalIndex = startIndex + index;
      const isEven = globalIndex % 2 === 0;

      // Individual file display only - no batch grouping
      historyHTML += renderSingleUpload(log, isEven);
    });

    contentElement.innerHTML = historyHTML;
  }

  function renderPagination() {
    if (totalPages <= 1) {
      paginationElement.style.display = 'none';
      return;
    }

    paginationElement.style.display = 'block';
    let paginationHTML = `
      <div style="display: flex; justify-content: center; align-items: center; gap: 0.5rem; margin-top: 1rem;">
        <button onclick="uploadHistoryPagination.goToPage(${currentPage - 1})" 
                ${currentPage === 1 ? 'disabled' : ''} 
                class="pagination-button"
                style="padding: 0.4rem 0.8rem; border: 1px solid var(--border-color); background: var(--section-bg); border-radius: 4px; cursor: ${currentPage === 1 ? 'not-allowed' : 'pointer'}; color: var(--text-color) !important;">
          ◀ Prev
        </button>
        <span style="padding: 0.4rem 1rem; color: var(--text-color) !important; opacity: 0.8;">
          Page ${currentPage} of ${totalPages} (${logs.length} total uploads)
        </span>
        <button onclick="uploadHistoryPagination.goToPage(${currentPage + 1})" 
                ${currentPage === totalPages ? 'disabled' : ''} 
                class="pagination-button"
                style="padding: 0.4rem 0.8rem; border: 1px solid var(--border-color); background: var(--section-bg); border-radius: 4px; cursor: ${currentPage === totalPages ? 'not-allowed' : 'pointer'}; color: var(--text-color) !important;">
          Next ▶
        </button>
      </div>
    `;

    paginationElement.innerHTML = paginationHTML;
  }

  // Create global pagination controller
  window.uploadHistoryPagination = {
    goToPage: function(page) {
      if (page >= 1 && page <= totalPages) {
        currentPage = page;
        renderPage(currentPage);
        renderPagination();
      }
    }
  };

  // Initial render
  renderPage(currentPage);
  renderPagination();
}

// 🔧 Conditional Logging System - Production Performance Optimization
const DEBUG_MODE = false; // Set to true for development, false for production
const DEBUG_LEVELS = {
  ERROR: 0,   // Always shown (security, critical errors)
  WARN: 1,    // Important warnings
  INFO: 2,    // General information
  DEBUG: 3    // Detailed debugging (upload progress, etc.)
};

const currentLogLevel = DEBUG_MODE ? DEBUG_LEVELS.DEBUG : DEBUG_LEVELS.ERROR;

// Optimized logging functions
const log = {
  error: (msg, ...args) => {
    if (currentLogLevel >= DEBUG_LEVELS.ERROR) console.error('❌', msg, ...args);
  },
  warn: (msg, ...args) => {
    if (currentLogLevel >= DEBUG_LEVELS.WARN) console.warn('⚠️', msg, ...args);
  },
  info: (msg, ...args) => {
    if (currentLogLevel >= DEBUG_LEVELS.INFO) console.info('ℹ️', msg, ...args);
  },
  debug: (msg, ...args) => {
    if (currentLogLevel >= DEBUG_LEVELS.DEBUG) console.log('🔍', msg, ...args);
  },
  upload: (msg, ...args) => {
    if (currentLogLevel >= DEBUG_LEVELS.DEBUG) console.log('📤', msg, ...args);
  },
  network: (msg, ...args) => {
    if (currentLogLevel >= DEBUG_LEVELS.DEBUG) console.log('🌐', msg, ...args);
  }
};

// Clipboard WebSocket connection
function connectClipboardWS(showClipboardOnly) {
  const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws';
  const wsUrl = `${protocol}://${window.location.host}/ws/clipboard`;
  const ws = new WebSocket(wsUrl);

  ws.onopen = () => {
    log.network('Clipboard WebSocket connected');
    if (typeof refreshClipboardHistory === 'function') {
      setTimeout(() => refreshClipboardHistory(), 50);
    }
  };

  ws.onmessage = (event) => {
    if (event.data === 'refresh' && typeof refreshClipboardHistory === 'function') {
      refreshClipboardHistory();
    }
  };

  ws.onclose = () => {
    log.warn('Clipboard WebSocket disconnected, reconnecting...');
    setTimeout(() => connectClipboardWS(showClipboardOnly), 1000);
  };

  ws.onerror = () => {
    ws.close();
  };

  if (showClipboardOnly) {
    document.addEventListener('DOMContentLoaded', () => connectClipboardWS(true));
    window.addEventListener('beforeunload', () => ws.close());
  }
}
