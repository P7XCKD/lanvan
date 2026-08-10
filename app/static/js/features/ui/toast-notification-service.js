/**
 * @file toast-notification-service.js
 * @description Floating toast notification component for Lanvan.
 *              Coordinates user status alerts, upload progress messages, and persistence state.
 * @module ToastNotificationService
 */

(function (window) {
  'use strict';

  let toastTimeout = null;
  let lastToastMessage = '';
  let isPersistentToast = false;

  /**
   * Display a floating toast notification.
   * @param {string} message - Notification text
   * @param {number} [duration=3000] - Duration in ms (0 for persistent)
   * @param {Object} [transferData=null] - Optional detail transfer log payload
   * @param {string} [type='default'] - Toast type styling
   */
  function showToast(message, duration = 3000, transferData = null, type = 'default') {
    const isMobile = window.innerWidth <= 768;
    const bottomPos = isMobile ? '90px' : '28px';

    let toast = (window.DOM_CACHE && window.DOM_CACHE.toast) || document.getElementById('toast');
    if (!toast) {
      toast = document.createElement('div');
      toast.id = 'toast';
      toast.className = 'lanvan-toast';
      toast.style.cssText = 'position:fixed; left:50%; transform:translateX(-50%) translateY(12px); background:rgba(24, 26, 34, 0.94); color:#ffffff; padding:10px 22px; border-radius:24px; font-size:0.88rem; font-weight:600; z-index:999999; border:1px solid rgba(255,255,255,0.18); backdrop-filter:blur(14px); box-shadow:0 12px 36px rgba(0,0,0,0.5); display:none; opacity:0; transition:all 0.22s cubic-bezier(0.16, 1, 0.3, 1); pointer-events:auto; font-family:inherit; text-align:center; max-width:90vw; word-break:break-word;';
      document.body.appendChild(toast);
      if (window.DOM_CACHE) window.DOM_CACHE.toast = toast;
    }

    toast.style.bottom = bottomPos;
    toast.innerText = message;
    toast.style.display = 'block';

    if (transferData) {
      toast._transferData = transferData;
    }

    requestAnimationFrame(() => {
      toast.style.opacity = '1';
      toast.style.transform = 'translateX(-50%) translateY(0px)';
    });

    if (toastTimeout) {
      clearTimeout(toastTimeout);
      toastTimeout = null;
    }

    if (duration > 0) {
      toastTimeout = setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transform = 'translateX(-50%) translateY(12px)';
        setTimeout(() => {
          if (!isPersistentToast) {
            toast.style.display = 'none';
          }
        }, 220);
      }, duration);
    }
  }

  /**
   * Update the text content of active toast without resetting display state.
   * @param {string} message - Updated notification text
   */
  function updateToastContent(message) {
    const toast = (window.DOM_CACHE && window.DOM_CACHE.toast) || document.getElementById('toast');
    if (!toast) return;

    if (!isPersistentToast) {
      toast.innerText = message;
      lastToastMessage = message;
      toast.style.display = 'block';
      toast.style.backgroundColor = '#333';
      toast.style.whiteSpace = 'normal';
    }
  }

  /**
   * Alias for updateToastContent to support progress status calls.
   * @param {string} message - Progress message
   */
  function updateProgressToast(message) {
    updateToastContent(message);
  }

  /**
   * Hide and reset the current active toast notification.
   */
  function hideToast() {
    const toast = (window.DOM_CACHE && window.DOM_CACHE.toast) || document.getElementById('toast');
    if (!toast) return;

    if (isPersistentToast) return;

    if (toastTimeout) {
      clearTimeout(toastTimeout);
      toastTimeout = null;
    }

    Object.assign(toast.style, {
      opacity: '0',
      transform: 'translateX(-50%) translateY(20px)'
    });

    setTimeout(() => {
      if (!isPersistentToast) {
        toast.style.display = 'none';
        delete toast._transferData;
      }
    }, 300);
  }

  /**
   * Update toast position based on viewport breakpoint.
   */
  function updateToastPosition() {
    const toast = (window.DOM_CACHE && window.DOM_CACHE.toast) || document.getElementById('toast');
    if (!toast) return;
    const isMobile = window.innerWidth <= 768;
    toast.style.bottom = isMobile ? '90px' : '28px';
  }

  // Freeze immutable service interface
  const ToastNotificationService = Object.freeze({
    showToast: showToast,
    hideToast: hideToast,
    updateToastContent: updateToastContent,
    updateProgressToast: updateProgressToast,
    updateToastPosition: updateToastPosition
  });

  window.ToastNotificationService = ToastNotificationService;

  // Preserve global API backward compatibility aliases
  window.showToast = window.showToast || showToast;
  window.hideToast = window.hideToast || hideToast;
  window.updateToastContent = window.updateToastContent || updateToastContent;
  window.updateProgressToast = window.updateProgressToast || updateProgressToast;
  window.updateToastPosition = window.updateToastPosition || updateToastPosition;

})(window);
