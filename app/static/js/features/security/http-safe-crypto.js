/**
 * @file http-safe-crypto.js
 * @description HTTP-Safe AES encryption and metadata obfuscation helper module for Lanvan.
 *              Provides metadata-obfuscated upload helpers and Web Crypto integration.
 * @module HttpSafeCrypto
 */

(function (window) {
  'use strict';

  /**
   * Determine whether HTTP-Safe AES encryption is active for current connection.
   * @returns {boolean} True if on HTTP and encryption toggle is checked.
   */
  function isHttpSafeEnabled() {
    const aesToggle = document.getElementById('enableEncryption');
    const isHTTP = location.protocol === 'http:';

    // HTTP-Safe metadata obfuscation is ONLY needed on HTTP connections.
    // On HTTPS, TLS already encrypts all headers, file names, and metadata natively.
    return isHTTP && !!(aesToggle && aesToggle.checked);
  }

  /**
   * Generate decoy network traffic to mask metadata timing patterns.
   */
  async function generateDecoyTraffic() {
    try {
      await fetch('/generate_decoy', { method: 'POST' });
    } catch (e) {
      console.log('Decoy traffic bypass:', e);
    }
  }

  /**
   * Send file to backend /encrypt_http_safe endpoint for AES metadata-obfuscated encryption.
   * @param {File} file - Original file object
   * @returns {Promise<Object>} Server response payload with obfuscated metadata
   */
  async function encryptFileHttpSafe(file) {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('http_safe', 'true');

    const response = await fetch('/encrypt_http_safe', { method: 'POST', body: formData });
    if (!response.ok) {
      throw new Error(`HTTP-Safe encryption failed with status ${response.status}`);
    }
    return await response.json();
  }

  /**
   * Create obfuscated upload structure wrapping encrypted metadata.
   * @param {Object} encryptedData - Response payload from /encrypt_http_safe
   * @param {File} file - Original file reference
   * @returns {Object} Obfuscated upload descriptor
   */
  function createObfuscatedUpload(encryptedData, file) {
    const dummyBlob = new Blob([], { type: 'application/octet-stream' });
    const obfuscatedName = (encryptedData && encryptedData.obfuscated_filename) ? encryptedData.obfuscated_filename : file.name;
    const obfuscatedFile = new File([dummyBlob], obfuscatedName, {
      type: 'application/octet-stream'
    });

    return {
      file: obfuscatedFile,
      originalName: file.name,
      originalSize: file.size,
      encryptedSize: (encryptedData && typeof encryptedData.encrypted_size === 'number') ? encryptedData.encrypted_size : file.size,
      metadata: (encryptedData && encryptedData.metadata) ? encryptedData.metadata : {}
    };
  }

  // Freeze immutable interface export
  const HttpSafeCrypto = Object.freeze({
    isHttpSafeEnabled: isHttpSafeEnabled,
    generateDecoyTraffic: generateDecoyTraffic,
    encryptFileHttpSafe: encryptFileHttpSafe,
    createObfuscatedUpload: createObfuscatedUpload
  });

  window.HttpSafeCrypto = HttpSafeCrypto;

  // Preserve global backward compatibility aliases
  window.isHttpSafeEnabled = window.isHttpSafeEnabled || isHttpSafeEnabled;
  window.generateDecoyTraffic = window.generateDecoyTraffic || generateDecoyTraffic;
  window.encryptFileHttpSafe = window.encryptFileHttpSafe || encryptFileHttpSafe;
  window.createObfuscatedUpload = window.createObfuscatedUpload || createObfuscatedUpload;

})(window);
