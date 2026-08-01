/**
 * @file connect-panel.js
 * @description Connect Panel UI, QR Code rendering, LAN/mDNS tab switching, and URL copy handlers.
 * @module ConnectPanel
 */

(function (window) {
    'use strict';

    if (window.ConnectPanel) {
        return;
    }

    function renderSidebarQR() {
        var qrBox = document.getElementById("qrBox");
        var connectAddress = document.getElementById("connectAddress");
        if (!qrBox) return;

        var url = window.location.origin;
        if (window._currentNetworkInfo && window._currentNetworkInfo.fullUrl) {
            url = window._currentNetworkInfo.fullUrl;
        }

        if (connectAddress) {
            connectAddress.textContent = url;
        }

        qrBox.innerHTML = "";
        var qrApiUrl = "/api/qr-code?text=" + encodeURIComponent(url) + "&size=140&_=" + Math.random().toString(36).substr(2, 9);
        var img = document.createElement("img");
        img.alt = "QR Code";
        img.style.cssText = "width:102px;height:102px;object-fit:contain;display:block;margin:0 auto;";
        img.src = qrApiUrl;
        img.onerror = function () {
            qrBox.innerHTML = '<div style="font-size:0.6rem;color:var(--text-muted);text-align:center;padding:8px;">Scan to connect</div>';
        };
        qrBox.appendChild(img);
    }

    function renderDialogQR() {
        var dialogBox = document.getElementById("connectQrDialogBox");
        var dialogAddress = document.getElementById("connectQrDialogAddress");
        if (!dialogBox) return;

        var url = window.location.origin;
        if (window._currentNetworkInfo && window._currentNetworkInfo.fullUrl) {
            url = window._currentNetworkInfo.fullUrl;
        }

        if (dialogAddress) {
            dialogAddress.textContent = url;
        }

        dialogBox.innerHTML = "";
        var qrApiUrl = "/api/qr-code?text=" + encodeURIComponent(url) + "&size=200&_=" + Math.random().toString(36).substr(2, 9);
        var img = document.createElement("img");
        img.alt = "QR Code";
        img.style.cssText = "max-width:100%;max-height:100%;object-fit:contain;display:block;margin:0 auto;";
        img.src = qrApiUrl;
        img.onerror = function () {
            dialogBox.innerHTML = '<div style="font-size:0.8rem;color:var(--text-muted);text-align:center;padding:12px;">Scan to connect</div>';
        };
        dialogBox.appendChild(img);
    }

    function copyQRUrl() {
        var connectAddress = document.getElementById("connectAddress");
        var url = connectAddress ? connectAddress.textContent : window.location.origin;
        if (navigator.clipboard && typeof navigator.clipboard.writeText === 'function') {
            navigator.clipboard.writeText(url).then(function () {
                if (typeof window.showToast === 'function') {
                    window.showToast("Connection URL copied to clipboard", "success");
                }
            }).catch(function () { });
        }
    }

    function copyStreamUrl(filename) {
        if (!filename) return;
        var url = window.location.origin + "/download/" + encodeURIComponent(filename);
        if (navigator.clipboard && typeof navigator.clipboard.writeText === 'function') {
            navigator.clipboard.writeText(url).then(function () {
                if (typeof window.showToast === 'function') {
                    window.showToast("Stream link copied to clipboard", "success");
                }
            }).catch(function () { });
        }
    }

    var ConnectPanel = Object.freeze({
        renderSidebarQR: renderSidebarQR,
        renderDialogQR: renderDialogQR,
        copyQRUrl: copyQRUrl,
        copyStreamUrl: copyStreamUrl
    });

    window.ConnectPanel = ConnectPanel;
    window.renderSidebarQR = renderSidebarQR;
    window.renderDialogQR = renderDialogQR;
    window.copyQRUrl = copyQRUrl;
    window.copyStreamUrl = copyStreamUrl;

})(window);
