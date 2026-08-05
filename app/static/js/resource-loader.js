/**
 * Progressive Resource Loader
 *
 * Handles asynchronous script fetching, CDN fallbacks (JSZip),
 * and environment feature detection (Safari/iOS) with platform-specific
 * timeout tuning and cache-recovery for bfcache restores.
 */
    // Platform detection for Safari/iOS-specific timeout and caching behavior.
    window.isSafari = /^((?!chrome|android).)*safari/i.test(navigator.userAgent);
    window.isiOS = /iPad|iPhone|iPod/.test(navigator.userAgent);
    window.isiOSSafari = window.isiOS && window.isSafari;

    // Universal Resource Loader - Non-blocking async loading
    window.resourceLoader = {
      loaded: {},
      callbacks: {},

      loadScript: function (src, callback, timeout = 5000) {
        if (this.loaded[src]) {
          if (callback) callback();
          return;
        }

        const script = document.createElement('script');
        script.async = true;
        script.defer = true;

        // Safari-specific optimizations
        if (window.isiOSSafari) {
          script.crossOrigin = 'anonymous';
          timeout = 3000; // Shorter timeout for Safari
        }

        const timeoutId = setTimeout(() => {
          console.warn(`Resource timeout: ${src}`);
          script.remove();
          if (this.callbacks[src]) {
            this.callbacks[src].forEach(cb => cb(new Error('timeout')));
            delete this.callbacks[src];
          }
        }, timeout);

        script.onload = () => {
          clearTimeout(timeoutId);
          this.loaded[src] = true;
          if (callback) callback();
          if (this.callbacks[src]) {
            this.callbacks[src].forEach(cb => cb());
            delete this.callbacks[src];
          }
        };

        script.onerror = () => {
          clearTimeout(timeoutId);
          console.warn(`Failed to load: ${src}`);
          script.remove();
          if (callback) callback(new Error('load failed'));
          if (this.callbacks[src]) {
            this.callbacks[src].forEach(cb => cb(new Error('load failed')));
            delete this.callbacks[src];
          }
        };

        script.src = src;
        document.head.appendChild(script);
      },

      waitForScript: function (src, callback) {
        if (this.loaded[src]) {
          callback();
          return;
        }
        if (!this.callbacks[src]) {
          this.callbacks[src] = [];
        }
        this.callbacks[src].push(callback);
      }
    };

    // Progressive Loading System
    window.progressiveLoader = {
      critical: [],
      enhanced: [],

      addCritical: function (fn) {
        if (document.readyState === 'loading') {
          this.critical.push(fn);
        } else {
          fn();
        }
      },

      addEnhanced: function (fn) {
        this.enhanced.push(fn);
      },

      init: function () {
        this.critical.forEach(fn => {
          try { fn(); } catch (e) { console.warn('Critical load error:', e); }
        });

        // Load enhanced resources after a platform-aware delay.
        // Safari benefits from a longer initial settling period before secondary loads.
        const delay = window.isiOSSafari ? 500 : 100;
        setTimeout(() => {
          this.enhanced.forEach(fn => {
            try { fn(); } catch (e) { console.warn('Enhanced load error:', e); }
          });
        }, delay);
      }
    };

    // JSZip Async Loader — loads the local bundle without blocking rendering.
    window.jsZipReady = false;
    window.jsZipCallbacks = [];

    function loadJSZip() {
      var jszipUrl = (window.LanvanConfig && window.LanvanConfig.jszipUrl) ? window.LanvanConfig.jszipUrl : '/static/js/jszip.min.js';
      window.resourceLoader.loadScript(
        jszipUrl,
        function (error) {
          if (error) {
            console.warn('JSZip failed to load locally');
          } else {
            window.jsZipReady = true;
          }

          window.jsZipCallbacks.forEach(cb => cb(!error));
          window.jsZipCallbacks = [];
        },
        window.isiOSSafari ? 3000 : 5000
      );
    }

    // Start loading JSZip immediately but non-blocking
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', loadJSZip);
    } else {
      loadJSZip();
    }

    // Helper function to wait for JSZip
    window.waitForJSZip = function (callback) {
      if (window.jsZipReady && window.JSZip) {
        callback(true);
      } else {
        window.jsZipCallbacks.push(callback);
      }
    };

    window.progressiveLoader.addEnhanced(function () {
      window.resourceLoader.loadScript(
        window.LanvanConfig ? window.LanvanConfig.fileUtilsUrl : '/static/js/file-utils.js',
        function (error) {
          if (error) {
            console.warn('File utils failed to load');
          } else {
            console.log(' File utils loaded');
          }
        }
      );
    });

    // iOS Safari optimization - Initialize progressive loading
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', () => {
        window.progressiveLoader.init();
      });
    } else {
      window.progressiveLoader.init();
    }

    // Universal QR Code Loader - Safari Optimized
    window.qrLoader = {
      loadImage: function (src, onSuccess, onError, timeout = null) {
        const img = new Image();
        const timeoutMs = timeout || (window.isiOSSafari ? 2000 : 5000);

        const timeoutId = setTimeout(() => {
          img.onload = img.onerror = null;
          if (onError) onError(new Error('QR load timeout'));
        }, timeoutMs);

        img.onload = () => {
          clearTimeout(timeoutId);
          if (onSuccess) onSuccess(img);
        };

        img.onerror = () => {
          clearTimeout(timeoutId);
          if (onError) onError(new Error('QR load failed'));
        };

        // Safari-specific optimizations
        if (window.isiOSSafari) {
          img.crossOrigin = 'anonymous';
        }

        img.src = src;
      },

      loadWithFallback: function (urls, onSuccess, onError) {
        let currentIndex = 0;

        const tryNext = () => {
          if (currentIndex >= urls.length) {
            if (onError) onError(new Error('All QR services failed'));
            return;
          }

          const url = urls[currentIndex++];
          this.loadImage(url, onSuccess, () => {
            console.warn(`QR service ${currentIndex} failed, trying next...`);
            setTimeout(tryNext, window.isiOSSafari ? 200 : 100);
          });
        };

        tryNext();
      }
    };

    // Add Safari-specific optimizations
    if (window.isiOSSafari) {
      // Prevent Safari from aggressive caching that causes issues
      window.addEventListener('pageshow', (event) => {
        if (event.persisted) {
          console.log('Page restored from cache, refreshing critical components');
          // Force refresh of dynamic content
          setTimeout(() => {
            if (typeof refreshFileListManually === 'function') {
              refreshFileListManually();
            }
          }, 500);
        }
      });

      // Safari memory management
      window.addEventListener('beforeunload', () => {
        // Clean up resources before page unload
        if (window.ws) window.ws.close();
        if (window.clipboardWS) window.clipboardWS.close();
      });
    }
