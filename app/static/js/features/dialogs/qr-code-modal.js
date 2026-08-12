/**
 * @file qr-code-modal.js
 * @description Offline-first QR Code generation, preloading, and connection information modal module for Lanvan.
 * @module QRCodeModal
 */

(function (window) {
  'use strict';

  /**
   * Enhanced QR Code Generation for Connection Info - Offline-First
   * @param {string} text - The URL or string to encode into QR code
   * @param {number} [size=200] - Desired size of QR image
   * @returns {Object} QR result object with primary URL, fallbacks, and toString helper
   */
  function generateQRCode(text, size) {
    var defaultSize = typeof size === 'number' ? size : 200;
    var isGuest = typeof window.detectGuestDevice === 'function' && window.detectGuestDevice();
    var qrSize = isGuest ? 180 : defaultSize;

    var offlineQR = '/api/qr-code?text=' + encodeURIComponent(text) + '&size=' + qrSize;
    var fallbackServices = [
      '/api/qr-code?text=' + encodeURIComponent(text) + '&size=' + qrSize
    ];

    return {
      primary: offlineQR,
      fallbacks: fallbackServices,
      toString: function () { return offlineQR; }
    };
  }

  /**
   * Preload QR code image from exact URL
   * @param {string} fullUrl 
   */
  function preloadQRFromUrl(fullUrl) {
    var isGuest = typeof window.detectGuestDevice === 'function' && window.detectGuestDevice();
    var qrSize = isGuest ? 180 : 200;
    var qrUrl = '/api/qr-code?text=' + encodeURIComponent(fullUrl) + '&size=' + qrSize;

    var testImg = new window.Image();
    var timeout = setTimeout(function () {
      if (window.DEBUG_MODE) console.log('QR API is slow/unavailable, will use offline generation');
      window._qrApiUnavailable = true;
    }, 5000);

    testImg.onload = function () {
      clearTimeout(timeout);
      window._preloadedQR = {
        url: qrUrl,
        img: testImg,
        timestamp: Date.now()
      };
      if (window.DEBUG_MODE) console.log('QR API is working, QR preloaded successfully');
    };

    testImg.onerror = function () {
      clearTimeout(timeout);
      if (window.DEBUG_MODE) console.log('QR API failed, will use offline generation');
      window._qrApiUnavailable = true;
    };

    testImg.src = qrUrl;
  }

  /**
   * Preload QR code image using protocol, hostname, and port
   * @param {string} protocol 
   * @param {string} hostname 
   * @param {string} port 
   */
  function preloadQR(protocol, hostname, port) {
    var fullUrl = protocol + '//' + hostname;
    if (port && port !== '80' && port !== '443') {
      fullUrl += ':' + port;
    }
    preloadQRFromUrl(fullUrl);
  }

  /**
   * Enhanced offline QR code generator & connection info modal with mDNS support
   */
  async function showConnectionInfo() {
    var protocol = location.protocol;
    var hostname = location.hostname;
    var port = location.port;
    var useMDNS = false;
    var mdnsUrl = null;
    var networkInfo = null;
    var lanIpUrl = null;

    try {
      var response = await fetch('/api/network-info');
      if (response.ok) {
        networkInfo = await response.json();

        if (networkInfo.lan_ip_url) {
          lanIpUrl = networkInfo.lan_ip_url;
        }

        if (networkInfo.mdns && networkInfo.mdns.status === 'active' && networkInfo.mdns.domain) {
          hostname = networkInfo.mdns.domain;
          useMDNS = true;
          mdnsUrl = networkInfo.mdns.url || networkInfo.hybrid_url;
        } else {
          if (hostname === 'localhost' || hostname === '127.0.0.1') {
            if (networkInfo.lan_ip && networkInfo.lan_ip !== '127.0.0.1') {
              hostname = networkInfo.lan_ip;
            }
          }
        }
      }
    } catch (error) {
      if (window.DEBUG_MODE) console.log('Network info fetch error:', error);
    }

    var isHTTPS = protocol === 'https:';

    var fullUrl;
    if (useMDNS && mdnsUrl) {
      fullUrl = mdnsUrl;
    } else {
      fullUrl = protocol + '//' + hostname;
      if (port && port !== '80' && port !== '443') {
        fullUrl += ':' + port;
      }
    }

    window._currentNetworkInfo = { networkInfo: networkInfo, lanIpUrl: lanIpUrl, useMDNS: useMDNS, fullUrl: fullUrl };

    var modal = document.createElement('div');
    modal.style.cssText = 'position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.7); z-index: 10000; display: flex; align-items: center; justify-content: center; padding: 1rem; box-sizing: border-box;';

    var dialog = document.createElement('div');
    dialog.style.cssText = 'background: white; border-radius: 15px; width: 90%; max-width: 500px; max-height: 90vh; overflow-y: auto; box-shadow: 0 10px 30px rgba(0,0,0,0.3); margin: 0 auto; padding: 2rem;';

    var isGuest = typeof window.detectGuestDevice === 'function' && window.detectGuestDevice();
    var qrSize = isGuest ? 180 : 200;

    var qrResult = generateQRCode(fullUrl, qrSize);
    var primaryQRUrl = qrResult.primary || qrResult.toString();
    var fallbackQRUrls = qrResult.fallbacks || [
      '/api/qr-code?text=' + encodeURIComponent(fullUrl) + '&size=' + qrSize
    ];

    setTimeout(function () {
      var primaryQR = document.getElementById('qr-primary');
      if (primaryQR) {
        if (window._qrApiUnavailable) {
          if (window.requestIdleCallback) {
            requestIdleCallback(function () { if (typeof window.showOfflineQR === 'function') window.showOfflineQR(); });
          } else {
            setTimeout(function () { if (typeof window.showOfflineQR === 'function') window.showOfflineQR(); }, 100);
          }
          return;
        }

        if (window._preloadedQR && window._preloadedQR.url === primaryQRUrl) {
          primaryQR.src = window._preloadedQR.img.src;
        } else {
          primaryQR.src = primaryQRUrl;
        }

        setTimeout(function () {
          if (primaryQR.style.display === 'none') {
            if (window.requestIdleCallback) {
              requestIdleCallback(function () { if (typeof window.showOfflineQR === 'function') window.showOfflineQR(); });
            } else {
              setTimeout(function () { if (typeof window.showOfflineQR === 'function') window.showOfflineQR(); }, 50);
            }
          }
        }, 5000);

        setTimeout(function () {
          if (primaryQR.style.display === 'none') {
            var fallbackQR = document.getElementById('qr-fallback');
            if (fallbackQR && fallbackQRUrls.length > 0) {
              fallbackQR.src = fallbackQRUrls[0];
              setTimeout(function () {
                if (fallbackQR.style.display === 'none') {
                  if (window.requestIdleCallback) {
                    requestIdleCallback(function () { if (typeof window.showOfflineQR === 'function') window.showOfflineQR(); });
                  } else {
                    setTimeout(function () { if (typeof window.showOfflineQR === 'function') window.showOfflineQR(); }, 50);
                  }
                }
              }, 3000);
            }
          }
        }, 8000);
      }
    }, 10);

    var lanInstructions = (location.hostname === 'localhost' || location.hostname === '127.0.0.1') && hostname === location.hostname ? [
      '<div style="background: #fff3cd; border: 1px solid #ffeaa7; padding: 1rem; border-radius: 8px; margin: 1rem 0;">',
      '  <h4 style="margin: 0 0 0.5rem 0; color: #856404;"> To share on LAN:</h4>',
      '  <p style="margin: 0; font-size: 0.9rem; color: #856404;">',
      '    • Replace "localhost" with your computer\'s IP address<br>',
      '    • Windows: Run <code>ipconfig</code> and look for IPv4<br>',
      '    • Linux/Mac: Run <code>ip addr</code> or <code>ifconfig</code><br>',
      '    • Android Termux: Run <code>ip route | grep default</code>',
      '  </p>',
      '</div>'
    ].join('\n') : '';

    var closeBtnAttr = typeof window.closeConnectionModal === 'function' ? 'onclick="closeConnectionModal()"' : 'onclick="if(window.currentConnectionModal)window.currentConnectionModal.remove();"';
    var mdnsDomain = (networkInfo && networkInfo.mdns && networkInfo.mdns.domain) ? networkInfo.mdns.domain : 'lanvan.local';

    dialog.innerHTML = [
      '<div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 1rem;">',
      '  <h3 style="margin: 0; color: #333; display: flex; align-items: center; gap: 0.5rem;">',
      '    <span>' + (isHTTPS ? '' : '') + '</span>',
      '    Connection Info',
      '  </h3>',
      '  <button ' + closeBtnAttr + ' style="background: #e74c3c; color: white; border: none; padding: 0.5rem 1rem; border-radius: 6px; cursor: pointer; font-size: 0.9rem;"> Close</button>',
      '</div>',
      '<div style="margin: 1.5rem 0;">',
      '  <div id="qr-container" style="text-align: center; min-height: 220px; position: relative;">',
      '    <img id="qr-primary" style="display: none; border: 2px solid #e1e1e1; border-radius: 10px; max-width: 180px; height: auto; margin: 0 auto;" onload="if(typeof showQRSuccess===\'function\')showQRSuccess(this, \'primary\');" onerror="if(typeof showOfflineQR===\'function\')showOfflineQR();">',
      '    <img id="qr-fallback" style="display: none; border: 2px solid #e1e1e1; border-radius: 10px; max-width: 180px; height: auto; margin: 0 auto;" onload="if(typeof showQRSuccess===\'function\')showQRSuccess(this, \'fallback\');" onerror="if(typeof showOfflineQR===\'function\')showOfflineQR();">',
      '    <div id="qr-loading" style="position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%);">',
      '      <div style="width: 40px; height: 40px; border: 4px solid var(--border-color); border-top: 4px solid #007bff; border-radius: 50%; animation: qr-spin 1s linear infinite; margin-bottom: 1rem;"></div>',
      '      <p style="margin: 0; color: var(--text-color); opacity: 0.8; font-size: 0.9rem;"> Generating QR Code...</p>',
      '    </div>',
      '    <canvas id="offline-qr" style="display: none; border: 2px solid #e1e1e1; border-radius: 10px; margin: 0 auto;"></canvas>',
      '    <p id="offline-qr-text" style="display: none; font-size: 0.8rem; color: var(--text-color); opacity: 0.8; margin-top: 0.5rem;"> Offline QR Code</p>',
      '  </div>',
      '</div>',
      '<div style="background: var(--input-bg); border-radius: 10px; padding: 1rem; margin: 1rem 0; border: 1px solid var(--border-color);">',
      useMDNS ? [
        '  <h4 style="margin: 0 0 0.5rem 0; color: var(--text-color);"> mDNS Connection URL:</h4>',
        '  <div style="display: flex; gap: 0.5rem; align-items: center; flex-wrap: wrap; margin-bottom: 1rem;">',
        '    <code id="connection-url" style="flex: 1; background: #d4edda; padding: 0.5rem; border-radius: 5px; border: 1px solid #c3e6cb; font-size: 0.85rem; word-break: break-all; min-width: 200px; color: #155724;">' + fullUrl + '</code>',
        '    <button onclick="if(typeof copyConnectionUrl===\'function\')copyConnectionUrl();" style="background: #28a745; color: white; border: none; padding: 0.5rem 1rem; border-radius: 5px; cursor: pointer; font-size: 0.85rem; white-space: nowrap;" title="Copy mDNS URL to clipboard"> Copy</button>',
        '  </div>',
        '  <div style="padding: 0.6rem; background: #d4edda; border: 1px solid #c3e6cb; border-radius: 6px; margin-bottom: 0.8rem;">',
        '    <small style="color: #155724; display: flex; align-items: center; gap: 0.3rem; font-size: 0.8rem;">',
        '      <span></span>',
        '      <strong>mDNS Active:</strong> Easy access via domain name - guests can use ' + mdnsDomain + '!',
        '    </small>',
        '  </div>',
        '  <h4 style="margin: 0 0 0.5rem 0; color: var(--text-color); opacity: 0.8; font-size: 0.9rem;"> Alternative IP Connection:</h4>',
        '  <div style="display: flex; gap: 0.5rem; align-items: center; flex-wrap: wrap; margin-bottom: 0.8rem;">',
        '    <code id="alternative-url" style="flex: 1; background: var(--section-bg); color: var(--text-color); padding: 0.4rem; border-radius: 5px; border: 1px solid var(--border-color); font-size: 0.8rem; word-break: break-all; min-width: 200px;">' + (lanIpUrl || 'http://192.168.x.x') + '</code>',
        '    <button onclick="if(typeof copyAlternativeUrl===\'function\')copyAlternativeUrl();" style="background: var(--settings-bg); color: white; border: none; padding: 0.4rem 0.8rem; border-radius: 5px; cursor: pointer; font-size: 0.8rem; white-space: nowrap;" title="Copy IP URL to clipboard"> Copy</button>',
        '  </div>',
        '  <div style="text-align: center; margin: 1rem 0; padding: 1rem; background: var(--input-bg); border-radius: 8px; border: 1px solid var(--border-color);">',
        '    <div style="margin-bottom: 0.5rem;">',
        '      <small style="color: var(--text-color); opacity: 0.8; font-size: 0.8rem; font-weight: 500;"> IP Access QR Code</small>',
        '    </div>',
        '    <div style="display: flex; justify-content: center; align-items: center;">',
        '      <img src="/api/qr-code?text=' + encodeURIComponent(lanIpUrl || 'http://192.168.0.106') + '&size=160" style="border: 2px solid var(--border-color); border-radius: 8px; max-width: 160px; height: auto; background: var(--section-bg); display: block;" alt="IP QR Code" onerror="this.style.display=\'none\'; this.parentElement.nextElementSibling.style.display=\'block\';" onload="this.style.display=\'block\';">',
        '    </div>',
        '    <div style="display: none; padding: 0.5rem; background: var(--input-bg); border: 1px solid var(--border-color); border-radius: 5px; color: var(--text-color); opacity: 0.8; font-size: 0.8rem;">',
        '      QR code generation failed',
        '    </div>',
        '    <div style="margin-top: 0.5rem;">',
        '      <small style="color: var(--text-color); opacity: 0.7; font-size: 0.75rem;">Scan if mDNS doesn\'t work</small>',
        '    </div>',
        '  </div>',
        '  <div style="margin-top: 0.5rem;">',
        '    <small style="color: #666; font-size: 0.75rem;">',
        '       <strong>For guests:</strong> Try mDNS first (' + mdnsDomain + '), use IP if that fails',
        '    </small>',
        '  </div>'
      ].join('\n') : [
        '  <h4 style="margin: 0 0 0.5rem 0; color: var(--text-color);"> Connection URL:</h4>',
        '  <div style="display: flex; gap: 0.5rem; align-items: center; flex-wrap: wrap;">',
        '    <code id="connection-url" style="flex: 1; background: var(--input-bg); color: var(--text-color); padding: 0.5rem; border-radius: 5px; border: 1px solid var(--border-color); font-size: 0.85rem; word-break: break-all; min-width: 200px;">' + fullUrl + '</code>',
        '    <button onclick="if(typeof copyConnectionUrl===\'function\')copyConnectionUrl();" style="background: #007bff; color: white; border: none; padding: 0.5rem 1rem; border-radius: 5px; cursor: pointer; font-size: 0.85rem; white-space: nowrap;" title="Copy URL to clipboard"> Copy</button>',
        '  </div>',
        '  <div style="margin-top: 0.8rem; padding: 0.6rem; background: var(--input-bg); border: 1px solid var(--border-color); border-radius: 6px;">',
        '    <small style="color: var(--text-color); opacity: 0.8; display: flex; align-items: center; gap: 0.3rem; font-size: 0.8rem;">',
        '      <span></span>',
        '      <strong>Using IP Address:</strong> mDNS not available - guests must use IP to connect',
        '    </small>',
        '  </div>'
      ].join('\n'),
      '</div>',
      lanInstructions
    ].join('\n');

    modal.appendChild(dialog);
    document.body.appendChild(modal);

    window.currentConnectionModal = modal;

    setTimeout(function () {
      var primaryQR = document.getElementById('qr-primary');
      if (primaryQR) {
        primaryQR.src = primaryQRUrl;
        if (isGuest) {
          setTimeout(function () {
            if (primaryQR.style.display === 'none') {
              if (typeof window.showOfflineQR === 'function') window.showOfflineQR();
            }
          }, 1000);
        }
      }
    }, 10);

    modal.addEventListener('click', function (e) {
      if (e.target === modal) {
        if (typeof window.closeConnectionModal === 'function') {
          window.closeConnectionModal();
        } else {
          modal.remove();
        }
      }
    });

    document.addEventListener('keydown', function escapeHandler(e) {
      if (e.key === 'Escape') {
        if (typeof window.closeConnectionModal === 'function') {
          window.closeConnectionModal();
        } else if (window.currentConnectionModal) {
          window.currentConnectionModal.remove();
        }
        document.removeEventListener('keydown', escapeHandler);
      }
    });
  }

  // Preload QR on DOMContentLoaded
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initQRPreload);
  } else {
    initQRPreload();
  }

  function initQRPreload() {
    var protocol = location.protocol;
    var hostname = location.hostname;
    var port = location.port;

    // Always fetch network-info to get the authoritative LAN URL.
    // lan_ip_url from the backend is the single source of truth.
    fetch('/api/network-info').then(function (response) { return response.json(); }).then(function (networkInfo) {
      if (networkInfo.mdns && networkInfo.mdns.status === 'active' && networkInfo.mdns.url) {
        // mDNS is active — preload the mDNS URL
        preloadQRFromUrl(networkInfo.mdns.url);
      } else if (networkInfo.lan_ip_url) {
        // Backend has a valid LAN URL (native runtime or Docker with LANVAN_ADVERTISE_HOST)
        preloadQRFromUrl(networkInfo.lan_ip_url);
      }
      // If lan_ip_url is null (Docker bridge without env var), do NOT preload localhost.
      // The connect-panel will show the "LAN address unavailable" notice instead.
    }).catch(function () {
      // Only fall back to current hostname if it is not localhost/127.0.0.1.
      // This preserves behavior for native runtimes that don't have the API yet.
      if (hostname !== 'localhost' && hostname !== '127.0.0.1') {
        preloadQR(protocol, hostname, port);
      }
    });

    if (typeof window.updateMDNSStatus === 'function') {
      // Single startup check — no polling timer.
      // Further mDNS status changes are driven by WebSocket server events, not polling.
      window.updateMDNSStatus();
    }
  }

  const QRCodeModal = Object.freeze({
    generateQRCode: generateQRCode,
    preloadQRFromUrl: preloadQRFromUrl,
    preloadQR: preloadQR,
    showConnectionInfo: showConnectionInfo
  });

  window.QRCodeModal = QRCodeModal;
  window.generateQRCode = generateQRCode;
  window.preloadQRFromUrl = preloadQRFromUrl;
  window.preloadQR = preloadQR;
  window.showConnectionInfo = showConnectionInfo;

})(window);
