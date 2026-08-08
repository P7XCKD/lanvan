/**
 * Shared Data Contract & Utility Helpers for Lanvan System
 * Centralizes common formatters, escape helpers, and defensive getters.
 */

(function (window) {
  'use strict';

  function getItemSize(item) {
    if (!item) return 0;
    if (typeof item.fileSize === 'number' && !isNaN(item.fileSize)) {
      return item.fileSize;
    }
    if (item.file && typeof item.file.size === 'number' && !isNaN(item.file.size)) {
      return item.file.size;
    }
    if (typeof item.size === 'number' && !isNaN(item.size)) {
      return item.size;
    }
    return 0;
  }

  function getItemName(item) {
    if (!item) return 'Unknown';
    if (item.fileName && typeof item.fileName === 'string') {
      return item.fileName;
    }
    if (item.file && item.file.name && typeof item.file.name === 'string') {
      return item.file.name;
    }
    if (item.name && typeof item.name === 'string') {
      return item.name;
    }
    return 'Unknown';
  }

  function getItemProgress(item) {
    if (!item || typeof item.progress !== 'number' || isNaN(item.progress)) {
      return 0;
    }
    return Math.min(100, Math.max(0, item.progress));
  }

  function getItemFolder(item) {
    if (!item) return '';
    var folder = item.targetDir || item.parent_path || item.folder || '';
    if (folder === 'Home' || folder === 'Home/') {
      return '';
    }
    return folder;
  }

  function escapeHtml(text) {
    if (text === null || text === undefined) return '';
    var map = {
      '&': '&',
      '<': '<',
      '>': '>',
      '"': '"',
      "'": '&#039;'
    };
    return String(text).replace(/[&<>"']/g, function (m) { return map[m]; });
  }

  function formatBytes(bytes, decimals) {
    if (bytes === 0 || !bytes) return '0 Bytes';
    var k = 1024;
    var dm = decimals < 0 ? 0 : (decimals || 2);
    var sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB', 'PB'];
    var i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + ' ' + sizes[i];
  }

  function formatFileSize(bytes) {
    return formatBytes(bytes, 1);
  }

  function formatSpeed(bytesPerSecond) {
    if (bytesPerSecond === 0 || !bytesPerSecond) return '0 B/s';
    var k = 1024;
    var sizes = ['B/s', 'KB/s', 'MB/s', 'GB/s'];
    var i = Math.floor(Math.log(bytesPerSecond) / Math.log(k));
    return parseFloat((bytesPerSecond / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
  }

  function getBrowserInfo(ua) {
    var userAgent = ua || navigator.userAgent;
    if (userAgent.includes('Chrome')) return { name: 'Chrome' };
    if (userAgent.includes('Firefox')) return { name: 'Firefox' };
    if (userAgent.includes('Safari') && !userAgent.includes('Chrome')) return { name: 'Safari' };
    if (userAgent.includes('Edg')) return { name: 'Edge' };
    return { name: 'Browser' };
  }

  function getDeviceInfo() {
    var deviceName = 'Unknown_Device';
    var displayName = 'Unknown Device';
    try {
      var userAgent = navigator.userAgent;
      var browserInfo = getBrowserInfo(userAgent);
      if (userAgent.includes('Windows')) {
        deviceName = userAgent.includes('Windows NT 10') ? 'Windows_PC' : 'Windows_Legacy';
        displayName = deviceName.replace('_', ' ');
      } else if (userAgent.includes('Mac')) {
        if (userAgent.includes('iPhone')) { deviceName = 'iPhone'; displayName = 'iPhone'; }
        else if (userAgent.includes('iPad')) { deviceName = 'iPad'; displayName = 'iPad'; }
        else { deviceName = 'Mac'; displayName = 'Mac'; }
      } else if (userAgent.includes('Android')) {
        deviceName = 'Android_Device'; displayName = 'Android Device';
      } else if (userAgent.includes('Linux')) {
        deviceName = 'Linux_PC'; displayName = 'Linux PC';
      }
      deviceName = deviceName + '_' + browserInfo.name;
      displayName = displayName + ' (' + browserInfo.name + ')';
    } catch (e) {
      deviceName = 'Unknown_Device';
      displayName = 'Unknown Device';
    }
    return { name: deviceName, displayName: displayName };
  }

  function getCurrentDeviceId() {
    var deviceId = sessionStorage.getItem('Lanvan_device_id');
    if (!deviceId) {
      var deviceInfo = getDeviceInfo();
      var timestamp = Date.now();
      var randomId = Math.random().toString(36).substring(2, 8);
      deviceId = deviceInfo.name + '_' + timestamp + '_' + randomId;
      sessionStorage.setItem('Lanvan_device_id', deviceId);
    }
    return deviceId;
  }

  window.LANVAN_DEBUG = false;
  function logDebug() {
    if (window.LANVAN_DEBUG && typeof console !== 'undefined' && console.log) {
      console.log.apply(console, arguments);
    }
  }

  /**
   * Helper: format seconds into "Xm Ys" or "Ys".
   */
  function formatEta(seconds) {
    if (!seconds || seconds <= 0 || seconds === Infinity) return '';
    var s = Math.round(seconds);
    if (s < 60) return s + 's';
    var m = Math.floor(s / 60);
    var r = s % 60;
    return m + 'm' + (r > 0 ? ' ' + r + 's' : '');
  }

  /**
   * Pure function: builds an UploadBatchSummary from an array of upload items.
   * Never reads global state. Accepts any array of upload item objects.
   *
   * Percentage is BYTE-BASED: uploadedBytes / effectiveTotalBytes.
   * effectiveTotalBytes = totalBytes - cancelledBytes.
   *
  /**
   * Pure function: calculates authoritative UploadBatchSummary from uploadItems and metrics.
   * Never accesses DOM, never reads window.uploadQueue directly.
   * @param {Array} uploadItems - Array of upload items
   * @param {Object} [metrics] - Live metrics { speed, eta }
   * @returns {Object} UploadBatchSummary
   */
  function getUploadBatchSummary(uploadItems, metrics) {
    var items = Array.isArray(uploadItems) ? uploadItems : [];
    var mSpeed = (metrics && metrics.speed !== undefined && metrics.speed !== null) ? metrics.speed : null;
    var mEta = (metrics && metrics.eta !== undefined && metrics.eta !== null) ? metrics.eta : null;

    var totalFiles = items.length;
    var completedFiles = 0;
    var activeFiles = 0;
    var queuedFiles = 0;
    var pausedFiles = 0;
    var cancelledFiles = 0;
    var failedFiles = 0;

    var totalBytes = 0;
    var cancelledBytes = 0;
    var uploadedBytes = 0;
    var sumSpeed = 0;
    var maxEtaSeconds = 0;

    for (var i = 0; i < items.length; i++) {
      var item = items[i];
      if (!item) continue;

      var sz = (typeof getItemSize === 'function') ? getItemSize(item) : (item.fileSize || (item.file && item.file.size) || 0);
      var status = (typeof getItemStatus === 'function') ? getItemStatus(item) : (item.status || 'QUEUED');

      totalBytes += sz;
      if (status === 'CANCELLED' || status === 'DELETED') {
        cancelledFiles++;
        var cancelledDone = item.bytesUploaded || item.uploadedBytes || 0;
        if (!cancelledDone && item.progress && sz) {
          cancelledDone = Math.round((sz * item.progress) / 100);
        }
        var unuploadedBytes = Math.max(0, sz - cancelledDone);
        cancelledBytes += unuploadedBytes;
        uploadedBytes += cancelledDone;
      } else if (status === 'COMPLETED') {
        completedFiles++;
        uploadedBytes += sz;
      } else if (status === 'FAILED' || status === 'ERROR') {
        failedFiles++;
      } else if (status === 'PAUSED') {
        pausedFiles++;
        var pausedDone = item.bytesUploaded || item.uploadedBytes || 0;
        if (!pausedDone && item.progress && sz) {
          pausedDone = Math.round((sz * item.progress) / 100);
        }
        uploadedBytes += pausedDone;
      } else if (status === 'UPLOADING' || status === 'PROCESSING') {
        activeFiles++;
        var activeDone = item.bytesUploaded || item.uploadedBytes || 0;
        if (!activeDone && item.progress && sz) {
          activeDone = Math.round((sz * item.progress) / 100);
        }
        uploadedBytes += activeDone;
        sumSpeed += (item.speed || 0);

        var remItem = sz - activeDone;
        if (item.speed > 0 && remItem > 0) {
          var etaItem = remItem / item.speed;
          if (etaItem > maxEtaSeconds) maxEtaSeconds = etaItem;
        }
      } else {
        queuedFiles++;
      }
    }

    var effectiveTotalFiles = Math.max(0, totalFiles - cancelledFiles);
    var effectiveTotalBytes = Math.max(0, totalBytes - cancelledBytes);
    var remainingBytes = Math.max(0, totalBytes - uploadedBytes);

    var rawPercent = totalBytes > 0
      ? Math.min(100, Math.floor((uploadedBytes / totalBytes) * 100))
      : 0;

    // Compute explicit batch state
    var state = 'IDLE';
    if (totalFiles === 0) {
      state = 'IDLE';
    } else if (activeFiles > 0 || queuedFiles > 0) {
      state = 'UPLOADING';
    } else if (pausedFiles > 0 && activeFiles === 0 && queuedFiles === 0) {
      state = 'PAUSED';
    } else if (failedFiles > 0 && activeFiles === 0 && queuedFiles === 0) {
      state = 'FAILED';
    } else if (cancelledFiles > 0 && activeFiles === 0 && queuedFiles === 0) {
      state = 'CANCELLED';
    } else if (completedFiles === effectiveTotalFiles && effectiveTotalFiles > 0) {
      state = 'COMPLETED';
    }

    var batchEtaSeconds = (sumSpeed > 0 && remainingBytes > 0) ? (remainingBytes / sumSpeed) : 0;

    var speedStr = (state === 'UPLOADING')
      ? (mSpeed !== null ? (typeof mSpeed === 'number' ? formatSpeed(mSpeed) : String(mSpeed)) : (sumSpeed > 0 ? formatSpeed(sumSpeed) : ''))
      : '';

    var etaStr = (state === 'UPLOADING')
      ? (mEta !== null ? (typeof mEta === 'number' ? formatEta(mEta) : String(mEta)) : (batchEtaSeconds > 0 ? formatEta(batchEtaSeconds) : ''))
      : '';

    // Monotonic Progress Guard (Rule 7 Invariant): Progress MUST NEVER move backward during active transfers
    var percent = rawPercent;
    if (state === 'UPLOADING' || state === 'PAUSED') {
      if (typeof window._maxBatchPercent === 'undefined') {
        window._maxBatchPercent = 0;
      }
      percent = Math.max(rawPercent, window._maxBatchPercent);
      window._maxBatchPercent = percent;
    } else if (state === 'COMPLETED') {
      percent = 100;
      window._maxBatchPercent = 100;
    } else {
      window._maxBatchPercent = 0;
    }

    return {
      totalFiles: totalFiles,
      effectiveTotalFiles: effectiveTotalFiles,
      completedFiles: completedFiles,
      activeFiles: activeFiles,
      queuedFiles: queuedFiles,
      pausedFiles: pausedFiles,
      cancelledFiles: cancelledFiles,
      failedFiles: failedFiles,
      totalBytes: totalBytes,
      cancelledBytes: cancelledBytes,
      effectiveTotalBytes: effectiveTotalBytes,
      uploadedBytes: uploadedBytes,
      remainingBytes: remainingBytes,
      percent: percent,
      speed: speedStr,
      eta: etaStr,
      state: state
    };
  }

  function buildUploadBatchSummary(uploadItems, metrics) {
    return getUploadBatchSummary(uploadItems, metrics);
  }

  /**
   * Pure formatter: converts UploadBatchSummary to two-line display strings.
   * @param {Object} summary - Output from getUploadBatchSummary()
   * @returns {Object} { line1, line2, percent, state }
   */
  function formatUploadBatchStatus(summary) {
    if (!summary || summary.state === 'IDLE' || summary.totalFiles === 0) {
      return { line1: "No active uploads", line2: "Ready", percent: 0, state: "IDLE" };
    }

    var line1 = "";
    var line2 = "";

    switch (summary.state) {
      case 'UPLOADING':
        // Byte-weighted processed file index: maps overall byte percentage monotonically to [1, effectiveTotalFiles]
        var visibleProcessedFiles = summary.effectiveTotalFiles > 0
          ? Math.max(1, Math.min(summary.effectiveTotalFiles, Math.ceil((summary.percent / 100) * summary.effectiveTotalFiles)))
          : 0;
        line1 = "Uploading " + visibleProcessedFiles + " of " + summary.effectiveTotalFiles + " files";

        var parts = [];
        if (summary.speed) {
          parts.push(summary.speed);
        } else {
          var queue = (typeof window !== 'undefined' && window.uploadQueue) ? window.uploadQueue : [];
          var activeItem = null;
          for (var qIdx = 0; qIdx < queue.length; qIdx++) {
            if (queue[qIdx] && queue[qIdx].status === 'UPLOADING' && queue[qIdx].speed > 0) {
              activeItem = queue[qIdx];
              break;
            }
          }
          if (activeItem && typeof formatSpeed === 'function') {
            parts.push(formatSpeed(activeItem.speed));
          } else {
            parts.push("Calculating...");
          }
        }
        line2 = parts.join(" • ");
        break;

      case 'PAUSED':
        line1 = "Upload paused";
        line2 = "Resume to continue";
        break;

      case 'COMPLETED':
        line1 = "Uploads completed";
        line2 = summary.completedFiles + " files uploaded successfully";
        break;

      case 'CANCELLED':
        line1 = "Upload completed";
        line2 = summary.completedFiles + " uploaded • " + summary.cancelledFiles + " cancelled";
        break;

      case 'FAILED':
        line1 = "Upload completed with errors";
        line2 = summary.completedFiles + " uploaded • " + summary.failedFiles + " failed";
        break;

      default:
        line1 = "No active uploads";
        line2 = "Ready";
        break;
    }

    return {
      line1: line1,
      line2: line2,
      speed: summary.speed || "",
      eta: summary.eta || "",
      percent: summary.percent,
      state: summary.state
    };
  }

  // Export helpers globally if not already defined
  window.getItemSize = window.getItemSize || getItemSize;
  window.getItemName = window.getItemName || getItemName;
  window.getItemProgress = window.getItemProgress || getItemProgress;
  window.getItemFolder = window.getItemFolder || getItemFolder;
  window.escapeHtml = window.escapeHtml || escapeHtml;
  window.formatBytes = window.formatBytes || formatBytes;
  window.formatFileSize = window.formatFileSize || formatFileSize;
  window.formatSpeed = window.formatSpeed || formatSpeed;
  window.getDeviceInfo = window.getDeviceInfo || getDeviceInfo;
  window.getCurrentDeviceId = window.getCurrentDeviceId || getCurrentDeviceId;
  window.logDebug = window.logDebug || logDebug;
  window.getUploadBatchSummary = getUploadBatchSummary;
  window.buildUploadBatchSummary = getUploadBatchSummary;
  window.formatUploadBatchStatus = formatUploadBatchStatus;

})(typeof window !== 'undefined' ? window : this);