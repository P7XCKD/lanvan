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
      '&': '&amp;',
      '<': '&lt;',
      '>': '&gt;',
      '"': '&quot;',
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

})(typeof window !== 'undefined' ? window : this);
