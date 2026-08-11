/**
 * @file network-info-modal-adapter.js
 * @description Network IP access, mDNS monitoring, and QR code presentation modal adapter for Lanvan.
 *              Manages connection modal dialogs, network IP URL clipboard copying, and offline QR canvas rendering.
 * @module NetworkInfoModalAdapter
 */

(function (window) {
  'use strict';

  /**
   * Copy main connection URL to system clipboard.
   */
  async function copyConnectionUrl() {
    const urlElement = document.getElementById('connection-url');
    if (!urlElement) return;

    const url = urlElement.textContent;

    try {
      if (navigator.clipboard && window.isSecureContext) {
        await navigator.clipboard.writeText(url);
        if (typeof window.showToast === 'function') window.showToast(' Connection URL copied to clipboard!', 3000);
      } else {
        const textArea = document.createElement('textarea');
        textArea.value = url;
        textArea.style.position = 'fixed';
        textArea.style.opacity = '0';
        document.body.appendChild(textArea);
        textArea.focus();
        textArea.select();
        document.execCommand('copy');
        document.body.removeChild(textArea);
        if (typeof window.showToast === 'function') window.showToast(' Connection URL copied to clipboard!', 3000);
      }
    } catch (err) {
      console.error('Copy failed:', err);
      if (typeof window.showToast === 'function') window.showToast(' Copy failed. Please copy manually.', 4000);
    }
  }

  /**
   * Copy alternative LAN IP URL to system clipboard.
   */
  async function copyAlternativeUrl() {
    const urlElement = document.getElementById('alternative-url');
    if (!urlElement) {
      const networkInfo = window._currentNetworkInfo;
      if (networkInfo && networkInfo.lanIpUrl) {
        try {
          if (navigator.clipboard && window.isSecureContext) {
            await navigator.clipboard.writeText(networkInfo.lanIpUrl);
            if (typeof window.showToast === 'function') window.showToast(' Alternative IP URL copied to clipboard!', 3000);
          } else {
            const textArea = document.createElement('textarea');
            textArea.value = networkInfo.lanIpUrl;
            textArea.style.position = 'fixed';
            textArea.style.opacity = '0';
            document.body.appendChild(textArea);
            textArea.focus();
            textArea.select();
            document.execCommand('copy');
            document.body.removeChild(textArea);
            if (typeof window.showToast === 'function') window.showToast(' Alternative IP URL copied to clipboard!', 3000);
          }
        } catch (err) {
          console.error('Copy failed:', err);
          if (typeof window.showToast === 'function') window.showToast(' Copy failed. Please copy manually.', 4000);
        }
      }
      return;
    }

    const url = urlElement.textContent;

    try {
      if (navigator.clipboard && window.isSecureContext) {
        await navigator.clipboard.writeText(url);
        if (typeof window.showToast === 'function') window.showToast(' Alternative IP URL copied to clipboard!', 3000);
      } else {
        const textArea = document.createElement('textarea');
        textArea.value = url;
        textArea.style.position = 'fixed';
        textArea.style.opacity = '0';
        document.body.appendChild(textArea);
        textArea.focus();
        textArea.select();
        document.execCommand('copy');
        document.body.removeChild(textArea);
        if (typeof window.showToast === 'function') window.showToast(' Alternative IP URL copied to clipboard!', 3000);
      }
    } catch (err) {
      console.error('Copy failed:', err);
      if (typeof window.showToast === 'function') window.showToast(' Copy failed. Please copy manually.', 4000);
    }
  }

  /**
   * Display IP Access QR Code popup modal.
   */
  function showIPQRCode() {
    const networkInfo = window._currentNetworkInfo;
    if (!networkInfo || !networkInfo.lanIpUrl) {
      if (typeof window.showToast === 'function') window.showToast(' IP URL not available', 3000);
      return;
    }

    const qrModal = document.createElement('div');
    qrModal.style.cssText = `
      position: fixed;
      top: 0;
      left: 0;
      width: 100%;
      height: 100%;
      background: rgba(0,0,0,0.8);
      z-index: 10001;
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 1rem;
      box-sizing: border-box;
    `;

    const qrDialog = document.createElement('div');
    qrDialog.style.cssText = `
      background: white;
      border-radius: 15px;
      padding: 2rem;
      text-align: center;
      max-width: 400px;
      width: 90%;
      box-shadow: 0 10px 30px rgba(0,0,0,0.3);
    `;

    qrDialog.innerHTML = `
      <h3 style="margin: 0 0 1rem 0; color: #333;"> IP Access QR Code</h3>
      <div style="margin: 1rem 0;">
        <img src="/api/qr-code?text=${encodeURIComponent(networkInfo.lanIpUrl)}&size=200" 
             style="border: 2px solid #ddd; border-radius: 10px; max-width: 200px; height: auto;" 
             alt="IP QR Code">
      </div>
      <p style="margin: 0.5rem 0; font-size: 0.9rem; color: #666; word-break: break-all;">
        ${networkInfo.lanIpUrl}
      </p>
      <div style="margin-top: 1.5rem;">
        <button onclick="this.closest('.qr-modal').remove()" 
                style="background: var(--settings-bg); color: white; border: none; padding: 0.5rem 1.5rem; border-radius: 8px; cursor: pointer; font-size: 0.9rem;">
          Close
        </button>
      </div>
    `;

    qrModal.className = 'qr-modal';
    qrModal.appendChild(qrDialog);

    qrModal.addEventListener('click', (e) => {
      if (e.target === qrModal) {
        qrModal.remove();
      }
    });

    document.body.appendChild(qrModal);

    if (typeof window.showToast === 'function') window.showToast(' IP QR Code displayed', 2000);
  }

  /**
   * Close active connection info modal dialog.
   */
  function closeConnectionModal() {
    const modal = window.currentConnectionModal;
    if (modal) {
      modal.remove();
      window.currentConnectionModal = null;
    }
  }

  /**
   * Refresh network connection info and QR code metadata.
   */
  function refreshConnectionInfo() {
    if (typeof window.preloadQRFromNetworkInfo === 'function') {
      fetch('/api/network-info')
        .then(response => response.json())
        .then(networkInfo => {
          if (networkInfo.mdns?.status === 'active' && networkInfo.hybrid_url) {
            if (typeof window.preloadQRFromUrl === 'function') {
              window.preloadQRFromUrl(networkInfo.hybrid_url);
            }
            console.log(' QR codes refreshed for mDNS URL:', networkInfo.hybrid_url);
          }
        })
        .catch(() => { });
    }

    if (window.currentConnectionModal) {
      window.currentConnectionModal.remove();
      window.currentConnectionModal = null;
      setTimeout(() => {
        if (typeof window.showConnectionInfo === 'function') {
          window.showConnectionInfo();
        }
      }, 200);
    }
  }

  /**
   * Monitor real-time mDNS service status and update UI hint pills.
   */
  async function updateMDNSStatus() {
    try {
      const response = await fetch('/api/network-info');
      if (response.ok) {
        const networkInfo = await response.json();
        const qrHintText = document.getElementById('qrHintText');
        const mdnsTab = document.getElementById('mdnsTab');
        const qrMdnsTab = document.getElementById('connectQrMdnsTab');

        const isMdnsActive = networkInfo.mdns && networkInfo.mdns.status === 'active';

        if (isMdnsActive) {
          if (mdnsTab) mdnsTab.style.display = '';
          if (qrMdnsTab) qrMdnsTab.style.display = '';

          if (qrHintText) {
            const domain = networkInfo.mdns.domain;
            const conflictInfo = networkInfo.mdns.conflict_resolved
              ? ` (resolved conflict #${networkInfo.mdns.conflict_count + 1})`
              : '';

            if (!qrHintText.innerHTML.includes('mDNS:')) {
              qrHintText.innerHTML = ` <strong>mDNS:</strong> ${domain}${conflictInfo} • Click for QR`;
              qrHintText.style.color = '#22c55e';
              qrHintText.style.setProperty('color', '#22c55e', 'important');
              qrHintText.title = `mDNS service active - accessible via ${domain}`;

              if (typeof window.showToast === 'function') {
                window.showToast(` mDNS service is now active! Accessible via ${domain}${conflictInfo}`, 4000);
              }

              if (typeof window.setConnectMode === 'function') {
                window.setConnectMode('mdns');
              }
              refreshConnectionInfo();
            }
          }
        } else {
          // Hide mDNS tabs completely if mDNS service is not available (e.g. Docker bridge or unsupported environment)
          if (mdnsTab) mdnsTab.style.display = 'none';
          if (qrMdnsTab) qrMdnsTab.style.display = 'none';

          if (typeof window.setConnectMode === 'function') {
            window.setConnectMode('ip');
          }

          if (qrHintText && qrHintText.innerHTML.includes('mDNS:')) {
            qrHintText.innerHTML = '• Click for QR code';
            qrHintText.style.color = 'var(--protocol-text)';
            qrHintText.title = '';
          }
        }
      }
    } catch (error) {
      console.log('Could not fetch mDNS status:', error);
    }
  }

  function showQRSuccess(imgElement, type) {
    const loadingDiv = document.getElementById('qr-loading');
    if (loadingDiv) loadingDiv.style.display = 'none';
    imgElement.style.display = 'block';
    imgElement.classList.add('qr-reveal');
    console.log(` QR Code loaded successfully (${type})`);
  }

  function tryFallbackQR() {
    console.log(' Primary QR failed, trying fallback...');
    const fallbackQR = document.getElementById('qr-fallback');
    const urlEl = document.getElementById('connection-url');
    const url = urlEl ? urlEl.textContent : '';
    if (fallbackQR && url) {
      fallbackQR.src = `/api/qr-code?text=${encodeURIComponent(url)}&size=200`;
    }
  }

  function showOfflineQR() {
    if (window._qrBlocked) {
      console.log('⏸ QR generation blocked during upload - will retry later');
      setTimeout(() => showOfflineQR(), 1000);
      return;
    }

    console.log(' Using offline QR generator...');

    const loadingDiv = document.getElementById('qr-loading');
    const primaryQR = document.getElementById('qr-primary');
    const fallbackQR = document.getElementById('qr-fallback');

    if (loadingDiv) loadingDiv.style.display = 'none';
    if (primaryQR) primaryQR.style.display = 'none';
    if (fallbackQR) fallbackQR.style.display = 'none';

    const canvas = document.getElementById('offline-qr');
    const text = document.getElementById('offline-qr-text');

    if (canvas) {
      canvas.style.display = 'block';
      canvas.width = 200;
      canvas.height = 200;

      let url;
      const connectionUrl = document.getElementById('connection-url');
      if (connectionUrl) {
        url = connectionUrl.textContent;
      } else {
        url = window.location.href;
      }

      try {
        if (typeof window.generateOfflineQR === 'function') {
          window.generateOfflineQR(url, canvas);
        }
        canvas.classList.add('qr-reveal');
        console.log(' Offline QR generated successfully');
      } catch (error) {
        console.error(' Failed to generate offline QR:', error);
        const ctx = canvas.getContext('2d');
        ctx.fillStyle = 'var(--text-color)';
        ctx.font = '14px Arial';
        ctx.textAlign = 'center';
        ctx.fillText('QR Code', 100, 90);
        ctx.fillText('Generation', 100, 110);
        ctx.fillText('Failed', 100, 130);
      }
    }

    if (text) text.style.display = 'block';
  }

  function showQRCode(imgElement) {
    const loadingDiv = document.getElementById('qr-loading');
    if (loadingDiv) loadingDiv.style.display = 'none';
    imgElement.style.display = 'block';
    imgElement.style.margin = '0 auto';
    imgElement.classList.add('qr-reveal');
    console.log(' QR Code loaded successfully');
  }

  function showQRFallback() {
    const loadingDiv = document.getElementById('qr-loading');
    const qrImage = document.getElementById('qr-image');
    const fallbackDiv = document.getElementById('qr-offline-fallback');

    if (loadingDiv) loadingDiv.style.display = 'none';
    if (qrImage) qrImage.style.display = 'none';
    if (fallbackDiv) {
      fallbackDiv.style.display = 'block';
      const canvas = document.getElementById('offline-qr');
      if (canvas) {
        const urlElement = document.getElementById('connection-url');
        const url = urlElement ? urlElement.textContent : window.location.href;
        if (typeof window.generateOfflineQR === 'function') {
          const offlineQR = window.generateOfflineQR(url, canvas);
          const ctx = canvas.getContext('2d');
          const img = new Image();
          img.onload = () => {
            ctx.drawImage(img, 0, 0);
            canvas.classList.add('qr-reveal');
          };
          img.src = offlineQR;
        }
      }
    }
    console.log(' QR Code fallback activated - using offline generator');
  }

  // Freeze immutable adapter interface
  const NetworkInfoModalAdapter = Object.freeze({
    copyConnectionUrl: copyConnectionUrl,
    copyAlternativeUrl: copyAlternativeUrl,
    showIPQRCode: showIPQRCode,
    closeConnectionModal: closeConnectionModal,
    refreshConnectionInfo: refreshConnectionInfo,
    updateMDNSStatus: updateMDNSStatus,
    showQRSuccess: showQRSuccess,
    tryFallbackQR: tryFallbackQR,
    showOfflineQR: showOfflineQR,
    showQRCode: showQRCode,
    showQRFallback: showQRFallback
  });

  window.NetworkInfoModalAdapter = NetworkInfoModalAdapter;

  // Preserve global backward compatibility aliases
  window.copyConnectionUrl = window.copyConnectionUrl || copyConnectionUrl;
  window.copyAlternativeUrl = window.copyAlternativeUrl || copyAlternativeUrl;
  window.showIPQRCode = window.showIPQRCode || showIPQRCode;
  window.closeConnectionModal = window.closeConnectionModal || closeConnectionModal;
  window.refreshConnectionInfo = window.refreshConnectionInfo || refreshConnectionInfo;
  window.updateMDNSStatus = window.updateMDNSStatus || updateMDNSStatus;
  window.showQRSuccess = window.showQRSuccess || showQRSuccess;
  window.tryFallbackQR = window.tryFallbackQR || tryFallbackQR;
  window.showOfflineQR = window.showOfflineQR || showOfflineQR;
  window.showQRCode = window.showQRCode || showQRCode;
  window.showQRFallback = window.showQRFallback || showQRFallback;

})(window);
