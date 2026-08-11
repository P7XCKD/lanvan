/**
 * @file server-shutdown-monitor.js
 * @description Encapsulates background server status health check polling,
 *              theme-aware centered offline notification UI, graceful upload cancellation,
 *              and automatic seamless workspace recovery upon server reconnection.
 * @module ServerShutdownMonitor
 */

(function () {
  'use strict';

  let shutdownCheckInterval = null;
  let serverShutdown = false;

  /**
   * Starts background server status monitoring loop (every 2s).
   */
  function startServerStatusMonitoring() {
    if (shutdownCheckInterval) return;

    shutdownCheckInterval = setInterval(async () => {
      try {
        const response = await fetch('/api/server-status', {
          method: 'GET',
          headers: { 'Content-Type': 'application/json' }
        });

        if (!response.ok || response.status === 503) {
          if (!serverShutdown) {
            handleServerShutdown('Server connection lost - server may have been shut down');
          }
          return;
        }

        const data = await response.json();
        if (data.shutdown) {
          if (!serverShutdown) {
            const shutdownMessage = data.message || 'Server is shutting down gracefully';
            const timeRemaining = data.timeRemaining || 5;
            handleServerShutdown(shutdownMessage, timeRemaining);
          }
        } else {
          // Server is online! If previously shut down, perform automatic seamless recovery
          if (serverShutdown) {
            handleServerRecovery();
          }
        }
      } catch (error) {
        // Network error - server appears to be offline
        if (!serverShutdown) {
          handleServerShutdown('Server connection failed - server appears to be offline');
        }
      }
    }, 2000);
  }

  /**
   * Restores the workspace after the server becomes available again.
   */
  function handleServerRecovery() {
    console.log(' Server connection restored - auto-recovering workspace...');
    serverShutdown = false;

    const overlay = document.getElementById('shutdownOverlay');
    if (overlay) {
      const pill = overlay.querySelector('.shutdown-pill-container');
      if (pill) {
        pill.style.borderColor = 'rgba(34, 197, 94, 0.4)';
        pill.innerHTML = `
          <div style="width: 10px; height: 10px; background: #22c55e; border-radius: 50%; box-shadow: 0 0 10px rgba(34, 197, 94, 0.6); flex-shrink: 0;"></div>
          <span>Server is Online</span>
        `;
      }

      setTimeout(() => {
        overlay.style.transition = 'opacity 0.4s ease';
        overlay.style.opacity = '0';
        setTimeout(() => {
          if (overlay.parentNode) overlay.parentNode.removeChild(overlay);
        }, 400);
      }, 1000);
    }

    if (typeof window.showToast === 'function') {
      window.showToast(' Server is back online!', 3000);
    }

    if (typeof window.startAutoRefresh === 'function') window.startAutoRefresh();
    if (typeof window.refreshFileList === 'function') window.refreshFileList();
    if (typeof window.connectWebSocket === 'function') window.connectWebSocket();
  }

  /**
   * Displays a scheduled shutdown warning and updates it until the countdown completes.
   * @param {string} message - The warning message to display.
   * @param {number} countdown - The remaining time in seconds.
   */
  function showShutdownWarning(message, countdown) {
    const warningToast = ` ${message} (${countdown}s)`;
    if (typeof window.showToast === 'function') {
      window.showToast(warningToast, 0, null, 'warning');
    }

    let remainingTime = countdown;
    const countdownInterval = setInterval(() => {
      remainingTime--;
      if (remainingTime > 0) {
        const updatedWarning = ` ${message} (${remainingTime}s)`;
        if (typeof window.updateToastContent === 'function') {
          window.updateToastContent(updatedWarning);
        }
      } else {
        clearInterval(countdownInterval);
        if (typeof window.updateToastContent === 'function') {
          window.updateToastContent(' SERVER IS SHUT DOWN - All operations halted');
        }
        document.body.style.borderTop = '5px solid #dc3545';
        console.log(' Server shutdown completed - final message displayed');
      }
    }, 1000);

    document.body.style.borderTop = '5px solid #ffc107';
    console.log(` Shutdown warning: ${message} - ${countdown}s remaining`);
  }

  /**
   * Marks the server as offline, cancels active uploads, pauses auto-refresh, and displays a theme-aware blocking overlay.
   * @param {string} reason - The reason the server was detected as offline.
   * @param {number} gracefulTime - The graceful shutdown duration in milliseconds.
   */
  function handleServerShutdown(reason = 'Server has been shut down', gracefulTime = 0) {
    if (serverShutdown) return;
    serverShutdown = true;

    // Stop active uploads gracefully
    if (Array.isArray(window.uploadQueue) && window.uploadQueue.length > 0) {
      window.uploadQueue.forEach(item => {
        if (item) {
          if (item.xhr) item.xhr.abort();
          if (item.currentXhr) item.currentXhr.abort();
          item.status = 'CANCELLED';
          item.error = 'Server shutdown';
        }
      });
      if (typeof window.updateUploadManager === 'function') window.updateUploadManager();
    }

    if (typeof window.pauseAutoRefresh === 'function') window.pauseAutoRefresh();

    // Detect theme mode dynamically (Light vs Dark Mode)
    const isLight = document.body.classList.contains('light-theme') ||
                    document.documentElement.classList.contains('light-theme') ||
                    document.documentElement.dataset.theme === 'light' ||
                    localStorage.getItem('lanvan_theme') === 'light';

    const overlayBg = isLight ? 'rgba(255, 255, 255, 0.55)' : 'rgba(15, 23, 42, 0.45)';
    const pillBg = isLight ? '#ffffff' : '#0f172a';
    const pillColor = isLight ? '#0f172a' : '#ffffff';
    const pillShadow = isLight 
      ? '0 12px 30px rgba(0, 0, 0, 0.12), 0 0 15px rgba(239, 68, 68, 0.15)' 
      : '0 15px 35px rgba(15, 23, 42, 0.4), 0 0 20px rgba(239, 68, 68, 0.2)';

    let overlay = document.getElementById('shutdownOverlay');
    if (!overlay) {
      overlay = document.createElement('div');
      overlay.id = 'shutdownOverlay';
      overlay.style.cssText = `
        position: fixed;
        top: 0;
        left: 0;
        width: 100vw;
        height: 100vh;
        background: ${overlayBg};
        backdrop-filter: blur(4px);
        -webkit-backdrop-filter: blur(4px);
        z-index: 10000;
        display: flex;
        align-items: center;
        justify-content: center;
        pointer-events: all;
        cursor: not-allowed;
        animation: shutdownFadeIn 0.3s ease;
      `;

      const style = document.createElement('style');
      style.textContent = `
        @keyframes shutdownFadeIn {
          from { opacity: 0; }
          to { opacity: 1; }
        }
        @keyframes shutdownScaleUp {
          from { transform: scale(0.9); opacity: 0; }
          to { transform: scale(1); opacity: 1; }
        }
        @keyframes shutdownRedPulse {
          0% { box-shadow: 0 0 0 0 rgba(239, 68, 68, 0.8); }
          70% { box-shadow: 0 0 0 10px rgba(239, 68, 68, 0); }
          100% { box-shadow: 0 0 0 0 rgba(239, 68, 68, 0); }
        }
      `;
      document.head.appendChild(style);

      const pill = document.createElement('div');
      pill.className = 'shutdown-pill-container';
      pill.style.cssText = `
        background: ${pillBg};
        color: ${pillColor};
        border: 1px solid rgba(239, 68, 68, 0.4);
        box-shadow: ${pillShadow};
        border-radius: 50px;
        padding: 0.85rem 1.65rem;
        display: flex;
        align-items: center;
        gap: 0.75rem;
        font-size: 0.95rem;
        font-weight: 600;
        letter-spacing: 0.01em;
        pointer-events: auto;
        cursor: not-allowed;
        animation: shutdownScaleUp 0.3s cubic-bezier(0.16, 1, 0.3, 1);
      `;

      pill.innerHTML = `
        <div style="width: 10px; height: 10px; background: #ef4444; border-radius: 50%; animation: shutdownRedPulse 1.5s infinite; flex-shrink: 0;"></div>
        <div style="display: flex; flex-direction: column; align-items: flex-start; text-align: left;">
          <span style="font-weight: 600; font-size: 0.95rem; line-height: 1.2;">Server is Offline</span>
          <span style="font-size: 0.78rem; opacity: 0.75; font-weight: 400; margin-top: 2px;">Ask host to start Lanvan</span>
        </div>
      `;

      overlay.appendChild(pill);
      document.body.appendChild(overlay);
    }

    console.error(` Server shutdown detected:`, {
      reason: reason,
      timestamp: new Date().toISOString(),
      gracefulTime: gracefulTime,
      uploadsActive: Array.isArray(window.uploadQueue) ? window.uploadQueue.length : 0,
      deviceInfo: navigator.userAgent,
      url: location.href
    });

    try {
      const shutdownInfo = {
        timestamp: Date.now(),
        reason: reason,
        url: location.href,
        uploadsLost: Array.isArray(window.uploadQueue) ? window.uploadQueue.length : 0
      };
      localStorage.setItem('lastServerShutdown', JSON.stringify(shutdownInfo));
    } catch (e) {
      console.log('Could not save shutdown info to localStorage');
    }
  }

  // Expose namespace & global aliases for backward compatibility
  window.ServerShutdownMonitor = {
    startServerStatusMonitoring,
    handleServerRecovery,
    showShutdownWarning,
    handleServerShutdown
  };

  window.startServerStatusMonitoring = startServerStatusMonitoring;
  window.handleServerRecovery = handleServerRecovery;
  window.showShutdownWarning = showShutdownWarning;
  window.handleServerShutdown = handleServerShutdown;
})();
