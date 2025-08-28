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
