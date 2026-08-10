/**
 * @file device-logs-modal-adapter.js
 * @description Device session activity logs UI modal adapter & sessionStorage log history controller.
 *              Provides session-specific upload log stats, device ID management, plain-text export, and log clearing.
 * @module DeviceLogsModalAdapter
 */

(function (window) {
  'use strict';

  function getCurrentDeviceId() {
    let deviceId = sessionStorage.getItem('Lanvan_device_id');
    if (!deviceId) {
      const deviceInfo = getDeviceInfo();
      const timestamp = Date.now();
      const randomId = Math.random().toString(36).substring(2, 8);
      deviceId = `${deviceInfo.name}_${timestamp}_${randomId}`;
      sessionStorage.setItem('Lanvan_device_id', deviceId);
      console.log(` New device session created: ${deviceInfo.displayName}`);
    }
    return deviceId;
  }

  function getDeviceInfo() {
    let deviceName = 'Unknown_Device';
    let displayName = 'Unknown Device';

    try {
      if (typeof window.clientInformation !== 'undefined' && window.clientInformation.platform) {
        const platform = window.clientInformation.platform;
        deviceName = platform.replace(/\s+/g, '_');
      }

      const userAgent = navigator.userAgent;
      const browserInfo = typeof window.getBrowserInfo === 'function' 
        ? window.getBrowserInfo(userAgent) 
        : { name: 'Browser' };

      if (userAgent.includes('Windows')) {
        if (userAgent.includes('Windows NT 10')) deviceName = 'Windows_PC';
        else if (userAgent.includes('Windows NT 6')) deviceName = 'Windows_Legacy';
        displayName = deviceName.replace('_', ' ');
      } else if (userAgent.includes('Mac')) {
        if (userAgent.includes('iPhone')) {
          deviceName = 'iPhone';
          displayName = 'iPhone';
        } else if (userAgent.includes('iPad')) {
          deviceName = 'iPad';
          displayName = 'iPad';
        } else {
          deviceName = 'Mac';
          displayName = 'Mac';
        }
      } else if (userAgent.includes('Android')) {
        deviceName = 'Android_Device';
        displayName = 'Android Device';
      } else if (userAgent.includes('Linux')) {
        deviceName = 'Linux_PC';
        displayName = 'Linux PC';
      }

      deviceName = `${deviceName}_${browserInfo.name}`;
      displayName = `${displayName} (${browserInfo.name})`;
    } catch (error) {
      console.log('Could not detect device info, using fallback');
      deviceName = 'Unknown_Device';
      displayName = 'Unknown Device';
    }

    return {
      name: deviceName,
      displayName: displayName
    };
  }

  function getDeviceUploadHistory() {
    try {
      const deviceId = getCurrentDeviceId();
      const sessionKey = `uploadHistory_${deviceId}`;
      const deviceHistory = JSON.parse(sessionStorage.getItem(sessionKey) || '[]');
      return deviceHistory.sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp));
    } catch (e) {
      console.log(' Failed to load device upload history:', e);
      return [];
    }
  }

  function saveToDeviceUploadHistory(stats) {
    try {
      const deviceId = getCurrentDeviceId();
      const sessionKey = `uploadHistory_${deviceId}`;
      const deviceHistory = getDeviceUploadHistory();

      const enhancedStats = {
        ...stats,
        deviceId: deviceId,
        sessionTimestamp: Date.now()
      };

      deviceHistory.unshift(enhancedStats);
      sessionStorage.setItem(sessionKey, JSON.stringify(deviceHistory));
      console.log(` Saved to device history (${deviceId}):`, stats.type, stats.size, stats.time);
    } catch (e) {
      console.log(' Failed to save to device upload history:', e);
    }
  }

  function toggleDeviceLogs() {
    const modal = document.getElementById('deviceLogsModal');
    if (!modal) return;
    modal.style.display = 'flex';

    populateDeviceLogsModal();

    document.addEventListener('keydown', function escapeHandler(e) {
      if (e.key === 'Escape') {
        closeDeviceLogsModal();
        document.removeEventListener('keydown', escapeHandler);
      }
    });

    modal.addEventListener('click', (e) => {
      if (e.target === modal) {
        closeDeviceLogsModal();
      }
    });
  }

  function closeDeviceLogsModal() {
    const modal = document.getElementById('deviceLogsModal');
    if (modal) modal.style.display = 'none';
  }

  function populateDeviceLogsModal() {
    const logsContent = document.getElementById('deviceLogsContent');
    const logsStats = document.getElementById('deviceLogsStats');
    const logsPagination = document.getElementById('deviceLogsPagination');

    if (!logsContent) return;

    try {
      const deviceUploadLogs = getDeviceUploadHistory();

      if (deviceUploadLogs.length === 0) {
        logsContent.innerHTML = `
          <div style="text-align: center; color: var(--text-color); opacity: 0.6; padding: 2rem;">
            <div style="font-size: 3rem; margin-bottom: 1rem;"></div>
            <div style="font-size: 1.1rem; color: var(--text-color) !important;">No device logs for this session yet</div>
            <div style="font-size: 0.9rem; margin-top: 0.5rem; color: var(--text-color) !important; opacity: 0.7;">Upload some files to see activity logs here</div>
            <div style="font-size: 0.85rem; margin-top: 1rem; color: var(--text-color) !important; opacity: 0.7;">
               Logs are device-specific and clear when you close the browser
            </div>
          </div>
        `;
        if (logsStats) logsStats.innerHTML = '';
        if (logsPagination) logsPagination.style.display = 'none';
      } else {
        const totalFiles = deviceUploadLogs.length;
        const totalSizeBytes = deviceUploadLogs.reduce((sum, log) => {
          const sizeMB = parseFloat(log.size?.replace(/[^\d.-]/g, '') || '0');
          return sum + sizeMB;
        }, 0);
        const sessionStartTime = deviceUploadLogs[deviceUploadLogs.length - 1]?.timestamp;

        if (logsStats) {
          logsStats.innerHTML = `
            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 1rem;">
              <div><strong> Total Entries:</strong> ${totalFiles}</div>
              <div><strong> Total Data:</strong> ${totalSizeBytes.toFixed(1)} MB</div>
              <div><strong> Device Session:</strong> ${getCurrentDeviceId().substring(0, 8)}...</div>
              <div><strong>⏰ Session Started:</strong> ${sessionStartTime || 'Unknown'}</div>
            </div>
          `;
        }

        displayDeviceLogsWithPagination(deviceUploadLogs, logsContent, logsPagination);
        console.log(' Device logs populated in modal:', deviceUploadLogs.length, 'entries');
      }
    } catch (error) {
      console.error('Error loading device logs:', error);
      logsContent.innerHTML = `
        <div style="text-align: center; color: #dc3545; padding: 2rem;">
          <div style="font-size: 2rem; margin-bottom: 1rem;"></div>
          <div>Failed to load device logs</div>
          <div style="font-size: 0.9rem; margin-top: 0.5rem;">${error.message}</div>
        </div>
      `;
      if (logsStats) logsStats.innerHTML = '';
    }
  }

  function displayDeviceLogsWithPagination(logs, contentElement, paginationElement) {
    const itemsPerPage = 10;
    const sortedLogs = logs.sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp));
    const totalPages = Math.ceil(sortedLogs.length / itemsPerPage);
    let currentPage = 1;

    function renderPage(page) {
      const startIndex = (page - 1) * itemsPerPage;
      const endIndex = startIndex + itemsPerPage;
      const pageItems = sortedLogs.slice(startIndex, endIndex);

      let historyHTML = '';
      pageItems.forEach((log, index) => {
        const globalIndex = startIndex + index;
        const isEven = globalIndex % 2 === 0;
        historyHTML += renderSingleUpload(log, isEven);
      });

      contentElement.innerHTML = historyHTML;
    }

    function renderPagination() {
      if (!paginationElement) return;
      if (totalPages <= 1) {
        paginationElement.style.display = 'none';
        return;
      }

      paginationElement.style.display = 'block';
      paginationElement.innerHTML = `
        <div style="display: flex; justify-content: center; align-items: center; gap: 0.5rem; margin-top: 1rem;">
          <button onclick="uploadHistoryPagination.goToPage(${currentPage - 1})" 
                  ${currentPage === 1 ? 'disabled' : ''} 
                  class="pagination-button"
                  style="padding: 0.4rem 0.8rem; border: 1px solid var(--border-color); background: var(--section-bg); border-radius: 4px; cursor: ${currentPage === 1 ? 'not-allowed' : 'pointer'}; color: var(--text-color) !important;">
            ◀ Prev
          </button>
          <span style="padding: 0.4rem 1rem; color: var(--text-color) !important; opacity: 0.8;">
            Page ${currentPage} of ${totalPages} (${logs.length} total uploads)
          </span>
          <button onclick="uploadHistoryPagination.goToPage(${currentPage + 1})" 
                  ${currentPage === totalPages ? 'disabled' : ''} 
                  class="pagination-button"
                  style="padding: 0.4rem 0.8rem; border: 1px solid var(--border-color); background: var(--section-bg); border-radius: 4px; cursor: ${currentPage === totalPages ? 'not-allowed' : 'pointer'}; color: var(--text-color) !important;">
            Next ▶
          </button>
        </div>
      `;
    }

    window.uploadHistoryPagination = {
      goToPage: function (page) {
        if (page >= 1 && page <= totalPages) {
          currentPage = page;
          renderPage(currentPage);
          renderPagination();
        }
      }
    };

    renderPage(currentPage);
    renderPagination();
  }

  function renderSingleUpload(log, isEven) {
    const chunkInfo = log.chunksUsed ? `<span style="color: #0056b3 !important;"> ${log.chunkCount || log.chunks || 'Unknown'} chunks</span>` : '<span style="color: var(--text-color) !important; opacity: 0.7;"> Direct</span>';

    return `
      <div style="background: ${isEven ? 'var(--section-bg)' : 'var(--input-bg)'}; padding: 1rem; margin-bottom: 0.5rem; border-radius: 6px; border: 1px solid var(--border-color);">
        <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 0.5rem;">
          <div style="font-weight: bold; color: var(--text-color) !important; flex: 1;">
            ${typeof window.escapeHtml === 'function' ? window.escapeHtml(log.filename || 'Unknown File') : (log.filename || 'Unknown File')}
            <span style="font-size: 0.8rem; color: var(--text-color) !important; opacity: 0.7; margin-left: 0.5rem;">.${typeof window.escapeHtml === 'function' ? window.escapeHtml(log.fileExtension || 'unknown') : (log.fileExtension || 'unknown')}</span>
          </div>
          <div style="color: var(--text-color) !important; opacity: 0.7; font-size: 0.85rem;">${log.timestamp || 'Unknown Date'}</div>
        </div>
        
        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(130px, 1fr)); gap: 0.5rem; font-size: 0.9rem; color: var(--text-color) !important;">
          <div><strong> Size:</strong> ${log.size || 'Unknown'}</div>
          <div><strong> Speed:</strong> ${log.speed || 'Unknown'}</div>
          <div><strong>⏱ Time:</strong> ${log.time || 'Unknown'}</div>
          <div><strong> Protocol:</strong> ${log.protocol || 'Unknown'}</div>
          <div><strong> Method:</strong> ${log.method || 'Unknown'}</div>
          <div><strong> Chunks:</strong> ${chunkInfo}</div>
          ${log.encrypted ? '<div><strong> Encrypted:</strong> <span style="color: #dc3545 !important;">Yes</span></div>' : '<div><strong> Encrypted:</strong> <span style="color: var(--text-color) !important; opacity: 0.7;">No</span></div>'}
        </div>
      </div>
    `;
  }

  function downloadDeviceLogs() {
    try {
      const deviceUploadLogs = getDeviceUploadHistory();

      if (deviceUploadLogs.length === 0) {
        if (typeof window.showToast === 'function') window.showToast(' No device logs to download', 3000);
        return;
      }

      const deviceId = getCurrentDeviceId();
      const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
      const filename = `Lanvan-device-logs-${deviceId.substring(0, 8)}-${timestamp}.txt`;

      let reportContent = `Lanvan DEVICE LOGS REPORT
========================================
Generated: ${new Date().toLocaleString()}
Device Session ID: ${deviceId}
Total Entries: ${deviceUploadLogs.length}
Report Format: Plain Text

`;

      const totalFiles = deviceUploadLogs.filter(log => log.type.includes('File Upload')).length;
      const singleUploads = deviceUploadLogs.filter(log => log.type === 'Single File Upload').length;
      const chunkedUploads = deviceUploadLogs.filter(log => log.type === 'Chunked File Upload').length;
      const httpsUploads = deviceUploadLogs.filter(log => log.protocol === 'HTTPS').length;
      const totalSizeBytes = deviceUploadLogs.filter(log => log.type.includes('File Upload')).reduce((sum, log) => {
        const sizeMB = parseFloat(log.size?.replace(/[^\d.-]/g, '') || '0');
        return sum + sizeMB;
      }, 0);
      const fileUploadLogs = deviceUploadLogs.filter(log => log.type.includes('File Upload'));
      const sessionStart = fileUploadLogs[fileUploadLogs.length - 1]?.startTime || fileUploadLogs[fileUploadLogs.length - 1]?.timestamp;
      const sessionEnd = fileUploadLogs[0]?.endTime || fileUploadLogs[0]?.timestamp;

      reportContent += `SESSION SUMMARY
========================================
Total Upload Entries: ${totalFiles}
- Single File Uploads: ${singleUploads}
- Chunked Uploads: ${chunkedUploads}
- HTTPS Uploads: ${httpsUploads} (${totalFiles > 0 ? ((httpsUploads / totalFiles) * 100).toFixed(1) : 0}%)

Total Data Transferred: ${totalSizeBytes.toFixed(2)} MB
Session Started: ${sessionStart || 'Unknown'}
Last Upload: ${sessionEnd || 'Unknown'}
Average Entry Size: ${totalFiles > 0 ? (totalSizeBytes / totalFiles).toFixed(2) : 0} MB
Security: ${httpsUploads > (totalFiles / 2) ? 'Mostly Secure (HTTPS)' : 'Mixed HTTP/HTTPS'}

`;

      reportContent += `DETAILED UPLOAD LOG
========================================

`;

      deviceUploadLogs.filter(log => log.type.includes('File Upload')).forEach((log, index) => {
        reportContent += `[${index + 1}] ${log.filename || 'Unknown File'}
    Upload Start: ${log.startTime || log.timestamp || 'Unknown'}
    Upload End: ${log.endTime || 'Unknown'}
    Duration: ${log.time || 'Unknown'} (${log.timeSeconds || 'Unknown'}s)
    File Size: ${log.size || 'Unknown'} (${log.sizeBytes || 'Unknown'} bytes)
    Transfer Speed: ${log.speed || 'Unknown'} (${log.speedMBps || 'Unknown'} MB/s)
    Upload Type: ${log.chunksUsed ? 'Chunked' : 'Direct'}
    Chunk Count: ${log.chunkCount || 0}
    Chunk Size: ${log.chunkSize || 'N/A'}
    Protocol: ${log.protocol || 'Unknown'}
    Method: ${log.method || 'Unknown'}
    ${log.encrypted ? 'Encryption: AES-256-CBC' : 'Encryption: No'}
    File Extension: .${log.fileExtension || 'unknown'}
    Network Condition: ${log.networkCondition || 'Unknown'}
    Transfer Efficiency: ${log.transferEfficiency || 'Unknown'}
    
    Advanced Stats:
    - Resume Count: ${log.resumeCount || 0}
    - Supports Resume: ${log.supportsResume ? 'Yes' : 'No'}
    - Upload ID: ${log.uploadId || 'Unknown'}
    - Session ID: ${log.sessionId || 'Unknown'}
    - Upload Method: ${log.uploadMethod || 'Unknown'}
    - Average Chunk Time: ${log.avgChunkTime || 'N/A'}

`;
      });

      reportContent += `
========================================
End of Report - Generated by Lanvan File Transfer System
Device Session will reset when browser is closed
========================================`;

      const blob = new Blob([reportContent], { type: 'text/plain' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);

      if (typeof window.showToast === 'function') window.showToast(` Device logs downloaded: ${filename}`, 4000);
    } catch (error) {
      console.error('Error downloading device logs:', error);
      if (typeof window.showToast === 'function') window.showToast(' Failed to download device logs', 3000);
    }
  }

  function clearDeviceLogs() {
    try {
      const deviceId = getCurrentDeviceId();
      const sessionKey = `uploadHistory_${deviceId}`;
      const currentHistory = getDeviceUploadHistory();

      if (currentHistory.length === 0) {
        if (typeof window.showToast === 'function') window.showToast(' No device logs to clear', 2000);
        return;
      }

      sessionStorage.removeItem(sessionKey);

      const logsSection = document.getElementById('deviceLogsSection');
      const logsContent = document.getElementById('deviceLogsContent');
      const logsStats = document.getElementById('deviceLogsStats');
      const logsPagination = document.getElementById('deviceLogsPagination');

      if (logsSection && logsSection.style.display !== 'none') {
        if (logsContent) {
          logsContent.innerHTML = `
            <div style="text-align: center; color: var(--text-color); opacity: 0.6; padding: 2rem;">
              <div style="font-size: 3rem; margin-bottom: 1rem;"></div>
              <div style="font-size: 1.1rem;">Device logs cleared successfully</div>
              <div style="font-size: 0.9rem; margin-top: 0.5rem;">Upload some files to see new activity logs here</div>
              <div style="font-size: 0.85rem; margin-top: 1rem; color: #999;">
                 Logs are device-specific and clear when you close the browser
              </div>
            </div>
          `;
        }
        if (logsStats) logsStats.innerHTML = '';
        if (logsPagination) logsPagination.style.display = 'none';
      }

      if (typeof window.showToast === 'function') {
        window.showToast(` Successfully cleared ${currentHistory.length} device log entries for this session`, 3000);
      }
    } catch (error) {
      console.error('Error clearing device logs:', error);
      if (typeof window.showToast === 'function') window.showToast(' Failed to clear device logs', 3000);
    }
  }

  const DeviceLogsModalAdapter = Object.freeze({
    getCurrentDeviceId: getCurrentDeviceId,
    getDeviceInfo: getDeviceInfo,
    getDeviceUploadHistory: getDeviceUploadHistory,
    saveToDeviceUploadHistory: saveToDeviceUploadHistory,
    toggleDeviceLogs: toggleDeviceLogs,
    closeDeviceLogsModal: closeDeviceLogsModal,
    populateDeviceLogsModal: populateDeviceLogsModal,
    downloadDeviceLogs: downloadDeviceLogs,
    clearDeviceLogs: clearDeviceLogs
  });

  window.DeviceLogsModalAdapter = DeviceLogsModalAdapter;

  window.getCurrentDeviceId = window.getCurrentDeviceId || getCurrentDeviceId;
  window.getDeviceInfo = window.getDeviceInfo || getDeviceInfo;
  window.getDeviceUploadHistory = window.getDeviceUploadHistory || getDeviceUploadHistory;
  window.saveToDeviceUploadHistory = window.saveToDeviceUploadHistory || saveToDeviceUploadHistory;
  window.toggleDeviceLogs = window.toggleDeviceLogs || toggleDeviceLogs;
  window.closeDeviceLogsModal = window.closeDeviceLogsModal || closeDeviceLogsModal;
  window.populateDeviceLogsModal = window.populateDeviceLogsModal || populateDeviceLogsModal;
  window.downloadDeviceLogs = window.downloadDeviceLogs || downloadDeviceLogs;
  window.clearDeviceLogs = window.clearDeviceLogs || clearDeviceLogs;

})(window);
