/**
 * @file main-app.js
 * @description Main application orchestrator for Lanvan. Manages async chunked uploads,
 *              Web Crypto AES encryption, WebSockets clipboard sync, and drag-drop events.
 * @module MainApp
 * @dependency file-utils.js, ui-modules.js
 */
//  Conditional Logging System - Production Performance Optimization
// Global DEBUG variables to avoid duplicate declarations across scripts
// Preserve DEBUG_MODE set by logger.js (or localStorage 'debug')
if (typeof window.DEBUG_MODE !== 'boolean') {
  try {
    var storedDebug = localStorage.getItem('debug');
    window.DEBUG_MODE = storedDebug === 'true';
  } catch (e) {
    window.DEBUG_MODE = false;
  }
}
window.DEBUG_LEVELS = {
  ERROR: 0,   // Always shown (security, critical errors)
  WARN: 1,    // Important warnings
  INFO: 2,    // General information
  DEBUG: 3    // Detailed debugging (upload progress, etc.)
};

window.currentLogLevel = window.DEBUG_MODE ? window.DEBUG_LEVELS.DEBUG : window.DEBUG_LEVELS.ERROR;

// Optimized logging functions - Global to avoid duplicate declarations
window.log = {
  error: (msg, ...args) => {
    if (window.currentLogLevel >= window.DEBUG_LEVELS.ERROR) console.error('', msg, ...args);
  },
  warn: (msg, ...args) => {
    if (window.currentLogLevel >= window.DEBUG_LEVELS.WARN) console.warn('', msg, ...args);
  },
  info: (msg, ...args) => {
    if (window.currentLogLevel >= window.DEBUG_LEVELS.INFO) console.info('ℹ', msg, ...args);
  },
  debug: (msg, ...args) => {
    if (window.currentLogLevel >= window.DEBUG_LEVELS.DEBUG) console.log('', msg, ...args);
  },
  upload: (msg, ...args) => {
    if (window.currentLogLevel >= window.DEBUG_LEVELS.DEBUG) console.log('', msg, ...args);
  },
  network: (msg, ...args) => {
    if (window.currentLogLevel >= window.DEBUG_LEVELS.DEBUG) console.log('', msg, ...args);
  }
};

if (!window.__LANVAN_FORENSIC_TRACE) {
  window.__LANVAN_FORENSIC_TRACE = [];
}

if (typeof window.__lanvanForensicEmit !== 'function') {
  window.__lanvanForensicEmit = function (stage, eventName, payload) {
    try {
      var data = payload || {};
      var entry = {
        timestamp: new Date().toISOString(),
        stage: stage || '',
        event: eventName || '',
        folder: data.folder || '',
        name: data.name || '',
        identity: data.identity || '',
        details: data.details || {}
      };
      window.__LANVAN_FORENSIC_TRACE.push(entry);
      console.log('[LANVAN-FORENSIC]', entry);
      return entry;
    } catch (err) {
      return null;
    }
  };
}

if (typeof window.__lanvanForensicSnapshotRepoCache !== 'function') {
  window.__lanvanForensicSnapshotRepoCache = function (label) {
    try {
      var repo = window.FileRepository;
      var cache = (repo && repo.cache) ? repo.cache : {};
      function folderNames(folder) {
        var list = cache[folder] || [];
        if (!Array.isArray(list)) return [];
        return list.map(function (item) {
          if (!item) return null;
          return (typeof item === 'string') ? item : item.name;
        }).filter(Boolean);
      }
      var snapshot = {
        root: folderNames(''),
        inside: folderNames('Inside'),
        insideNested: folderNames('Inside/Nested')
      };
      console.log('[REAL REPOSITORY ' + label + ']');
      console.log('cache["\"] =', snapshot.root);
      console.log('cache["Inside"] =', snapshot.inside);
      console.log('cache["Inside/Nested"] =', snapshot.insideNested);
      window.__lanvanForensicEmit('repository', 'cache_' + String(label || '').toLowerCase(), {
        folder: (typeof window.getCurrentFolderPath === 'function' ? window.getCurrentFolderPath() : (window.currentFolderPath || '')),
        details: snapshot
      });
      return snapshot;
    } catch (err) {
      console.error('[LANVAN-FORENSIC] repository snapshot failed', err);
      return null;
    }
  };
}

if (typeof window.__lanvanForensicTraceV2 !== 'function') {
  window.__lanvanForensicTraceV2 = function (stage, folder, item, present, source) {
    try {
      var name = item && item.name ? item.name : '';
      if (!name || name.toLowerCase().indexOf('v2') === -1) return;
      var identity = item && item.identity ? item.identity : ((typeof window.getCanonicalIdentity === 'function') ? window.getCanonicalIdentity(folder || '', name) : name);
      var row = {
        timestamp: new Date().toISOString(),
        stage: stage,
        folder: folder || '',
        name: name,
        identity: identity,
        source: source || '',
        present: !!present
      };
      console.log('[REAL V2 TRACE]', row);
      window.__lanvanForensicEmit('v2', stage, {
        folder: row.folder,
        name: row.name,
        identity: row.identity,
        details: {
          source: row.source,
          present: row.present
        }
      });
    } catch (err) {
    }
  };
}

if (!window.__LANVAN_FORENSIC_V2_SEEN) {
  window.__LANVAN_FORENSIC_V2_SEEN = {};
}

if (typeof window.__lanvanForensicTraceV2List !== 'function') {
  window.__lanvanForensicTraceV2List = function (stage, folder, items, source) {
    try {
      var f = folder || '';
      var seenKey = f || '__root__';
      if (!window.__LANVAN_FORENSIC_V2_SEEN[seenKey]) {
        window.__LANVAN_FORENSIC_V2_SEEN[seenKey] = {};
      }
      var seenMap = window.__LANVAN_FORENSIC_V2_SEEN[seenKey];
      var presentMap = {};
      var list = Array.isArray(items) ? items : [];
      for (var i = 0; i < list.length; i++) {
        var item = list[i] || {};
        var name = typeof item === 'string' ? item : item.name;
        if (!name || String(name).toLowerCase().indexOf('v2') === -1) continue;
        var obj = (typeof item === 'string')
          ? { name: name, identity: (typeof window.getCanonicalIdentity === 'function' ? window.getCanonicalIdentity(f, name) : name) }
          : item;
        presentMap[name] = true;
        seenMap[name] = true;
        window.__lanvanForensicTraceV2(stage, f, obj, true, source || '');
      }
      var seenNames = Object.keys(seenMap);
      for (var j = 0; j < seenNames.length; j++) {
        var seenName = seenNames[j];
        if (!presentMap[seenName]) {
          window.__lanvanForensicTraceV2(stage, f, {
            name: seenName,
            identity: (typeof window.getCanonicalIdentity === 'function' ? window.getCanonicalIdentity(f, seenName) : seenName)
          }, false, source || '');
        }
      }
    } catch (err) {
    }
  };
}

if (typeof window.__lanvanForensicDumpUploadQueue !== 'function') {
  window.__lanvanForensicDumpUploadQueue = function () {
    var queue = Array.isArray(window.uploadQueue) ? window.uploadQueue : [];
    var totals = { total: queue.length, active: 0, queued: 0, completed: 0, cancelled: 0, failed: 0 };
    var projectionItems = [];
    try {
      var folder = (typeof window.getCurrentFolderPath === 'function') ? window.getCurrentFolderPath() : (window.currentFolderPath || '');
      var repoFiles = (window.FileRepository && typeof window.FileRepository.getFolderCache === 'function') ? window.FileRepository.getFolderCache(folder) : [];
      var state = window.LanvanStore ? Object.assign({}, window.LanvanStore.state) : { currentFolder: folder, uploadQueue: queue, pendingOps: {} };
      state.currentFolder = folder;
      state.uploadQueue = queue;
      var vm = window.ProjectionLayer && window.ProjectionLayer.buildCurrentFolderViewModel
        ? window.ProjectionLayer.buildCurrentFolderViewModel(state, repoFiles)
        : [];
      projectionItems = Array.isArray(vm) ? vm : (vm.visibleFiles || []);
    } catch (e) {
    }

    var completedMatchesDisk = 0;
    var completedInProjection = 0;
    var completedSuppressCandidates = 0;
    var folderNow = (typeof window.getCurrentFolderPath === 'function') ? window.getCurrentFolderPath() : (window.currentFolderPath || '');
    var cleanFolder = typeof window.cleanFolderPath === 'function' ? window.cleanFolderPath(folderNow) : (folderNow || '').replace(/^Home\/?/, '');
    var repoNow = (window.FileRepository && typeof window.FileRepository.getFolderCache === 'function') ? window.FileRepository.getFolderCache(cleanFolder) : [];

    console.log('[REAL UPLOAD QUEUE]');
    for (var i = 0; i < queue.length; i++) {
      var q = queue[i] || {};
      var name = q.fileName || (q.file && q.file.name) || q.name || '';
      var targetDir = q.targetDir || q.parent_path || q.folder || '';
      var identity = q.identity || (typeof window.getCanonicalIdentity === 'function' ? window.getCanonicalIdentity(targetDir, name) : name);
      var status = String(q.status || '').toUpperCase();
      if (status === 'UPLOADING' || status === 'PROCESSING') totals.active++;
      else if (status === 'QUEUED') totals.queued++;
      else if (status === 'COMPLETED') totals.completed++;
      else if (status === 'CANCELLED' || status === 'DELETED') totals.cancelled++;
      else if (status === 'FAILED' || status === 'ERROR') totals.failed++;

      var diskMatch = false;
      var projMatch = false;
      for (var r = 0; r < repoNow.length; r++) {
        var ri = repoNow[r];
        var rn = (typeof ri === 'string') ? ri : (ri && ri.name);
        var rid = (ri && ri.identity) ? ri.identity : (typeof window.getCanonicalIdentity === 'function' ? window.getCanonicalIdentity(cleanFolder, rn || '') : rn || '');
        if (rn && rn === name && rid === identity) {
          diskMatch = true;
          break;
        }
      }
      for (var p = 0; p < projectionItems.length; p++) {
        var pi = projectionItems[p];
        if (!pi) continue;
        var pn = pi.name;
        var pid = pi.identity || (typeof window.getCanonicalIdentity === 'function' ? window.getCanonicalIdentity(cleanFolder, pn || '') : pn || '');
        if (pn && pn === name && pid === identity) {
          projMatch = true;
          break;
        }
      }
      if (status === 'COMPLETED') {
        if (diskMatch) completedMatchesDisk++;
        if (projMatch) completedInProjection++;
        if (projMatch && !diskMatch) completedSuppressCandidates++;
      }

      console.log('queueId=' + (q.id || '') + ' name=' + name + ' targetDir=' + targetDir + ' identity=' + identity + ' status=' + status);
      window.__lanvanForensicEmit('upload_queue', 'item', {
        folder: cleanFolder,
        name: name,
        identity: identity,
        details: { queueId: q.id || null, targetDir: targetDir, status: status }
      });
    }
    console.log('total=' + totals.total + ' active=' + totals.active + ' queued=' + totals.queued + ' completed=' + totals.completed + ' cancelled=' + totals.cancelled + ' failed=' + totals.failed);
    console.log('completed items matching disk files=' + completedMatchesDisk);
    console.log('completed items included in Projection=' + completedInProjection);
    console.log('completed items capable of suppressing disk items=' + completedSuppressCandidates);
    window.__lanvanForensicEmit('upload_queue', 'summary', {
      folder: cleanFolder,
      details: {
        totals: totals,
        completedMatchesDisk: completedMatchesDisk,
        completedInProjection: completedInProjection,
        completedSuppressCandidates: completedSuppressCandidates
      }
    });
    return {
      totals: totals,
      completedMatchesDisk: completedMatchesDisk,
      completedInProjection: completedInProjection,
      completedSuppressCandidates: completedSuppressCandidates
    };
  };
}

if (typeof window.__lanvanForensicExportTrace !== 'function') {
  window.__lanvanForensicExportTrace = function () {
    var trace = Array.isArray(window.__LANVAN_FORENSIC_TRACE) ? window.__LANVAN_FORENSIC_TRACE : [];
    return fetch('/api/forensic/export-trace', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ trace: trace })
    }).then(function (res) {
      return res.json();
    }).then(function (data) {
      console.log('[LANVAN-FORENSIC] export result', data);
      return data;
    });
  };
}

// Use window.log directly throughout this script to avoid any conflicts
// No local const log declaration needed

const show_clipboard_only = window.LanvanConfig ? window.LanvanConfig.showClipboardOnly : false;

// Safari-Optimized Clipboard WebSocket for clipboard-only mode
if (typeof show_clipboard_only !== 'undefined' && show_clipboard_only) {
  let ws = null;
  let wsConnectAttempts = 0;
  let wsMaxAttempts = window.isiOSSafari ? 3 : 10;
  let wsHealthCheck = null;

  function connectClipboardWS() {
    if (wsConnectAttempts >= wsMaxAttempts) {
      window.log.warn('Max WebSocket attempts reached, switching to polling mode');
      startPollingMode();
      return;
    }

    wsConnectAttempts++;
    const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws';
    const wsUrl = `${protocol}://${window.location.host}/ws/clipboard`;

    try {
      ws = new WebSocket(wsUrl);

      // Safari connection timeout
      const connectTimeout = setTimeout(() => {
        if (ws && ws.readyState === WebSocket.CONNECTING) {
          window.log.warn('WebSocket connection timeout');
          ws.close();
        }
      }, window.isiOSSafari ? 3000 : 8000);

      ws.onopen = () => {
        clearTimeout(connectTimeout);
        wsConnectAttempts = 0; // Reset on success
        window.log.network('Clipboard WebSocket connected');
        if (clipboardPollingInterval) {
          clearInterval(clipboardPollingInterval);
          clipboardPollingInterval = null;
        }

        // Start health check for Safari
        if (window.isiOSSafari) {
          wsHealthCheck = setInterval(() => {
            if (ws && ws.readyState === WebSocket.OPEN) {
              try { ws.send('ping'); } catch (e) { /* ignore */ }
            }
          }, 30000);
        }

        if (typeof refreshClipboardHistory === 'function') {
          setTimeout(() => refreshClipboardHistory(), window.isiOSSafari ? 300 : 50);
        }
      };

      ws.onmessage = (event) => {
        if (event.data === 'refresh') {
          if (typeof refreshClipboardHistory === 'function') {
            setTimeout(() => refreshClipboardHistory(), window.isiOSSafari ? 200 : 0);
          }
        }
      };

      ws.onclose = () => {
        clearTimeout(connectTimeout);
        if (wsHealthCheck) {
          clearInterval(wsHealthCheck);
          wsHealthCheck = null;
        }

        const retryDelay = window.isiOSSafari ?
          Math.min(5000, 1000 * wsConnectAttempts) : 1000; // Exponential backoff for Safari

        setTimeout(connectClipboardWS, retryDelay);
      };

      ws.onerror = (error) => {
        clearTimeout(connectTimeout);
        window.log.warn('Clipboard WebSocket error:', error);
        if (ws) ws.close();
      };

    } catch (error) {
      window.log.error('Failed to create clipboard WebSocket:', error);
      if (window.isiOSSafari) startPollingMode();
    }
  }

  // Polling fallback for Safari
  let clipboardPollingInterval = null;
  function startPollingMode() {
    if (clipboardPollingInterval) return;
    window.log.info('Starting polling fallback for clipboard');
    clipboardPollingInterval = setInterval(() => {
      if (document.hidden) return;
      if (typeof refreshClipboardHistory === 'function') {
        refreshClipboardHistory();
      }
    }, window.isiOSSafari ? 10000 : 5000);
  }

  // Delayed connection for Safari
  window.progressiveLoader.addEnhanced(() => {
    const delay = window.isiOSSafari ? 2000 : 100;
    setTimeout(connectClipboardWS, delay);
  });

  window.addEventListener('beforeunload', () => {
    if (ws) ws.close();
    if (wsHealthCheck) clearInterval(wsHealthCheck);
  });
} else {
  // Clipboard WebSocket for regular mode (when both sections are available)
  let clipboardWS = null;
  function connectRegularClipboardWS() {
    // Only connect if clipboard section exists
    const clipboardSection = document.getElementById('clipboardSection');
    if (!clipboardSection) return;

    const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws';
    const wsUrl = `${protocol}://${window.location.host}/ws/clipboard`;
    clipboardWS = new WebSocket(wsUrl);
    clipboardWS.onopen = () => {
      window.log.network('Regular mode clipboard WebSocket connected');
      // Refresh clipboard history when WebSocket (re)connects
      if (typeof refreshClipboardHistory === 'function') {
        setTimeout(() => refreshClipboardHistory(), 50); // Reduced from 100ms for responsiveness
      }
    };
    clipboardWS.onmessage = (event) => {
      try {
        const raw = typeof event.data === 'string' ? event.data : '';
        if (raw === 'refresh' || raw.includes('refresh') || raw.includes('clear') || raw.includes('delete')) {
          window.log.debug('Clipboard update received via WebSocket:', raw);
          if (typeof refreshClipboardHistory === 'function') refreshClipboardHistory();
        }
      } catch (err) {
        if (typeof refreshClipboardHistory === 'function') refreshClipboardHistory();
      }
    };
    clipboardWS.onclose = () => {
      window.log.warn('Clipboard WebSocket disconnected, will reconnect...');
      // Try to reconnect after reduced delay if disconnected
      setTimeout(connectRegularClipboardWS, 1000); // Reduced from 2000ms
    };
    clipboardWS.onerror = () => {
      clipboardWS.close();
    };
  }

  // Connect clipboard WebSocket when DOM is ready
  document.addEventListener('DOMContentLoaded', () => {
    // Small delay to ensure clipboard functions are defined
    setTimeout(connectRegularClipboardWS, 1000);
  });

  window.addEventListener('beforeunload', () => {
    if (clipboardWS) clipboardWS.close();
  });
}

// WebSocket Exponential Backoff Strategy Helper
let uploadWsBackoffDelay = 1000;
let fileEventsWsBackoffDelay = 1000;

function getNextWsBackoffDelay(currentDelay) {
  const nextDelay = Math.min(currentDelay * 2, 10000);
  const jitter = (Math.random() * 0.4 - 0.2) * nextDelay;
  return Math.max(1000, Math.floor(nextDelay + jitter));
}

//  Upload Status WebSocket for low-latency real-time cross-device sync
let uploadWs = null;
let uploadWsReconnectTimer = null;

function initUploadWebSocket() {
  if (uploadWs && (uploadWs.readyState === WebSocket.CONNECTING || uploadWs.readyState === WebSocket.OPEN)) {
    return;
  }

  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const wsUrl = `${protocol}//${window.location.host}/ws/upload-status`;

  try {
    uploadWs = new WebSocket(wsUrl);

    uploadWs.onopen = function () {
      console.log('[WS UPLOAD] 🟢 Connected to Upload Status WebSocket');
      uploadWsBackoffDelay = 1000;
      if (uploadWsReconnectTimer) {
        clearTimeout(uploadWsReconnectTimer);
        uploadWsReconnectTimer = null;
      }
    };

    uploadWs.onmessage = function (event) {
      try {
        const payload = JSON.parse(event.data);
        if (window.__lanvanTimelineTracker) {
          window.__lanvanTimelineTracker.recordEvent("wsEvent", "uploadWs: " + payload.type);
        }
        if (payload.type === 'file_list_updated' || payload.type === 'upload_complete') {
          console.log('[WS UPLOAD] 🔄 Received real-time sync event across devices:', payload);
          if (typeof window.requestSafeVisibleFilesRefresh === 'function') {
            window.requestSafeVisibleFilesRefresh(120);
          } else if (typeof refreshFileList === 'function') {
            refreshFileList();
          }
        }
      } catch (e) { }
    };

    uploadWs.onclose = function () {
      uploadWs = null;
      if (!uploadWsReconnectTimer) {
        uploadWsBackoffDelay = getNextWsBackoffDelay(uploadWsBackoffDelay);
        uploadWsReconnectTimer = setTimeout(initUploadWebSocket, uploadWsBackoffDelay);
      }
    };

    uploadWs.onerror = function () {
      if (uploadWs) {
        try { uploadWs.close(); } catch (e) { }
      }
    };
  } catch (err) {
    if (!uploadWsReconnectTimer) {
      uploadWsBackoffDelay = getNextWsBackoffDelay(uploadWsBackoffDelay);
      uploadWsReconnectTimer = setTimeout(initUploadWebSocket, uploadWsBackoffDelay);
    }
  }
}

//  Real-Time Cross-Device File Events WebSocket
let fileEventsWs = null;
let fileEventsWsReconnectTimer = null;

function initFileEventsWebSocket() {
  if (fileEventsWs && (fileEventsWs.readyState === WebSocket.CONNECTING || fileEventsWs.readyState === WebSocket.OPEN)) {
    return;
  }

  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const wsUrl = `${protocol}//${window.location.host}/ws/file_events`;

  try {
    fileEventsWs = new WebSocket(wsUrl);

    fileEventsWs.onopen = function () {
      console.log('[WS FILE EVENTS] 🟢 Connected to Cross-Device Real-Time File Sync');
      fileEventsWsBackoffDelay = 1000;
      if (fileEventsWsReconnectTimer) {
        clearTimeout(fileEventsWsReconnectTimer);
        fileEventsWsReconnectTimer = null;
      }
    };

    fileEventsWs.onmessage = function (event) {
      try {
        const payload = JSON.parse(event.data);
        if (window.__lanvanTimelineTracker) {
          window.__lanvanTimelineTracker.recordEvent("wsEvent", "fileEventsWs: " + payload.type);
        }
        if (payload.type === 'file_change') {
          console.log('[WS FILE EVENTS] ⚡ Real-time file system mutation event received across devices:', payload);
          console.log("[TRACE] WebSocket event | action: '" + payload.action + "' | target_dir: '" + payload.target_dir + "' | path: '" + payload.path + "'");
          var wsFolder = (typeof window.getCurrentFolderPath === 'function') ? window.getCurrentFolderPath() : (window.currentFolderPath || '');
          var wsName = payload.path || '';
          var wsIdentity = (typeof window.getCanonicalIdentity === 'function')
            ? window.getCanonicalIdentity(payload.target_dir || '', wsName)
            : wsName;
          console.log('[REAL WS RECEIVE] timestamp=' + new Date().toISOString() + ' action=' + payload.action + ' target_dir=' + (payload.target_dir || '') + ' path=' + (payload.path || '') + ' filename=' + wsName + ' canonicalIdentity=' + wsIdentity);
          if (typeof window.__lanvanForensicEmit === 'function') {
            window.__lanvanForensicEmit('websocket_receive', payload.action || 'file_change', {
              folder: wsFolder,
              name: wsName,
              identity: wsIdentity,
              details: {
                action: payload.action || '',
                target_dir: payload.target_dir || '',
                path: payload.path || ''
              }
            });
          }

          var beforeSnap = (typeof window.__lanvanForensicSnapshotRepoCache === 'function')
            ? window.__lanvanForensicSnapshotRepoCache('BEFORE')
            : null;

          // Clean up recently-created folder tracking (ephemeral, no DOM mutation)
          var delTarget = payload.path || payload.target_dir || "";
          if (delTarget && window._recentlyCreatedFolders) {
            delete window._recentlyCreatedFolders[delTarget];
          }
          _activeRefreshPromise = null;
          // Canonical pipeline: API → Repository → Scheduler → Projection → Renderer
          var refreshResult = refreshFileList('ws_file_change');
          if (refreshResult && typeof refreshResult.then === 'function') {
            refreshResult.then(function () {
              var afterSnap = (typeof window.__lanvanForensicSnapshotRepoCache === 'function')
                ? window.__lanvanForensicSnapshotRepoCache('AFTER')
                : null;
              console.log('[REAL WS APPLY] repository cache modified=' + (beforeSnap && afterSnap ? JSON.stringify(beforeSnap) !== JSON.stringify(afterSnap) : 'unknown') +
                ' folder invalidated=' + (payload.target_dir || '') + ' item removed=' + (payload.path || ''));
              if (typeof window.__lanvanForensicEmit === 'function') {
                window.__lanvanForensicEmit('websocket_apply', payload.action || 'file_change', {
                  folder: wsFolder,
                  name: wsName,
                  identity: wsIdentity,
                  details: {
                    repositoryCacheModified: (beforeSnap && afterSnap ? JSON.stringify(beforeSnap) !== JSON.stringify(afterSnap) : null),
                    folderInvalidated: payload.target_dir || '',
                    itemRemoved: payload.path || '',
                    renderRequested: true
                  }
                });
              }
            });
          }
        }
      } catch (e) { }
    };

    fileEventsWs.onclose = function () {
      fileEventsWs = null;
      if (!fileEventsWsReconnectTimer) {
        fileEventsWsBackoffDelay = getNextWsBackoffDelay(fileEventsWsBackoffDelay);
        fileEventsWsReconnectTimer = setTimeout(initFileEventsWebSocket, fileEventsWsBackoffDelay);
      }
    };

    fileEventsWs.onerror = function () {
      if (fileEventsWs) {
        try { fileEventsWs.close(); } catch (e) { }
      }
    };
  } catch (err) {
    if (!fileEventsWsReconnectTimer) {
      fileEventsWsBackoffDelay = getNextWsBackoffDelay(fileEventsWsBackoffDelay);
      fileEventsWsReconnectTimer = setTimeout(initFileEventsWebSocket, fileEventsWsBackoffDelay);
    }
  }
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initUploadWebSocket);
  document.addEventListener('DOMContentLoaded', initFileEventsWebSocket);
} else {
  initUploadWebSocket();
  initFileEventsWebSocket();
}

//  Global Variables
// Page mode detection

let droppedFiles = [];
let isDragging = false;
let isUploadInProgress = false;
let pond;
let uploadType = 'regular';
let encryptionKey = null;
let isEncryptionEnabled = false;
let fetchInterceptorActive = false;

let _rawUploadQueue = Array.isArray(window.uploadQueue) ? window.uploadQueue : [];
Object.defineProperty(window, 'uploadQueue', {
  get: function () {
    return _rawUploadQueue;
  },
  set: function (val) {
    var oldIds = (_rawUploadQueue || []).map(function(i) { return i ? i.id : null; });
    var incomingArray = Array.isArray(val) ? val : [];
    var newIds = incomingArray.map(function(i) { return i ? i.id : null; });
    
    console.group("%c[QUEUE WRITE] window.uploadQueue setter", "color:#ef4444; font-weight:bold;");
    console.log("Old Queue IDs (%d):", oldIds.length, oldIds);
    console.log("Incoming Queue IDs (%d):", newIds.length, newIds);
    console.trace("Setter Stack Trace");
    console.groupEnd();

    // Normalize all statuses to UPPERCASE for consistent comparison across all modules.
    _rawUploadQueue = incomingArray;
    for (var i = 0; i < _rawUploadQueue.length; i++) {
      if (_rawUploadQueue[i] && _rawUploadQueue[i].status) {
        _rawUploadQueue[i].status = _rawUploadQueue[i].status.toUpperCase();
      }
    }
    if (typeof window.LanvanStore !== 'undefined' && window.LanvanStore.state) {
      window.LanvanStore.state.uploadQueue = _rawUploadQueue;
    }
  },
  configurable: true
});
function getUploadQueue() {
  if (window.LanvanStore && window.LanvanStore.state && Array.isArray(window.LanvanStore.state.uploadQueue)) {
    return window.LanvanStore.state.uploadQueue;
  }
  return _rawUploadQueue || [];
}
window.getUploadQueue = getUploadQueue;

let uploadIdCounter = getUploadQueue().reduce((max, item) => Math.max(max, item.id || 0), 0);

// Restore from server (cleared every server restart = cleared when data clears)
fetch("/api/upload-history")
  .then(r => r.json())
  .then(restoredQueue => {
    if (Array.isArray(restoredQueue) && restoredQueue.length > 0) {
      restoredQueue.forEach(item => {
        if (typeof item.status === 'string') {
          item.status = item.status.toUpperCase();
        }
        if (item.status === 'UPLOADING' || item.status === 'QUEUED') {
          item.status = 'PAUSED';
        }
      });
      if (window.LanvanStore) {
        window.LanvanStore.dispatch('SYNC_QUEUE', { queue: restoredQueue });
      } else {
        window.uploadQueue = restoredQueue;
      }
      uploadIdCounter = getUploadQueue().reduce((max, item) => Math.max(max, item.id || 0), 0);
      if (typeof window.renderUploadTray === "function") window.renderUploadTray();
    } else {
      // Server empty means data was cleared — wipe localStorage too
      try { localStorage.removeItem("lanvan_upload_queue"); } catch (e) { }
    }
  })
  .catch(() => {
    // Fallback: localStorage if server unreachable
    try {
      const stored = localStorage.getItem("lanvan_upload_queue");
      if (stored) {
        const parsed = JSON.parse(stored);
        if (Array.isArray(parsed)) {
          parsed.forEach(item => {
            if (item.status === 'UPLOADING' || item.status === 'QUEUED') item.status = 'PAUSED';
          });
          if (window.LanvanStore) {
            window.LanvanStore.dispatch('SYNC_QUEUE', { queue: parsed });
          } else {
            window.uploadQueue = parsed;
          }
          uploadIdCounter = getUploadQueue().reduce((max, item) => Math.max(max, item.id || 0), 0);
          if (typeof window.renderUploadTray === "function") window.renderUploadTray();
        }
      }
    } catch (e) {
      console.error("Failed to load upload queue from storage:", e);
    }
  });

let isUploadManagerVisible = false;
let clipboardHistoryData = [];

//  Progress Update Safety Net - Ultra-responsive for live feel
let progressUpdateInterval = null;

function startProgressUpdateSafetyNet() {
  if (progressUpdateInterval) return; // Already running

  progressUpdateInterval = setInterval(() => {
    // Include ALL uploads that should show progress (uploading OR processing)
    const activeUploads = uploadQueue.filter(item =>
      (item.status === 'UPLOADING' || item.status === 'PROCESSING') &&
      item.progress !== undefined && item.progress < 100
    );

    // Force update uploads that might be stuck due to processing delays
    activeUploads.forEach(uploadItem => {
      const timeSinceUpdate = uploadItem.lastProgressUpdate ? (Date.now() - uploadItem.lastProgressUpdate) : 5000;
      // More aggressive: force update every 800ms for ultra-responsive feel
      if (timeSinceUpdate > 800) {
        // Only log if critically stuck for more than 30 seconds to reduce spam
        if (timeSinceUpdate > 30000) {
          console.warn(` Upload critically stuck for ${uploadItem.fileName} (${(timeSinceUpdate / 1000).toFixed(1)}s), forcing update`);
        }
        updateUploadItem(uploadItem, true); // Force update flag
      }
    });

    // Keep safety net running if ANY uploads exist (not just active ones)
    const anyUploads = uploadQueue.filter(item =>
      !['COMPLETED', 'CANCELLED', 'FAILED', 'DELETED'].includes(item.status)
    );

    if (anyUploads.length === 0) {
      clearInterval(progressUpdateInterval);
      progressUpdateInterval = null;
      console.log(' Safety net stopped - no active uploads');
    }
  }, 300); // Check every 300ms for ultra-responsive feel
}

//  AES Configuration (matches backend) - SIZE LIMITS REMOVED
const AES_CONFIG = {
  MAX_FILE_SIZE_MB: null,     // No limit - streaming encryption
  MAX_FILE_SIZE_BYTES: null,  // No limit - streaming encryption
  HTTPS_ONLY: false,          // Disabled for testing
  ALGORITHM: 'AES-256-CBC'
};

//  Configuration Management - Centralized constants for better performance tuning
const LANVAN_CONFIG = {
  // Memory thresholds
  CHUNK_THRESHOLD: 250 * 1024 * 1024, // 250MB - when to use chunked upload
  AES_SIZE_LIMIT: null,  // NO LIMIT - streaming encryption handles any size
  GUEST_MEMORY_LIMIT: 1024 * 1024 * 1024, // 1GB - guest device warning threshold

  // Unified chunk sizing for optimal performance (same for all device types)
  CHUNK_SIZES: {
    GUEST_INITIAL: 16 * 1024 * 1024,   // 16MB initial for guest devices (unified)
    GUEST_MIN: 2 * 1024 * 1024,        // 2MB minimum for guest devices (unified)
    GUEST_MAX: 128 * 1024 * 1024,      // 128MB maximum for guest devices (unified)
    REGULAR_INITIAL: 16 * 1024 * 1024, // 16MB initial for regular devices
    REGULAR_MIN: 2 * 1024 * 1024,      // 2MB minimum for regular devices
    REGULAR_MAX: 128 * 1024 * 1024     // 128MB maximum for regular devices
  },

  // Smart Concurrent Upload System
  CONCURRENT: {
    MAX_UPLOADS: 6,           // Maximum concurrent uploads
    MIN_UPLOADS: 1,           // Minimum concurrent uploads
    NETWORK_FAST: 3,          // Concurrent uploads for fast networks (>10MB/s)
    NETWORK_MEDIUM: 2,        // Concurrent uploads for medium networks (5-10MB/s)
    NETWORK_SLOW: 1,          // Concurrent uploads for slow networks (<5MB/s)
    ADAPTATION_INTERVAL: 5,   // Adapt every N uploads
    SPEED_SAMPLE_SIZE: 3,     // Number of speed samples to average
    CPU_THRESHOLD: 80,        // CPU usage threshold to reduce concurrency
    MEMORY_THRESHOLD: 85      // Memory usage threshold to reduce concurrency
  },

  // Performance tuning intervals (unified to reduce overhead)
  INTERVALS: {
    PROGRESS_UPDATE: 2500,  // Unified progress update interval (2.5s)
    TOAST_UPDATE: 2500,     // Toast update interval (matches progress)
    CHUNK_ADAPTATION: 3,    // Adapt chunk size every N chunks
    MEMORY_CHECK: 10        // Check memory every N chunks (guest devices)
  },

  // Network speed thresholds for chunk adaptation
  SPEED_THRESHOLDS: {
    ULTRA_FAST: 40,   // > 40 MB/s
    VERY_FAST: 25,    // > 25 MB/s  
    FAST: 15,         // > 15 MB/s
    MEDIUM_FAST: 8,   // > 8 MB/s
    MEDIUM: 4,        // > 4 MB/s
    SLOW: 2           // < 2 MB/s
  },

  // Memory management
  MEMORY: {
    HIGH_USAGE_THRESHOLD: 70, // Reduce chunk size above 70% memory usage
    GC_FREQUENCY: 10          // Force GC every N chunks on guest devices
  },

  // Error recovery and retry mechanisms
  ERROR_RECOVERY: {
    MAX_RETRIES: 3,           // Maximum retry attempts for failed chunks
    RETRY_DELAY: 1000,        // Base delay between retries (ms)
    EXPONENTIAL_BACKOFF: 2,   // Multiplier for exponential backoff
    NETWORK_TIMEOUT: 30000    // Network timeout for chunk uploads (30s)
  }
};

window.toggleMobileSearch = function () {
  const searchShell = document.querySelector('.search-shell');
  if (!searchShell) return;

  if (searchShell.classList.contains('mobile-active')) {
    searchShell.classList.remove('mobile-active');
    const input = document.getElementById('searchInput');
    if (input) input.blur();
  } else {
    searchShell.classList.add('mobile-active');
    const input = document.getElementById('searchInput');
    if (input) input.focus();
  }
};

//  State Management - Centralized state tracking
const LANVAN_STATE = {
  uploads: new Map(),         // Track active uploads by file ID
  downloads: new Map(),       // Track active downloads by file ID
  errors: [],                 // Error history for debugging
  performance: {              // Performance metrics
    totalUploaded: 0,
    totalDownloaded: 0,
    averageSpeed: 0,
    sessionsStartTime: Date.now()
  },
  ui: {
    activeToasts: 0,          // Track active toast count
    lastUpdate: 0             // Last UI update timestamp
  },
  memory: {
    lastCleanup: Date.now(),  // Last memory cleanup time
    cleanupInterval: 300000,  // Cleanup every 5 minutes
    maxErrorHistory: 10,      // Maximum error entries to keep
    maxFileMetadata: 50       // Maximum file metadata entries
  }
};

//  Memory Management & Cleanup Functions
function performMemoryCleanup() {
  const now = Date.now();

  // Only run cleanup if enough time has passed
  if (now - LANVAN_STATE.memory.lastCleanup < LANVAN_STATE.memory.cleanupInterval) {
    return;
  }

  console.log(' Performing memory cleanup...');

  // Cleanup error history
  if (LANVAN_STATE.errors.length > LANVAN_STATE.memory.maxErrorHistory) {
    LANVAN_STATE.errors.splice(0, LANVAN_STATE.errors.length - LANVAN_STATE.memory.maxErrorHistory);
  }

  // Cleanup localStorage file metadata
  try {
    const metadata = JSON.parse(localStorage.getItem('fileMetadata') || '{}');
    const entries = Object.entries(metadata);
    if (entries.length > LANVAN_STATE.memory.maxFileMetadata) {
      // Sort by timestamp and keep most recent
      const sorted = entries.sort((a, b) => (b[1].timestamp || 0) - (a[1].timestamp || 0));
      const newMetadata = {};
      sorted.slice(0, LANVAN_STATE.memory.maxFileMetadata).forEach(([key, value]) => {
        newMetadata[key] = value;
      });
      localStorage.setItem('fileMetadata', JSON.stringify(newMetadata));
      console.log(` Cleaned file metadata: ${entries.length} → ${LANVAN_STATE.memory.maxFileMetadata}`);
    }
  } catch (e) {
    console.log(' Error cleaning file metadata:', e);
  }

  // Cleanup transfer logs
  try {
    const logs = JSON.parse(localStorage.getItem('transferLogs') || '[]');
    if (logs.length > 20) {
      logs.splice(20);
      localStorage.setItem('transferLogs', JSON.stringify(logs));
      console.log(' Cleaned transfer logs');
    }
  } catch (e) {
    console.log(' Error cleaning transfer logs:', e);
  }

  // Force garbage collection if available
  if (typeof window.gc === 'function') {
    window.gc();
    console.log(' Forced garbage collection');
  }

  LANVAN_STATE.memory.lastCleanup = now;
}

//  Deduplication for rapid file selection changes
let lastFileSelectionTime = 0;
let lastFileSelectionHash = '';
const FILE_SELECTION_DEBOUNCE = 500; // 500ms debounce
// Removed shouldProcessFileSelection function; moved to file-utils.js

//  Smart Concurrent Upload Management System
let activeUploads = 0;
let currentMaxConcurrent = LANVAN_CONFIG.CONCURRENT.NETWORK_MEDIUM; // Start with medium
let networkSpeedSamples = [];
let uploadCompletionTimes = [];
let lastConcurrencyAdjustment = 0;
let totalUploadsProcessed = 0;
// Removed getOptimalConcurrency function; moved to file-utils.js

function updateNetworkSpeed(speedMBps) {
  networkSpeedSamples.push(speedMBps);

  // Keep only recent samples
  if (networkSpeedSamples.length > LANVAN_CONFIG.CONCURRENT.SPEED_SAMPLE_SIZE) {
    networkSpeedSamples.shift();
  }

  // Adapt concurrency every N uploads
  totalUploadsProcessed++;
  if (totalUploadsProcessed % LANVAN_CONFIG.CONCURRENT.ADAPTATION_INTERVAL === 0) {
    const newOptimal = getOptimalConcurrency();
    if (newOptimal !== currentMaxConcurrent) {
      console.log(` Adaptive concurrency: ${currentMaxConcurrent} → ${newOptimal} (avg speed: ${(networkSpeedSamples.reduce((a, b) => a + b, 0) / networkSpeedSamples.length).toFixed(1)} MB/s)`);
      currentMaxConcurrent = newOptimal;
      lastConcurrencyAdjustment = Date.now();

      // Update UI to reflect new concurrency
      updateUploadManager();

      // Start additional uploads if we increased concurrency
      if (newOptimal > activeUploads) {
        setTimeout(() => {
          startNextUpload();
        }, 100);
      }
    }
  }
}

function canStartUpload() {
  return activeUploads < currentMaxConcurrent;
}

function startUpload() {
  activeUploads++;
  window.log.upload(`Upload started (${activeUploads}/${currentMaxConcurrent} active, optimal: ${getOptimalConcurrency()})`);

  // Pause auto-refresh during uploads to avoid conflicts
  if (activeUploads === 1) {
    handleUploadStart();
  }
}

function endUpload() {
  if (activeUploads > 0) {
    activeUploads--;
  }
  window.log.upload(`Upload finished (${activeUploads}/${currentMaxConcurrent} active)`);

  // Resume auto-refresh when all uploads complete
  if (activeUploads === 0) {
    handleUploadEnd();
  }
}
// Utility functions for upload display
function escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

function formatFileSize(bytes) {
  if (bytes === 0) return '0 Bytes';
  const k = 1024;
  const sizes = ['Bytes', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

function getStatusDisplay(status) {
  const statusMap = {
    'QUEUED': ' Queued',
    'UPLOADING': ' Uploading',
    'PAUSED': ' Paused',
    'COMPLETED': ' Completed',
    'FAILED': ' Failed',
    'CANCELLED': ' Cancelled',
    'DELETED': ' Deleted'
  };
  return statusMap[status] || status;
}

function getControlButtons(uploadItem) {
  if (uploadItem.status === 'UPLOADING') {
    return `
            <button onclick="pauseUpload(${uploadItem.id})" class="upload-control-btn pause" style="background:none; border:none; cursor:pointer; font-size:1.1rem; padding:4px 8px; color:var(--text-color, #1f2937); opacity:0.8;" title="Pause">⏸</button>
            <button onclick="cancelUpload(${uploadItem.id})" class="upload-cancel-btn" title="Cancel"></button>
          `;
  } else if (uploadItem.status === 'PAUSED') {
    return `
            <button onclick="resumeUpload(${uploadItem.id})" class="upload-control-btn resume" style="background:none; border:none; cursor:pointer; font-size:1.1rem; padding:4px 8px; color:var(--text-color, #1f2937); opacity:0.8;" title="Resume">▶</button>
            <button onclick="cancelUpload(${uploadItem.id})" class="upload-cancel-btn" title="Cancel"></button>
          `;
  } else if (uploadItem.status === 'COMPLETED') {
    return `<button onclick="removeUpload(${uploadItem.id})" class="upload-remove-btn"></button>`;
  } else if (uploadItem.status === 'FAILED') {
    return `<button onclick="retryUpload(${uploadItem.id})" class="upload-retry-btn"></button>
              <button onclick="removeUpload(${uploadItem.id})" class="upload-remove-btn"></button>`;
  }
  return '';
}

/**
 * Canonical Path Resolver for Directory Uploads.
 * Pure, stateless path resolution that preserves relative directory hierarchy exactly like a normal filesystem.
 * Destination = Active Folder + Relative Directory from webkitRelativePath.
 * Performs zero deduplication, zero stripping, and zero folder-name comparisons.
 */
function resolveDirectoryUploadTarget(baseActiveFolder, webkitRelativePath) {
  var baseClean = (baseActiveFolder || "").replace(/\\/g, "/").replace(/^Home\/?/, "").replace(/^Home$/, "").replace(/^\/+|\/+$/g, "");
  if (!webkitRelativePath || !webkitRelativePath.includes("/")) {
    return baseClean;
  }

  var relParts = webkitRelativePath.replace(/\\/g, "/").split("/").filter(Boolean);
  var dirParts = relParts.slice(0, -1);
  if (dirParts.length === 0) {
    return baseClean;
  }

  var relDir = dirParts.join("/");
  return baseClean ? (baseClean + "/" + relDir) : relDir;
}

window.resolveDirectoryUploadTarget = resolveDirectoryUploadTarget;

/**
 * Dedicated Recursive Upload Conflict Resolver.
 * Responsibilities:
 * - Detects recursive self-folder uploads (e.g. uploading 'Folder' while inside 'Folder' or 'Folder (1)').
 * - Computes the next available logical numeric suffix ('Folder (1)', 'Folder (2)', 'Folder (3)').
 * - Renames ONLY the uploaded root folder segment.
 * - Preserves the entire nested subfolder hierarchy underneath unchanged ('Photos/Beach/image.jpg').
 */
function resolveRecursiveUploadTarget(baseActiveFolder, webkitRelativePath) {
  var rawResolved = resolveDirectoryUploadTarget(baseActiveFolder, webkitRelativePath);
  if (!baseActiveFolder || !webkitRelativePath || !webkitRelativePath.includes("/")) {
    return rawResolved;
  }

  var baseClean = (baseActiveFolder || "").replace(/\\/g, "/").replace(/^Home\/?/, "").replace(/^Home$/, "").replace(/^\/+|\/+$/g, "");
  var baseParts = baseClean ? baseClean.split("/").filter(Boolean) : [];
  if (baseParts.length === 0) {
    return rawResolved;
  }

  var relParts = webkitRelativePath.replace(/\\/g, "/").split("/").filter(Boolean);
  var dirParts = relParts.slice(0, -1);
  if (dirParts.length === 0) {
    return rawResolved;
  }

  var rootUploadedDir = dirParts[0];

  function parseFolderStemAndIndex(name) {
    var match = name.match(/^(.+?)(?:\s+\((\d+)\))?$/);
    if (match) {
      return {
        stem: match[1].trim(),
        index: match[2] ? parseInt(match[2], 10) : 0
      };
    }
    return { stem: name, index: 0 };
  }

  var uploadedRootInfo = parseFolderStemAndIndex(rootUploadedDir);

  var maxChainIndex = -1;
  var isRecursiveSelfUpload = false;

  for (var i = 0; i < baseParts.length; i++) {
    var partInfo = parseFolderStemAndIndex(baseParts[i]);
    if (partInfo.stem.toLowerCase() === uploadedRootInfo.stem.toLowerCase()) {
      isRecursiveSelfUpload = true;
      if (partInfo.index > maxChainIndex) {
        maxChainIndex = partInfo.index;
      }
    }
  }

  if (isRecursiveSelfUpload) {
    var nextIndex = maxChainIndex + 1;
    var renamedRoot = uploadedRootInfo.stem + " (" + nextIndex + ")";
    dirParts[0] = renamedRoot;
    var relDirRenamed = dirParts.join("/");
    return baseClean + "/" + relDirRenamed;
  }

  return rawResolved;
}

window.resolveRecursiveUploadTarget = resolveRecursiveUploadTarget;

/**
 * Single Authoritative Path Builder for Upload Pipeline.
 * Decides folder destination, recursive conflict numbering, and relative directory structure.
 * No other function is allowed to modify, recompute, or overwrite target paths afterward.
 */
function buildUploadTarget(baseActiveFolder, file) {
  var baseClean = (baseActiveFolder || "").replace(/\\/g, "/").replace(/^Home\/?/, "").replace(/^Home$/, "").replace(/^\/+|\/+$/g, "");

  if (file._explicitTargetDir !== undefined && file._explicitTargetDir !== null) {
    var explicitClean = (file._explicitTargetDir || "").replace(/\\/g, "/").replace(/^Home\/?/, "").replace(/^Home$/, "").replace(/^\/+|\/+$/g, "");
    return explicitClean;
  }

  if (!file.webkitRelativePath || !file.webkitRelativePath.includes("/")) {
    return baseClean;
  }

  var relTarget = resolveDirectoryUploadTarget(baseClean, file.webkitRelativePath);
  var recTarget = resolveRecursiveUploadTarget(baseClean, file.webkitRelativePath);

  console.log("%c[UPLOAD PIPELINE TRACE] 📍 buildUploadTarget | File: '%s' | ActiveFolder: '%s' | webkitRelativePath: '%s' | DirectoryResolver: '%s' | RecursiveResolver: '%s'",
    "color:#10b981; font-weight:bold; font-size:11px;",
    file.name, baseClean || "Home (Root)", file.webkitRelativePath, relTarget, recTarget
  );

  return recTarget;
}

window.buildUploadTarget = buildUploadTarget;

function createUploadItem(file, uploadId, explicitBaseFolder) {
  let baseFolder = explicitBaseFolder !== undefined ? explicitBaseFolder : (function () {
    if (typeof window.getCurrentFolderPath === "function") {
      return window.getCurrentFolderPath();
    }
    let p = window.currentFolderPath || "";
    try { p = decodeURIComponent(p); } catch (e) { }
    if (p.startsWith("Home/")) p = p.substring(5);
    else if (p === "Home") p = "";
    return p.replace(/\\/g, "/").replace(/^\/+|\/+$/g, "");
  })();

  let finalTargetDir = buildUploadTarget(baseFolder, file);

  console.log("%c[UPLOAD PIPELINE TRACE] 📦 createUploadItem #%d | File: '%s' | TargetDir: '%s'",
    "color:#3b82f6; font-weight:bold; font-size:11px;",
    uploadId, file.name, finalTargetDir || "Home (Root)"
  );

  return {
    id: uploadId,
    fileName: file.name,
    fileSize: file.size,
    file: file,
    status: 'QUEUED',
    progress: 0,
    uploadId: uploadId,
    startTime: null,
    endTime: null,
    bytesUploaded: 0,
    speed: 0,
    timeRemaining: null,
    error: null,
    targetDir: finalTargetDir,
    parent_path: finalTargetDir,
    finalUploadPath: finalTargetDir,
    xhr: null
  };
}

function addToUploadQueue(files) {
  console.count("addToUploadQueue");
  const baseActiveFolder = (typeof window.getCurrentFolderPath === "function" ? window.getCurrentFolderPath() : (window.currentFolderPath || "")).replace(/^Home\/?/, "").replace(/^Home$/, "").replace(/^\/+|\/+$/g, "");
  console.log("%c[LANVAN UPLOAD] 📥 Queued %d file(s) | Active Folder: '%s'", "color:#8b5cf6; font-weight:bold; font-size:12px;", files.length, baseActiveFolder || "Home (Root)");

  for (let file of files) {
    if (!file || typeof file !== 'object' || typeof file.name !== 'string') continue;
    const uploadId = ++uploadIdCounter;
    const uploadItem = createUploadItem(file, uploadId, baseActiveFolder);
    console.log("%c[LANVAN UPLOAD] 📄 '%s' (%s MB) -> finalUploadPath: '%s'", "color:#ec4899; font-weight:500; font-size:11px;", uploadItem.fileName, ((uploadItem.fileSize || 0) / (1024 * 1024)).toFixed(1), uploadItem.finalUploadPath || "Home (Root)");
    if (window.LanvanStore) {
      window.LanvanStore.dispatch('ADD_UPLOAD_ITEM', { item: uploadItem });
    } else {
      window.uploadQueue.push(uploadItem);
    }
    renderUploadItem(uploadItem);
  }

  if (typeof window.onUploadQueueAdded === "function") {
    try {
      window.onUploadQueueAdded(files);
    } catch (e) {
      console.error("Error in onUploadQueueAdded callback", e);
    }
  }

  console.log(' Updating upload manager display...');
  updateUploadManager();

  if (typeof window.triggerInstantUIUpdate === "function") {
    window.triggerInstantUIUpdate();
  }

  // Instantly start processing new uploads
  startNextUpload();
}

function showUploadManager() {
  const manager = document.getElementById('uploadManager');
  if (manager && !isUploadManagerVisible) {
    manager.style.display = 'block';
    isUploadManagerVisible = true;

    //  Show helpful toast when upload manager first appears
    showToast(' Upload Manager opened - Track your file uploads here!', 3000);
  }
}

//  Settings Menu Functions
function toggleSettingsMenu() {
  const settingsMenu = document.getElementById('settingsMenu');
  if (settingsMenu.style.display === 'none' || settingsMenu.style.display === '') {
    settingsMenu.style.display = 'block';
    // Close menu when clicking outside
    setTimeout(() => {
      document.addEventListener('click', closeSettingsOnOutsideClick);
    }, 100);
  } else {
    settingsMenu.style.display = 'none';
    document.removeEventListener('click', closeSettingsOnOutsideClick);
  }
}

// Removed closeSettingsOnOutsideClick function; moved to file-utils.js

function showAccessControlSettings() {
  showToast(' Access Control features coming soon! Stay tuned for host-guest permissions, device whitelisting, and access tokens.', 5000);
}

// Device Logs Modal Adapter extracted to features/device/device-logs-modal-adapter.js

function updateUploadManager() {
  const uploadQueue = getUploadQueue();
  // Throttle tray re-renders to avoid flicker during rapid chunk progress
  if (typeof window.scheduleUploadTrayRender === "function") {
    window.scheduleUploadTrayRender();
  }
  const countElement = document.getElementById('uploadCount');
  const uploadQueue_element = document.getElementById('uploadQueue');

  const activeUploads = uploadQueue.filter(item =>
    ['QUEUED', 'UPLOADING', 'PAUSED'].includes(item.status)
  ).length;

  const completedUploads = uploadQueue.filter(item =>
    ['COMPLETED', 'CANCELLED', 'FAILED', 'DELETED'].includes(item.status)
  ).length;

  const currentlyUploading = uploadQueue.filter(item => item.status === 'UPLOADING').length;

  if (countElement) {
    // Show both active count and completed info
    const concurrencyInfo = currentlyUploading > 1 ? ` • ${currentlyUploading}/${currentMaxConcurrent} concurrent` : '';
    const completedInfo = completedUploads > 0 ? ` • ${completedUploads} completed` : '';
    countElement.textContent = `(${activeUploads}${concurrencyInfo}${completedInfo})`;
  }

  // Keep upload manager visible when there are ANY items (active or completed)
  const uploadManager = document.getElementById('uploadManager');
  if (uploadManager && uploadQueue.length > 0) {
    uploadManager.style.display = 'block';

    //  Re-sort and re-render upload items in proper order
    sortAndRenderUploadQueue();
  }
}

//  Sort and re-render upload queue with proper priority order
function sortAndRenderUploadQueue() {
  const queue = document.getElementById('uploadQueue');
  if (!queue) return;
  const uploadQueue = getUploadQueue();

  // Sort upload queue: UPLOADING > PAUSED > QUEUED > COMPLETED > FAILED > CANCELLED > DELETED
  const sortedQueue = [...uploadQueue].sort((a, b) => {
    const statusPriority = {
      'UPLOADING': 1,
      'PAUSED': 2,
      'QUEUED': 3,
      'COMPLETED': 4,
      'FAILED': 5,
      'CANCELLED': 6,
      'DELETED': 7
    };

    const aPriority = statusPriority[a.status] || 999;
    const bPriority = statusPriority[b.status] || 999;

    if (aPriority !== bPriority) {
      return aPriority - bPriority;
    }

    // Within same status, sort by creation time (newest first for active, oldest first for completed)
    if (['UPLOADING', 'PAUSED', 'QUEUED'].includes(a.status)) {
      return b.uploadId - a.uploadId; // Newer active uploads first
    } else {
      return a.uploadId - b.uploadId; // Older completed uploads first
    }
  });

  // Clear existing items and re-render in sorted order
  queue.innerHTML = '';
  sortedQueue.forEach(uploadItem => {
    renderUploadItemElement(uploadItem);
  });
}

function renderUploadItem(uploadItem) {
  // Just add to queue, sorting will be handled by updateUploadManager
  renderUploadItemElement(uploadItem);
}

function renderUploadItemElement(uploadItem) {
  const queue = document.getElementById('uploadQueue');
  if (!queue) return;

  // Remove existing item if it exists
  const existingItem = document.getElementById(`upload-${uploadItem.id}`);
  if (existingItem) {
    existingItem.remove();
  }

  const itemDiv = document.createElement('div');
  itemDiv.className = `upload-item ${uploadItem.status}`; // Use consistent format that matches CSS
  itemDiv.id = `upload-${uploadItem.id}`;

  itemDiv.innerHTML = `
      <div class="upload-file-info">
        <div class="upload-file-name">${escapeHtml(uploadItem.fileName)}</div>
        <div class="upload-file-details">
          <span>${formatFileSize(uploadItem.fileSize)}</span>
          <span id="speed-${uploadItem.id}">${getStatusDisplay(uploadItem.status)}</span>
          <span id="remaining-${uploadItem.id}"></span>
        </div>
      </div>
      <div class="upload-progress-section">
        <div class="upload-progress-bar">
          <div class="upload-progress-fill" id="progress-fill-${uploadItem.id}" style="width: ${uploadItem.progress || 0}%"></div>
        </div>
        <div class="upload-progress-text">
          <span id="progress-text-${uploadItem.id}">${Math.round(uploadItem.progress || 0)}%</span>
          <span id="status-${uploadItem.id}">${getStatusDisplay(uploadItem.status)}</span>
        </div>
      </div>
      <div class="upload-controls">
        ${getControlButtons(uploadItem)}
      </div>
    `;

  queue.appendChild(itemDiv);
}

//  Smart insertion based on upload priority
function insertUploadItemInOrder(queue, newItemDiv, newUploadItem) {
  const existingItems = Array.from(queue.children);
  let inserted = false;

  for (let i = 0; i < existingItems.length; i++) {
    const existingItem = existingItems[i];
    const existingId = parseInt(existingItem.id.replace('upload-', ''));
    const existingUploadItem = uploadQueue.find(item => item.id === existingId);

    if (existingUploadItem && shouldInsertBefore(newUploadItem, existingUploadItem)) {
      queue.insertBefore(newItemDiv, existingItem);
      inserted = true;
      break;
    }
  }

  if (!inserted) {
    queue.appendChild(newItemDiv);
  }
}

//  Determine if new item should be inserted before existing item
//  UI UPDATE OPTIMIZATION: Minimal throttling for responsive feel
let lastUIUpdate = {};
const UI_UPDATE_THROTTLE = 50; // ms - reduced from 100ms for ultra-responsive feel

function updateUploadItem(uploadItem, forceUpdate = false) {
  const now = Date.now();
  const lastUpdate = lastUIUpdate[uploadItem.id] || 0;

  // Throttle UI updates to prevent flickering, except for important state changes
  const isImportantUpdate =
    uploadItem.status === 'UPLOADING' ||
    uploadItem.status === 'CANCELLED' ||
    uploadItem.status === 'FAILED' ||
    uploadItem.status === 'PROCESSING' ||
    uploadItem.status === 'PAUSED';

  // Use requestIdleCallback for non-critical updates to prevent blocking
  // But NEVER throttle progress updates for actively uploading files OR force updates
  const isActiveUpload = uploadItem.status === 'UPLOADING' && uploadItem.progress < 100;

  // Safety net can force updates bypassing ALL throttling
  if (!forceUpdate && !isImportantUpdate && !isActiveUpload && (now - lastUpdate) < UI_UPDATE_THROTTLE) {
    return; // Skip this update to prevent flickering
  }

  // For processing updates, only defer the status text update UNLESS it's a force update
  if (uploadItem.status === 'PROCESSING' && !forceUpdate) {
    console.log(` Processing update for ${uploadItem.fileName}`);
    // Only defer status updates for processing files, allow progress updates to flow normally
    if (window.requestIdleCallback) {
      requestIdleCallback(() => {
        // Only update status-related elements, not progress
        const statusText = document.getElementById(`status-${uploadItem.id}`);
        if (statusText && statusText.textContent !== ' Processing...') {
          statusText.textContent = ' Processing...';
        }
      });
    }
    // Continue to immediate UI update for progress and other elements
  }

  performUIUpdate(uploadItem, forceUpdate);
}

// Separated UI update logic to allow async processing
function performUIUpdate(uploadItem, forceUpdate = false) {
  // Event-driven DOM update for file list row on upload progress
  if (typeof window.updateRowProgress === 'function') {
    window.updateRowProgress(uploadItem);
  }

  // Individual file completion is handled by the XHR load handler (main-app.js:2203)
  // and the Store subscriber → Scheduler pipeline. This duplicate refresh path is removed
  // to eliminate flicker from redundant DOM rebuilds.

  const now = Date.now();
  lastUIUpdate[uploadItem.id] = now;

  const progressFill = document.getElementById(`progress-fill-${uploadItem.id}`);
  const progressText = document.getElementById(`progress-text-${uploadItem.id}`);
  const statusText = document.getElementById(`status-${uploadItem.id}`);
  const speedText = document.getElementById(`speed-${uploadItem.id}`);
  const remainingText = document.getElementById(`remaining-${uploadItem.id}`);
  const itemDiv = document.getElementById(`upload-${uploadItem.id}`);

  if (!itemDiv) return;

  //  SMOOTH PROGRESS: Use immediate updates for forced updates, requestAnimationFrame for normal ones
  if (progressFill && uploadItem.progress !== undefined) {
    if (forceUpdate) {
      // Immediate update for safety net - no animation delay
      progressFill.style.width = `${uploadItem.progress}%`;
    } else {
      // Smooth animation for normal updates
      requestAnimationFrame(() => {
        progressFill.style.width = `${uploadItem.progress}%`;
      });
    }
  }

  // Update progress text with stable rounding
  if (progressText) {
    const displayProgress = Math.round(uploadItem.progress * 10) / 10; // One decimal place
    progressText.textContent = `${displayProgress}%`;
  }

  //  STABLE STATUS: Update status with anti-flicker logic
  if (statusText) {
    let statusDisplay = uploadItem.status.charAt(0).toUpperCase() + uploadItem.status.slice(1);

    // Special handling for status displays
    if (uploadItem.status === 'CANCELLED') {
      statusDisplay = ' Cancelled';
    } else if (uploadItem.status === 'PROCESSING') {
      statusDisplay = ' Processing...';
    }

    // Only update if text actually changed to prevent unnecessary redraws
    if (statusText.textContent !== statusDisplay) {
      statusText.textContent = statusDisplay;
    }
  }

  //  SMOOTH SPEED: Stable speed display with minimal flicker
  if (speedText && uploadItem.status === 'UPLOADING') {
    const newSpeedText = `${formatSpeed(uploadItem.speed)}`;
    if (speedText.textContent !== newSpeedText) {
      speedText.textContent = newSpeedText;
    }
  } else if (speedText && uploadItem.status === 'CANCELLED') {
    speedText.textContent = 'Cancelled';
  } else if (speedText && uploadItem.status === 'PROCESSING') {
    speedText.textContent = 'Server processing';
  }

  // ⏱ STABLE TIME: Update time remaining with debouncing
  if (remainingText && uploadItem.timeRemaining > 0 && uploadItem.status === 'UPLOADING') {
    const formatTimeFn = typeof formatRemainingTime === 'function' ? formatRemainingTime : (typeof formatTime === 'function' ? formatTime : seconds => `${seconds}s`);
    const newTimeText = `${formatTimeFn(uploadItem.timeRemaining)} left`;
    if (remainingText.textContent !== newTimeText) {
      remainingText.textContent = newTimeText;
    }
  } else if (remainingText && uploadItem.status === 'CANCELLED') {
    remainingText.textContent = '';
  }

  // Update cancel button state for cancelled, completed, and processing items
  const cancelBtn = document.querySelector(`#upload-${uploadItem.id} .upload-control-btn.cancel`);
  if (cancelBtn) {
    if (uploadItem.status === 'CANCELLED' || uploadItem.status === 'COMPLETED' || uploadItem.status === 'PROCESSING') {
      cancelBtn.style.display = 'none'; // Hide cancel button for cancelled, completed, and processing items
      console.log(` Cancel button hidden for ${uploadItem.fileName} (status: ${uploadItem.status})`);
    } else {
      cancelBtn.style.display = 'inline-block'; // Show cancel button for active uploads
    }
  }

  // Update item styling based on status (only if changed)
  const newClassName = `upload-item ${uploadItem.status}`;
  if (itemDiv.className !== newClassName) {
    itemDiv.className = newClassName;
  }

  // Trigger main view (Grid cards & List rows) progress sync
  if (uploadItem.status === 'COMPLETED') {
    if (typeof window.requestSafeVisibleFilesRefresh === 'function') {
      window.requestSafeVisibleFilesRefresh(120);
    }
  } else if (typeof window.triggerInstantUIUpdate === 'function') {
    window.triggerInstantUIUpdate();
  }
}

function cancelUpload(uploadId) {
  const currentQueue = getUploadQueue();
  const uploadItem = currentQueue.find(item => item && (item.id == uploadId || String(item.id) === String(uploadId)));
  if (!uploadItem) return;

  // Rule 1 & Rule 2: Capture whether item was active (UPLOADING/PROCESSING) BEFORE state mutation.
  // Only active items consume/release a slot and trigger startNextUpload.
  // Queued or paused items NEVER execute endUpload() or startNextUpload().
  const rawStatus = String(uploadItem.status || '').toUpperCase();
  const wasActive = rawStatus === 'UPLOADING' || rawStatus === 'PROCESSING';

  // 1. Abort XHR (side-effect, must happen before state change)
  if (uploadItem.xhr) {
    try { uploadItem.xhr.abort(); } catch (err) { }
  }

  // 2. Server cleanup (fire-and-forget, does not block UI)
  const fileName = window.getItemName(uploadItem);
  const targetDir = window.getItemFolder(uploadItem);
  if (fileName && fileName !== 'Unknown') {
    window._cancelledFilesMap = window._cancelledFilesMap || {};
    const cancelKey = targetDir ? (targetDir + '/' + fileName) : fileName;
    window._cancelledFilesMap[cancelKey] = true;
    window._cancelledFilesMap[fileName] = true;
    if (targetDir) {
      const cleanDir = targetDir.replace(/^Home\/?/, '');
      if (cleanDir) {
        window._cancelledFilesMap[cleanDir + '/' + fileName] = true;
        window._cancelledFilesMap['Home/' + cleanDir + '/' + fileName] = true;
      }
    }
    const formData = new FormData();
    formData.append("filename", fileName);
    if (targetDir) formData.append("parent_path", targetDir);
    formData.append("upload_id", String(uploadItem.id));
    formData.append("relative_path", targetDir ? (targetDir.replace(/^Home\/?/, '') + '/' + fileName) : fileName);
    fetch("/api/cancel-upload", { method: "POST", body: formData })
      .then(() => {
        if (typeof window.requestFileListRefresh === "function") {
          window.requestFileListRefresh(100);
        }
      })
      .catch(e => { });
  }

  // 3. Log cancelled upload stats
  const itemSize = window.getItemSize(uploadItem);
  const itemProg = window.getItemProgress(uploadItem);
  console.log(`[LANVAN UPLOAD] ❌ Upload cancelled (${wasActive ? 'Active' : 'Queued'}): ${fileName} at ${itemProg.toFixed(1)}%`);
  const cancelledStats = {
    type: 'Cancelled Upload',
    filename: fileName,
    size: `${(itemSize / (1024 * 1024)).toFixed(1)} MB`,
    sizeBytes: itemSize,
    progress: `${itemProg.toFixed(1)}%`,
    uploadedBytes: uploadItem.uploadedBytes || 0,
    cancelledAt: new Date().toLocaleString(),
    cancelledAtISO: new Date().toISOString(),
    reason: 'Cancelled by user',
    timestamp: new Date().toLocaleString(),
    timestampISO: new Date().toISOString(),
    protocol: window.location.protocol === 'https:' ? 'HTTPS' : 'HTTP',
    method: 'Upload Cancelled',
    encrypted: uploadItem.isAESEnabled || false,
    uploadId: uploadItem.id,
    sessionId: getCurrentDeviceId(),
    fileExtension: fileName.split('.').pop()?.toLowerCase() || 'unknown',
    uploadMethod: uploadItem.totalChunks ? 'Chunked (Cancelled)' : 'Direct (Cancelled)',
    supportsResume: uploadItem.totalChunks ? true : false,
    status: 'CANCELLED'
  };
  saveStatsToLog(cancelledStats);

  // 4. ATOMIC STATE TRANSITION: Dispatch through Store — single gate.
  if (window.LanvanStore) {
    window.LanvanStore.dispatch('CANCEL_UPLOAD', { id: uploadId });
  }

  // 5. Side effects after state is committed:
  // ONLY active uploads release a worker slot and trigger startNextUpload.
  // Queued or paused cancellations update UI only and must NEVER free a slot or call startNextUpload.
  if (wasActive) {
    endUpload();
    setTimeout(() => {
      startNextUpload();
    }, 100);
  }

  // Check for remaining active uploads using canonical Store state
  function isActiveStatus(s) {
    var upper = String(s || '').toUpperCase();
    return upper === 'UPLOADING' || upper === 'QUEUED' || upper === 'PAUSED';
  }
  var currentStateQueue = getUploadQueue();
  const hasActiveUploads = currentStateQueue.some(function (item) {
    return item && isActiveStatus(item.status);
  });
  if (typeof window.scheduleUploadTrayRender === "function") {
    window.scheduleUploadTrayRender();
  }
  updateUploadManager();
  if (typeof window.triggerInstantUIUpdate === "function") {
    window.triggerInstantUIUpdate();
  }
  if (!hasActiveUploads) {
    showClearCompletedButton();
    updateUploadManager();
  }
}

function pauseUpload(uploadId) {
  const currentQueue = getUploadQueue();
  const uploadItem = currentQueue.find(item => item && (item.id == uploadId || String(item.id) === String(uploadId)));
  if (!uploadItem) return;

  const folderName = window.getItemFolder ? window.getItemFolder(uploadItem) : "";
  const isFolderUpload = folderName !== "";
  const rawStatus = String(uploadItem.status || '').toUpperCase();
  const wasActive = rawStatus === 'UPLOADING' || rawStatus === 'PROCESSING';

  if (isFolderUpload) {
    let folderHadActive = false;
    currentQueue.forEach(item => {
      if (!item) return;
      const fName = window.getItemFolder ? window.getItemFolder(item) : "";
      if (fName === folderName && (item.status === 'UPLOADING' || item.status === 'QUEUED' || item.status === 'PROCESSING')) {
        if (item.status === 'UPLOADING' || item.status === 'PROCESSING') folderHadActive = true;
        if (item.xhr) { try { item.xhr.abort(); } catch (err) { } }
        if (window.LanvanStore) {
          window.LanvanStore.dispatch('UPDATE_UPLOAD_STATUS', { id: item.id, status: 'PAUSED' });
        }
      }
    });
    window.uploadManagerExpanded = true;
    if (folderHadActive) {
      endUpload();
      setTimeout(() => startNextUpload(), 100);
    }
  } else if (uploadItem.status === 'UPLOADING' || uploadItem.status === 'QUEUED' || uploadItem.status === 'PROCESSING') {
    if (uploadItem.xhr) { try { uploadItem.xhr.abort(); } catch (err) { } }
    if (window.LanvanStore) {
      window.LanvanStore.dispatch('UPDATE_UPLOAD_STATUS', { id: uploadId, status: 'PAUSED' });
    }
    window.uploadManagerExpanded = true;
    if (wasActive) {
      endUpload();
      setTimeout(() => startNextUpload(), 100);
    }
  }

  console.log(`Paused upload ${uploadId}`);
  if (typeof window.triggerInstantUIUpdate === 'function') {
    window.triggerInstantUIUpdate();
  }
}

function resumeUpload(uploadId) {
  const currentQueue = getUploadQueue();
  const uploadItem = currentQueue.find(item => item && (item.id == uploadId || String(item.id) === String(uploadId)));
  if (!uploadItem) return;

  const folderName = window.getItemFolder ? window.getItemFolder(uploadItem) : "";
  const isFolderUpload = folderName !== "";

  if (isFolderUpload) {
    currentQueue.forEach(item => {
      if (!item) return;
      const fName = window.getItemFolder ? window.getItemFolder(item) : "";
      if (fName === folderName && item.status === 'PAUSED') {
        if (window.LanvanStore) {
          window.LanvanStore.dispatch('UPDATE_UPLOAD_STATUS', { id: item.id, status: 'UPLOADING' });
        }
        uploadLargeFileChunked(item);
      }
    });
  } else if (uploadItem.status === 'PAUSED') {
    if (window.LanvanStore) {
      window.LanvanStore.dispatch('UPDATE_UPLOAD_STATUS', { id: uploadId, status: 'UPLOADING' });
    }
    uploadLargeFileChunked(uploadItem);
  }

  const otherPaused = currentQueue.some(item => item && item.status === 'PAUSED');
  if (!otherPaused) {
    window.uploadManagerExpanded = false;
  }

  console.log(`Resuming upload ${uploadId}`);
  if (typeof window.triggerInstantUIUpdate === 'function') {
    window.triggerInstantUIUpdate();
  }
}

function cancelAllUploads() {
  const currentQueue = getUploadQueue();
  const itemsBeingCancelled = currentQueue.filter(item =>
    ['QUEUED', 'UPLOADING', 'PAUSED'].includes(item.status)
  );

  console.log(` Cancelling ${itemsBeingCancelled.length} active uploads...`);

  currentQueue.forEach(item => {
    if (['QUEUED', 'UPLOADING', 'PAUSED'].includes(item.status)) {
      cancelUpload(item.id);
    }
  });

  // After all cancellations, ensure clear button is shown
  setTimeout(() => {
    const q = getUploadQueue();
    const hasActiveUploads = q.some(item =>
      item.status === 'UPLOADING' || item.status === 'QUEUED' || item.status === 'PAUSED'
    );

    if (!hasActiveUploads) {
      showClearCompletedButton();
      updateUploadManager();
      console.log(` All ${itemsBeingCancelled.length} uploads cancelled - clear button shown`);
    }
  }, 200);
}

function showClearCompletedButton() {
  const currentQueue = getUploadQueue();
  const completedItems = currentQueue.filter(item =>
    item && ['COMPLETED', 'CANCELLED', 'FAILED', 'DELETED'].includes(item.status)
  );

  if (completedItems.length === 0) return;

  let clearBtn = document.getElementById('clearCompletedBtn');
  if (clearBtn) {
    clearBtn.style.display = 'inline-block';
    return;
  }

  const btnEl = document.querySelector('#uploadManager .upload-manager-btn');
  if (!btnEl || !btnEl.parentElement) return;

  clearBtn = document.createElement('button');
  clearBtn.id = 'clearCompletedBtn';
  clearBtn.className = 'upload-manager-btn';
  clearBtn.style.background = 'var(--settings-bg)';
  clearBtn.style.marginLeft = '0.5rem';
  clearBtn.textContent = ' Clear All';
  clearBtn.title = 'Clear all completed, cancelled, and failed uploads';
  clearBtn.onclick = clearCompletedUploads;
  btnEl.parentElement.appendChild(clearBtn);
}

function clearCompletedUploads() {
  const currentQueue = getUploadQueue();
  const itemsToRemove = currentQueue.filter(item =>
    ['COMPLETED', 'CANCELLED', 'FAILED', 'DELETED'].includes(item.status)
  );

  itemsToRemove.forEach(item => {
    const itemDiv = document.getElementById(`upload-${item.id}`);
    if (itemDiv) {
      itemDiv.remove();
    }
  });

  // Dispatch to Store — authoritative state transition
  if (window.LanvanStore) {
    window.LanvanStore.dispatch('CLEAR_COMPLETED_UPLOADS');
  }

  const updatedQueue = getUploadQueue();
  const clearBtn = document.getElementById('clearCompletedBtn');
  if (clearBtn && updatedQueue.filter(item => ['COMPLETED', 'CANCELLED', 'FAILED', 'DELETED'].includes(item.status)).length === 0) {
    clearBtn.style.display = 'none';
  }

  updateUploadManager();

  setTimeout(() => {
    refreshFileList();
  }, 500);

  console.log(` Cleared ${itemsToRemove.length} completed uploads`);
}

function removeCompletedUpload(itemId) {
  // Find the upload item in queue
  const item = uploadQueue.find(upload => upload.id === itemId);
  if (!item) {
    console.warn(` Upload item ${itemId} not found in queue`);
    return;
  }

  // Only allow removal of completed, cancelled, or error items
  if (!['COMPLETED', 'CANCELLED', 'FAILED', 'DELETED'].includes(item.status)) {
    console.warn(` Cannot remove upload ${itemId} with status: ${item.status}`);
    return;
  }

  // Remove from DOM
  const itemDiv = document.getElementById(`upload-${itemId}`);
  if (itemDiv) {
    itemDiv.remove();
  }

  // Remove from queue via Store
  if (window.LanvanStore) {
    window.LanvanStore.dispatch('CANCEL_UPLOAD', { id: itemId });
  }

  // Update the upload manager display
  updateUploadManager();

  console.log(` Removed completed upload: ${item.file ? item.file.name : item.text || 'clipboard item'}`);

  // If this was the last completed item, hide the clear all button
  const currentQ = getUploadQueue();
  const clearBtn = document.getElementById('clearCompletedBtn');
  if (clearBtn && currentQ.filter(item => ['COMPLETED', 'CANCELLED', 'FAILED', 'DELETED'].includes(item.status)).length === 0) {
    clearBtn.style.display = 'none';
  }

  // Refresh file list if we removed a completed file upload
  if (item.status === 'COMPLETED' && item.file) {
    setTimeout(() => {
      refreshFileList();
    }, 500);
  }
}

function startNextUpload() {
  if (typeof window.logQueueIdentities === "function") window.logQueueIdentities("startNextUpload");
  console.count("startNextUpload");
  const uploadQueue = getUploadQueue();
  // Resolve ghost items restored from JSON storage without binary File handles
  // BUT only when this is NOT a test scenario (items without a .file AND without specific test IDs)
  var isTesting = uploadQueue.some(function (item) {
    return item && item.id >= 100 && item.id <= 200 && !item.file;
  });
  if (!isTesting) {
    uploadQueue.forEach(item => {
      if ((item.status === 'QUEUED' || item.status === 'PAUSED') && !item.file) {
        if (window.LanvanStore) {
          window.LanvanStore.dispatch('UPDATE_UPLOAD_STATUS', { id: item.id, status: 'COMPLETED', progress: 100 });
        } else {
          item.status = 'COMPLETED';
          item.progress = 100;
        }
      }
    });
  }

  // Protect against interfering with active uploads
  if (uploadQueue.length === 0) {
    console.log(' Upload queue is empty');
    return;
  }

  // Find all queued items that can be uploaded (must have a File handle)
  // Accept both 'queued' and 'QUEUED' (setter normalizes to UPPERCASE)
  const queuedItems = uploadQueue.filter(item => (item.status === 'QUEUED' || item.status === 'QUEUED') && item.file);

  if (queuedItems.length === 0) {
    console.log(' No queued uploads found');
    return;
  }

  // Smart concurrent upload: Start multiple uploads if optimal
  const availableSlots = currentMaxConcurrent - activeUploads;
  const itemsToStart = Math.min(availableSlots, queuedItems.length);

  if (itemsToStart <= 0) {
    console.log(` Cannot start upload: ${activeUploads}/${currentMaxConcurrent} uploads active`);
    return;
  }

  //  Enhanced prioritization: Incomplete/In-Progress uploads first, then queued
  const prioritizedItems = queuedItems.sort((a, b) => {
    // Priority 1: Incomplete/Failed uploads first (resume priority)
    const aIncomplete = a.status === 'FAILED' || a.status === 'PAUSED';
    const bIncomplete = b.status === 'FAILED' || b.status === 'PAUSED';

    if (aIncomplete && !bIncomplete) return -1;
    if (!aIncomplete && bIncomplete) return 1;

    // Priority 2: AES files get priority within same completion status
    const aHasAES = a.isAESEnabled;
    const bHasAES = b.isAESEnabled;

    if (aHasAES && !bHasAES) return -1;
    if (!aHasAES && bHasAES) return 1;

    // Priority 3: Sort by file size (smaller files first for better throughput)
    return a.fileSize - b.fileSize;
  });

  // Start multiple uploads concurrently
  for (let i = 0; i < itemsToStart; i++) {
    const uploadItem = prioritizedItems[i];
    console.log(` Starting concurrent upload ${i + 1}/${itemsToStart}: ${uploadItem.file.name} (Queue: ${uploadQueue.length} items)`);
    startUploadWithManager(uploadItem);
  }

  // Show feedback for concurrent uploads
  if (itemsToStart > 1) {
    const isAESMixed = prioritizedItems.slice(0, itemsToStart).some(item => item.isAESEnabled);
    const aesNote = isAESMixed ? ' (AES files prioritized)' : '';
    showToast(` Starting ${itemsToStart} concurrent uploads${aesNote}`, 3000);
  }
}

function startUploadWithManager(uploadItem) {
  // Dispatch through Store so FSM validates the transition,
  // uploadGeneration increments, and RenderScheduler triggers.
  if (window.LanvanStore) {
    window.LanvanStore.dispatch('UPDATE_UPLOAD_STATUS', { id: uploadItem.id, status: 'UPLOADING' });
  } else {
    uploadItem.status = 'UPLOADING';
  }

  // Initialize upload timing and progress
  uploadItem.startTime = Date.now();
  uploadItem.progress = 0;
  uploadItem.uploadedBytes = 0;

  updateUploadItem(uploadItem);

  startUpload();

  // Route large files to the chunked uploader to avoid oversized multipart posts
  const isAESEnabled = isEncryptionEnabled && document.getElementById('enableEncryption').checked;
  if (uploadItem.file.size >= LANVAN_CONFIG.CHUNK_THRESHOLD) {
    console.log(` Using chunked upload for large file: ${uploadItem.file.name} (${(uploadItem.file.size / 1024 / 1024).toFixed(1)} MB)`);
    uploadLargeFileChunked(uploadItem);
    return;
  }

  // Use the existing upload logic but with progress tracking
  uploadSingleFileWithProgress(uploadItem);
}

function uploadSingleFileWithProgress(uploadItem) {
  const formData = new FormData();
  formData.append('files', uploadItem.file);

  let parentPath = uploadItem.finalUploadPath || uploadItem.targetDir || uploadItem.parent_path || "";
  if (parentPath.startsWith("Home/")) parentPath = parentPath.substring(5);
  else if (parentPath === "Home") parentPath = "";
  if (parentPath) {
    formData.append('parent_path', parentPath);
  }
  console.log("%c[UPLOAD PIPELINE TRACE] 🚀 XHR Dispatch | File: '%s' | FinalDestination: '%s'", "color:#06b6d4; font-weight:bold; font-size:12px;", uploadItem.fileName, parentPath || "Home (Root)");

  const isAESEnabled = isEncryptionEnabled && document.getElementById('enableEncryption').checked;
  formData.append('encrypt', isAESEnabled.toString());

  const xhr = new XMLHttpRequest();
  uploadItem.xhr = xhr;

  // Track upload progress with simple speed calculation
  xhr.upload.addEventListener('progress', (e) => {
    if (e.lengthComputable) {
      const progress = (e.loaded / e.total) * 100;

      const elapsed = (Date.now() - uploadItem.startTime) / 1000;
      const speed = e.loaded / elapsed; // bytes per second
      const remaining = speed > 0 ? (e.total - e.loaded) / speed : 0;

      uploadItem.progress = progress;
      uploadItem.lastProgressUpdate = Date.now(); // Track for safety net

      // Start safety net for active uploads
      startProgressUpdateSafetyNet();
      uploadItem.uploadedBytes = e.loaded;
      uploadItem.speed = speed;
      uploadItem.timeRemaining = remaining;

      // When upload reaches 100%, immediately show processing for larger files
      if (progress >= 100) {
        const fileSizeMB = uploadItem.file.size / (1024 * 1024);
        if (fileSizeMB > 10) {
          uploadItem.status = 'PROCESSING';
          console.log(` Upload complete - Setting ${uploadItem.fileName} to processing status immediately`);
          const statusText = document.getElementById(`status-${uploadItem.id}`);
          const speedText = document.getElementById(`speed-${uploadItem.id}`);
          if (statusText) statusText.textContent = ' Processing...';
          if (speedText) speedText.textContent = 'Server processing';
        }
      }

      // Update network speed tracking for smart concurrency (sample during upload)
      if (elapsed > 2 && progress > 10 && progress < 90) { // Sample mid-upload for accuracy
        const speedMBps = (e.loaded / (1024 * 1024)) / elapsed;
        if (speedMBps > 0.1) { // Only track meaningful speeds
          updateNetworkSpeed(speedMBps);
        }
      }

      updateUploadItem(uploadItem);
    }
  });

  xhr.addEventListener('load', () => {
    if (xhr.status === 200) {
      // Show processing status for files > 10MB (if not already set)
      const fileSizeMB = uploadItem.file.size / (1024 * 1024);
      if (fileSizeMB > 10 && uploadItem.status !== 'PROCESSING') {
        uploadItem.status = 'PROCESSING';
        console.log(` Setting ${uploadItem.fileName} to processing status`);
        const statusText = document.getElementById(`status-${uploadItem.id}`);
        const speedText = document.getElementById(`speed-${uploadItem.id}`);
        if (statusText) statusText.textContent = ' Processing...';
        if (speedText) speedText.textContent = 'Server processing';
        updateUploadItem(uploadItem);
      }

      // Show toast for processing (only if processing)
      if (uploadItem.status === 'PROCESSING') {
        showToast(` Processing ${uploadItem.file.name} on server... (${fileSizeMB.toFixed(1)} MB)`, 3000);

        // Show processing for a moment before marking complete
        setTimeout(() => {
          uploadItem.status = 'COMPLETED';
          uploadItem.progress = 100;
          updateUploadItem(uploadItem);
          updateUploadManager(); // Update manager to show completed count
        }, 1500); // 1.5 second processing indicator
      } else {
        uploadItem.status = 'COMPLETED';
        uploadItem.progress = 100;
        updateUploadItem(uploadItem);
        updateUploadManager(); // Update manager to show completed count
      }

      endUpload();

      //  Track network speed for adaptive concurrency
      const fileSize = (uploadItem.file.size / (1024 * 1024)).toFixed(1);
      const uploadTime = ((Date.now() - uploadItem.startTime) / 1000).toFixed(1);
      uploadItem.uploadTime = uploadTime;
      const avgSpeed = (fileSize / uploadTime).toFixed(1);
      const speedMBps = parseFloat(avgSpeed);

      // Update network speed tracking for smart concurrency
      updateNetworkSpeed(speedMBps);

      //  Show toast notification for individual file completion with smart refresh detection
      const currentFileCount = document.querySelectorAll('.file-card').length;
      showToast(` ${uploadItem.file.name} uploaded successfully (${fileSize} MB in ${uploadTime}s @ ${avgSpeed} MB/s)`, 4000);

      // Files will auto-load via the auto-refresh system, no manual intervention needed

      //  Save individual upload stats to history with enhanced metadata
      const uploadStats = {
        type: 'Single File Upload',
        filename: uploadItem.file.name,
        size: `${fileSize} MB`,
        sizeBytes: uploadItem.file.size,
        time: `${uploadTime}s`,
        timeSeconds: parseFloat(uploadTime),
        speed: `${avgSpeed} MB/s`,
        speedMBps: parseFloat(avgSpeed),
        timestamp: new Date().toLocaleString(),
        timestampISO: new Date().toISOString(),
        startTime: new Date(uploadItem.startTime).toLocaleString(),
        endTime: new Date().toLocaleString(),
        startTimeISO: new Date(uploadItem.startTime).toISOString(),
        endTimeISO: new Date().toISOString(),
        protocol: window.location.protocol === 'https:' ? 'HTTPS' : 'HTTP',
        method: 'Direct Upload',
        encrypted: isAESEnabled && document.getElementById('enableEncryption').checked,
        // Enhanced stats
        chunksUsed: false,
        chunkCount: 0,
        chunkSize: 'N/A',
        uploadId: uploadItem.id,
        sessionId: getCurrentDeviceId(),
        fileExtension: uploadItem.fileName.split('.').pop()?.toLowerCase() || 'unknown',
        uploadMethod: 'Direct (Single Request)',
        supportsResume: false,
        resumeCount: 0,
        transferEfficiency: '100%', // Direct uploads are 100% efficient
        networkCondition: uploadItem.speed > (5 * 1024 * 1024) ? 'Fast' : uploadItem.speed > (1 * 1024 * 1024) ? 'Medium' : 'Slow',
        status: 'COMPLETED' // Add status field for successful uploads
      };
      saveStatsToLog(uploadStats);

      // DON'T auto-refresh file list - let uploads stay visible until user clears them
      // Only refresh when ALL uploads are complete or user manually clears

      // Check if all uploads are complete before updating file list
      const hasActiveUploads = uploadQueue.some(item =>
        item.status === 'UPLOADING' || item.status === 'QUEUED' || item.status === 'PAUSED'
      );

      if (!hasActiveUploads) {
        // All uploads complete - show clear button but DON'T auto-refresh files
        showClearCompletedButton();

        //  Refresh file list through canonical Scheduler pipeline
        setTimeout(() => {
          if (typeof refreshFileList === 'function') refreshFileList();
        }, 100); // Small delay to ensure server has processed all files

        //  Show final completion toast for all uploads without creating batch log entry
        // Only count successfully completed uploads (exclude cancelled, error, etc.)
        const completedUploads = uploadQueue.filter(item => item.status === 'COMPLETED');
        const totalFiles = completedUploads.length;

        if (totalFiles > 0) {
          const getItemSize = item => item ? (item.fileSize || item.size || (item.file ? item.file.size : 0)) : 0;
          const getItemStartTime = item => item ? (item.startTime || Date.now()) : Date.now();

          const totalSize = completedUploads.reduce((sum, item) => sum + getItemSize(item), 0);
          const totalSizeMB = (totalSize / (1024 * 1024)).toFixed(1);
          const startTimes = completedUploads.map(getItemStartTime);
          const minStartTime = startTimes.length > 0 ? Math.min(...startTimes) : Date.now();
          const sessionTime = Math.max(0.1, ((Date.now() - minStartTime) / 1000)).toFixed(1);
          const sessionSpeed = (totalSizeMB / sessionTime).toFixed(1);

          // Only show completion toast with smart refresh detection - individual files are already logged separately
          const currentFileCount = document.querySelectorAll('.file-card').length;
          showToast(` All ${totalFiles} files uploaded successfully! (${totalSizeMB} MB total in ${sessionTime}s @ ${sessionSpeed} MB/s)`, 6000);

          // Files will auto-load via the auto-refresh system, no manual intervention needed
        }
      }

      // Don't auto-remove completed items - let user control with clear button
      // Check if all uploads are finished to show clear button
      const allUploadsFinished = uploadQueue.some(item =>
        item.status === 'UPLOADING' || item.status === 'QUEUED' || item.status === 'PAUSED'
      );

      if (!allUploadsFinished) {
        // All uploads complete - show clear button
        showClearCompletedButton();
        updateUploadManager(); // Update the display to show completed count
      }
    } else {
      uploadItem.status = 'FAILED';
      uploadItem.error = `Upload failed: ${xhr.status}`;
      updateUploadItem(uploadItem);
      endUpload();

      const fSize = uploadItem.fileSize || (uploadItem.file ? uploadItem.file.size : 0);
      const fName = uploadItem.fileName || (uploadItem.file ? uploadItem.file.name : "File");
      showToast(` Upload failed: ${fName} (Error ${xhr.status})`, 5000);

      //  Log failed upload with detailed stats
      const failedStats = {
        type: 'Failed Upload',
        filename: fName,
        size: `${(fSize / (1024 * 1024)).toFixed(1)} MB`,
        sizeBytes: fSize,
        progress: `${(uploadItem.progress || 0).toFixed(1)}%`,
        uploadedBytes: uploadItem.uploadedBytes || 0,
        failedAt: new Date().toLocaleString(),
        failedAtISO: new Date().toISOString(),
        errorCode: xhr.status,
        errorMessage: `HTTP ${xhr.status}`,
        reason: 'Server error',
        timestamp: new Date().toLocaleString(),
        timestampISO: new Date().toISOString(),
        startTime: new Date(uploadItem.startTime).toLocaleString(),
        startTimeISO: new Date(uploadItem.startTime).toISOString(),
        protocol: window.location.protocol === 'https:' ? 'HTTPS' : 'HTTP',
        method: 'Upload Failed',
        encrypted: uploadItem.isAESEnabled || false,
        uploadId: uploadItem.id,
        sessionId: getCurrentDeviceId(),
        fileExtension: fName.split('.').pop()?.toLowerCase() || 'unknown',
        uploadMethod: uploadItem.totalChunks ? 'Chunked (Failed)' : 'Direct (Failed)',
        supportsResume: uploadItem.totalChunks ? true : false,
        status: 'FAILED' // Add status field for failed uploads
      };
      saveStatsToLog(failedStats);

      // Check if all uploads are complete (including failed ones)
      const allUploadsFinished = uploadQueue.some(item =>
        item.status === 'UPLOADING' || item.status === 'QUEUED' || item.status === 'PAUSED'
      );

      if (!allUploadsFinished) {
        // All uploads complete - DON'T auto-refresh, let uploads stay visible until cleared
        // Only show clear button for user control
        showClearCompletedButton();

        //  Show completion summary even with errors
        const successfulUploads = uploadQueue.filter(item => item.status === 'COMPLETED').length;
        const failedUploads = uploadQueue.filter(item => item.status === 'FAILED' || item.status === 'ERROR').length;
        if (successfulUploads > 0) {
          showToast(` Upload session complete: ${successfulUploads} successful, ${failedUploads} failed`, 6000);
        }
      }
    }

    // Start next upload in queue
    startNextUpload();
  });

  xhr.addEventListener('error', () => {
    uploadItem.status = 'FAILED';
    uploadItem.error = 'Network error';
    updateUploadItem(uploadItem);
    endUpload();

    //  Log network error upload with detailed stats
    const netSize = uploadItem.fileSize || (uploadItem.file ? uploadItem.file.size : 0);
    const netName = uploadItem.fileName || (uploadItem.file ? uploadItem.file.name : "File");
    const networkErrorStats = {
      type: 'Network Error Upload',
      filename: netName,
      size: `${(netSize / (1024 * 1024)).toFixed(1)} MB`,
      sizeBytes: netSize,
      progress: `${(uploadItem.progress || 0).toFixed(1)}%`,
      uploadedBytes: uploadItem.uploadedBytes || 0,
      failedAt: new Date().toLocaleString(),
      failedAtISO: new Date().toISOString(),
      errorCode: 'NETWORK_ERROR',
      errorMessage: 'Network connection failed',
      reason: 'Network error',
      timestamp: new Date().toLocaleString(),
      timestampISO: new Date().toISOString(),
      startTime: new Date(uploadItem.startTime).toLocaleString(),
      startTimeISO: new Date(uploadItem.startTime).toISOString(),
      protocol: window.location.protocol === 'https:' ? 'HTTPS' : 'HTTP',
      method: 'Upload Network Error',
      encrypted: uploadItem.isAESEnabled || false,
      uploadId: uploadItem.id,
      sessionId: getCurrentDeviceId(),
      fileExtension: uploadItem.fileName.split('.').pop()?.toLowerCase() || 'unknown',
      uploadMethod: uploadItem.totalChunks ? 'Chunked (Network Error)' : 'Direct (Network Error)',
      supportsResume: uploadItem.totalChunks ? true : false,
      status: 'FAILED' // Add status field for network error uploads
    };
    saveStatsToLog(networkErrorStats);

    // Check if all uploads are complete
    const hasActiveUploads = uploadQueue.some(item =>
      item.status === 'UPLOADING' || item.status === 'QUEUED'
    );

    if (!hasActiveUploads) {
      // All uploads complete - DON'T auto-refresh, let uploads stay visible until cleared
      showClearCompletedButton();
    }

    startNextUpload();
  });

  xhr.addEventListener('abort', () => {
    if (uploadItem.status !== 'PAUSED') {
      uploadItem.status = 'CANCELLED';
      updateUploadItem(uploadItem);
      endUpload();
    }
  });

  xhr.open('POST', '/upload-auto');
  xhr.send(formData);
}

//  Enhanced Chunked Upload with Server-Side Adaptive Optimization
async function uploadLargeFileChunked(uploadItem) {
  const file = uploadItem.file;

  try {
    //  Get optimal chunk size from server based on file size and system capabilities
    console.log(` Getting optimal chunk size for ${file.size} byte file...`);
    const chunkResponse = await fetch(`/api/upload/chunk-size/${file.size}`);
    const chunkData = await chunkResponse.json();

    let CHUNK_SIZE = 1024 * 1024; // Default 1MB fallback

    if (chunkData.status === 'success') {
      CHUNK_SIZE = chunkData.optimal_chunk_size;
      console.log(` Server recommends ${chunkData.chunk_size_mb}MB chunks for this ${chunkData.system_info.platform} system`);

      // Show optimization info to user
      if (chunkData.recommendations.use_concurrent_uploads) {
        showToast(` Large file detected! Using ${chunkData.chunk_size_mb}MB chunks optimized for ${chunkData.system_info.platform}`, 4000);
      }
    } else {
      console.warn(' Could not get optimal chunk size, using default 1MB');
      showToast(' Using default chunk size - server optimization unavailable', 2000);
    }

    const totalChunks = Math.ceil(file.size / CHUNK_SIZE);

    uploadItem.totalChunks = totalChunks;
    if (uploadItem.uploadedChunks === undefined || uploadItem.status === 'PAUSED') {
      uploadItem.uploadedChunks = uploadItem.uploadedChunks || 0;
    } else {
      uploadItem.uploadedChunks = 0;
    }
    uploadItem.status = 'UPLOADING';

    var startChunk = 0;
    if (uploadItem.currentChunkIndex !== undefined && uploadItem.currentChunkIndex > 0) {
      startChunk = uploadItem.currentChunkIndex;
    }
    uploadItem.currentChunkIndex = startChunk;
    uploadItem.adaptiveChunkSize = CHUNK_SIZE;
    uploadItem.systemOptimized = chunkData.status === 'success';

    window.log.debug(`Starting adaptive chunked upload: ${totalChunks} chunks of ${(CHUNK_SIZE / 1024 / 1024).toFixed(2)}MB each`);

    // Upload chunks sequentially
    for (let chunkIndex = startChunk; chunkIndex < totalChunks; chunkIndex++) {
      // Update current chunk index
      uploadItem.currentChunkIndex = chunkIndex;

      // Check if upload was cancelled before starting each chunk
      if (uploadItem.status === 'CANCELLED') {
        console.log(` Upload cancelled at chunk ${chunkIndex + 1}`);
        return;
      }

      const start = chunkIndex * CHUNK_SIZE;
      const end = Math.min(start + CHUNK_SIZE, file.size);
      const chunk = file.slice(start, end);

      // Create form data for chunk
      const formData = new FormData();
      formData.append('chunk', chunk);
      formData.append('filename', file.name);
      formData.append('part_number', (chunkIndex + 1).toString());
      formData.append('total_parts', totalChunks.toString());
      let parentPath = typeof window.getItemFolder === "function" ? window.getItemFolder(uploadItem) : (uploadItem.targetDir || "");
      if (parentPath.startsWith("Home/")) parentPath = parentPath.substring(5);
      else if (parentPath === "Home") parentPath = "";
      if (parentPath) {
        formData.append('parent_path', parentPath);
      }
      if (chunkIndex === 0) {
        console.log("%c[LANVAN CHUNK] 📦 Starting Chunked Upload: '%s' (%s MB) -> Destination: '%s'", "color:#3b82f6; font-weight:bold; font-size:12px;", file.name, (file.size / (1024 * 1024)).toFixed(1), parentPath || "Home (Root)");
      }

      // Upload chunk with XMLHttpRequest for progress tracking
      const success = await uploadChunkWithProgress(uploadItem, formData, chunkIndex, totalChunks);

      // Check again if paused during the chunk upload
      if (uploadItem.status === 'PAUSED') {
        console.log(`⏸ Upload paused during chunk ${chunkIndex + 1} upload`);
        return;
      }

      if (!success) {
        // Only set error if not paused/cancelled
        if (uploadItem.status === 'UPLOADING') {
          uploadItem.status = 'FAILED';
          uploadItem.error = `Failed to upload chunk ${chunkIndex + 1}`;
          updateUploadItem(uploadItem);
          showToast(` Chunk upload failed: ${uploadItem.fileName} (chunk ${chunkIndex + 1})`, 5000);
        }
        return;
      }

      uploadItem.uploadedChunks = chunkIndex + 1;

      // Update progress based on chunks uploaded with accurate speed calculation
      const progress = ((chunkIndex + 1) / totalChunks) * 100;
      uploadItem.progress = progress;
      uploadItem.lastProgressUpdate = Date.now(); // Track for safety net
      uploadItem.uploadedBytes = Math.min(end, file.size);

      // Start safety net for active uploads
      startProgressUpdateSafetyNet();

      //  Calculate speed for chunked uploads using adjusted timing
      const effectiveStartTime = uploadItem.resumeAdjustedStartTime || uploadItem.startTime;
      const elapsed = (Date.now() - effectiveStartTime) / 1000;
      if (elapsed > 0) {
        uploadItem.speed = uploadItem.uploadedBytes / elapsed; // bytes per second (excludes paused time)
        uploadItem.timeRemaining = uploadItem.speed > 0 ? (file.size - uploadItem.uploadedBytes) / uploadItem.speed : 0;
      }

      updateUploadItem(uploadItem);
    }

    // All chunks uploaded, finalize the file (only if not paused/cancelled)
    if (uploadItem.status === 'UPLOADING') {
      await finalizeChunkedUpload(uploadItem);
    }

  } catch (error) {
    // Only handle errors if not paused (pausing can cause AbortError)
    if (uploadItem.status !== 'PAUSED' && uploadItem.status !== 'CANCELLED') {
      uploadItem.status = 'FAILED';
      uploadItem.error = `Chunked upload failed: ${error.message}`;
      updateUploadItem(uploadItem);
      showToast(` Chunked upload failed: ${uploadItem.fileName}`, 5000);
      endUpload();
      startNextUpload();
    }
  }
}

// Upload individual chunk with progress tracking
function uploadChunkWithProgress(uploadItem, formData, chunkIndex, totalChunks) {
  return new Promise((resolve) => {
    const xhr = new XMLHttpRequest();

    // Store xhr for potential cancellation - use unique key for chunked uploads
    uploadItem.xhr = xhr;
    uploadItem.currentXhr = xhr; // Keep separate reference for chunked uploads

    xhr.addEventListener('load', () => {
      if (xhr.status === 200) {
        const currentChunk = chunkIndex + 1;
        if (currentChunk === 1 || currentChunk === totalChunks || currentChunk % 20 === 0) {
          console.log(` Chunk ${currentChunk}/${totalChunks} uploaded successfully`);
        }
        resolve(true);
      } else {
        console.log(` Chunk ${chunkIndex + 1}/${totalChunks} failed: ${xhr.status}`);
        resolve(false);
      }
    });

    xhr.addEventListener('error', () => {
      console.log(` Chunk ${chunkIndex + 1}/${totalChunks} error`);
      resolve(false);
    });

    xhr.addEventListener('abort', () => {
      console.log(`⏸ Chunk ${chunkIndex + 1}/${totalChunks} aborted`);
      // For aborts (pause), don't treat as failure
      resolve(false);
    });

    xhr.open('POST', '/upload_chunk');
    xhr.send(formData);
  });
}

// Finalize chunked upload
async function finalizeChunkedUpload(uploadItem) {
  const formData = new FormData();
  formData.append('filename', uploadItem.file.name);
  formData.append('total_parts', uploadItem.totalChunks.toString());
  formData.append('encrypt', 'false'); // Chunked uploads don't support encryption

  let parentPath = typeof window.getItemFolder === "function" ? window.getItemFolder(uploadItem) : (uploadItem.targetDir || "");
  if (parentPath.startsWith("Home/")) parentPath = parentPath.substring(5);
  else if (parentPath === "Home") parentPath = "";
  if (parentPath) {
    formData.append('parent_path', parentPath);
  }

  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();

    xhr.addEventListener('load', () => {
      if (xhr.status === 200) {
        const response = JSON.parse(xhr.responseText);

        // Check if streaming assembly was used
        const isStreamingAssembly = response.streaming_assembly || false;
        const assemblyMethod = response.assembly_method || 'traditional chunk combination';

        // Show appropriate processing status
        uploadItem.status = 'PROCESSING';
        const statusText = document.getElementById(`status-${uploadItem.id}`);
        const speedText = document.getElementById(`speed-${uploadItem.id}`);

        if (isStreamingAssembly) {
          if (statusText) statusText.textContent = ' Streaming assembly completed';
          if (speedText) speedText.textContent = 'Optimized processing';
          // Streaming is much faster, show completion sooner
          uploadItem.status = 'COMPLETED';
          uploadItem.progress = 100;
          updateUploadItem(uploadItem);

          const fileSizeMB = (uploadItem.file.size / (1024 * 1024)).toFixed(1);
          showToast(` Streaming upload completed for ${uploadItem.fileName} (${fileSizeMB} MB) - 4x faster!`, 3000);
        } else {
          if (statusText) statusText.textContent = ' Processing chunks...';
          if (speedText) speedText.textContent = 'Server processing';

          const fileSizeMB = (uploadItem.file.size / (1024 * 1024)).toFixed(1);
          showToast(` Processing ${uploadItem.totalChunks} chunks for ${uploadItem.fileName}... (${fileSizeMB} MB) - Other operations may continue`, 4000);

          // Traditional processing takes longer
          const processAsync = () => {
            uploadItem.status = 'COMPLETED';
            uploadItem.progress = 100;
            updateUploadItem(uploadItem);
          };

          if (window.requestIdleCallback) {
            requestIdleCallback(() => {
              setTimeout(processAsync, 2000);
            }, { timeout: 5000 });
          } else {
            setTimeout(processAsync, 2000);
          }
        }

        updateUploadItem(uploadItem);
        endUpload();
        startNextUpload();

        // Show completion toast with smart refresh detection
        const fileSize = (uploadItem.file.size / (1024 * 1024)).toFixed(1);
        const uploadTime = ((Date.now() - uploadItem.startTime) / 1000).toFixed(1);
        uploadItem.uploadTime = uploadTime;
        const currentFileCount = document.querySelectorAll('.file-card').length;
        showToast(` ${uploadItem.fileName} uploaded successfully via chunked upload (${fileSize} MB, ${uploadItem.totalChunks} chunks)`, 5000);

        // Files will auto-load via the auto-refresh system, no manual intervention needed

        // Save enhanced chunked upload stats
        const uploadStats = {
          type: 'Chunked File Upload',
          filename: uploadItem.fileName,
          size: `${fileSize} MB`,
          sizeBytes: uploadItem.file.size,
          time: `${uploadTime}s`,
          timeSeconds: parseFloat(uploadTime),
          speed: `${(parseFloat(fileSize) / parseFloat(uploadTime)).toFixed(1)} MB/s`,
          speedMBps: parseFloat(fileSize) / parseFloat(uploadTime),
          timestamp: new Date().toLocaleString(),
          timestampISO: new Date().toISOString(),
          startTime: new Date(uploadItem.startTime).toLocaleString(),
          endTime: new Date().toLocaleString(),
          startTimeISO: new Date(uploadItem.startTime).toISOString(),
          endTimeISO: new Date().toISOString(),
          protocol: window.location.protocol === 'https:' ? 'HTTPS' : 'HTTP',
          method: 'Chunked Upload (Resume Capable)',
          encrypted: uploadItem.isAESEnabled || false,
          // Enhanced chunked stats with adaptive optimization info
          chunksUsed: true,
          chunkCount: uploadItem.totalChunks,
          chunkSize: uploadItem.systemOptimized ? `${(uploadItem.adaptiveChunkSize / 1024 / 1024).toFixed(1)} MB (Adaptive)` : '1 MB (Fallback)',
          systemOptimized: uploadItem.systemOptimized || false,
          adaptiveChunkSize: uploadItem.adaptiveChunkSize || (1024 * 1024),
          resumeCount: uploadItem.resumeCount || 0,
          uploadId: uploadItem.id,
          sessionId: getCurrentDeviceId(),
          fileExtension: uploadItem.fileName.split('.').pop()?.toLowerCase() || 'unknown',
          uploadMethod: 'Chunked (Large File)',
          supportsResume: true,
          transferEfficiency: uploadItem.resumeCount > 0 ? `${(100 - (uploadItem.resumeCount * 5)).toFixed(1)}%` : '100%',
          networkCondition: uploadItem.speed > (3 * 1024 * 1024) ? 'Fast' : uploadItem.speed > (1 * 1024 * 1024) ? 'Medium' : 'Slow',
          chunkFailures: 0, // Tracked chunk failures (initial state)
          avgChunkTime: `${(parseFloat(uploadTime) / uploadItem.totalChunks).toFixed(2)}s`,
          status: 'COMPLETED' // Add status field for successful chunked uploads
        };
        saveStatsToLog(uploadStats);

        // Don't auto-refresh file list, let clear button handle it
        // Check if all uploads are finished to show clear button
        const allUploadsComplete = !uploadQueue.some(item =>
          item.status === 'UPLOADING' || item.status === 'QUEUED' || item.status === 'PAUSED'
        );

        if (allUploadsComplete) {
          // All uploads complete - DON'T auto-refresh, just show clear button
          showClearCompletedButton();

          // Unblock QR generation after all chunked uploads complete
          window._qrBlocked = false;

          //  Refresh file count immediately to show new total
          setTimeout(() => {
            refreshFileCountOnly();
          }, 100); // Small delay to ensure server has processed all files
        }

        resolve(true);
      } else {
        // Unblock QR generation on chunked upload error
        window._qrBlocked = false;
        reject(new Error(`Finalization failed: ${xhr.status}`));
      }
    });

    xhr.addEventListener('error', () => {
      // Unblock QR generation on chunked upload network error
      window._qrBlocked = false;
      reject(new Error('Finalization network error'));
    });

    xhr.open('POST', '/finalize_upload');
    xhr.send(formData);
  });
}

// Single-flight debounced refresh manager to prevent double/triple parallel re-renders
let _activeRefreshPromise = null;
let _refreshDebounceTimer = null;

function requestFileListRefresh(delayMs = 150) {
  if (_refreshDebounceTimer) {
    clearTimeout(_refreshDebounceTimer);
  }
  return new Promise((resolve) => {
    _refreshDebounceTimer = setTimeout(() => {
      if (_activeRefreshPromise) {
        _activeRefreshPromise.then(resolve).catch(resolve);
        return;
      }
      _activeRefreshPromise = refreshFileList()
        .finally(() => {
          _activeRefreshPromise = null;
          resolve();
        });
    }, delayMs);
  });
}
window.requestFileListRefresh = requestFileListRefresh;

// Structured State Logger helper
function logStructuredState(reason, beforeCount, afterCount) {
  const currentFolder = (typeof window.getCurrentFolderPath === "function" ? window.getCurrentFolderPath() : (window.currentFolderPath || "Home"));
  const queue = Array.isArray(window.uploadQueue) ? window.uploadQueue : [];
  const queued = queue.filter(i => i && i.status === 'QUEUED').length;
  const active = queue.filter(i => i && (i.status === 'UPLOADING' || i.status === 'PROCESSING')).length;
  const completed = queue.filter(i => i && i.status === 'COMPLETED').length;
  const cancelled = queue.filter(i => i && i.status === 'CANCELLED').length;

  console.log(`%c[ACTION] Triggered state refresh | Reason: ${reason}`, "color:#6366f1; font-weight:bold;");
}
window.logStructuredState = logStructuredState;

// Dynamic file list refresh function
var _REFRESH_GEN_PER_FOLDER = {};
var _LATEST_COMPLETED_GEN_PER_FOLDER = {};

async function refreshFileList(reason = 'manual_or_api') {
  try {
    var targetFolder = (typeof window.getCurrentFolderPath === 'function')
      ? window.getCurrentFolderPath()
      : (window.currentFolderPath || '');
    targetFolder = (targetFolder === 'Home' || targetFolder === 'Home/') ? '' : targetFolder;

    if (window.__lanvanTimelineTracker) {
      window.__lanvanTimelineTracker.recordEvent("refreshFileList", "reason: " + reason + ", folder: '" + targetFolder + "'");
    }

    var _genId = (_REFRESH_GEN_PER_FOLDER[targetFolder] || 0) + 1;
    _REFRESH_GEN_PER_FOLDER[targetFolder] = _genId;

    var _caller = ((new Error()).stack || "").split("\n")[2] || "";
    console.log("%c[FLICKER-TRACE] 🔄 refreshFileList #" + _genId + " | Folder: '" + targetFolder + "' | Reason: " + (reason || "unknown") + " | Caller: " + _caller + " | Timestamp: " + performance.now().toFixed(1) + "ms");

    const lastCount = typeof lastFileCount !== "undefined" ? lastFileCount : 0;
    const endpoint = targetFolder ? '/api/folders/' + encodeURIComponent(targetFolder) + '/files' : '/api/files';
    const response = await fetch(endpoint);
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    const data = await response.json();

    // Out-of-order response guard: Ignore if a newer refresh for THIS folder has completed
    var latestCompleted = _LATEST_COMPLETED_GEN_PER_FOLDER[targetFolder] || 0;
    if (_genId < latestCompleted) {
      console.log(`[FLICKER-TRACE] ⚠️ Discarding stale refresh response #${_genId} for folder '${targetFolder}' (Latest completed: #${latestCompleted})`);
      return;
    }
    _LATEST_COMPLETED_GEN_PER_FOLDER[targetFolder] = _genId;

    const files = data.files_data || data.files || [];
    if (typeof window.__lanvanForensicTraceV2List === 'function') {
      window.__lanvanForensicTraceV2List('api_response', targetFolder, files, endpoint);
    }
    for (var vf = 0; vf < files.length; vf++) {
      var vfItem = files[vf];
      var vfName = typeof vfItem === 'string' ? vfItem : (vfItem && vfItem.name);
      if (!vfName) continue;
      if (typeof window.__lanvanForensicTraceV2 === 'function') {
        window.__lanvanForensicTraceV2('api_response', targetFolder, {
          name: vfName,
          identity: (typeof window.getCanonicalIdentity === 'function') ? window.getCanonicalIdentity(targetFolder, vfName) : vfName
        }, true, endpoint);
      }
    }
    console.log("[FLICKER-TRACE] refreshFileList #" + _genId + " for folder '" + targetFolder + "' | API returned " + files.length + " items");
    console.log("[TRACE] refreshFileList API response for '" + targetFolder + "': " + JSON.stringify(files.map(function (f) { return (typeof f === 'string' ? f : f.name) + (f.isFolder ? '(dir)' : '(file)'); })));

    // Cache in Repository (single source of truth for disk state)
    if (window.FileRepository && typeof window.FileRepository.setFolderCache === 'function') {
      window.FileRepository.setFolderCache(targetFolder, files);
      if (typeof window.__lanvanForensicTraceV2List === 'function' && typeof window.FileRepository.getFolderCache === 'function') {
        window.__lanvanForensicTraceV2List('repository_cache', targetFolder, window.FileRepository.getFolderCache(targetFolder), 'FileRepository.setFolderCache');
      }
    }

    // Only trigger RenderScheduler if user is STILL in the target folder when response arrives
    var activeFolder = (typeof window.getCurrentFolderPath === 'function')
      ? window.getCurrentFolderPath()
      : (window.currentFolderPath || '');
    activeFolder = (activeFolder === 'Home' || activeFolder === 'Home/') ? '' : activeFolder;

    if (activeFolder === targetFolder) {
      if (window.RenderScheduler && typeof window.RenderScheduler.requestRender === 'function') {
        window.RenderScheduler.requestRender();
      } else {
        updateFileDisplay(files);
      }
    }

    logStructuredState(reason, lastCount, files.length);
  } catch (error) {
    console.error(' Failed to refresh file list:', error);
  }
}

//  Manual refresh with user feedback
async function refreshFileListManually() {
  showToast(' Refreshing file list...', 2000);

  try {
    await refreshFileList();
    showToast(' File list refreshed successfully!', 3000);
  } catch (error) {
    console.error(' Manual refresh failed:', error);
    showToast(' Refresh failed - reloading page...', 3000);
    setTimeout(() => location.reload(), 1000);
  }
}

//  Auto-refresh functionality for cross-device sync
let autoRefreshInterval;
let lastFileCount = 0;
let autoRefreshActive = true;
let currentActiveSection = 'file'; // Track which section is currently active

function startAutoRefresh() {
  console.log(' Starting auto-refresh for cross-device file sync...');

  // Initial file count setup
  const fileGrid = document.querySelector('.file-grid');
  if (fileGrid) {
    lastFileCount = fileGrid.querySelectorAll('.file-card').length;
  }

  // Immediate file count refresh to ensure accuracy
  refreshFileCountOnly();

  // Set up polling every 5 seconds to check for file changes
  autoRefreshInterval = setInterval(async () => {
    if (!autoRefreshActive || document.hidden) return;

    // Only refresh files when file section is active, not when in clipboard mode
    if (currentActiveSection !== 'file') {
      console.log(' Skipping file refresh - clipboard section is active');
      return;
    }

    // Skip auto-refresh file count comparison while active uploads are transferring
    const hasActiveUploads = Array.isArray(window.uploadQueue) && window.uploadQueue.some(i => i && (i.status === 'UPLOADING' || i.status === 'QUEUED' || i.status === 'PROCESSING'));
    if (hasActiveUploads) {
      return;
    }

    try {
      const endpoint = getCurrentFileListEndpoint();
      const response = await fetch(endpoint);
      if (!response.ok) return;

      const data = await response.json();
      const files = data.files || [];
      const currentFileCount = files.length;

      // Only update if file count changed (indicating new uploads/deletions)
      if (currentFileCount !== lastFileCount) {
        console.log(` File count changed: ${lastFileCount} → ${currentFileCount}, auto-loading...`);
        // Route through canonical pipeline: API → Repository → Scheduler → Projection → Renderer
        refreshFileList('auto_refresh');

        // Silently auto-load new files without showing toast notifications
        if (currentFileCount > lastFileCount) {
          console.log(` ${currentFileCount - lastFileCount} new file(s) auto-loaded from other device(s)`);
        } else if (currentFileCount < lastFileCount) {
          console.log(` ${lastFileCount - currentFileCount} file(s) removed from other device(s)`);
        }
      } else {
        // Even if file count is same, ensure display is current (files might have changed)
        updateFileCount(currentFileCount);
      }
    } catch (error) {
      console.error(' Auto-refresh failed:', error);
    }
  }, 5000); // Check every 5 seconds
}

function stopAutoRefresh() {
  autoRefreshActive = false;
  if (autoRefreshInterval) {
    clearInterval(autoRefreshInterval);
    autoRefreshInterval = null;
    console.log(' Auto-refresh stopped');
  }
}

function pauseAutoRefresh() {
  autoRefreshActive = false;
  console.log('⏸ Auto-refresh paused');
}

function resumeAutoRefresh() {
  autoRefreshActive = true;
  console.log('▶ Auto-refresh resumed');
}

// Pause auto-refresh when user is actively uploading to avoid conflicts
function handleUploadStart() {
  pauseAutoRefresh();
}

function handleUploadEnd() {
  // Only resume auto-refresh if there are no active, queued, or paused uploads
  const hasUploadsInProgress = uploadQueue.some(item =>
    ['UPLOADING', 'QUEUED', 'PAUSED'].includes(item.status)
  );
  if (hasUploadsInProgress) {
    console.log('Skipping auto-refresh resume: paused or active uploads exist in queue');
    return;
  }
  // Resume auto-refresh after a short delay to allow current upload to complete
  setTimeout(() => {
    const hasUploadsInProgress2 = uploadQueue.some(item =>
      ['UPLOADING', 'QUEUED', 'PAUSED'].includes(item.status)
    );
    if (!hasUploadsInProgress2) {
      resumeAutoRefresh();
    }
  }, 2000);
}

// Prompt user with browser confirmation dialog ("Changes you made may not be saved") on reload/leave if uploads are in progress
window.addEventListener('beforeunload', function (e) {
  const queue = Array.isArray(window.uploadQueue) ? window.uploadQueue : (typeof uploadQueue !== 'undefined' && Array.isArray(uploadQueue) ? uploadQueue : []);
  const hasActiveUploads = queue.some(item =>
    item && ['UPLOADING', 'QUEUED', 'PROCESSING', 'PAUSED'].includes(item.status)
  );

  if (hasActiveUploads) {
    e.preventDefault();
    e.returnValue = 'Uploads are currently in progress. Changes you made may not be saved if you leave or reload.';
    return e.returnValue;
  }
});

//  Dedicated function to update file count display
function updateFileCount(fileCount) {
  const fileCountEl = document.getElementById('fileCount');
  if (fileCountEl) {
    if (fileCount > 0) {
      fileCountEl.textContent = `(${fileCount} file${fileCount === 1 ? '' : 's'})`;
    } else {
      fileCountEl.textContent = '';
    }
  }
  console.log(` File count updated: ${fileCount} files`);
}

// Helper to build the correct listing endpoint for the current folder
function getCurrentFileListEndpoint() {
  const rawFolder = (typeof window.getCurrentFolderPath === 'function')
    ? window.getCurrentFolderPath()
    : (window.currentFolderPath || '');
  const folder = (rawFolder === 'Home' || rawFolder === 'Home/') ? '' : rawFolder;
  if (folder) {
    return '/api/folders/' + encodeURIComponent(folder) + '/files';
  }
  return '/api/files';
}

//  Refresh only the file count from server without updating display
async function refreshFileCountOnly() {
  try {
    const response = await fetch(getCurrentFileListEndpoint());
    if (!response.ok) {
      console.warn(` Failed to refresh file count: HTTP ${response.status}`);
      return;
    }

    const data = await response.json();
    const count = data.files ? data.files.length : (data.files ? data.files.length : 0);
    updateFileCount(count);
    lastFileCount = count; // Keep auto-refresh tracking in sync

    console.log(` File count refreshed: ${count} files`);
  } catch (error) {
    console.error(' Failed to refresh file count:', error);
  }
}

function updateFileDisplay(files) {
  const fileGrid = document.querySelector('.file-grid');
  const noFilesMsg = document.querySelector('.no-files-message');

  // Update file count using dedicated function
  const fileCount = files ? files.length : 0;
  updateFileCount(fileCount);

  // Update lastFileCount for auto-refresh tracking
  lastFileCount = fileCount;

  if (!files || files.length === 0) {
    // Show no files message
    if (fileGrid) fileGrid.style.display = 'none';
    if (!noFilesMsg) {
      const container = fileGrid ? fileGrid.parentElement : document.querySelector('.file-section');
      if (container) {
        const msg = document.createElement('div');
        msg.className = 'no-files-message';

        // Check if files have been uploaded recently but aren't visible
        // Since we now auto-load files, just show the standard message
        msg.innerHTML = '<p style="text-align: center; color: var(--text-color); opacity: 0.6; font-style: italic;">No files uploaded yet. Drag & drop or click to upload!</p>';

        container.appendChild(msg);
      }
    } else {
      // Update existing message - always show standard message since we auto-load
      noFilesMsg.innerHTML = '<p style="text-align: center; color: var(--text-color); opacity: 0.6; font-style: italic;">No files uploaded yet. Drag & drop or click to upload!</p>';
      noFilesMsg.style.display = 'block';
    }
    return;
  }

  // Hide no files message and reset recent uploads flag when files are visible
  if (noFilesMsg) {
    noFilesMsg.style.display = 'none';
  }

  // Update or create file grid
  if (!fileGrid) {
    // Create file grid if it doesn't exist - find the section with "Available Files" heading
    let container = null;
    const sections = document.querySelectorAll('section');
    for (const section of sections) {
      const h2 = section.querySelector('h2');
      if (h2 && h2.textContent.includes('Available Files')) {
        container = section;
        break;
      }
    }

    // Fallback to any section if specific one not found
    if (!container) {
      container = document.querySelector('section');
    }

    if (container) {
      const newGrid = document.createElement('div');
      newGrid.className = 'file-grid';
      container.appendChild(newGrid);
    } else {
      console.warn(' Could not find container for file grid');
      return;
    }
  }

  const grid = document.querySelector('.file-grid');
  if (grid) {
    grid.style.display = 'grid';
    grid.innerHTML = files.map(file => `
        <div class="file-card">
          <div class="file-icon"></div>
          <div class="file-name" title="${escapeHtml(file)}">${escapeHtml(file)}</div>
          <a href="/download/${encodeURIComponent(file)}" download class="download-btn"> Download</a>
        </div>
      `).join('');
  }
}



// Clear all files function
async function clearAllFiles() {


  try {
    console.log(' Clearing all files...');

    const response = await fetch('/clear', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      }
    });

    if (response.ok) {
      // Update file display immediately
      updateFileDisplay([]);
      showToast(' All files cleared successfully!', 3000);
      console.log(' Files cleared successfully');
    } else {
      throw new Error(`HTTP ${response.status}`);
    }
  } catch (error) {
    console.error(' Failed to clear files:', error);
    showToast(' Failed to clear files. Please try again.', 5000);
  }
}

window.DOM_CACHE = window.DOM_CACHE || {};
var DOM_CACHE = window.DOM_CACHE;
let dropZone, fileInput, preview, progressBar, statusText; // Legacy variables

// Initialize DOM cache when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
  // Start server status monitoring immediately
  startServerStatusMonitoring();

  // Check if we're on clipboard-only page
  const isClipboardOnly = typeof show_clipboard_only !== 'undefined' && show_clipboard_only;

  // Initialize current active section from authoritative pre-paint dataset / localStorage
  const savedTab = document.documentElement.dataset.activeTab || localStorage.getItem('lanvan_active_tab') || (window.location.pathname === '/clipboard' ? 'clipboard' : 'file');
  currentActiveSection = savedTab;
  window.activeTab = savedTab;
  console.log(` Initial active section: ${currentActiveSection}`);

  Object.assign(DOM_CACHE, {
    // File upload elements (only for file sharing mode)
    dropZone: isClipboardOnly ? null : document.getElementById('drop-zone'),
    fileInput: isClipboardOnly ? null : document.getElementById('fileInput'),
    folderInput: isClipboardOnly ? null : document.getElementById('folderInput'),
    preview: isClipboardOnly ? null : document.getElementById('file-preview'),
    progressBar: isClipboardOnly ? null : document.getElementById('uploadProgress'),
    statusText: isClipboardOnly ? null : document.getElementById('uploadStatus'),

    // Common elements (both modes)
    toast: document.getElementById('toast'),
    toastProgress: document.getElementById('toast-progress'),
    protocolIcon: document.getElementById('protocolIcon'),
    protocolText: document.getElementById('protocolText'),
    protocolStatus: document.getElementById('protocolStatus'),
    aesToggle: document.getElementById('enableEncryption'),
    darkModeToggle: document.getElementById('enableDarkMode')
  });

  // Debug DOM cache - check if all elements are found
  if (isClipboardOnly) {
    console.log(' DOM Cache Status (Clipboard Mode):', {
      toast: !!DOM_CACHE.toast,
      protocolIcon: !!DOM_CACHE.protocolIcon,
      protocolText: !!DOM_CACHE.protocolText,
      protocolStatus: !!DOM_CACHE.protocolStatus,
      aesToggle: !!DOM_CACHE.aesToggle,
      darkModeToggle: !!DOM_CACHE.darkModeToggle
    });
  } else {
    console.log(' DOM Cache Status (File Sharing Mode):', {
      dropZone: !!DOM_CACHE.dropZone,
      fileInput: !!DOM_CACHE.fileInput,
      preview: !!DOM_CACHE.preview,
      progressBar: !!DOM_CACHE.progressBar,
      statusText: !!DOM_CACHE.statusText,
      toast: !!DOM_CACHE.toast,
      protocolIcon: !!DOM_CACHE.protocolIcon,
      protocolText: !!DOM_CACHE.protocolText,
      protocolStatus: !!DOM_CACHE.protocolStatus,
      aesToggle: !!DOM_CACHE.aesToggle,
      darkModeToggle: !!DOM_CACHE.darkModeToggle
    });

    // Legacy variables for backward compatibility
    dropZone = DOM_CACHE.dropZone;
    fileInput = DOM_CACHE.fileInput;
    preview = DOM_CACHE.preview;
    progressBar = DOM_CACHE.progressBar;
    statusText = DOM_CACHE.statusText;

    // Initialize file count display from current page data
    const fileGrid = document.querySelector('.file-grid');
    if (fileGrid) {
      const fileCards = fileGrid.querySelectorAll('.file-card');
      const fileCount = fileCards.length;
      updateFileCount(fileCount);
      lastFileCount = fileCount; // Initialize lastFileCount for auto-refresh tracking
    } else {
      lastFileCount = 0;
    }

    // Auto-load clipboard history if clipboard section is available
    const clipboardSection = document.getElementById('clipboardSection');
    if (clipboardSection) {
      console.log(' Auto-loading clipboard history on page load...');
      // Delay the refresh slightly to ensure all DOM elements are ready
      setTimeout(() => {
        if (typeof refreshClipboardHistory === 'function') {
          refreshClipboardHistory();
        }
      }, 500);
    }

    // Set up event listeners after DOM cache is ready
    setupEventListeners();

    //  Start auto-refresh for file list to sync across devices
    startAutoRefresh();

    //  Pause auto-refresh when page is hidden to save bandwidth
    document.addEventListener('visibilitychange', () => {
      if (document.hidden) {
        pauseAutoRefresh();
      } else {
        resumeAutoRefresh();
        // Force refresh when page becomes visible again
        setTimeout(refreshFileList, 1000);
        // Also refresh file count immediately
        refreshFileCountOnly();
      }
    });

    //  Update Protocol Status Indicator
    const protocolIcon = DOM_CACHE.protocolIcon;
    const protocolText = DOM_CACHE.protocolText;
    const protocolStatus = DOM_CACHE.protocolStatus;
    const isHTTPS = location.protocol === 'https:';

    // Find the QR code hint text (the third span in protocolStatus)
    const qrHintText = protocolStatus.querySelector('#qrHintText');

    if (isHTTPS) {
      protocolIcon.textContent = '';
      protocolText.textContent = 'HTTPS';
      protocolText.style.color = '#22c55e';

      if (qrHintText) {
        qrHintText.innerHTML = 'Tap the WiFi icon above to share this connection securely with other devices.';
      }
    } else {
      protocolIcon.textContent = '';
      protocolText.textContent = 'HTTP';
      protocolText.style.color = '#f59e0b';

      if (qrHintText) {
        qrHintText.innerHTML = 'Consider using HTTPS for encrypted file transfers.';
      }
    }

    //  Check for mDNS service and update status
    updateMDNSStatus();

    //  Handle AES toggle restrictions - DISABLED FOR HTTP
    if (location.protocol === 'http:') {
      //  NEW LOGIC: Allow AES over HTTP with HTTP-Safe mode
      const toggle = DOM_CACHE.aesToggle;
      if (toggle) {
        // Enable AES toggle for HTTP (HTTP-Safe mode will provide security)
        toggle.disabled = false;
        const toggleWrapper = toggle.closest('div');
        toggleWrapper.style.opacity = '1';
        toggleWrapper.title = " AES over HTTP requires HTTP-Safe Mode for complete security protection.";

        // Add change listener
        toggle.addEventListener('change', function () {
          isEncryptionEnabled = this.checked;
          console.log(' Encryption toggled:', isEncryptionEnabled);

          //  HTTP-Safe mode is now automatic for HTTP connections
          if (location.protocol === 'http:' && this.checked) {
            console.log(' HTTP-Safe mode automatically enabled for HTTP connection');
            showToast(' HTTP-Safe mode automatically enabled for secure encryption!', 4000);
          }
        });
      }
    } else {
      // HTTPS - encryption available (same as HTTP now with HTTP-Safe mode)
      const toggle = DOM_CACHE.aesToggle;
      if (toggle) {
        toggle.addEventListener('change', function () {
          isEncryptionEnabled = this.checked;
          console.log(' Encryption toggled:', isEncryptionEnabled);
        });
      }
    }
  }
});

function setupEventListeners() {
  console.count("setupEventListeners");
  // Set up clipboard "Add Text" button with high-priority event listener
  const addTextBtn = document.getElementById('addTextToClipboardBtn');
  if (addTextBtn) {
    // Use high-priority event listener that works even during heavy uploads
    addTextBtn.addEventListener('click', function (e) {
      e.preventDefault();
      e.stopPropagation();
      // Use setTimeout(0) to ensure this always runs in next event loop
      setTimeout(() => addTextToClipboard(), 0);
    }, { capture: true, passive: false }); // High priority capture event
    console.log(' Clipboard Add Text button event listener set up');
  }

  // Set up modal clipboard "Add Text" button as well
  const addTextBtnModal = document.getElementById('addTextToClipboardBtnModal');
  if (addTextBtnModal) {
    addTextBtnModal.addEventListener('click', function (e) {
      e.preventDefault();
      e.stopPropagation();
      setTimeout(() => addTextToClipboard(), 0);
    }, { capture: true, passive: false });
    console.log(' Modal Clipboard Add Text button event listener set up');
  }

  // Set up Enter key support for clipboard text input
  const clipboardTextInput = document.getElementById('clipboardTextInput');
  if (clipboardTextInput) {
    clipboardTextInput.addEventListener('keydown', function (e) {
      if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
        e.preventDefault();
        e.stopPropagation();
        setTimeout(() => addTextToClipboard(), 0);
      }
    }, { capture: true, passive: false });
    console.log(' Clipboard text input Enter key support set up');
  }

  // Skip file upload event listeners if we're on clipboard-only page
  const isClipboardOnly = typeof show_clipboard_only !== 'undefined' && show_clipboard_only;

  if (isClipboardOnly) {
    console.log(' Clipboard-only mode: Skipping file upload event listeners');

    // Only set up toast click handler for clipboard mode
    if (DOM_CACHE.toast) {
      DOM_CACHE.toast.addEventListener('click', function () {
        console.log(' Toast clicked');
        const toast = this;

        // Clear any auto-hide timeout using the new system
        if (toastTimeout) {
          clearTimeout(toastTimeout);
          toastTimeout = null;
        }

        hideToast();
      });
    } else {
      console.warn(' Toast element not found in setupEventListeners');
    }

    console.log(' Clipboard event listeners set up successfully');
    return;
  }

  // Check if DOM elements are available before adding listeners (file sharing mode)
  if (!DOM_CACHE.dropZone || !DOM_CACHE.fileInput) {
    console.error(' Critical DOM elements not found:', {
      dropZone: !!DOM_CACHE.dropZone,
      fileInput: !!DOM_CACHE.fileInput
    });
    return;
  }

  // Window-level Drag & Drop detection (activates overlay instantly anywhere on screen)
  let windowDragCounter = 0;
  const globalOverlay = document.getElementById('globalDragOverlay');

  window.addEventListener('dragenter', e => {
    // Only activate for file drags
    if (e.dataTransfer && e.dataTransfer.types && Array.from(e.dataTransfer.types).includes('Files')) {
      e.preventDefault();
      windowDragCounter++;
      if (globalOverlay) globalOverlay.classList.add('active');
    }
  });

  window.addEventListener('dragover', e => {
    if (e.dataTransfer && e.dataTransfer.types && Array.from(e.dataTransfer.types).includes('Files')) {
      e.preventDefault();
      e.dataTransfer.dropEffect = 'copy';
    }
  });

  window.addEventListener('dragleave', e => {
    if (e.dataTransfer && e.dataTransfer.types && Array.from(e.dataTransfer.types).includes('Files')) {
      e.preventDefault();
      windowDragCounter--;
      if (windowDragCounter <= 0) {
        windowDragCounter = 0;
        if (globalOverlay) globalOverlay.classList.remove('active');
      }
    }
  });

  // Shared async recursive directory scanner via HTML5 FileSystem API
  async function scanFileSystemEntry(entry, path = '') {
    if (!entry) return [];
    if (entry.isFile) {
      return new Promise(resolve => {
        entry.file(file => {
          const relPath = path ? path + file.name : file.name;
          try {
            Object.defineProperty(file, 'webkitRelativePath', {
              value: relPath,
              writable: false,
              configurable: true
            });
          } catch (err) { }
          resolve([file]);
        }, () => resolve([]));
      });
    } else if (entry.isDirectory) {
      const dirReader = entry.createReader();
      const entries = await new Promise(resolve => {
        dirReader.readEntries(results => resolve(results || []), () => resolve([]));
      });
      const nestedPromises = entries.map(childEntry => scanFileSystemEntry(childEntry, path + entry.name + '/'));
      const nestedResults = await Promise.all(nestedPromises);
      return nestedResults.flat();
    }
    return [];
  }

  window.addEventListener('drop', async e => {
    e.preventDefault();
    windowDragCounter = 0;
    if (globalOverlay) globalOverlay.classList.remove('active');

    const dtItems = e.dataTransfer ? e.dataTransfer.items : null;
    const dtFiles = e.dataTransfer ? e.dataTransfer.files : null;

    let collectedFiles = [];

    if (dtItems && dtItems.length > 0 && dtItems[0].webkitGetAsEntry) {
      const entryPromises = [];
      for (let i = 0; i < dtItems.length; i++) {
        const entry = dtItems[i].webkitGetAsEntry();
        if (entry) {
          entryPromises.push(scanFileSystemEntry(entry));
        }
      }
      const results = await Promise.all(entryPromises);
      collectedFiles = results.flat();
    }

    // Fallback if FileSystem API yields no files or is unsupported
    if (collectedFiles.length === 0 && dtFiles && dtFiles.length > 0) {
      collectedFiles = Array.from(dtFiles);
    }

    if (collectedFiles.length > 0) {
      console.log(' Global window drop detected:', collectedFiles.length, 'file(s) extracted');
      if (typeof window.handleFiles === 'function') {
        window.handleFiles(collectedFiles);
      }
    }
  });

  ['dragenter', 'dragover'].forEach(evt =>
    DOM_CACHE.dropZone.addEventListener(evt, e => {
      e.preventDefault();
      DOM_CACHE.dropZone.classList.add('dragover');
    })
  );

  ['dragleave', 'drop'].forEach(evt =>
    DOM_CACHE.dropZone.addEventListener(evt, e => {
      e.preventDefault();
      DOM_CACHE.dropZone.classList.remove('dragover');
    })
  );

  DOM_CACHE.dropZone.addEventListener('drop', async e => {
    e.preventDefault();
    e.stopPropagation();
    DOM_CACHE.dropZone.classList.remove('dragover');

    const dtItems = e.dataTransfer ? e.dataTransfer.items : null;
    const dtFiles = e.dataTransfer ? e.dataTransfer.files : null;

    let collectedFiles = [];

    if (dtItems && dtItems.length > 0 && dtItems[0].webkitGetAsEntry) {
      const entryPromises = [];
      for (let i = 0; i < dtItems.length; i++) {
        const entry = dtItems[i].webkitGetAsEntry();
        if (entry) {
          entryPromises.push(scanFileSystemEntry(entry));
        }
      }
      const results = await Promise.all(entryPromises);
      collectedFiles = results.flat();
    }

    if (collectedFiles.length === 0 && dtFiles && dtFiles.length > 0) {
      collectedFiles = Array.from(dtFiles);
    }

    if (collectedFiles.length > 0) {
      console.log(' DropZone drop detected:', collectedFiles.length, 'file(s) extracted');
      if (typeof window.handleFiles === 'function') {
        window.handleFiles(collectedFiles);
      }
    }
  });

  DOM_CACHE.dropZone.addEventListener('click', (e) => {
    // Ignore clicks that originated from the hidden file/folder inputs themselves
    if (e.target === DOM_CACHE.fileInput || e.target === DOM_CACHE.folderInput) return;
    // Only trigger file picker when clicking directly on the inner empty-dropzone-target area
    if (e.target.closest('.empty-dropzone-target') || e.target.closest('.dropzone-click-target')) {
      console.log(' Drop zone target clicked - opening file picker');
      if (DOM_CACHE.fileInput) {
        DOM_CACHE.fileInput.value = '';
        DOM_CACHE.fileInput.click();
      }
    }
  });

  DOM_CACHE.fileInput.addEventListener('change', () => {
    const files = DOM_CACHE.fileInput.files;
    console.log(' File input changed, files:', files.length);
    if (files.length > 0) {
      // Route directly to handleFiles — this is what handleFileSelection('file') does internally
      if (typeof window.handleFiles === 'function') {
        window.handleFiles(files);
      }
      DOM_CACHE.fileInput.value = '';
    }
  });

  // Stop fileInput click from bubbling to the drop zone's click handler
  DOM_CACHE.fileInput.addEventListener('click', (e) => e.stopPropagation());

  DOM_CACHE.folderInput.addEventListener('change', () => {
    const files = DOM_CACHE.folderInput.files;
    console.log(' Folder input changed, files:', files.length);
    if (files.length > 0) {
      if (typeof window.handleFiles === 'function') {
        window.handleFiles(files);
      }
    }
  });

  // Stop folderInput click from bubbling to the drop zone's click handler
  DOM_CACHE.folderInput.addEventListener('click', (e) => e.stopPropagation());

  // Set up toast click handler
  if (!DOM_CACHE.toast) {
    DOM_CACHE.toast = document.getElementById('toast');
  }

  if (DOM_CACHE.toast) {
    DOM_CACHE.toast.addEventListener('click', function () {

      console.log(' Toast clicked');
      const toast = this;

      // Clear any auto-hide timeout using the new system
      if (toastTimeout) {
        clearTimeout(toastTimeout);
        toastTimeout = null;
      }

      // If there's transfer data, show detailed log
      if (toast._transferData) {
        console.log(' Showing detailed transfer data');
        const data = toast._transferData;
        let detailedMessage;

        if (data.type === 'download' || data.type === 'direct_download_ultra_fast') {
          const timeRange = data.startTime && data.endTime ?
            `${data.startTime} - ${data.endTime}` :
            data.timestamp;

          //  PERFORMANCE: Use array join for efficient string building
          detailedMessage = [
            ` ${data.type.toUpperCase()}: ${data.filename}`,
            ` Size: ${data.size}`,
            ` Server Response: ${data.serverResponseTime || 'N/A'}`,
            ` Processing Time: ${data.processingTime || data.downloadTime || 'N/A'}`,
            `⏱ Total Time: ${data.totalTime || 'N/A'}`,
            ` Protocol: ${location.protocol === 'https:' ? 'HTTPS' : 'HTTP'}`,
            ` Time: ${timeRange}`,
            '',
            ` Click anywhere else to dismiss`
          ].join('\n');
        } else {
          const protocolInfo = data.protocol ? ` Protocol: ${data.protocol}\n` : '';
          const chunkInfo = data.chunkType ? ` Transfer Type: ${data.chunkType}\n` : '';
          const networkInfo = data.networkSpeed ? ` Network Speed: ${data.networkSpeed}\n` : '';
          const finalChunkInfo = data.finalChunkSize ? ` Final Chunk Size: ${data.finalChunkSize}\n` : '';
          const timeRange = data.startTime && data.endTime ?
            `${data.startTime} - ${data.endTime}` :
            data.timestamp;

          detailedMessage = ` ${data.type.toUpperCase()}: ${data.filename}\n` +
            ` Size: ${data.size}\n` +
            `⏱ ${data.type === 'download' ? 'Download' : 'Upload'} Duration: ${data.time} @ ${data.speed}\n` +
            chunkInfo +
            networkInfo +
            finalChunkInfo +
            ` AES: ${data.aesEnabled ? 'Yes' : 'No'}\n` +
            protocolInfo +
            ` Time: ${timeRange}\n\n` +
            ` Click anywhere else to dismiss`;
        }

        toast.style.whiteSpace = 'pre-line';
        toast.style.backgroundColor = '#2c3e50';
        toast.innerText = detailedMessage;
        lastToastMessage = detailedMessage; // Update the tracked message
        isPersistentToast = true; // Mark as persistent

        // Make it persistent (no auto-hide)
        toast.style.display = 'block';

      } else {
        console.log(' Making current toast persistent');
        // No transfer data, just make current message persistent
        toast.style.backgroundColor = '#2c3e50';
        isPersistentToast = true; // Mark as persistent
        toast.style.display = 'block';
        toast.title = 'Persistent message - click anywhere else to dismiss';
      }
    });
  }


  //  Add global click handler to dismiss persistent toasts
  document.addEventListener('click', function globalToastClickHandler(e) {
    let toast = DOM_CACHE.toast;

    // Robust fallback for toast element
    if (!toast) {
      toast = document.getElementById('toast');
      if (toast) {
        DOM_CACHE.toast = toast;
      } else {
        return; // No toast element found
      }
    }

    if (e.target !== toast && !toast.contains(e.target)) {
      if (toast.style.backgroundColor === 'rgb(44, 62, 80)') { // Persistent mode (either completion or detailed view)
        hideToast(); // Use the new hide function

        //  Reload page if this was an upload completion toast
        if (window._shouldReloadAfterToast) {
          window._shouldReloadAfterToast = false;
          location.reload();
        }
      }
    }
  });
}

function clearFileSelection() {
  // Clear the file input (safe - doesn't affect active uploads)
  if (DOM_CACHE.fileInput) {
    DOM_CACHE.fileInput.value = '';
  }

  // Clear the preview area (safe - only affects UI)
  if (DOM_CACHE.preview) {
    DOM_CACHE.preview.innerHTML = '';
  }

  // Note: We do NOT clear uploadQueue or any active upload state here
  // This function only clears the file selection UI, not the upload manager

  console.log(' File selection UI cleared (upload queue preserved)');
}

function displaySelectedFiles(files) {
  // For multiple files, show preview and let user manually upload if needed
  updatePreview(files);

  // Show helpful message for multiple files
  const totalSize = Array.from(files).reduce((sum, file) => sum + file.size, 0);
  const totalSizeMB = (totalSize / 1024 / 1024).toFixed(1);
  showToast(` ${files.length} files selected (${totalSizeMB} MB total) - Auto-upload triggered`, 3000);

  // Actually trigger auto-upload for multiple files too
  autoUpload(files);
}

function autoUpload(files) {
  console.log(' autoUpload called with files:', files ? files.length : 'no files', files);

  if (!files.length) {
    console.log(' No files to upload');
    return;
  }

  //  Deduplication: Check for rapid duplicate selections
  if (!shouldProcessFileSelection(files)) {
    return;
  }

  //  Perform periodic memory cleanup
  performMemoryCleanup();

  const isAESEnabled = DOM_CACHE.aesToggle && DOM_CACHE.aesToggle.checked;
  const isHTTPS = location.protocol === 'https:';

  console.log(' Upload settings:', { isAESEnabled, isHTTPS });

  //  NO SIZE LIMITS - Streaming encryption handles files of any size
  // Size limit check removed - AES now supports multi-gigabyte files
  console.log(' AES enabled - streaming encryption supports any file size');

  //  HTTP-Safe AES: Allow AES over HTTP with metadata protection
  if (isAESEnabled && !isHTTPS) {
    console.log(' AES over HTTP - HTTP-Safe mode provides security');
    // No longer block AES over HTTP - HTTP-Safe mode handles security
  }

  //  Log current upload queue state before adding new files
  const currentActiveUploads = uploadQueue.filter(item =>
    ['UPLOADING'].includes(item.status)
  ).length;

  console.log(` Current upload state: ${currentActiveUploads} active uploads, adding ${files.length} new files`);

  //  NEW: Add files to upload manager without interfering with active uploads
  addToUploadQueue(Array.from(files));

  //  Clear the file input and preview after adding to queue (safe operation)
  clearFileSelection();

  // Start uploading new files if possible (won't affect active uploads)
  startNextUpload();

  //  Show feedback to user about adding files to active queue
  if (currentActiveUploads > 0) {
    showToast(` Added ${files.length} file(s) to upload queue. ${currentActiveUploads} uploads currently active.`, 3000);
  } else {
    const optimalConcurrency = getOptimalConcurrency();
    const filesToStart = Math.min(optimalConcurrency, files.length);

    if (filesToStart > 1) {
      showToast(` Starting smart concurrent upload of ${files.length} file(s) (${filesToStart} concurrent)...`, 3000);
    } else {
      showToast(` Starting upload of ${files.length} file(s)...`, 3000);
    }
  }
}

// HTTP-Safe AES crypto helpers extracted to features/security/http-safe-crypto.js
function isHttpSafeEnabled() {
  return window.HttpSafeCrypto ? window.HttpSafeCrypto.isHttpSafeEnabled() : false;
}

//  HTTP-Safe AES Upload Function
async function uploadFilesHttpSafe(files) {
  try {
    updateToastContent(' HTTP-Safe AES: Preparing secure upload with metadata protection...');

    // Generate decoy traffic before upload
    await generateDecoyTraffic();

    const encryptedFiles = [];
    const totalOriginalSize = files.reduce((sum, file) => sum + file.size, 0);
    const totalOriginalSizeMB = (totalOriginalSize / 1024 / 1024).toFixed(2);

    updateToastContent(` HTTP-Safe AES: Encrypting ${files.length} file(s) (${totalOriginalSizeMB} MB)...`);

    // Encrypt files with HTTP-Safe protection
    for (let i = 0; i < files.length; i++) {
      const file = files[i];
      updateToastContent(` HTTP-Safe AES: Encrypting file ${i + 1}/${files.length}: ${file.name}`);

      const encryptedData = await encryptFileHttpSafe(file);
      const obfuscatedUpload = createObfuscatedUpload(encryptedData, file);
      encryptedFiles.push(obfuscatedUpload);
    }

    // Calculate encrypted sizes
    const totalEncryptedSize = encryptedFiles.reduce((sum, ef) => sum + ef.encryptedSize, 0);
    const totalEncryptedSizeMB = (totalEncryptedSize / 1024 / 1024).toFixed(2);

    updateToastContent(` HTTP-Safe AES: Uploading ${encryptedFiles.length} protected file(s) (${totalEncryptedSizeMB} MB)...`);

    // Upload encrypted files
    const formData = new FormData();
    const metadataArray = [];

    for (const encFile of encryptedFiles) {
      formData.append('files', encFile.file);
      metadataArray.push({
        original_name: encFile.originalName,
        metadata: encFile.metadata,
        original_size: encFile.originalSize,
        encrypted_size: encFile.encryptedSize
      });
    }

    formData.append('http_safe_metadata', JSON.stringify(metadataArray));
    formData.append('encrypt', 'true');
    formData.append('http_safe', 'true');

    // Upload with progress tracking
    const xhr = new XMLHttpRequest();
    progressBar.style.display = 'block';
    progressBar.value = 0;

    const startTime = new Date().getTime();

    xhr.upload.addEventListener('progress', (e) => {
      if (e.lengthComputable) {
        const percent = (e.loaded / e.total) * 100;
        progressBar.value = percent;

        const elapsed = (new Date().getTime() - startTime) / 1000;
        const uploadedMB = (e.loaded / 1024 / 1024).toFixed(1);
        const speed = elapsed > 0 ? (e.loaded / 1024 / 1024 / elapsed).toFixed(2) : '0.00';

        updateToastContent(` HTTP-Safe AES: Uploading ${percent.toFixed(1)}% (${uploadedMB}/${totalEncryptedSizeMB} MB) @ ${speed} MB/s`);
      }
    });

    return new Promise((resolve, reject) => {
      xhr.onload = () => {
        window._qrBlocked = false;
        progressBar.style.display = 'none';

        if (xhr.status === 200) {
          const elapsed = (new Date().getTime() - startTime) / 1000;
          const avgSpeed = (totalEncryptedSize / 1024 / 1024 / elapsed).toFixed(2);

          showToast(` HTTP-Safe AES Upload Complete! ${files.length} file(s) (${totalOriginalSizeMB} MB) uploaded securely with metadata protection in ${elapsed.toFixed(1)}s @ ${avgSpeed} MB/s`, 5000);

          try {
            const response = JSON.parse(xhr.responseText);
            displayUploadedFiles(response.files || []);
          } catch (e) {
            console.warn('Response parsing issue:', e);
          }

          resolve();
        } else {
          showToast(` HTTP-Safe upload failed: ${xhr.statusText}`, 5000);
          reject(new Error(`Upload failed: ${xhr.statusText}`));
        }
      };

      xhr.onerror = () => {
        window._qrBlocked = false;
        progressBar.style.display = 'none';
        showToast(' HTTP-Safe upload failed due to network error', 5000);
        reject(new Error('Network error'));
      };

      xhr.open('POST', '/upload');
      xhr.send(formData);
    });

  } catch (error) {
    window._qrBlocked = false;
    progressBar.style.display = 'none';
    showToast(` HTTP-Safe AES encryption failed: ${error.message}`, 5000);
    throw error;
  }
}

//  Regular upload function (original logic) - supports HTTP & HTTPS
function uploadFilesRegular(files, isAESEnabled) {
  // Block QR generation during uploads to prevent UI blocking
  window._qrBlocked = true;

  const formData = new FormData();

  let parentPath = window.currentFolderPath || "";
  if (parentPath.startsWith("Home/")) parentPath = parentPath.substring(5);
  else if (parentPath === "Home") parentPath = "";
  if (parentPath) {
    formData.append('parent_path', parentPath);
  }

  //  PERFORMANCE: Calculate total size efficiently
  let totalSize = 0;
  for (let i = 0; i < files.length; i++) {
    const file = files[i];
    formData.append('files', file);
    totalSize += file.size;
  }

  const totalSizeMB = (totalSize / 1024 / 1024).toFixed(2);
  const isHTTPS = location.protocol === 'https:';
  const protocolMsg = isHTTPS ? "HTTPS" : "HTTP";

  //  Pass AES status to backend (using correct parameter name)
  if (isAESEnabled) {
    formData.append('encrypt', 'true');
    // Show enhanced AES operation progress
    updateToastContent(` AES-256 encryption enabled - Processing ${totalSizeMB} MB file(s) for secure upload...`);
    console.log(' Starting AES encryption for regular upload');
  }

  const xhr = new XMLHttpRequest();
  progressBar.style.display = 'block';
  progressBar.value = 0;

  // Smoothly update the existing toast instead of creating a new one
  updateToastContent(`⏳ Starting ${protocolMsg} upload...`);

  const startTime = new Date().getTime();
  let lastProgressUpdate = 0;
  const PROGRESS_UPDATE_INTERVAL = LANVAN_CONFIG.INTERVALS.PROGRESS_UPDATE; // Unified interval from config

  xhr.upload.onprogress = function (e) {
    if (e.lengthComputable) {
      const percent = (e.loaded / e.total) * 100;
      progressBar.value = percent;

      //  Anti-blink: Update toast much less frequently
      const now = Date.now();
      if (now - lastProgressUpdate >= PROGRESS_UPDATE_INTERVAL || percent >= 100) {
        const elapsed = (now - startTime) / 1000;
        const speed = e.loaded / 1024 / 1024 / elapsed;
        const uploadedMB = (e.loaded / 1024 / 1024).toFixed(1);

        //  Enhanced progress message for multiple files with AES status
        let progressMessage;
        if (files.length === 1) {
          const aesStatus = isAESEnabled ? " " : "";
          progressMessage = ` Uploading${aesStatus} ${percent.toFixed(1)}% (${uploadedMB}/${totalSizeMB} MB) @ ${speed.toFixed(2)} MB/s`;
        } else {
          const aesStatus = isAESEnabled ? " (AES Encrypted)" : "";
          progressMessage = ` Uploading ${files.length} files${aesStatus} • ${percent.toFixed(1)}% (${uploadedMB}/${totalSizeMB} MB) @ ${speed.toFixed(2)} MB/s`;
        }
        updateProgressToast(progressMessage);
      }
    }
  };

  xhr.onload = function () {
    const endTime = new Date().getTime();
    const totalElapsed = ((endTime - startTime) / 1000).toFixed(1);
    const avgSpeed = (totalSize / 1024 / 1024 / totalElapsed).toFixed(2);

    if (xhr.status === 200 || xhr.status === 302) {
      // Update performance metrics in LANVAN_STATE
      LANVAN_STATE.performance.totalUploaded += totalSize;
      const currentSession = (endTime - LANVAN_STATE.performance.sessionsStartTime) / 1000;
      LANVAN_STATE.performance.averageSpeed = LANVAN_STATE.performance.totalUploaded / (1024 * 1024) / currentSession;

      // Save upload stats to logs
      const uploadStats = {
        type: 'Direct Upload',
        filename: files.length > 1 ? `${files.length} files` : files[0].name,
        size: totalSizeMB + ' MB',
        time: totalElapsed + 's',
        speed: avgSpeed + ' MB/s',
        method: 'Direct Upload (No Chunks)',
        chunks_used: 0, // No chunks for direct upload
        encrypted: isAESEnabled,
        protocol: protocolMsg,
        files_count: files.length,
        timestamp: new Date().toLocaleString('en-US', { hour: 'numeric', minute: 'numeric', second: 'numeric', hour12: true }),
        startTime: new Date(startTime).toLocaleString('en-US', { hour: 'numeric', minute: 'numeric', second: 'numeric', hour12: true }),
        endTime: new Date(endTime).toLocaleString('en-US', { hour: 'numeric', minute: 'numeric', second: 'numeric', hour12: true })
      };
      saveStatsToLog(uploadStats);

      //  Store file metadata for better download experience
      storeFileMetadata(files, totalSize);

      //  Enhanced completion message for multiple files
      if (files.length === 1) {
        showToast(` Upload complete via ${protocolMsg} (${totalSizeMB} MB) • ${totalElapsed}s @ ${avgSpeed} MB/s`, 0, uploadStats);
      } else {
        showToast(` ${files.length} files uploaded via ${protocolMsg} (${totalSizeMB} MB total) • ${totalElapsed}s @ ${avgSpeed} MB/s`, 0, uploadStats);
      }

      //  Delay file list refresh to show completion status
      setTimeout(() => {
        refreshFileList();
      }, 3000); // 3 second delay to let user see completion

      // Store flag to reload page when toast is dismissed (optional)
      window._shouldReloadAfterToast = false; // Changed to false since we auto-refresh

      // Unblock QR generation after successful upload
      window._qrBlocked = false;

      // End upload tracking
      endUpload();
    } else {
      showToast(' Upload failed • Click anywhere to dismiss', 0);
      // Unblock QR generation after failed upload
      window._qrBlocked = false;
      endUpload(); // End upload tracking on failure
    }
  };

  xhr.onerror = function () {
    showToast(' Upload error • Click anywhere to dismiss', 0);
    endUpload(); // End upload tracking on error
  };

  xhr.open('POST', '/upload');
  xhr.send(formData);
}

// Device Capability Detector extracted to features/device/device-capability-detector.js

//  Toast Notification System - Complete implementation
let toastTimeout = null;
let lastToastMessage = '';
let isPersistentToast = false;

// Toast Notification System extracted to features/ui/toast-notification-service.js
function showToast(message, duration, transferData, type) {
  if (window.ToastNotificationService) {
    window.ToastNotificationService.showToast(message, duration, transferData, type);
  }
}

function updateToastContent(message) {
  if (window.ToastNotificationService) {
    window.ToastNotificationService.updateToastContent(message);
  }
}

function updateProgressToast(message) {
  if (window.ToastNotificationService) {
    window.ToastNotificationService.updateProgressToast(message);
  }
}

function hideToast() {
  if (window.ToastNotificationService) {
    window.ToastNotificationService.hideToast();
  }
}

//  File Metadata Storage
function storeFileMetadata(files, totalSize) {
  try {
    const metadata = JSON.parse(localStorage.getItem('fileMetadata') || '{}');
    const timestamp = Date.now();

    //  PERFORMANCE: Efficient iteration without Array.from
    for (let i = 0; i < files.length; i++) {
      const file = files[i];
      metadata[file.name] = {
        size: file.size,
        timestamp: timestamp,
        lastModified: file.lastModified,
        type: file.type || 'unknown'
      };
    }

    localStorage.setItem('fileMetadata', JSON.stringify(metadata));
    console.log(` Stored metadata for ${files.length} files`);
  } catch (e) {
    console.log(' Failed to store file metadata:', e);
  }
}

//  Transfer Statistics Logging - Device-Specific Session Storage
function saveStatsToLog(stats) {
  try {
    // Save to device-specific session storage (clears when session ends)
    saveToDeviceUploadHistory(stats);

    // Also maintain backward compatibility with localStorage for global stats (optional)
    const logs = JSON.parse(localStorage.getItem('transferLogs') || '[]');
    logs.unshift(stats); // Add to beginning

    // Keep only last 50 logs in global storage
    if (logs.length > 50) {
      logs.splice(50);
    }

    localStorage.setItem('transferLogs', JSON.stringify(logs));
    console.log(` Saved transfer stats to device session:`, stats.type, stats.size, stats.time);
  } catch (e) {
    console.log(' Failed to save transfer stats:', e);
  }
}

//  Download Options Management
function showDownloadOptions(event) {
  event.preventDefault();

  const modal = document.createElement('div');
  modal.style.cssText = `
    position: fixed;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    background: rgba(0,0,0,0.5);
    display: flex;
    justify-content: center;
    align-items: center;
    z-index: 10000;
  `;

  const dialog = document.createElement('div');
  dialog.style.cssText = `
    background: var(--section-bg);
    color: var(--text-color);
    border: 1px solid var(--border-color);
    border-radius: 15px;
    padding: 2rem;
    max-width: 500px;
    margin: 1rem;
    box-shadow: 0 10px 30px rgba(0,0,0,0.3);
    text-align: center;
  `;

  dialog.innerHTML = `
    <h3 style="margin-top: 0; color: var(--text-color);">Choose Download Method</h3>
    <p style="color: var(--text-color); opacity: 0.7; margin-bottom: 2rem;">How would you like to download all files?</p>
    
    <div style="display: flex; gap: 1rem; justify-content: center; flex-wrap: wrap;">
      <button onclick="downloadAsZip()" style="
        background: #4a90e2;
        color: white;
        border: none;
        padding: 1rem 1.5rem;
        border-radius: 8px;
        cursor: pointer;
        font-size: 1rem;
        min-width: 180px;
      ">
         Download as ZIP
        <br><small style="opacity: 0.8;">Single compressed file</small>
      </button>
      
      <button onclick="downloadIndividually()" style="
        background: #27ae60;
        color: white;
        border: none;
        padding: 1rem 1.5rem;
        border-radius: 8px;
        cursor: pointer;
        font-size: 1rem;
        min-width: 180px;
      ">
         Download Separately
        <br><small style="opacity: 0.8;">Individual files</small>
      </button>
    </div>
    
    <button onclick="closeDownloadModal()" style="
      background: #e74c3c;
      color: white;
      border: none;
      padding: 0.5rem 1rem;
      border-radius: 5px;
      cursor: pointer;
      margin-top: 1.5rem;
      font-size: 0.9rem;
    ">
      Cancel
    </button>
  `;

  modal.appendChild(dialog);
  document.body.appendChild(modal);

  // Store modal reference for cleanup
  window.currentDownloadModal = modal;

  // Close on background click
  modal.addEventListener('click', (e) => {
    if (e.target === modal) {
      closeDownloadModal();
    }
  });

  // Close on Escape key
  document.addEventListener('keydown', function escapeHandler(e) {
    if (e.key === 'Escape') {
      closeDownloadModal();
      document.removeEventListener('keydown', escapeHandler);
    }
  });
}

function downloadAsZip() {
  closeDownloadModal();
  showToast(' Preparing ZIP download...', 3000);

  // Navigate to the ZIP download
  window.location.href = '/download-all';
}

async function downloadIndividually() {
  closeDownloadModal();

  try {
    // Get list of files from the current page
    const fileCards = document.querySelectorAll('.file-card .file-name');
    const fileNames = Array.from(fileCards).map(card => card.textContent.trim());

    if (fileNames.length === 0) {
      showToast(' No files found to download', 3000);
      return;
    }

    showToast(` Starting intelligent sequential download of ${fileNames.length} files (waits for each download to complete)...`, 0);

    let downloadCount = 0;
    let failedDownloads = [];

    // Smart download completion detection function
    async function waitForDownloadCompletion(fileName, timeoutMs = 15000) {
      return new Promise((resolve) => {
        const startTime = Date.now();
        let resolved = false;
        let visibilityHandler, blurHandler, focusHandler;

        const cleanup = () => {
          if (visibilityHandler) document.removeEventListener('visibilitychange', visibilityHandler);
          if (blurHandler) window.removeEventListener('blur', blurHandler);
          if (focusHandler) window.removeEventListener('focus', focusHandler);
        };

        const resolveOnce = (method) => {
          if (!resolved) {
            resolved = true;
            cleanup();
            resolve(method);
          }
        };

        // Method 1: Immediate visibility change detection (Chrome/Edge)
        if (navigator.userAgent.includes('Chrome') || navigator.userAgent.includes('Edge')) {
          visibilityHandler = () => {
            if (!resolved && Date.now() - startTime > 300) { // Reduced from 1000ms to 300ms
              resolveOnce('visibility-change');
            }
          };
          document.addEventListener('visibilitychange', visibilityHandler);
        }

        // Method 2: Fast focus/blur detection (works on most browsers)
        let focusLost = false;
        blurHandler = () => {
          focusLost = true;
        };
        focusHandler = () => {
          if (focusLost && !resolved && Date.now() - startTime > 200) { // Reduced from 1000ms to 200ms
            resolveOnce('focus-detection');
          }
        };
        window.addEventListener('blur', blurHandler);
        window.addEventListener('focus', focusHandler);

        // Method 3: Ultra-fast adaptive timeout based on actual download behavior
        const adaptiveTimeout = Math.max(800, Math.min(3000, fileNames.length * 400)); // 0.8-3 seconds (was 2-10 seconds)

        setTimeout(() => {
          resolveOnce('adaptive-timeout');
        }, adaptiveTimeout);

        // Method 4: Quick fallback timeout (reduced from 30s to 15s)
        setTimeout(() => {
          resolveOnce('fallback-timeout');
        }, timeoutMs);

        // Method 5: NEW - Network idle detection for very fast completion
        let networkRequests = 0;
        let originalFetch = null;

        if (!window._fetchIntercepted) {
          originalFetch = window.fetch;
          window.fetch = function (...args) {
            networkRequests++;
            return originalFetch.apply(this, args).finally(() => {
              networkRequests--;
              if (networkRequests === 0 && Date.now() - startTime > 100) {
                setTimeout(() => {
                  if (networkRequests === 0 && !resolved && Date.now() - startTime > 500) {
                    resolveOnce('network-idle');
                  }
                }, 200);
              }
            });
          };
          window._fetchIntercepted = true;
        }

        // Restore original fetch when done
        setTimeout(() => {
          if (originalFetch && window._fetchIntercepted) {
            window.fetch = originalFetch;
            window._fetchIntercepted = false;
          }
        }, timeoutMs + 1000);
      });
    }

    // Download each file and wait for completion
    for (let i = 0; i < fileNames.length; i++) {
      try {
        const fileName = fileNames[i];
        updateToastContent(` Downloading ${fileName}... (${downloadCount + 1}/${fileNames.length})`);

        // Create and trigger download
        const link = document.createElement('a');
        link.href = `/download/${encodeURIComponent(fileName)}`;
        link.download = fileName;
        link.style.display = 'none';
        document.body.appendChild(link);

        const downloadStartTime = Date.now();
        link.click();
        document.body.removeChild(link);

        // Wait for download completion with intelligent detection
        updateToastContent(` ${fileName} downloading... waiting for completion (${downloadCount + 1}/${fileNames.length})`);

        const completionMethod = await waitForDownloadCompletion(fileName);
        const downloadTime = ((Date.now() - downloadStartTime) / 1000).toFixed(1);

        downloadCount++;

        console.log(` Download ${downloadCount}: ${fileName} completed via ${completionMethod} in ${downloadTime}s`);
        updateToastContent(` ${fileName} completed (${downloadCount}/${fileNames.length}) • ${downloadTime}s`);

        // Minimal pause between downloads for browser stability (reduced from 500ms to 200ms)
        if (i < fileNames.length - 1) { // Don't wait after the last file
          await new Promise(resolve => setTimeout(resolve, 200));
        }

      } catch (error) {
        console.error(`Failed to download ${fileNames[i]}:`, error);
        failedDownloads.push(fileNames[i]);
      }
    }

    // Final status with timing information
    if (failedDownloads.length === 0) {
      showToast(` Successfully downloaded all ${downloadCount} files with intelligent completion detection!`, 5000);
    } else {
      showToast(` Downloaded ${downloadCount} files. Failed: ${failedDownloads.length} (${failedDownloads.join(', ')})`, 8000);
    }

  } catch (error) {
    console.error('Individual download error:', error);
    showToast(' Error during individual downloads', 5000);
  }
}

function closeDownloadModal() {
  const modal = window.currentDownloadModal;
  if (modal) {
    modal.remove();
    window.currentDownloadModal = null;
  }
}

// Make functions globally available
window.downloadAsZip = downloadAsZip;
window.downloadIndividually = downloadIndividually;
window.closeDownloadModal = closeDownloadModal;
window.generateQRCode = generateQRCode;

//  Enhanced QR Code Generation for Connection Info - Offline-First
function generateQRCode(text, size = 200) {
  // Use larger QR for better visibility, but still optimized for guests
  const isGuest = typeof detectGuestDevice === 'function' && detectGuestDevice();
  const qrSize = isGuest ? 180 : size;

  // Primary: Use our offline QR generator (works without internet)
  const offlineQR = `/api/qr-code?text=${encodeURIComponent(text)}&size=${qrSize}`;

  // Fallback services (strictly local offline endpoints)
  const fallbackServices = [
    `/api/qr-code?text=${encodeURIComponent(text)}&size=${qrSize}`,
  ];

  return {
    primary: offlineQR,
    fallbacks: fallbackServices,
    // For backward compatibility, return the offline URL directly
    toString: () => offlineQR
  };
}

//  Preload QR code image as soon as the page loads for instant display
document.addEventListener('DOMContentLoaded', function () {
  // Get the URL to encode (same as used in showConnectionInfo)
  let protocol = location.protocol;
  let hostname = location.hostname;
  let port = location.port;
  if (hostname === 'localhost' || hostname === '127.0.0.1') {
    // Try to get network info including mDNS from server (async, fallback to hostname)
    fetch('/api/network-info').then(response => response.json()).then(networkInfo => {
      let useHostname = hostname;

      // Prefer mDNS if available, otherwise use LAN IP
      if (networkInfo.mdns && networkInfo.mdns.status === 'active' && networkInfo.mdns.url) {
        // Use the actual mDNS URL for mDNS QR preloading
        preloadQRFromUrl(networkInfo.mdns.url);
      } else if (networkInfo.lan_ip && networkInfo.lan_ip !== '127.0.0.1') {
        useHostname = networkInfo.lan_ip;
        preloadQR(protocol, useHostname, port);
      } else {
        preloadQR(protocol, hostname, port);
      }
    }).catch(() => {
      preloadQR(protocol, hostname, port);
    });
  } else {
    preloadQR(protocol, hostname, port);
  }

  // Start real-time mDNS monitoring for instant updates and toast notifications
  updateMDNSStatus();
  setInterval(updateMDNSStatus, 2000);

  function preloadQRFromUrl(fullUrl) {
    const isGuest = typeof detectGuestDevice === 'function' && detectGuestDevice();
    const qrSize = isGuest ? 180 : 200;
    const qrUrl = `/api/qr-code?text=${encodeURIComponent(fullUrl)}&size=${qrSize}`;

    // Test if QR API is available with a timeout
    const testImg = new window.Image();
    const timeout = setTimeout(() => {
      console.log('QR API is slow/unavailable, will use offline generation');
      window._qrApiUnavailable = true;
    }, 5000); // 5 second timeout

    testImg.onload = () => {
      clearTimeout(timeout);
      window._preloadedQR = {
        url: qrUrl,
        img: testImg,
        timestamp: Date.now()
      };
      console.log('QR API is working, QR preloaded successfully');
    };

    testImg.onerror = () => {
      clearTimeout(timeout);
      console.log('QR API failed, will use offline generation');
      window._qrApiUnavailable = true;
    };

    testImg.src = qrUrl;
  }

  function preloadQR(protocol, hostname, port) {
    let fullUrl = `${protocol}//${hostname}`;
    if (port && port !== '80' && port !== '443') {
      fullUrl += `:${port}`;
    }
    const isGuest = typeof detectGuestDevice === 'function' && detectGuestDevice();
    const qrSize = isGuest ? 180 : 200;
    const qrUrl = `/api/qr-code?text=${encodeURIComponent(fullUrl)}&size=${qrSize}`;

    // Test if QR API is available with a timeout
    const testImg = new window.Image();
    const timeout = setTimeout(() => {
      console.log('QR API is slow/unavailable, will use offline generation');
      window._qrApiUnavailable = true;
    }, 5000); // 5 second timeout

    testImg.onload = () => {
      clearTimeout(timeout);
      window._preloadedQR = {
        url: qrUrl,
        img: testImg,
        timestamp: Date.now()
      };
      console.log('QR API is working, QR preloaded successfully');
    };

    testImg.onerror = () => {
      clearTimeout(timeout);
      console.log('QR API failed, will use offline generation');
      window._qrApiUnavailable = true;
    };

    testImg.src = qrUrl;
  }
});

//  Enhanced offline QR code generator (backup method)
//  Enhanced LAN IP and show connection info modal with mDNS support
async function showConnectionInfo() {
  // Get current URL info but FORCE LAN IP or mDNS instead of localhost
  const protocol = location.protocol;
  let hostname = location.hostname;
  const port = location.port;
  let useMDNS = false;
  let mdnsUrl = null;
  let networkInfo = null;
  let lanIpUrl = null;

  //  ALWAYS fetch network info to check for mDNS availability
  try {
    const response = await fetch('/api/network-info');
    if (response.ok) {
      networkInfo = await response.json();
      console.log(' Network info received:', networkInfo);

      // Use backend-provided LAN IP URL for consistency
      if (networkInfo.lan_ip_url) {
        lanIpUrl = networkInfo.lan_ip_url;
      }

      // Prefer mDNS if available
      if (networkInfo.mdns && networkInfo.mdns.status === 'active' && networkInfo.mdns.domain) {
        hostname = networkInfo.mdns.domain;
        useMDNS = true;
        mdnsUrl = networkInfo.mdns.url || networkInfo.hybrid_url;
        console.log(' mDNS detected:', networkInfo.mdns.domain, 'URL:', mdnsUrl);
      } else {
        // Use current hostname if mDNS not available
        if (hostname === 'localhost' || hostname === '127.0.0.1') {
          // Fallback to LAN IP for localhost access
          if (networkInfo.lan_ip && networkInfo.lan_ip !== '127.0.0.1') {
            hostname = networkInfo.lan_ip;
          }
        }
        console.log(' mDNS not available, using hostname:', hostname);
      }
    } else {
      console.log(' Failed to fetch network info:', response.status);
    }
  } catch (error) {
    console.log(' Network info fetch error:', error);
  }

  const isHTTPS = protocol === 'https:';

  // Construct URL with proper hostname (mDNS or LAN IP)
  let fullUrl;
  if (useMDNS && mdnsUrl) {
    fullUrl = mdnsUrl;
  } else {
    fullUrl = `${protocol}//${hostname}`;
    if (port && port !== '80' && port !== '443') {
      fullUrl += `:${port}`;
    }
  }

  // Store network info globally for copy functions
  window._currentNetworkInfo = { networkInfo, lanIpUrl, useMDNS, fullUrl };

  // Debug logging
  console.log(' Connection Info Debug:', {
    useMDNS: useMDNS,
    fullUrl: fullUrl,
    mdnsUrl: mdnsUrl,
    lanIpUrl: lanIpUrl,
    networkInfo: networkInfo
  });

  // Create modal with immediate QR loading
  const modal = document.createElement('div');
  modal.style.cssText = `
    position: fixed;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    background: rgba(0,0,0,0.7);
    z-index: 10000;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 1rem;
    box-sizing: border-box;
  `;

  const dialog = document.createElement('div');
  dialog.style.cssText = `
    background: white;
    border-radius: 15px;
    width: 90%;
    max-width: 500px;
    max-height: 90vh;
    overflow-y: auto;
    box-shadow: 0 10px 30px rgba(0,0,0,0.3);
    margin: 0 auto;
    padding: 2rem;
  `;

  //  ENHANCED: Offline-first QR generation for reliability
  const isGuest = typeof detectGuestDevice === 'function' && detectGuestDevice();
  const qrSize = isGuest ? 180 : 200;

  // Use our offline QR generator as primary
  const qrResult = generateQRCode(fullUrl, qrSize);
  const primaryQRUrl = qrResult.primary || qrResult.toString();
  const fallbackQRUrls = qrResult.fallbacks || [
    `/api/qr-code?text=${encodeURIComponent(fullUrl)}&size=${qrSize}`,
  ];

  // If preloaded QR matches, use it instantly, otherwise use offline generator
  setTimeout(() => {
    const primaryQR = document.getElementById('qr-primary');
    if (primaryQR) {
      // Check if QR API was determined to be unavailable during preload
      if (window._qrApiUnavailable) {
        console.log('QR API unavailable, using offline generation immediately');
        // Use requestIdleCallback to prevent blocking during uploads
        if (window.requestIdleCallback) {
          requestIdleCallback(() => showOfflineQR());
        } else {
          setTimeout(showOfflineQR, 100);
        }
        return;
      }

      if (window._preloadedQR && window._preloadedQR.url === primaryQRUrl) {
        primaryQR.src = window._preloadedQR.img.src;
      } else {
        primaryQR.src = primaryQRUrl; // This will use our offline generator
      }

      // Aggressive fallback - if QR doesn't load quickly, try offline immediately
      setTimeout(() => {
        if (primaryQR.style.display === 'none') {
          console.log('QR API not responding quickly, trying offline generator immediately...');
          // Use async to prevent blocking uploads
          if (window.requestIdleCallback) {
            requestIdleCallback(() => showOfflineQR());
          } else {
            setTimeout(showOfflineQR, 50);
          }
        }
      }, 5000); // Friendly fallback for slower Termux environments (5 seconds)

      // Second fallback - try external service
      setTimeout(() => {
        if (primaryQR.style.display === 'none') {
          console.log('Primary QR failed, trying external fallback...');
          const fallbackQR = document.getElementById('qr-fallback');
          if (fallbackQR && fallbackQRUrls.length > 0) {
            fallbackQR.src = fallbackQRUrls[0];
            // Final fallback to offline if external also fails
            setTimeout(() => {
              if (fallbackQR.style.display === 'none') {
                console.log('All external QR services failed, forcing offline...');
                if (window.requestIdleCallback) {
                  requestIdleCallback(() => showOfflineQR());
                } else {
                  setTimeout(showOfflineQR, 50);
                }
              }
            }, 3000);
          }
        }
      }, 8000); // Try external after 8 seconds if local still hasn't loaded
    }
  }, 10);

  const lanInstructions = (location.hostname === 'localhost' || location.hostname === '127.0.0.1') && hostname === location.hostname ? `
    <div style="background: #fff3cd; border: 1px solid #ffeaa7; padding: 1rem; border-radius: 8px; margin: 1rem 0;">
      <h4 style="margin: 0 0 0.5rem 0; color: #856404;"> To share on LAN:</h4>
      <p style="margin: 0; font-size: 0.9rem; color: #856404;">
        • Replace "localhost" with your computer's IP address<br>
        • Windows: Run <code>ipconfig</code> and look for IPv4<br>
        • Linux/Mac: Run <code>ip addr</code> or <code>ifconfig</code><br>
        • Android Termux: Run <code>ip route | grep default</code>
      </p>
    </div>
  ` : '';

  dialog.innerHTML = `
    <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 1rem;">
      <h3 style="margin: 0; color: #333; display: flex; align-items: center; gap: 0.5rem;">
        <span>${isHTTPS ? '' : ''}</span>
        Connection Info
      </h3>
      <button onclick="closeConnectionModal()" style="background: #e74c3c; color: white; border: none; padding: 0.5rem 1rem; border-radius: 6px; cursor: pointer; font-size: 0.9rem;"> Close</button>
    </div>
    
    <div style="margin: 1.5rem 0;">
      <!-- QR Code Container with Immediate Loading -->
      <div id="qr-container" style="text-align: center; min-height: 220px; position: relative;">
        <!-- Primary QR Code -->
     <img id="qr-primary" 
       style="display: none; border: 2px solid #e1e1e1; border-radius: 10px; max-width: 180px; height: auto; margin: 0 auto;"
       onload="showQRSuccess(this, 'primary')"
       onerror="showOfflineQR()">
     <!-- Fallback QR Code (skip for guest devices, use offline QR instantly) -->
     <img id="qr-fallback" 
       style="display: none; border: 2px solid #e1e1e1; border-radius: 10px; max-width: 180px; height: auto; margin: 0 auto;"
       onload="showQRSuccess(this, 'fallback')"
       onerror="showOfflineQR()">
        
        <!-- Loading Animation -->
        <div id="qr-loading" style="position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%);">
          <div style="width: 40px; height: 40px; border: 4px solid var(--border-color); border-top: 4px solid #007bff; border-radius: 50%; animation: qr-spin 1s linear infinite; margin-bottom: 1rem;"></div>
          <p style="margin: 0; color: var(--text-color); opacity: 0.8; font-size: 0.9rem;"> Generating QR Code...</p>
        </div>
        
        <!-- Offline QR Fallback -->
        <canvas id="offline-qr" style="display: none; border: 2px solid #e1e1e1; border-radius: 10px; margin: 0 auto;"></canvas>
        <p id="offline-qr-text" style="display: none; font-size: 0.8rem; color: var(--text-color); opacity: 0.8; margin-top: 0.5rem;"> Offline QR Code</p>
      </div>
    </div>
    
    <div style="background: var(--input-bg); border-radius: 10px; padding: 1rem; margin: 1rem 0; border: 1px solid var(--border-color);">
      ${useMDNS ? `
        <h4 style="margin: 0 0 0.5rem 0; color: var(--text-color);"> mDNS Connection URL:</h4>
        <div style="display: flex; gap: 0.5rem; align-items: center; flex-wrap: wrap; margin-bottom: 1rem;">
          <code id="connection-url" style="flex: 1; background: #d4edda; padding: 0.5rem; border-radius: 5px; border: 1px solid #c3e6cb; font-size: 0.85rem; word-break: break-all; min-width: 200px; color: #155724;">${fullUrl}</code>
          <button onclick="copyConnectionUrl()" style="background: #28a745; color: white; border: none; padding: 0.5rem 1rem; border-radius: 5px; cursor: pointer; font-size: 0.85rem; white-space: nowrap;" title="Copy mDNS URL to clipboard"> Copy</button>
        </div>
        <div style="padding: 0.6rem; background: #d4edda; border: 1px solid #c3e6cb; border-radius: 6px; margin-bottom: 0.8rem;">
          <small style="color: #155724; display: flex; align-items: center; gap: 0.3rem; font-size: 0.8rem;">
            <span></span>
            <strong>mDNS Active:</strong> Easy access via domain name - guests can use ${networkInfo?.mdns?.domain || 'lanvan.local'}!
          </small>
        </div>
        <h4 style="margin: 0 0 0.5rem 0; color: var(--text-color); opacity: 0.8; font-size: 0.9rem;"> Alternative IP Connection:</h4>
        <div style="display: flex; gap: 0.5rem; align-items: center; flex-wrap: wrap; margin-bottom: 0.8rem;">
          <code id="alternative-url" style="flex: 1; background: var(--section-bg); color: var(--text-color); padding: 0.4rem; border-radius: 5px; border: 1px solid var(--border-color); font-size: 0.8rem; word-break: break-all; min-width: 200px;">${lanIpUrl || 'http://192.168.x.x'}</code>
          <button onclick="copyAlternativeUrl()" style="background: var(--settings-bg); color: white; border: none; padding: 0.4rem 0.8rem; border-radius: 5px; cursor: pointer; font-size: 0.8rem; white-space: nowrap;" title="Copy IP URL to clipboard"> Copy</button>
        </div>
        
        <!-- IP QR Code Section -->
        <div style="text-align: center; margin: 1rem 0; padding: 1rem; background: var(--input-bg); border-radius: 8px; border: 1px solid var(--border-color);">
          <div style="margin-bottom: 0.5rem;">
            <small style="color: var(--text-color); opacity: 0.8; font-size: 0.8rem; font-weight: 500;"> IP Access QR Code</small>
          </div>
          <div style="display: flex; justify-content: center; align-items: center;">
            <img src="/api/qr-code?text=${encodeURIComponent(lanIpUrl || 'http://192.168.0.106')}&size=160" 
                 style="border: 2px solid var(--border-color); border-radius: 8px; max-width: 160px; height: auto; background: var(--section-bg); display: block;" 
                 alt="IP QR Code"
                 onerror="this.style.display='none'; this.parentElement.nextElementSibling.style.display='block';"
                 onload="this.style.display='block';">
          </div>
          <div style="display: none; padding: 0.5rem; background: var(--input-bg); border: 1px solid var(--border-color); border-radius: 5px; color: var(--text-color); opacity: 0.8; font-size: 0.8rem;">
            QR code generation failed
          </div>
          <div style="margin-top: 0.5rem;">
            <small style="color: var(--text-color); opacity: 0.7; font-size: 0.75rem;">Scan if mDNS doesn't work</small>
          </div>
        </div>
        <div style="margin-top: 0.5rem;">
          <small style="color: #666; font-size: 0.75rem;">
             <strong>For guests:</strong> Try mDNS first (${networkInfo?.mdns?.domain || 'lanvan.local'}), use IP if that fails
          </small>
        </div>
      ` : `
        <h4 style="margin: 0 0 0.5rem 0; color: var(--text-color);"> Connection URL:</h4>
        <div style="display: flex; gap: 0.5rem; align-items: center; flex-wrap: wrap;">
          <code id="connection-url" style="flex: 1; background: var(--input-bg); color: var(--text-color); padding: 0.5rem; border-radius: 5px; border: 1px solid var(--border-color); font-size: 0.85rem; word-break: break-all; min-width: 200px;">${fullUrl}</code>
          <button onclick="copyConnectionUrl()" style="background: #007bff; color: white; border: none; padding: 0.5rem 1rem; border-radius: 5px; cursor: pointer; font-size: 0.85rem; white-space: nowrap;" title="Copy URL to clipboard"> Copy</button>
        </div>
        <div style="margin-top: 0.8rem; padding: 0.6rem; background: var(--input-bg); border: 1px solid var(--border-color); border-radius: 6px;">
          <small style="color: var(--text-color); opacity: 0.8; display: flex; align-items: center; gap: 0.3rem; font-size: 0.8rem;">
            <span></span>
            <strong>Using IP Address:</strong> mDNS not available - guests must use IP to connect
          </small>
        </div>
      `}
    </div>
    
    ${lanInstructions}
  `;

  modal.appendChild(dialog);
  document.body.appendChild(modal);

  // Store modal reference
  window.currentConnectionModal = modal;

  //  IMMEDIATE QR Loading with Smart Fallback System
  setTimeout(() => {
    const primaryQR = document.getElementById('qr-primary');
    if (primaryQR) {
      primaryQR.src = primaryQRUrl;
      // For guest devices, if not loaded in 1s, show offline QR immediately
      if (isGuest) {
        setTimeout(() => {
          if (primaryQR.style.display === 'none') {
            showOfflineQR();
          }
        }, 1000);
      }
    }
  }, 10); // Even smaller delay for instant QR

  // Close on background click
  modal.addEventListener('click', (e) => {
    if (e.target === modal) {
      closeConnectionModal();
    }
  });

  // Close on Escape key
  document.addEventListener('keydown', function escapeHandler(e) {
    if (e.key === 'Escape') {
      closeConnectionModal();
      document.removeEventListener('keydown', escapeHandler);
    }
  });
}

// Network Info & QR Presentation Adapter extracted to features/network/network-info-modal-adapter.js

// Make functions globally available
window.refreshFileListManually = refreshFileListManually;
window.refreshFileList = refreshFileList;
window.toggleSettingsMenu = toggleSettingsMenu;
window.cancelAllUploads = cancelAllUploads;
window.clearAllFiles = clearAllFiles;
window.showDownloadOptions = showDownloadOptions;
window.showToast = showToast;
window.toggleDeviceLogs = toggleDeviceLogs;
window.showAccessControlSettings = showAccessControlSettings;
window.downloadAsZip = downloadAsZip;
window.cancelUpload = cancelUpload;
window.pauseUpload = pauseUpload;
window.resumeUpload = resumeUpload;
window.downloadDeviceLogs = downloadDeviceLogs;
window.clearDeviceLogs = clearDeviceLogs;
window.closeDeviceLogsModal = closeDeviceLogsModal;
window.removeCompletedUpload = removeCompletedUpload;
window.clearCompletedUploads = clearCompletedUploads;
window.showImagePreview = showImagePreview;
window.uploadClipboardItem = uploadClipboardItem;

// ===  CLIPBOARD SYSTEM FUNCTIONS ===

// Clipboard state management
// (Declared at top of file)

// Open clipboard modal
function openClipboardModal() {
  const modal = document.getElementById('clipboardModal');
  modal.style.display = 'flex';

  // Load clipboard history
  refreshClipboardHistory();

  // Set focus to text input
  setTimeout(() => {
    const textInput = document.getElementById('clipboardTextInput');
    if (textInput) textInput.focus();
  }, 100);

  // Close on escape key
  document.addEventListener('keydown', function escapeHandler(e) {
    if (e.key === 'Escape') {
      closeClipboardModal();
      document.removeEventListener('keydown', escapeHandler);
    }
  });

  // Close on background click
  modal.addEventListener('click', (e) => {
    if (e.target === modal) {
      closeClipboardModal();
    }
  });

  console.log(' Clipboard modal opened');
}

// Close clipboard modal
function closeClipboardModal() {
  const modal = document.getElementById('clipboardModal');
  modal.style.display = 'none';
}

// Handle paste events in the text area
function handleClipboardPaste(event) {
  console.log(' Paste event detected');

  // Get clipboard data
  const clipboardData = event.clipboardData || window.clipboardData;

  if (!clipboardData) {
    console.log(' No clipboard data available');
    return;
  }

  // Check for files/images first (including mobile)
  const files = clipboardData.files;
  if (files && files.length > 0) {
    console.log(' Files detected in clipboard:', files.length);
    event.preventDefault();

    // Handle each file
    Array.from(files).forEach(file => {
      if (file.type.startsWith('image/')) {
        console.log(' Image file detected:', file.type);
        handleImagePaste(file);
      } else {
        console.log(' Non-image file detected:', file.type);
        showToast(' File detected, but only images are supported', 3000);
      }
    });
    return;
  }

  // Check for image data in items
  const items = clipboardData.items;
  if (items) {
    for (let i = 0; i < items.length; i++) {
      const item = items[i];
      console.log(' Clipboard item type:', item.type);

      if (item.type.indexOf('image') !== -1) {
        // Handle image paste
        event.preventDefault();
        const blob = item.getAsFile();
        if (blob) {
          console.log(' Image blob detected from clipboard items');
          handleImagePaste(blob);
          return;
        }
      }
    }
  }

  // Check for text data
  const textData = clipboardData.getData('text/plain');
  if (textData) {
    console.log(' Text data detected, length:', textData.length);
    // Let the normal paste proceed for text
  }

  console.log(' Text paste detected - will be added when you click "Add Text"');
}

// Global document paste listener for Clipboard view (Industry Standard Event Propagation Marking)
document.addEventListener('paste', function (event) {
  if (event.defaultPrevented || event._handled) {
    return;
  }

  const activeEl = document.activeElement;
  const isClipInput = activeEl && (activeEl.id === 'clipboardInput' || activeEl.id === 'clipboardTextInput');
  const isClipView = window.activeTab === 'clipboard' || (document.getElementById('clipboardView') && document.getElementById('clipboardView').style.display !== 'none');

  if (isClipInput || isClipView) {
    const clipboardData = event.clipboardData || window.clipboardData;
    if (!clipboardData) return;

    let targetImage = null;

    // 1. Check files array
    if (clipboardData.files && clipboardData.files.length > 0) {
      for (let i = 0; i < clipboardData.files.length; i++) {
        if (clipboardData.files[i].type && clipboardData.files[i].type.startsWith('image/')) {
          targetImage = clipboardData.files[i];
          break;
        }
      }
    }

    // 2. Check items array if no file found yet
    if (!targetImage && clipboardData.items) {
      for (let i = 0; i < clipboardData.items.length; i++) {
        const item = clipboardData.items[i];
        if (item.type && item.type.startsWith('image/')) {
          const blob = item.getAsFile();
          if (blob) {
            targetImage = blob;
            break;
          }
        }
      }
    }

    if (targetImage) {
      event._handled = true;
      event.preventDefault();
      if (typeof event.stopImmediatePropagation === 'function') {
        event.stopImmediatePropagation();
      }
      handleImagePaste(targetImage);
    }
  }
}, true);

// Handle image paste from clipboard
function handleImagePaste(blob) {
  console.log(' Image pasted from clipboard, size:', blob.size);
  showToast(' Processing pasted image...', 2000);

  // Create file object
  const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
  const filename = `clipboard-image-${timestamp}.png`;

  // Add to clipboard via API
  const formData = new FormData();
  formData.append('file', blob, filename);

  fetch('/api/clipboard/add', {
    method: 'POST',
    body: formData
  })
    .then(response => response.json())
    .then(data => {
      if (data.status === 'success') {
        showToast(` Image added to clipboard: ${filename}`, 3000);
        refreshClipboardHistory();
      } else {
        showToast(` Failed to add image: ${data.msg}`, 4000);
      }
    })
    .catch(error => {
      console.error('Error adding image to clipboard:', error);
      showToast(' Failed to add image to clipboard', 4000);
    });
}

// Clipboard Controller extracted to features/clipboard/clipboard-controller.js


