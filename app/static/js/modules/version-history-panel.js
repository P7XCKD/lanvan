/**
 * Lanvan Version History Drawer Module (version-history-panel.js)
 * Provides a Google Drive / OneDrive style right-side slide-over drawer panel
 * for viewing file version timeline, downloading specific revisions, and restoring versions.
 * Supports both Light Mode and Dark Mode dynamically using Lanvan theme variables.
 */

(function (window) {
  'use strict';

  var currentLogicalFileId = null;
  var currentDisplayName = null;

  function createDrawerContainer() {
    var existing = document.getElementById('versionHistoryModal');
    if (existing) return existing;

    var drawer = document.createElement('div');
    drawer.id = 'versionHistoryModal';
    drawer.className = 'lanvan-version-drawer-backdrop';
    drawer.style.cssText = 'position:fixed; inset:0; background:rgba(0,0,0,0.35); backdrop-filter:blur(3px); z-index:99999; display:none; justify-content:flex-end; opacity:0; transition:opacity 0.22s cubic-bezier(0.16, 1, 0.3, 1); font-family:inherit;';

    drawer.innerHTML = `
      <div class="version-history-drawer-panel" style="background:var(--section-bg, #ffffff); color:var(--text-color, #1f2937); border-left:1px solid var(--border-color, rgba(0,0,0,0.12)); width:92%; max-width:430px; height:100%; display:flex; flex-direction:column; box-shadow:-10px 0 40px rgba(0,0,0,0.25); transform:translateX(100%); transition:transform 0.25s cubic-bezier(0.16, 1, 0.3, 1); overflow:hidden;">
        
        <!-- Header -->
        <div class="drawer-header" style="padding:20px 24px; border-bottom:1px solid var(--border-color, rgba(0,0,0,0.12)); display:flex; align-items:center; justify-content:space-between; background:var(--card-bg, #ffffff);">
          <div style="display:flex; align-items:center; gap:12px; overflow:hidden;">
            <div style="width:36px; height:36px; border-radius:10px; background:var(--primary-bg, rgba(37,99,235,0.1)); color:var(--primary, #2563eb); display:flex; align-items:center; justify-content:center; flex-shrink:0;">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><polyline points="12 6 12 12 16 14"></polyline></svg>
            </div>
            <div style="overflow:hidden;">
              <h3 id="vhModalTitle" style="margin:0; font-size:1.05rem; font-weight:700; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; color:var(--text-color, #1f2937);">Version History</h3>
              <div id="vhModalSub" style="font-size:0.8rem; color:var(--text-muted, #6b7280); margin-top:2px;">Version History Timeline</div>
            </div>
          </div>
          <button id="vhCloseBtn" style="background:none; border:none; color:var(--text-muted, #6b7280); cursor:pointer; padding:8px; border-radius:8px; display:flex; align-items:center; justify-content:center; transition:background 0.15s;" title="Close drawer">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>
          </button>
        </div>

        <!-- Body / Timeline -->
        <div id="vhTimeline" class="drawer-body" style="padding:24px; overflow-y:auto; flex:1; display:flex; flex-direction:column;">
          <!-- Version timeline entries rendered here -->
        </div>

      </div>
    `;

    document.body.appendChild(drawer);

    drawer.querySelector('#vhCloseBtn').addEventListener('click', closeVersionHistory);
    drawer.addEventListener('click', function (e) {
      if (e.target === drawer) closeVersionHistory();
    });

    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape' || e.keyCode === 27) {
        var modal = document.getElementById('versionHistoryModal');
        if (modal && modal.style.display !== 'none' && modal.style.opacity !== '0') {
          closeVersionHistory();
        }
      }
    });

    return drawer;
  }

  function openVersionHistory(logicalFileId, displayName) {
    if (!logicalFileId) return;
    currentLogicalFileId = logicalFileId;
    currentDisplayName = displayName || 'File';

    var drawer = createDrawerContainer();
    var panel = drawer.querySelector('.version-history-drawer-panel');
    var titleEl = drawer.querySelector('#vhModalTitle');
    var subEl = drawer.querySelector('#vhModalSub');
    var timelineEl = drawer.querySelector('#vhTimeline');

    if (titleEl) titleEl.textContent = currentDisplayName;
    if (subEl) subEl.textContent = 'Version History Timeline';
    if (timelineEl) timelineEl.innerHTML = '<div style="text-align:center; padding:40px 20px; color:var(--text-muted, #6b7280); font-size:0.9rem;">Fetching version history...</div>';

    drawer.style.display = 'flex';
    requestAnimationFrame(function () {
      drawer.style.opacity = '1';
      if (panel) panel.style.transform = 'translateX(0)';
    });

    // Fetch version history endpoint
    fetch('/api/files/' + encodeURIComponent(logicalFileId) + '/history')
      .then(function (r) { return r.json(); })
      .then(function (res) {
        if (res.status === 'success' && Array.isArray(res.versions)) {
          renderTimeline(res.versions);
        } else {
          timelineEl.innerHTML = '<div style="text-align:center; padding:40px 20px; color:#ef4444; font-size:0.9rem;">Failed to load version history.</div>';
        }
      })
      .catch(function (err) {
        timelineEl.innerHTML = '<div style="text-align:center; padding:40px 20px; color:#ef4444; font-size:0.9rem;">Error loading version history.</div>';
      });
  }

  function closeVersionHistory() {
    var drawer = document.getElementById('versionHistoryModal');
    if (!drawer) return;
    var panel = drawer.querySelector('.version-history-drawer-panel');
    if (panel) panel.style.transform = 'translateX(100%)';
    drawer.style.opacity = '0';
    setTimeout(function () {
      drawer.style.display = 'none';
    }, 250);
  }

  function formatBytes(bytes) {
    if (bytes === 0) return '0 B';
    var k = 1024;
    var sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
    var i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
  }

  function formatDate(isoStr) {
    if (!isoStr) return '--';
    if (typeof window.formatLastModified === 'function') {
      var res = window.formatLastModified(isoStr);
      return (res && res.display) ? res.display : String(res);
    }
    try {
      var d = new Date(isoStr);
      return d.toLocaleDateString() + ' ' + d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    } catch (e) {
      return isoStr;
    }
  }

  function renderTimeline(versions) {
    var timelineEl = document.getElementById('vhTimeline');
    if (!timelineEl) return;

    if (versions.length === 0) {
      timelineEl.innerHTML = '<div style="text-align:center; padding:40px 20px; color:var(--text-muted, #6b7280); font-size:0.9rem;">No version history available.</div>';
      return;
    }

    var html = '<div class="timeline-container" style="position:relative; padding-left:24px; display:flex; flex-direction:column; gap:20px;">';
    
    // Vertical timeline connector line
    html += '<div style="position:absolute; left:7px; top:12px; bottom:12px; width:2px; background:var(--border-color, rgba(0,0,0,0.12));"></div>';

    for (var i = 0; i < versions.length; i++) {
      var v = versions[i];
      var isLatest = v.isLatest || (i === 0);
      var versionNum = v.versionNumber || (versions.length - i);
      var changeType = v.changeType || 'uploaded';
      var restoredFrom = v.restoredFromVersion;

      var badgeText = isLatest ? 'Current (v' + versionNum + ')' : 'Version ' + versionNum;
      var badgeStyle = isLatest
        ? 'background:var(--primary-bg, rgba(37,99,235,0.15)); color:var(--primary, #2563eb); border:1px solid var(--primary-border, rgba(37,99,235,0.3));'
        : 'background:var(--card-bg, #f3f4f6); color:var(--text-muted, #6b7280); border:1px solid var(--border-color, rgba(0,0,0,0.12));';

      var dotStyle = isLatest
        ? 'background:var(--primary, #2563eb); border-color:var(--primary, #2563eb); color:#ffffff;'
        : 'background:var(--section-bg, #ffffff); border-color:var(--text-muted, #6b7280); color:transparent;';

      var dateObj = formatDate(v.uploadedAt);
      var sizeText = formatBytes(v.size || 0);
      if (changeType === 'restored' && restoredFrom) {
        sizeText += ' • Restored from v' + restoredFrom;
      }

      html += `
        <div class="timeline-item" style="position:relative;">
          
          <!-- Timeline Dot -->
          <div style="position:absolute; left:-24px; top:4px; width:16px; height:16px; border-radius:50%; border:2px solid; ${dotStyle} display:flex; align-items:center; justify-content:center; z-index:2;">
            ${isLatest ? '<svg width="9" height="9" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"></polyline></svg>' : ''}
          </div>

          <!-- Timeline Card -->
          <div class="timeline-card" style="background:var(--card-bg, #ffffff); border:1px solid var(--border-color, rgba(0,0,0,0.12)); border-radius:12px; padding:16px; box-shadow:0 2px 8px var(--shadow-color, rgba(0,0,0,0.06));">
            
            <div style="display:flex; align-items:center; justify-content:space-between; margin-bottom:10px;">
              <span style="font-size:0.72rem; font-weight:700; padding:3px 10px; border-radius:20px; ${badgeStyle}">${badgeText}</span>
              <span style="font-size:0.8rem; color:var(--text-muted, #6b7280); font-weight:500;">${dateObj}</span>
            </div>

            <div style="font-size:0.82rem; color:var(--text-muted, #6b7280); margin-bottom:14px;">Size: ${sizeText}</div>

            <div style="display:flex; gap:8px;">
              <a class="btn-icon-text" href="/api/files/${encodeURIComponent(currentLogicalFileId)}/download?versionId=${encodeURIComponent(v.id)}" target="_blank" download style="flex:1; padding:8px 12px; background:var(--primary-bg, rgba(37,99,235,0.08)); color:var(--primary, #2563eb); border:1px solid var(--primary-border, rgba(37,99,235,0.2)); border-radius:8px; text-decoration:none; font-size:0.82rem; font-weight:600; display:inline-flex; align-items:center; justify-content:center; gap:6px; transition:all 0.15s;" title="Download version binary">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path><polyline points="7 10 12 15 17 10"></polyline><line x1="12" y1="15" x2="12" y2="3"></line></svg>
                Download
              </a>
              ${!isLatest ? `
                <button class="btn-restore-version" data-version-id="${v.id}" data-version-num="${versionNum}" style="flex:1; padding:8px 12px; background:var(--primary, #2563eb); color:#ffffff; border:none; border-radius:8px; cursor:pointer; font-size:0.82rem; font-weight:600; display:inline-flex; align-items:center; justify-content:center; gap:6px; transition:opacity 0.15s; box-shadow:0 2px 6px rgba(37,99,235,0.25);" title="Restore this version">
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="1 4 1 10 7 10"></polyline><path d="M3.51 15a9 9 0 1 0 2.13-9.36L1 10"></path></svg>
                  Restore
                </button>
              ` : ''}
            </div>

          </div>

        </div>
      `;
    }

    html += '</div>';
    timelineEl.innerHTML = html;

    // Attach click listeners to restore buttons
    var restoreBtns = timelineEl.querySelectorAll('.btn-restore-version');
    restoreBtns.forEach(function (btn) {
      btn.addEventListener('click', function () {
        var vId = btn.getAttribute('data-version-id');
        var vNum = btn.getAttribute('data-version-num');
        handleRestoreVersion(vId, vNum);
      });
    });
  }

  function handleRestoreVersion(versionId, versionNum) {
    if (!currentLogicalFileId || !versionId) return;

    fetch('/api/files/' + encodeURIComponent(currentLogicalFileId) + '/restore', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ versionId: versionId })
    })
      .then(function (r) { return r.json(); })
      .then(function (res) {
        if (res.status === 'success') {
          if (typeof window.showToast === 'function') {
            window.showToast(res.message || ('Restored Version ' + versionNum));
          }
          openVersionHistory(currentLogicalFileId, currentDisplayName);
          if (window.LanvanStore && typeof window.LanvanStore.dispatch === 'function') {
            window.LanvanStore.dispatch('REFRESH_FILES');
          }
          if (typeof window.refreshFileList === 'function') {
            window.refreshFileList();
          }
        } else {
          if (typeof window.showToast === 'function') {
            window.showToast('Failed to restore version: ' + (res.message || 'Error'));
          }
        }
      })
      .catch(function (err) {
        if (typeof window.showToast === 'function') {
          window.showToast('Error restoring version');
        }
      });
  }

  // Export module API
  window.LanvanVersionHistoryPanel = {
    open: openVersionHistory,
    close: closeVersionHistory
  };

})(typeof window !== 'undefined' ? window : this);
