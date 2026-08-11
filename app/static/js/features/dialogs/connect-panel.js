/**
 * Connect Panel
 *
 * Renders QR codes for LAN and mDNS connection URLs, manages tab switching
 * between IP and mDNS modes, and provides clipboard copy handlers.
 */

(function (window) {
    'use strict';

    if (window.ConnectPanel && window.ConnectPanel._initialized) {
        return;
    }

    function renderSidebarQR() {
        var qrBox = document.getElementById("qrBox");
        var connectAddress = document.getElementById("connectAddress");
        if (!qrBox) return;

        var netInfo = window._currentNetworkInfo;
        if (netInfo && netInfo.docker_needs_host_env) {
            if (connectAddress) {
                connectAddress.textContent = "http://localhost";
            }
            qrBox.innerHTML = '<div style="font-size:0.7rem;color:var(--text-muted);text-align:center;padding:10px 4px;line-height:1.35;">Set <strong>LANVAN_ADVERTISE_HOST</strong> in compose.yaml for mobile QR code</div>';
            return;
        }

        var url = window.location.origin;
        if (netInfo && netInfo.fullUrl) {
            url = netInfo.fullUrl;
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

        var netInfo = window._currentNetworkInfo;
        if (netInfo && netInfo.docker_needs_host_env) {
            if (dialogAddress) {
                dialogAddress.textContent = "http://localhost";
            }
            dialogBox.innerHTML = '<div style="font-size:0.85rem;color:var(--text-muted);text-align:center;padding:24px 12px;line-height:1.4;">To enable mobile phone QR scanning in Docker bridge mode,<br>set <strong>LANVAN_ADVERTISE_HOST=&lt;YOUR_PC_LAN_IP&gt;</strong> in <code>compose.yaml</code></div>';
            return;
        }

        var url = window.location.origin;
        if (netInfo && netInfo.fullUrl) {
            url = netInfo.fullUrl;
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

    function fallbackCopyTextToClipboard(text) {
        var textArea = document.createElement("textarea");
        textArea.value = text;
        textArea.style.position = "fixed";
        textArea.style.top = "0";
        textArea.style.left = "0";
        textArea.style.width = "2em";
        textArea.style.height = "2em";
        textArea.style.padding = "0";
        textArea.style.border = "none";
        textArea.style.outline = "none";
        textArea.style.boxShadow = "none";
        textArea.style.background = "transparent";
        textArea.style.opacity = "0.01";
        textArea.style.zIndex = "999999";
        document.body.appendChild(textArea);
        textArea.focus();
        textArea.select();
        if (typeof textArea.setSelectionRange === "function") {
            textArea.setSelectionRange(0, 99999);
        }
        var success = false;
        try {
            success = document.execCommand('copy');
        } catch (err) {
            console.error('[COPY] Fallback copy error', err);
        }
        document.body.removeChild(textArea);
        return success;
    }

    function setConnectMode(mode) {
        var lanTab = document.getElementById("lanIpTab");
        var mdnsTab = document.getElementById("mdnsTab");
        var qrLanTab = document.getElementById("connectQrLanIpTab");
        var qrMdnsTab = document.getElementById("connectQrMdnsTab");

        var isMdns = mode === "mdns";
        if (lanTab) lanTab.classList.toggle("active", !isMdns);
        if (mdnsTab) mdnsTab.classList.toggle("active", isMdns);
        if (qrLanTab) qrLanTab.classList.toggle("active", !isMdns);
        if (qrMdnsTab) qrMdnsTab.classList.toggle("active", isMdns);

        if (window._currentNetworkInfo) {
            var url = window._currentNetworkInfo.lanIpUrl;
            var isMdnsActive = window._currentNetworkInfo.networkInfo && 
                               window._currentNetworkInfo.networkInfo.mdns && 
                               window._currentNetworkInfo.networkInfo.mdns.status === 'active';
            if (isMdns && isMdnsActive) {
                url = window._currentNetworkInfo.networkInfo.mdns.url || url;
            }
            window._currentNetworkInfo.fullUrl = url;
            window._currentNetworkInfo.currentMode = mode;
            renderSidebarQR();
            renderDialogQR();
        }

        if (typeof window.updateMDNSStatus === "function") window.updateMDNSStatus();
    }

    function openConnectQrDialog() {
        var dialog = document.getElementById("connectQrDialog");
        if (!dialog) return;
        dialog.style.display = "flex";
        renderDialogQR();
        if (typeof window.showConnectionInfo === "function") {
            var protoAddr = document.getElementById("connectQrDialogAddress");
            if (protoAddr && window._currentNetworkInfo) {
                protoAddr.textContent = window._currentNetworkInfo.fullUrl || "";
            }
        }
    }

    function closeConnectQrDialog() {
        var dialog = document.getElementById("connectQrDialog");
        if (dialog) dialog.style.display = "none";
    }

    function copyConnectAddress() {
        var dialog = document.getElementById("connectQrDialog");
        var dialogActive = dialog && dialog.style.display !== "none";
        var addr = dialogActive ? document.getElementById("connectQrDialogAddress") : document.getElementById("connectAddress");
        if (!addr) {
            addr = document.getElementById("connectAddress") || document.getElementById("connectQrDialogAddress");
        }
        var textToCopy = addr ? addr.textContent.trim() : "";
        if (!textToCopy || textToCopy === "...") {
            textToCopy = (window._currentNetworkInfo && window._currentNetworkInfo.fullUrl) ? window._currentNetworkInfo.fullUrl : window.location.origin;
        }

        if (textToCopy) {
            if (navigator.clipboard && navigator.clipboard.writeText) {
                navigator.clipboard.writeText(textToCopy).catch(function () {
                    fallbackCopyTextToClipboard(textToCopy);
                });
            } else {
                fallbackCopyTextToClipboard(textToCopy);
            }
        }

        var tooltips = document.querySelectorAll(".connect-tooltip");
        for (var i = 0; i < tooltips.length; i++) {
            tooltips[i].textContent = "Copied successfully!";
            tooltips[i].classList.add("copied");
        }
        setTimeout(function () {
            for (var j = 0; j < tooltips.length; j++) {
                tooltips[j].textContent = "Click to copy";
                tooltips[j].classList.remove("copied");
            }
        }, 1800);

        if (typeof window.showToast === "function") {
            window.showToast("Connection URL copied to clipboard", "success");
        }
    }

    function setThemePreference(theme) {
        localStorage.setItem("theme_preference", theme);
        localStorage.setItem("dark_mode_enabled", theme === "dark" ? "1" : "0");
        if (typeof window.applyThemePreference === "function") {
            window.applyThemePreference(theme);
        }
    }

    function toggleDarkMode() {
        var currentPref = localStorage.getItem("theme_preference") || "system";
        var nextPref = "system";
        if (currentPref === "system") {
            nextPref = "light";
        } else if (currentPref === "light") {
            nextPref = "dark";
        } else {
            nextPref = "system";
        }
        setThemePreference(nextPref);
    }

    function openSettingsDialog() {
        var dialog = document.getElementById("settingsDialog");
        if (!dialog) return;

        var aesProd = document.getElementById("enableEncryption");
        var aesSetting = document.getElementById("aesSettingToggle");
        if (aesProd && aesSetting) aesSetting.checked = aesProd.checked;

        var themePref = localStorage.getItem("theme_preference") || "system";
        if (typeof window.applyThemePreference === "function") {
            window.applyThemePreference(themePref);
        }

        dialog.style.display = "flex";

        if (aesSetting) {
            aesSetting.onchange = function () {
                if (aesProd) {
                    aesProd.checked = this.checked;
                    localStorage.setItem("aes_enabled", this.checked ? "1" : "0");
                    aesProd.dispatchEvent(new Event("change", { bubbles: true }));
                }
            };
        }
    }

    function closeSettingsDialog() {
        var dialog = document.getElementById("settingsDialog");
        if (dialog) dialog.style.display = "none";
    }

    var ConnectPanel = Object.freeze({
        _initialized: true,
        renderSidebarQR: renderSidebarQR,
        renderDialogQR: renderDialogQR,
        copyQRUrl: copyQRUrl,
        copyStreamUrl: copyStreamUrl,
        setConnectMode: setConnectMode,
        openConnectQrDialog: openConnectQrDialog,
        closeConnectQrDialog: closeConnectQrDialog,
        copyConnectAddress: copyConnectAddress,
        fallbackCopyTextToClipboard: fallbackCopyTextToClipboard,
        openSettingsDialog: openSettingsDialog,
        closeSettingsDialog: closeSettingsDialog,
        setThemePreference: setThemePreference,
        toggleDarkMode: toggleDarkMode
    });

    window.ConnectPanel = ConnectPanel;
    window.SettingsConnectManager = ConnectPanel;
    window.renderSidebarQR = renderSidebarQR;
    window.renderDialogQR = renderDialogQR;
    window.copyQRUrl = copyQRUrl;
    window.copyStreamUrl = copyStreamUrl;
    window.setConnectMode = setConnectMode;
    window.openConnectQrDialog = openConnectQrDialog;
    window.closeConnectQrDialog = closeConnectQrDialog;
    window.copyConnectAddress = copyConnectAddress;
    window.fallbackCopyTextToClipboard = fallbackCopyTextToClipboard;
    window.openSettingsDialog = openSettingsDialog;
    window.closeSettingsDialog = closeSettingsDialog;
    window.setThemePreference = setThemePreference;
    window.toggleDarkMode = toggleDarkMode;

})(window);
