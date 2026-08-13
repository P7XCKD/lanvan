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
    // Header Status pill update: status-warning (yellow) with 'Unavailable' text when running without network
    if (headerStatusPill && headerStatusText) {
      if (currentServerState === "running") {
        if (currentNetworkState === "disconnected") {
          headerStatusPill.className = "header-status-pill status-warning";
          headerStatusText.textContent = "Unavailable";
        } else {
          headerStatusPill.className = "header-status-pill status-running";
          headerStatusText.textContent = "Running";
        }
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
  // ==========================================================================
  // NEW UI INTERACTION HANDLERS
  // ==========================================================================
  if (newBtnStart) {
    newBtnStart.addEventListener("click", () => {
      updateServerState("running");
    });
  }

  if (newBtnStop) {
    newBtnStop.addEventListener("click", () => {
      updateServerState("stopped");
    });
  }

  if (newBtnSettings) {
    newBtnSettings.addEventListener("click", () => {
      newSettingsSheet.style.display = "flex";
    });
  }

  if (newBtnCloseSettings) {
    newBtnCloseSettings.addEventListener("click", () => {
      newSettingsSheet.style.display = "none";
    });
  }

  // --- NEW UI STORAGE SHEET & DIALOG HANDLERS ---
  const newStorageSheet = document.getElementById("new-storage-sheet");
  const newBtnCloseStorageSheet = document.getElementById("new-btn-close-storage-sheet");
  const newBtnOpenClearConfirm = document.getElementById("new-btn-open-clear-confirm");
  const storageSheetVal = document.getElementById("storage-sheet-val");
  const newBtnMainManageStorage = document.getElementById("new-btn-main-manage-storage");
  const newStorageMainVal = document.getElementById("new-storage-main-val");

  function openStorageManagementSheet() {
    if (storageSheetVal) storageSheetVal.textContent = `${storageMB.toFixed(2)} MB`;
    if (newStorageSheet) newStorageSheet.style.display = "flex";
  }

  if (newBtnManageStorage) {
    newBtnManageStorage.addEventListener("click", openStorageManagementSheet);
  }
  if (newBtnMainManageStorage) {
    newBtnMainManageStorage.addEventListener("click", openStorageManagementSheet);
  }

  if (newBtnCloseStorageSheet) {
    newBtnCloseStorageSheet.addEventListener("click", () => {
      if (newStorageSheet) newStorageSheet.style.display = "none";
    });
  }

  if (newBtnOpenClearConfirm) {
    newBtnOpenClearConfirm.addEventListener("click", () => {
      if (newConfirmModal) newConfirmModal.style.display = "flex";
      if (newBtnConfirmClear) {
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
      }
    });
  }

  if (newBtnCancelClear) {
    newBtnCancelClear.addEventListener("click", () => {
      if (newConfirmModal) newConfirmModal.style.display = "none";
    });
  }

  if (newBtnConfirmClear) {
    newBtnConfirmClear.addEventListener("click", () => {
      storageMB = 0.0;
      if (oldStorageText) oldStorageText.textContent = "Storage Used: 0.00 MB";
      if (newStorageVal) newStorageVal.textContent = "0.00 MB";
      if (storageSheetVal) storageSheetVal.textContent = "0.00 MB";
      if (newStorageMainVal) newStorageMainVal.textContent = "0.00 MB";
      if (newConfirmModal) newConfirmModal.style.display = "none";
      if (newStorageSheet) newStorageSheet.style.display = "none";
      alert("Simulated: Storage and clipboard data cleared!");
    });
  }

  if (newBtnCopyLogs) {
    newBtnCopyLogs.addEventListener("click", () => {
      alert("Simulated: Lanvan server logs copied to clipboard!");
    });
  }

  // --- COPY ADDRESS BUTTON WITH RELIABLE 2S TIMEOUT RESET ---
  let copyResetTimer = null;
  const originalCopyHtml = `<i data-lucide="copy" class="icon-xs"></i><span>Copy</span>`;

  if (newBtnCopyAddress) {
    newBtnCopyAddress.addEventListener("click", () => {
      const addrEl = document.getElementById("new-address-text");
      const text = addrEl ? addrEl.textContent : "";

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
        navigator.clipboard.writeText(text).catch(() => { });
      }
    });
  }

  // ==========================================================================
  // CONNECTION PROTOCOL DETAIL SHEET & SELECTION HANDLERS
  // ==========================================================================
  const rowConnectionProtocol = document.getElementById("new-row-connection-protocol");
  const newProtocolDetailSheet = document.getElementById("new-protocol-detail-sheet");
  const newBtnCloseProtocolDetail = document.getElementById("new-btn-close-protocol-detail");
  const protocolOptionHttp = document.getElementById("protocol-option-http");
  const protocolOptionHttps = document.getElementById("protocol-option-https");
  const protocolSummaryText = document.getElementById("new-protocol-summary-text");

  let currentProtocolSelection = "http"; // "http" (default) or "https"

  // Dynamically updates protocol detail card selections and main Settings summary text tag
  function updateProtocolUI() {
    if (!protocolSummaryText) return;

    if (currentProtocolSelection === "https") {
      if (protocolOptionHttp) protocolOptionHttp.classList.remove("active");
      if (protocolOptionHttps) protocolOptionHttps.classList.add("active");
      protocolSummaryText.innerHTML = `<span class="summary-item summary-on">HTTPS · Encrypted</span>`;
    } else {
      if (protocolOptionHttp) protocolOptionHttp.classList.add("active");
      if (protocolOptionHttps) protocolOptionHttps.classList.remove("active");
      protocolSummaryText.innerHTML = `<span class="summary-item summary-off">HTTP · Default</span>`;
    }
  }

  // Open protocol detail sheet when main Settings row is tapped
  if (rowConnectionProtocol && newProtocolDetailSheet) {
    rowConnectionProtocol.addEventListener("click", () => {
      newProtocolDetailSheet.style.display = "flex";
      if (window.lucide) window.lucide.createIcons();
    });
  }

  // Close protocol detail sheet
  if (newBtnCloseProtocolDetail && newProtocolDetailSheet) {
    newBtnCloseProtocolDetail.addEventListener("click", () => {
      newProtocolDetailSheet.style.display = "none";
    });
  }

  // Option selection handlers (only one protocol selected at a time)
  if (protocolOptionHttp) {
    protocolOptionHttp.addEventListener("click", () => {
      currentProtocolSelection = "http";
      updateProtocolUI();
    });
  }

  if (protocolOptionHttps) {
    protocolOptionHttps.addEventListener("click", () => {
      currentProtocolSelection = "https";
      updateProtocolUI();
    });
  }

  // Initial call on load
  updateProtocolUI();

  // ==========================================================================
  // BACKGROUND OPERATION DETAIL SHEET & STATE SWITCHER HANDLERS
  // ==========================================================================
  const rowBackgroundOperation = document.getElementById("new-row-background-operation");
  const newBackgroundDetailSheet = document.getElementById("new-background-detail-sheet");
  const newBtnCloseBackgroundDetail = document.getElementById("new-btn-close-background-detail");
  const bgSummaryText = document.getElementById("new-background-summary-text");
  const bgDetailStatusCard = document.getElementById("bg-detail-status-card");
  const bgDetailStatusTitle = document.getElementById("bg-detail-status-title");
  const bgDetailStatusSub = document.getElementById("bg-detail-status-sub");
  const bgStateButtons = document.querySelectorAll("#bg-state-control .btn-segment");
  const newBtnConfigureBackground = document.getElementById("new-btn-configure-background");

  let currentBgState = "allowed"; // "allowed", "restricted", "unknown"

  // Dynamically updates background summary tag, detail card state, and colors
  function updateBackgroundUI() {
    if (!bgSummaryText) return;

    // Update prototype toolbar segmented button active state
    bgStateButtons.forEach(btn => {
      if (btn.dataset.bg === currentBgState) {
        btn.classList.add("active");
      } else {
        btn.classList.remove("active");
      }
    });

    if (currentBgState === "allowed") {
      bgSummaryText.innerHTML = `<span class="summary-item summary-on">Allowed</span>`;
      if (bgDetailStatusCard) bgDetailStatusCard.className = "bg-status-card allowed";
      if (bgDetailStatusTitle) {
        bgDetailStatusTitle.textContent = "Allowed";
        bgDetailStatusTitle.style.color = "#8ab4f8";
      }
      if (bgDetailStatusSub) bgDetailStatusSub.textContent = "Lanvan can continue running in the background.";
    } else if (currentBgState === "restricted") {
      bgSummaryText.innerHTML = `<span class="summary-item summary-warning">Restricted</span>`;
      if (bgDetailStatusCard) bgDetailStatusCard.className = "bg-status-card restricted";
      if (bgDetailStatusTitle) {
        bgDetailStatusTitle.textContent = "Restricted";
        bgDetailStatusTitle.style.color = "#f9ab00";
      }
      if (bgDetailStatusSub) bgDetailStatusSub.textContent = "Android may stop Lanvan when it is running in the background.";
    } else {
      bgSummaryText.innerHTML = `<span class="summary-item summary-off">Unknown</span>`;
      if (bgDetailStatusCard) bgDetailStatusCard.className = "bg-status-card unknown";
      if (bgDetailStatusTitle) {
        bgDetailStatusTitle.textContent = "Unknown";
        bgDetailStatusTitle.style.color = "#9aa0a6";
      }
      if (bgDetailStatusSub) bgDetailStatusSub.textContent = "Background access status could not be determined.";
    }
  }

  // Open background detail sheet when main Settings row is tapped
  if (rowBackgroundOperation && newBackgroundDetailSheet) {
    rowBackgroundOperation.addEventListener("click", () => {
      newBackgroundDetailSheet.style.display = "flex";
      if (window.lucide) window.lucide.createIcons();
    });
  }

  // Close background detail sheet
  if (newBtnCloseBackgroundDetail && newBackgroundDetailSheet) {
    newBtnCloseBackgroundDetail.addEventListener("click", () => {
      newBackgroundDetailSheet.style.display = "none";
    });
  }

  // Handle toolbar state switcher buttons (Allowed / Restricted / Unknown)
  bgStateButtons.forEach(btn => {
    btn.addEventListener("click", () => {
      currentBgState = btn.dataset.bg;
      updateBackgroundUI();
    });
  });

  // Prototype action button inside detail sheet
  if (newBtnConfigureBackground) {
    newBtnConfigureBackground.addEventListener("click", () => {
      alert("Simulated: Opening Android System Battery & Background Access Settings");
    });
  }

  // Initial call on load
  updateBackgroundUI();

  // ==========================================================================
  // DANGEROUS FILE PROTECTION DETAIL SHEET & SUMMARY HANDLERS
  // ==========================================================================
  const rowDangerousProtection = document.getElementById("new-row-dangerous-protection");
  const newSecurityDetailSheet = document.getElementById("new-security-detail-sheet");
  const newBtnCloseSecurityDetail = document.getElementById("new-btn-close-security-detail");
  const switchBlockHttps = document.getElementById("new-switch-block-https");
  const switchBlockHttp = document.getElementById("new-switch-block-http");
  const securitySummaryText = document.getElementById("new-security-summary-text");

  // Dynamically updates the main Settings row summary tag with proper ON (blue) / OFF (grey) state colors
  function updateSecuritySummary() {
    if (!securitySummaryText || !switchBlockHttps || !switchBlockHttp) return;
    const isHttpOn = switchBlockHttp.checked;
    const isHttpsOn = switchBlockHttps.checked;

    const httpClass = isHttpOn ? "summary-on" : "summary-off";
    const httpsClass = isHttpsOn ? "summary-on" : "summary-off";

    const httpText = isHttpOn ? "On" : "Off";
    const httpsText = isHttpsOn ? "On" : "Off";

    securitySummaryText.innerHTML = `<span class="summary-item ${httpClass}">HTTP: ${httpText}</span><span class="summary-sep"> · </span><span class="summary-item ${httpsClass}">HTTPS: ${httpsText}</span>`;
  }

  // Open detail sheet when main Settings row is tapped
  if (rowDangerousProtection && newSecurityDetailSheet) {
    rowDangerousProtection.addEventListener("click", () => {
      newSecurityDetailSheet.style.display = "flex";
      if (window.lucide) window.lucide.createIcons();
    });
  }

  // Close detail sheet
  if (newBtnCloseSecurityDetail && newSecurityDetailSheet) {
    newBtnCloseSecurityDetail.addEventListener("click", () => {
      newSecurityDetailSheet.style.display = "none";
    });
  }

  // Update main Settings summary immediately when either toggle changes
  if (switchBlockHttps) {
    switchBlockHttps.addEventListener("change", updateSecuritySummary);
  }

  if (switchBlockHttp) {
    switchBlockHttp.addEventListener("change", updateSecuritySummary);
  }

  // Set initial summary state on load
  updateSecuritySummary();

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

  /*
  ==============================================================================
  FUTURE PRODUCTION GOOGLE PLAY BILLING CONCEPT NOTE
  ==============================================================================
  In production, Support Lanvan products map directly to Google Play Billing IDs:
  - Supporter: 'lanvan_support_tier_1' (Base price ₹49 / localized by Play Store)
  - Sponsor:   'lanvan_support_tier_2' (Base price ₹159 / localized by Play Store)
  - Patron:    'lanvan_support_tier_3' (Base price ₹399 / localized by Play Store)

  Google Play Billing client automatically handles localized currency display,
  regional taxes, and payment processing per user locale.
  ==============================================================================
  */

  supportTierCards.forEach(btn => {
    btn.addEventListener("click", () => {
      supportTierCards.forEach(b => b.classList.remove("active"));
      btn.classList.add("active");
    });
  });

  // ==========================================================================
  // HELP & FEEDBACK / DIAGNOSTICS WORKFLOW HANDLERS
  // ==========================================================================
  const newBtnSendFeedback = document.getElementById("new-btn-send-feedback");
  const newFeedbackSheet = document.getElementById("new-feedback-sheet");
  const newBtnCloseFeedback = document.getElementById("new-btn-close-feedback");
  const feedbackMessageInput = document.getElementById("feedback-message-input");
  const feedbackSwitchDiagnostics = document.getElementById("feedback-switch-diagnostics");
  const newBtnSubmitFeedback = document.getElementById("new-btn-submit-feedback");
  const newFeedbackConfirmDialog = document.getElementById("new-feedback-confirm-dialog");
  const newBtnCloseConfirm = document.getElementById("new-btn-close-confirm");
  const newBtnConfirmCloseAction = document.getElementById("new-btn-confirm-close-action");
  const feedbackConfirmTitle = document.getElementById("feedback-confirm-title");
  const feedbackConfirmMsg = document.getElementById("feedback-confirm-msg");

  // Open Send Feedback sheet
  if (newBtnSendFeedback && newFeedbackSheet) {
    newBtnSendFeedback.addEventListener("click", () => {
      if (feedbackMessageInput) feedbackMessageInput.value = "";
      newFeedbackSheet.style.display = "flex";
      if (window.lucide) window.lucide.createIcons();
    });
  }

  // Close Send Feedback sheet
  if (newBtnCloseFeedback && newFeedbackSheet) {
    newBtnCloseFeedback.addEventListener("click", () => {
      newFeedbackSheet.style.display = "none";
    });
  }

  /*
  ==============================================================================
  FUTURE PRODUCTION ANDROID IMPLEMENTATION NOTE
  ==============================================================================
  In the production Android app (Kotlin / ServerService.kt / MainActivity.kt):
  1. Do NOT use browser mailto: links or JS Blob downloads.
  2. Write diagnostic data to context.cacheDir:
     val diagFile = File(context.cacheDir, "lanvan-diagnostics-${dateStr}.txt")
  3. Use FileProvider to obtain a safe content URI:
     val contentUri = FileProvider.getUriForFile(context, "${packageName}.fileprovider", diagFile)
  4. Prepare an explicit Intent.ACTION_SEND:
     val intent = Intent(Intent.ACTION_SEND).apply {
         type = "text/plain"
         putExtra(Intent.EXTRA_EMAIL, arrayOf("p7xckd@gmail.com"))
         putExtra(Intent.EXTRA_SUBJECT, "Lanvan Feedback")
         putExtra(Intent.EXTRA_TEXT, "Hello Lanvan team,\n\n${userMessage}\n\nI've attached a diagnostic report to help investigate this issue.\n\nLanvan version: 1.0.0\n\nThank you,\nLanvan user")
         putExtra(Intent.EXTRA_STREAM, contentUri)
         addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
     }
     context.startActivity(Intent.createChooser(intent, "Send Feedback"))
  5. The user reviews the email in Gmail/Outlook and taps Send themselves.
  ==============================================================================
  */

  // Submit Feedback action handler with strict single-execution guard & timer tracking
  let isFeedbackSubmitting = false;

  const closeConfirmModal = () => {
    isFeedbackSubmitting = false;
    if (newFeedbackConfirmDialog) newFeedbackConfirmDialog.style.display = "none";
    if (newFeedbackSheet) newFeedbackSheet.style.display = "none";
  };

  if (newBtnCloseConfirm) newBtnCloseConfirm.addEventListener("click", closeConfirmModal);
  if (newBtnConfirmCloseAction) newBtnConfirmCloseAction.addEventListener("click", closeConfirmModal);

  if (newBtnSubmitFeedback) {
    newBtnSubmitFeedback.addEventListener("click", () => {
      // Guard against double clicks or repeated triggers
      if (isFeedbackSubmitting) return;
      isFeedbackSubmitting = true;

      const userMessage = feedbackMessageInput ? feedbackMessageInput.value.trim() : "";
      const feedbackText = userMessage || "(No feedback message provided)";
      const isDiagEnabled = feedbackSwitchDiagnostics ? feedbackSwitchDiagnostics.checked : true;
      const recipient = "p7xckd@gmail.com";
      const subject = "Lanvan Feedback";

      const currentDateStr = "2026-08-13";
      const fileName = `lanvan-diagnostics-${currentDateStr}.txt`;

      if (feedbackConfirmTitle) {
        feedbackConfirmTitle.textContent = "Feedback ready";
      }

      if (isDiagEnabled) {
        // --- 1. PROTOTYPE EMAIL BODY (Honest browser limitation wording) ---
        const emailBody = `Hello Lanvan team,\r\n\r\n${feedbackText}\r\n\r\nA diagnostic report was created:\r\n${fileName}\r\n\r\nThe browser prototype cannot attach local files automatically.\r\n\r\nLanvan version: 1.0.0\r\n\r\nThank you,\r\nLanvan user`;
        const mailtoUrl = `mailto:${recipient}?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(emailBody)}`;

        // --- 2. GATHER NON-SENSITIVE DIAGNOSTIC INFORMATION ---
        const switchBlockHttp = document.getElementById("new-switch-block-http");
        const switchBlockHttps = document.getElementById("new-switch-block-https");

        const httpBlock = switchBlockHttp ? (switchBlockHttp.checked ? "On" : "Off") : "Off";
        const httpsBlock = switchBlockHttps ? (switchBlockHttps.checked ? "On" : "Off") : "On";

        const bgStateFormatted = currentBgState.charAt(0).toUpperCase() + currentBgState.slice(1);
        const serverStateFormatted = currentServerState.charAt(0).toUpperCase() + currentServerState.slice(1);
        const netStateFormatted = currentNetworkState.charAt(0).toUpperCase() + currentNetworkState.slice(1);
        const protocolFormatted = currentProtocolSelection.toUpperCase();

        const diagReportText = `LANVAN DIAGNOSTIC REPORT
========================

Generated:
${currentDateStr}

Lanvan Version:
1.0.0

Android Version:
Android 14 (API 34)

Device:
Pixel / Modern Android (Prototype)

Server State:
${serverStateFormatted}

Network State:
${netStateFormatted}

Connection Protocol:
${protocolFormatted}

HTTP Dangerous File Protection:
${httpBlock}

HTTPS Dangerous File Protection:
${httpsBlock}

Background Operation:
${bgStateFormatted}

Storage Used:
${storageMB.toFixed(2)} MB

Recent Errors:
None`;

        // --- 3. DOWNLOAD DIAGNOSTIC FILE ONCE FOR INSPECTION ---
        const blob = new Blob([diagReportText], { type: "text/plain;charset=utf-8" });
        const downloadUrl = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = downloadUrl;
        a.download = fileName;
        a.click();
        setTimeout(() => URL.revokeObjectURL(downloadUrl), 1000);

        // --- 4. RENDER DIAGNOSTICS ON CONFIRMATION MESSAGE ---
        if (feedbackConfirmMsg) {
          feedbackConfirmMsg.innerHTML =
            `Your feedback has been added to an email draft.` +
            `<br><br>` +
            `<strong>Diagnostic report created:</strong><br>` +
            `<code style="color:#8ab4f8; font-size:12px;">${fileName}</code>` +
            `<br><br>` +
            `Your email app should now open.` +
            `<br><br>` +
            `<span style="font-size:11px; color:#9aa0a6;">The report was downloaded because the browser cannot attach local files automatically.</span>`;
        }

        // --- 5. OPEN MAIL APP ---
        try {
          window.location.href = mailtoUrl;
        } catch (e) {
          if (feedbackConfirmTitle) feedbackConfirmTitle.textContent = "Email app not available";
          if (feedbackConfirmMsg) feedbackConfirmMsg.innerHTML = "We couldn't open an email app on this device.";
        }
      } else {
        // --- DIAGNOSTICS OFF: FEEDBACK ONLY DRAFT ---
        const emailBody = `Hello Lanvan team,\r\n\r\n${feedbackText}\r\n\r\nLanvan version: 1.0.0\r\n\r\nThank you,\r\nLanvan user`;
        const mailtoUrl = `mailto:${recipient}?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(emailBody)}`;

        if (feedbackConfirmMsg) {
          feedbackConfirmMsg.innerHTML =
            `Your feedback has been added to an email draft.` +
            `<br><br>` +
            `Your email app should now open.`;
        }

        // Open mail app
        try {
          window.location.href = mailtoUrl;
        } catch (e) {
          if (feedbackConfirmTitle) feedbackConfirmTitle.textContent = "Email app not available";
          if (feedbackConfirmMsg) feedbackConfirmMsg.innerHTML = "We couldn't open an email app on this device.";
        }
      }

      // Show confirmation dialog
      if (newFeedbackConfirmDialog) {
        newFeedbackConfirmDialog.style.display = "flex";
      }
    });
   }

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
