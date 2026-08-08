/**
 * File Utilities Module
 * 
 * Provides utility functions for file handling, formatting, browser detection,
 * and security features across the application.
 */

// Global configuration object fallback
window.LANVAN_CONFIG = window.LANVAN_CONFIG || {
  CHUNK_THRESHOLD: 100 * 1024 * 1024, // 100MB
  MAX_CONCURRENT_UPLOADS: 3,
  DEFAULT_PAGE_SIZE: 50,
  INTERVALS: {
    PROGRESS_UPDATE: 100, // ms
    AUTO_REFRESH: 5000    // ms
  }
};

/**
 * Format file size in bytes to human-readable string
 * @param {number} bytes - File size in bytes
 * @param {number} decimals - Number of decimal places
 * @returns {string} Formatted size string (e.g. "1.5 MB")
 */
function formatFileSize(bytes, decimals = 2) {
  if (bytes === 0) return '0 Bytes';

  const k = 1024;
  const dm = decimals < 0 ? 0 : decimals;
  const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB', 'PB', 'EB', 'ZB', 'YB'];

  const i = Math.floor(Math.log(bytes) / Math.log(k));

  return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + ' ' + sizes[i];
}

/**
 * Format transfer speed in bytes per second to human-readable string
 * @param {number} bytesPerSecond - Transfer speed in bytes/sec
 * @returns {string} Formatted speed string (e.g. "12.5 MB/s")
 */
function formatSpeed(bytesPerSecond) {
  if (bytesPerSecond === 0 || !bytesPerSecond || isNaN(bytesPerSecond)) return '0 B/s';
  return formatFileSize(bytesPerSecond) + '/s';
}

/**
 * Format remaining time in seconds to human-readable string
 * @param {number} seconds - Remaining time in seconds
 * @returns {string} Formatted time string (e.g. "2m 15s")
 */
function formatRemainingTime(seconds) {
  if (seconds === Infinity || isNaN(seconds) || seconds < 0) return 'Calculating...';
  if (seconds === 0) return 'Done';

  if (seconds < 60) {
    return Math.round(seconds) + 's';
  } else if (seconds < 3600) {
    const minutes = Math.floor(seconds / 60);
    const remainingSeconds = Math.round(seconds % 60);
    return minutes + 'm ' + remainingSeconds + 's';
  } else {
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    return hours + 'h ' + minutes + 'm';
  }
}

/**
 * Get file extension from filename
 * @param {string} filename - Name of file
 * @returns {string} File extension without dot, lowercase
 */
function getFileExtension(filename) {
  if (!filename || typeof filename !== 'string') return '';
  const lastDotIndex = filename.lastIndexOf('.');
  if (lastDotIndex === -1 || lastDotIndex === 0) return '';
  return filename.substring(lastDotIndex + 1).toLowerCase();
}

/**
 * Check if a file extension represents an image
 * @param {string} ext - File extension
 * @returns {boolean} True if image extension
 */
function isImageExtension(ext) {
  const imageExts = ['jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp', 'svg', 'ico'];
  return imageExts.includes(ext ? ext.toLowerCase() : '');
}

/**
 * Check if a file extension represents a video
 * @param {string} ext - File extension
 * @returns {boolean} True if video extension
 */
function isVideoExtension(ext) {
  const videoExts = ['mp4', 'webm', 'ogg', 'mov', 'avi', 'mkv', 'm4v', 'flv'];
  return videoExts.includes(ext ? ext.toLowerCase() : '');
}

/**
 * Check if a file extension represents an audio file
 * @param {string} ext - File extension
 * @returns {boolean} True if audio extension
 */
function isAudioExtension(ext) {
  const audioExts = ['mp3', 'wav', 'ogg', 'aac', 'flac', 'm4a', 'wma'];
  return audioExts.includes(ext ? ext.toLowerCase() : '');
}

/**
 * Check if a file extension represents a document
 * @param {string} ext - File extension
 * @returns {boolean} True if document extension
 */
function isDocumentExtension(ext) {
  const docExts = ['pdf', 'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx', 'txt', 'rtf', 'csv'];
  return docExts.includes(ext ? ext.toLowerCase() : '');
}

/**
 * Check if a file extension represents an archive
 * @param {string} ext - File extension
 * @returns {boolean} True if archive extension
 */
function isArchiveExtension(ext) {
  const archiveExts = ['zip', 'rar', '7z', 'tar', 'gz', 'bz2', 'xz'];
  return archiveExts.includes(ext ? ext.toLowerCase() : '');
}

/**
 * Escape HTML special characters to prevent XSS
 * @param {string} str - String to escape
 * @returns {string} Escaped HTML string
 */
function escapeHtml(str) {
  if (typeof str !== 'string') return str;
  return str
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

/**
 * Sanitize filename by removing dangerous characters
 * @param {string} filename - Filename to sanitize
 * @returns {string} Sanitized filename
 */
function sanitizeFilename(filename) {
  if (typeof filename !== 'string') return '';
  return filename
    .replace(/[/\\?%*:|"<>]/g, '_')
    .replace(/\.\./g, '_')
    .trim();
}

/**
 * Get device performance rating
 * @returns {string} Performance rating: 'low', 'medium', 'high'
 */
function getDevicePerformanceRating() {
  try {
    const memory = navigator.deviceMemory || 4; // Default to 4GB if API unavailable
    const cores = navigator.hardwareConcurrency || 4;

    if (memory <= 2 || cores <= 2) {
      return 'low';
    } else if (memory <= 4 || cores <= 4) {
      return 'medium';
    } else {
      return 'high';
    }
  } catch (e) {
    return 'medium';
  }
}

/**
 * Check if incognito/private mode is likely active
 * @returns {boolean} True if private browsing detected
 */
function isIncognitoMode() {
  try {
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
 * Get appropriate icon for clipboard item type
 * @param {Object} item - Clipboard item with type and content_type
 * @returns {string} Emoji icon for the item type
 */
function getClipboardItemIcon(item) {
  if (item.type === 'file') {
    switch (item.content_type) {
      case 'image': return '🖼️';
      case 'text': return '📄';
      case 'document': return '📁';
      default: return '📎';
    }
  } else {
    switch (item.content_type) {
      case 'image_base64': return '🖼️';
      case 'url': return '🔗';
      default: return '📋';
    }
  }
}

if (typeof window !== 'undefined') {
  window.getClipboardItemIcon = getClipboardItemIcon;
  window.formatClipboardSize = window.formatClipboardSize || formatFileSize;
}

/**
 * Get control buttons HTML for upload item
 * @param {Object} uploadItem - Upload item with status and id
 * @returns {string} HTML string for control buttons
 */
function getControlButtons(uploadItem) {
  switch (uploadItem.status) {
    case 'UPLOADING':
      return `<button class="upload-control-btn pause" onclick="pauseUpload(${uploadItem.id})" title="Pause">⏸</button><button class="upload-control-btn cancel" onclick="cancelUpload(${uploadItem.id})" title="Cancel upload">Cancel</button>`;
    case 'PAUSED':
      return `<button class="upload-control-btn resume" onclick="resumeUpload(${uploadItem.id})" title="Resume">▶</button><button class="upload-control-btn cancel" onclick="cancelUpload(${uploadItem.id})" title="Cancel upload">Cancel</button>`;
    case 'QUEUED':
      return `<button class="upload-control-btn cancel" onclick="cancelUpload(${uploadItem.id})" title="Cancel upload">Cancel</button>`;
    default:
      return '';
  }
}

// Export utilities to window object for global availability
if (typeof window !== 'undefined') {
  window.formatFileSize = formatFileSize;
  window.formatSpeed = formatSpeed;
  window.formatRemainingTime = formatRemainingTime;
  window.getFileExtension = getFileExtension;
  window.isImageExtension = isImageExtension;
  window.isVideoExtension = isVideoExtension;
  window.isAudioExtension = isAudioExtension;
  window.isDocumentExtension = isDocumentExtension;
  window.isArchiveExtension = isArchiveExtension;
  window.escapeHtml = escapeHtml;
  window.sanitizeFilename = sanitizeFilename;
  window.getDevicePerformanceRating = getDevicePerformanceRating;
  window.isIncognitoMode = isIncognitoMode;
  window.getBrowserInfo = getBrowserInfo;
  window.getControlButtons = getControlButtons;
}
