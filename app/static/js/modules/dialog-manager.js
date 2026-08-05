/**
 * Dialog Manager
 *
 * Centralized launcher for modal dialogs (new folder, connect QR).
 * Manages dialog display state and input focus.
 */

(function (window) {
    'use strict';

    function openNewFolderDialog() {
        var contextMenu = document.getElementById("contextMenu");
        if (contextMenu) contextMenu.style.display = "none";

        var dialog = document.getElementById("newFolderDialog");
        var input = document.getElementById("newFolderNameInput");
        if (!dialog) return;

        dialog.style.display = "flex";

        if (input) {
            input.value = "Untitled folder";
            function doFocusAndSelect() {
                try {
                    input.focus({ preventScroll: true });
                    if (typeof input.setSelectionRange === "function") {
                        input.setSelectionRange(0, input.value.length);
                    } else if (typeof input.select === "function") {
                        input.select();
                    }
                } catch (e) { }
            }
            requestAnimationFrame(function () {
                requestAnimationFrame(function () {
                    doFocusAndSelect();
                });
            });
            setTimeout(doFocusAndSelect, 50);
            setTimeout(doFocusAndSelect, 150);
        }
    }

    function closeNewFolderDialog() {
        var dialog = document.getElementById("newFolderDialog");
        if (dialog) dialog.style.display = "none";
    }

    function openConnectQrDialog() {
        var dialog = document.getElementById("connectQrDialog");
        if (!dialog) return;
        dialog.style.display = "flex";
        if (typeof renderDialogQR === "function") renderDialogQR();
        if (typeof showConnectionInfo === "function") {
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

    window.DialogManager = {
        openNewFolderDialog: openNewFolderDialog,
        closeNewFolderDialog: closeNewFolderDialog,
        openConnectQrDialog: openConnectQrDialog,
        closeConnectQrDialog: closeConnectQrDialog
    };

    window.openNewFolderDialog = openNewFolderDialog;
    window.closeNewFolderDialog = closeNewFolderDialog;
    window.openConnectQrDialog = openConnectQrDialog;
    window.closeConnectQrDialog = closeConnectQrDialog;

})(window);
