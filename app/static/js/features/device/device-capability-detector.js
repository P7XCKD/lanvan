/**
 * @file device-capability-detector.js
 * @description Hardware capability and guest-device performance detector for Lanvan.
 *              Evaluates device memory, CPU concurrency, and storage quotas to optimize transfer behaviors.
 * @module DeviceCapabilityDetector
 */

(function (window) {
  'use strict';

  /**
   * Determines whether the device should be treated as constrained or operating in guest mode.
   * @returns {boolean} `true` if the device meets any constrained-device criterion or detection fails, `false` otherwise.
   */
  function detectGuestDevice() {
    try {
      const isLimitedMemory = navigator.deviceMemory && navigator.deviceMemory <= 2;
      const isLimitedConcurrency = navigator.hardwareConcurrency && navigator.hardwareConcurrency <= 2;

      const isIncognito = typeof window.checkIncognitoMode === 'function' ? window.checkIncognitoMode() : false;
      const hasLimitedStorage = typeof checkStorageQuota === 'function' ? checkStorageQuota() : false;
      const isSlowDevice = typeof checkDevicePerformance === 'function' ? checkDevicePerformance() : false;

      return isLimitedMemory || isLimitedConcurrency || isIncognito || hasLimitedStorage || isSlowDevice;
    } catch (e) {
      console.log('Device detection failed, assuming guest device for safety:', e);
      return true;
    }
  }

  /**
   * Checks storage availability without waiting for the quota estimate.
   * @return {boolean} `true` if an error occurs while accessing storage, `false` otherwise.
   */
  function checkStorageQuota() {
    try {
      if ('storage' in navigator && 'estimate' in navigator.storage) {
        navigator.storage.estimate().then(estimate => {
          const quota = estimate.quota || 0;
          return quota < 1024 * 1024 * 1024;
        });
      }
      return false;
    } catch (e) {
      return true;
    }
  }

  /**
   * Determines whether CPU performance indicates a constrained device.
   * @returns {boolean} `true` if the benchmark exceeds 50 milliseconds or an error occurs, `false` otherwise.
   */
  function checkDevicePerformance() {
    try {
      const start = performance.now();
      for (let i = 0; i < 100000; i++) {
        Math.random();
      }
      const duration = performance.now() - start;
      return duration > 50;
    } catch (e) {
      return true;
    }
  }

  // Freeze immutable detector interface
  const DeviceCapabilityDetector = Object.freeze({
    detectGuestDevice: detectGuestDevice,
    checkStorageQuota: checkStorageQuota,
    checkDevicePerformance: checkDevicePerformance
  });

  window.DeviceCapabilityDetector = DeviceCapabilityDetector;

  // Preserve global backward compatibility aliases
  window.detectGuestDevice = window.detectGuestDevice || detectGuestDevice;
  window.checkStorageQuota = window.checkStorageQuota || checkStorageQuota;
  window.checkDevicePerformance = window.checkDevicePerformance || checkDevicePerformance;

})(window);
