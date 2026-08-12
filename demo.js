/**
 * Lanvan Android UI Prototype Logic (demo.js)
 * Manages side-by-side OLD vs NEW UI views, server state simulation, and Settings dialog interactions.
 */

document.addEventListener("DOMContentLoaded", () => {
  // Initialize Lucide icons if available
  if (window.lucide) {
    window.lucide.createIcons();
  }

  // --- STATE VARIABLES ---
  let currentView = "old"; // "old", "new", "compare"
  let serverState = "stopped"; // "stopped", "running"
  let storageMB = 21.37;

  // --- DOM ELEMENTS: CONTROLS ---
  const viewModeButtons = document.querySelectorAll("#view-mode-control .btn-segment");
  const serverStateButtons = document.querySelectorAll("#server-state-control .btn-segment");
  const viewportSelect = document.getElementById("viewport-preset");

  // --- DOM ELEMENTS: WRAPPERS & FRAMES ---
  const wrapperOld = document.getElementById("wrapper-old");
  const wrapperNew = document.getElementById("wrapper-new");
  const frameOld = document.getElementById("frame-old");
  const frameNew = document.getElementById("frame-new");

  // --- OLD UI ELEMENTS ---
  const oldBtnToggle = document.getElementById("old-btn-toggle");
  const oldStatusText = document.getElementById("old-status-text");
  const oldInactiveContainer = document.getElementById("old-inactive-container");
  const oldQrContainer = document.getElementById("old-qr-container");
  const oldBtnSettings = document.getElementById("old-btn-settings");
  const oldSettingsDialog = document.getElementById("old-settings-dialog");
  const oldBtnCloseSettings = document.getElementById("old-btn-close-settings");
  const oldBtnClearStorage = document.getElementById("old-btn-clear-storage");
  const oldConfirmDialog = document.getElementById("old-confirm-dialog");
  const oldBtnCancelClear = document.getElementById("old-btn-cancel-clear");
  const oldBtnConfirmClear = document.getElementById("old-btn-confirm-clear");
  const oldStorageText = document.getElementById("old-storage-text");
  const oldBtnCopyLogs = document.getElementById("old-btn-copy-logs");

  // --- NEW UI ELEMENTS ---
  const newBtnStart = document.getElementById("new-btn-start");
  const newBtnStop = document.getElementById("new-btn-stop");
  const newStoppedCard = document.getElementById("new-stopped-card");
  const newRunningCard = document.getElementById("new-running-card");
  const newBtnSettings = document.getElementById("new-btn-settings");
  const newSettingsSheet = document.getElementById("new-settings-sheet");
  const newBtnCloseSettings = document.getElementById("new-btn-close-settings");
  const newBtnManageStorage = document.getElementById("new-btn-manage-storage");
  const newConfirmModal = document.getElementById("new-confirm-modal");
  const newBtnCancelClear = document.getElementById("new-btn-cancel-clear");
  const newBtnConfirmClear = document.getElementById("new-btn-confirm-clear");
  const newStorageVal = document.getElementById("new-storage-val");
  const newBtnCopyLogs = document.getElementById("new-btn-copy-logs");
  const newBtnCopyAddress = document.getElementById("new-btn-copy-address");
  const headerStatusPill = document.getElementById("header-status-pill");
  const headerStatusText = document.getElementById("header-status-text");

  // ==========================================================================
  // VIEW MODE CONTROLLER (OLD UI vs NEW UI vs Compare)
  // ==========================================================================
  function updateViewMode(view) {
    currentView = view;

    viewModeButtons.forEach(btn => {
      if (btn.dataset.view === view) {
        btn.classList.add("active");
      } else {
        btn.classList.remove("active");
      }
    });

    if (view === "old") {
      wrapperOld.style.display = "flex";
      wrapperNew.style.display = "none";
    } else if (view === "new") {
      wrapperOld.style.display = "none";
      wrapperNew.style.display = "flex";
    } else if (view === "compare") {
      wrapperOld.style.display = "flex";
      wrapperNew.style.display = "flex";
    }
  }

  viewModeButtons.forEach(btn => {
    btn.addEventListener("click", () => {
      updateViewMode(btn.dataset.view);
    });
  });

  // ==========================================================================
  // SERVER STATE CONTROLLER (Stopped vs Running)
  // ==========================================================================
  let currentServerState = "stopped";
  let currentNetworkState = "connected";

  const newSupportCard = document.getElementById("new-support-section-card");

  function updateSupportCardVisibility() {
    if (newSupportCard) {
      // Support card is visible ONLY when server is STOPPED and network is CONNECTED
      if (currentServerState === "stopped" && currentNetworkState === "connected") {
        newSupportCard.style.display = "flex";
      } else {
        newSupportCard.style.display = "none";
      }
    }
  }

  const newDegradedCard = document.getElementById("new-degraded-card");
  const newNetWarning = document.getElementById("new-net-warning");
  const newBtnReconnectWifi = document.getElementById("new-btn-reconnect-wifi");
  const newBtnDegradedStop = document.getElementById("new-btn-degraded-stop");

  if (newBtnReconnectWifi) {
    newBtnReconnectWifi.addEventListener("click", () => {
      alert("Prototype: On Android, this opens system Wi-Fi / Hotspot settings.");
    });
  }

  if (newBtnDegradedStop) {
    newBtnDegradedStop.addEventListener("click", () => {
      updateServerState("stopped");
    });
  }

  function updateMainUIState() {
    // Header Status is always 'Running' when server is running, 'Stopped' when stopped
    if (headerStatusPill && headerStatusText) {
      if (currentServerState === "running") {
        headerStatusPill.className = "header-status-pill status-running";
        headerStatusText.textContent = "Running";
      } else {
        headerStatusPill.className = "header-status-pill status-stopped";
        headerStatusText.textContent = "Stopped";
      }
    }

    // Hide all main cards first to enforce strict 1-card primary context
    newStoppedCard.style.display = "none";
    newRunningCard.style.display = "none";
    if (newDegradedCard) newDegradedCard.style.display = "none";
    if (newNetWarning) newNetWarning.style.display = "none";

    if (currentServerState === "stopped") {
      newStoppedCard.style.display = "flex";
      if (currentNetworkState === "disconnected" && newNetWarning) {
        newNetWarning.style.display = "flex";
      }
    } else if (currentServerState === "running") {
      if (currentNetworkState === "connected") {
        newRunningCard.style.display = "flex";
      } else {
        // RUNNING + DISCONNECTED: Render ONE coherent degraded state card
        if (newDegradedCard) newDegradedCard.style.display = "flex";
      }
    }

    updateSupportCardVisibility();
  }

  function updateServerState(state) {
    currentServerState = state;
    serverState = state;

    serverStateButtons.forEach(btn => {
      if (btn.dataset.state === state) {
        btn.classList.add("active");
      } else {
        btn.classList.remove("active");
      }
    });

    // --- UPDATE OLD UI BASELINE ---
    if (state === "running") {
      oldBtnToggle.textContent = "Stop Server";
      oldBtnToggle.style.backgroundColor = "#B00020";
      oldStatusText.textContent = "Server is active: http://192.168.1.34:5000";
      oldInactiveContainer.style.display = "none";
      oldQrContainer.style.display = "flex";
    } else {
      oldBtnToggle.textContent = "Start Server";
      oldBtnToggle.style.backgroundColor = "#6200EE";
      oldStatusText.textContent = "Server is inactive.";
      oldInactiveContainer.style.display = "flex";
      oldQrContainer.style.display = "none";

      // OPTION 2: Auto-clear storage on shutdown if toggle is enabled
      const newSwitchAutoclear = document.getElementById("new-switch-autoclear");
      if (newSwitchAutoclear && newSwitchAutoclear.checked) {
        storageMB = 0.0;
        oldStorageText.textContent = "Storage Used: 0.00 MB";
        newStorageVal.textContent = "0.00 MB";
        storageSheetVal.textContent = "0.00 MB";
        if (newStorageMainVal) newStorageMainVal.textContent = "0.00 MB";
      }
    }

    updateMainUIState();
  }

  serverStateButtons.forEach(btn => {
    btn.addEventListener("click", () => {
      updateServerState(btn.dataset.state);
    });
  });

  // ==========================================================================
  // VIEWPORT PRESET RESIZER
  // ==========================================================================
  viewportSelect.addEventListener("change", (e) => {
    const val = e.target.value;
    if (val === "390x844") {
      frameOld.style.width = "390px";
      frameOld.style.height = "844px";
      frameNew.style.width = "390px";
      frameNew.style.height = "844px";
    } else if (val === "360x800") {
      frameOld.style.width = "360px";
      frameOld.style.height = "800px";
      frameNew.style.width = "360px";
      frameNew.style.height = "800px";
    } else if (val === "412x915") {
      frameOld.style.width = "412px";
      frameOld.style.height = "915px";
      frameNew.style.width = "412px";
      frameNew.style.height = "915px";
    } else if (val === "responsive") {
      frameOld.style.width = "100%";
      frameOld.style.height = "750px";
      frameNew.style.width = "100%";
      frameNew.style.height = "750px";
    }
  });

  // ==========================================================================
  // OLD UI INTERACTION HANDLERS
  // ==========================================================================
  oldBtnToggle.addEventListener("click", () => {
    const nextState = (serverState === "stopped") ? "running" : "stopped";
    updateServerState(nextState);
  });

  oldBtnSettings.addEventListener("click", () => {
    oldSettingsDialog.style.display = "flex";
  });

  oldBtnCloseSettings.addEventListener("click", () => {
    oldSettingsDialog.style.display = "none";
  });

  oldBtnClearStorage.addEventListener("click", () => {
    oldConfirmDialog.style.display = "flex";
    oldBtnConfirmClear.disabled = true;
    let count = 3;
    oldBtnConfirmClear.textContent = `Clear (${count}s)`;

    const timer = setInterval(() => {
      count--;
      if (count > 0) {
        oldBtnConfirmClear.textContent = `Clear (${count}s)`;
      } else {
        clearInterval(timer);
        oldBtnConfirmClear.textContent = "Clear Data";
        oldBtnConfirmClear.disabled = false;
      }
    }, 1000);
  });

  oldBtnCancelClear.addEventListener("click", () => {
    oldConfirmDialog.style.display = "none";
  });

  oldBtnConfirmClear.addEventListener("click", () => {
    storageMB = 0.0;
    oldStorageText.textContent = "Storage Used: 0.00 MB";
    newStorageVal.textContent = "0.00 MB uploaded files & clipboards";
    oldConfirmDialog.style.display = "none";
    alert("Simulated: Storage and clipboard data cleared!");
  });

  oldBtnCopyLogs.addEventListener("click", () => {
    alert("Simulated: Lanvan server logs copied to clipboard!");
  });

  // ==========================================================================
  // NEW UI INTERACTION HANDLERS
  // ==========================================================================
  newBtnStart.addEventListener("click", () => {
    updateServerState("running");
  });

  newBtnStop.addEventListener("click", () => {
    updateServerState("stopped");
  });

  newBtnSettings.addEventListener("click", () => {
    newSettingsSheet.style.display = "flex";
  });

  newBtnCloseSettings.addEventListener("click", () => {
    newSettingsSheet.style.display = "none";
  });

  // --- NEW UI STORAGE SHEET & DIALOG HANDLERS ---
  const newStorageSheet = document.getElementById("new-storage-sheet");
  const newBtnCloseStorageSheet = document.getElementById("new-btn-close-storage-sheet");
  const newBtnOpenClearConfirm = document.getElementById("new-btn-open-clear-confirm");
  const storageSheetVal = document.getElementById("storage-sheet-val");
  const newBtnMainManageStorage = document.getElementById("new-btn-main-manage-storage");
  const newStorageMainVal = document.getElementById("new-storage-main-val");

  function openStorageManagementSheet() {
    storageSheetVal.textContent = `${storageMB.toFixed(2)} MB`;
    newStorageSheet.style.display = "flex";
  }

  newBtnManageStorage.addEventListener("click", openStorageManagementSheet);
  if (newBtnMainManageStorage) {
    newBtnMainManageStorage.addEventListener("click", openStorageManagementSheet);
  }

  newBtnCloseStorageSheet.addEventListener("click", () => {
    newStorageSheet.style.display = "none";
  });

  newBtnOpenClearConfirm.addEventListener("click", () => {
    newConfirmModal.style.display = "flex";
    newBtnConfirmClear.disabled = true;
    let count = 3;
    newBtnConfirmClear.textContent = `Clear (${count}s)`;

    const timer = setInterval(() => {
      count--;
      if (count > 0) {
        newBtnConfirmClear.textContent = `Clear (${count}s)`;
      } else {
        clearInterval(timer);
        newBtnConfirmClear.textContent = "Clear Data";
        newBtnConfirmClear.disabled = false;
      }
    }, 1000);
  });

  newBtnCancelClear.addEventListener("click", () => {
    newConfirmModal.style.display = "none";
  });

  newBtnConfirmClear.addEventListener("click", () => {
    storageMB = 0.0;
    oldStorageText.textContent = "Storage Used: 0.00 MB";
    newStorageVal.textContent = "0.00 MB";
    storageSheetVal.textContent = "0.00 MB";
    if (newStorageMainVal) newStorageMainVal.textContent = "0.00 MB";
    newConfirmModal.style.display = "none";
    newStorageSheet.style.display = "none";
    alert("Simulated: Storage and clipboard data cleared!");
  });

  newBtnCopyLogs.addEventListener("click", () => {
    alert("Simulated: Lanvan server logs copied to clipboard!");
  });

  // --- COPY ADDRESS BUTTON WITH RELIABLE 2S TIMEOUT RESET ---
  let copyResetTimer = null;
  const originalCopyHtml = `<i data-lucide="copy" class="icon-xs"></i><span>Copy</span>`;

  newBtnCopyAddress.addEventListener("click", () => {
    const text = document.getElementById("new-address-text").textContent;
    
    // Clear any pending reset timer to avoid timer collisions
    if (copyResetTimer) {
      clearTimeout(copyResetTimer);
    }

    newBtnCopyAddress.innerHTML = `<i data-lucide="check" class="icon-xs"></i><span>Copied!</span>`;
    if (window.lucide) window.lucide.createIcons();

    // Reset back to original Copy button after 2000ms
    copyResetTimer = setTimeout(() => {
      newBtnCopyAddress.innerHTML = originalCopyHtml;
      if (window.lucide) window.lucide.createIcons();
      copyResetTimer = null;
    }, 2000);

    // Write to clipboard in background (or fallback gracefully)
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).catch(() => {});
    }
  });

  // ==========================================================================
  // SUPPORT LANVAN PROTOTYPE HANDLERS
  // ==========================================================================
  const newBtnOpenSupport = document.getElementById("new-btn-open-support");
  const newSupportModal = document.getElementById("new-support-modal");
  const newBtnCloseSupport = document.getElementById("new-btn-close-support");
  const newBtnConfirmSupport = document.getElementById("new-btn-confirm-support");
  const supportTierCards = document.querySelectorAll(".support-tier-card");

  if (newBtnOpenSupport) {
    newBtnOpenSupport.addEventListener("click", () => {
      newSupportModal.style.display = "flex";
    });
  }

  if (newBtnCloseSupport) {
    newBtnCloseSupport.addEventListener("click", () => {
      newSupportModal.style.display = "none";
    });
  }

  if (newBtnConfirmSupport) {
    newBtnConfirmSupport.addEventListener("click", () => {
      newSupportModal.style.display = "none";
      alert("Simulated: Thank you for testing the Support Lanvan prototype flow!");
    });
  }

  supportTierCards.forEach(btn => {
    btn.addEventListener("click", () => {
      supportTierCards.forEach(b => b.classList.remove("active"));
      btn.classList.add("active");
    });
  });

  // ==========================================================================
  // NAVIGATION MODE SWITCHER (Gesture vs 3-Button System Inset Simulation)
  // ==========================================================================
  const navModeButtons = document.querySelectorAll("#nav-mode-control .btn-segment");

  function updateNavMode(navMode) {
    navModeButtons.forEach(btn => {
      if (btn.dataset.nav === navMode) {
        btn.classList.add("active");
      } else {
        btn.classList.remove("active");
      }
    });

    if (navMode === "buttons") {
      frameNew.classList.add("nav-buttons");
      frameOld.classList.add("nav-buttons");
    } else {
      frameNew.classList.remove("nav-buttons");
      frameOld.classList.remove("nav-buttons");
    }
  }

  navModeButtons.forEach(btn => {
    btn.addEventListener("click", () => {
      updateNavMode(btn.dataset.nav);
    });
  });

  // ==========================================================================
  // NETWORK STATE SWITCHER (Connected vs Disconnected Prototype Control)
  // ==========================================================================
  const netStateButtons = document.querySelectorAll("#net-state-control .btn-segment");
  const newNetWarningTitle = document.getElementById("new-net-warning-title");
  const newNetWarningSub = document.getElementById("new-net-warning-sub");

  function updateWarningMessaging() {
    if (!newNetWarningTitle || !newNetWarningSub) return;

    if (currentServerState === "running") {
      newNetWarningTitle.textContent = "Network connection lost";
      newNetWarningSub.textContent = "Reconnect to Wi-Fi or enable a hotspot to allow Lanvan to keep sharing.";
    } else {
      newNetWarningTitle.textContent = "No network connection";
      newNetWarningSub.textContent = "Connect to Wi-Fi or enable a hotspot before starting Lanvan.";
    }
  }

  function updateNetworkState(netState) {
    currentNetworkState = netState;
    netStateButtons.forEach(btn => {
      if (btn.dataset.net === netState) {
        btn.classList.add("active");
      } else {
        btn.classList.remove("active");
      }
    });

    updateMainUIState();
  }

  netStateButtons.forEach(btn => {
    btn.addEventListener("click", () => {
      updateNetworkState(btn.dataset.net);
    });
  });

  // --- INITIALIZE DEFAULT VIEW & STATE ---
  updateViewMode("compare"); // Default to side-by-side comparison mode for instant evaluation
  updateServerState("stopped");
  updateNavMode("gesture");
  updateNetworkState("connected");
});
