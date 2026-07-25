/**
 * @file ui-modules.js
 * @description Layout control and UI component layer for Lanvan. Coordinates Toast notifications,
 *              download progress animation sequences, file grid populating, and settings menus.
 * @module UIControllers
 * @dependency main-app.js, file-utils.js
 */
window.DOM_CACHE = window.DOM_CACHE || {};
var DOM_CACHE = window.DOM_CACHE;

function completeProgress(color = 'green') {
  try {
    // Use cached DOM element
    let progressBar = DOM_CACHE.toastProgress;
    if (!progressBar) {
      progressBar = document.getElementById('toast-progress');
      if (progressBar) DOM_CACHE.toastProgress = progressBar;
    }
    if (!progressBar) return; // Safe guard for guest devices

    setProgressColor(color);
    progressBar.style.width = '100%';

    // Fade out after completion
    setTimeout(() => {
      if (progressBar) progressBar.style.width = '0%';
    }, 1000);
  } catch (err) {
    console.log('Progress completion skipped on this device');
  }
}

//  Show persistent toast with elapsed time (Legacy - replaced by new system)

//  Handle download button clicks with direct download strategy - Lanvan Ultra-Fast Implementation
function setupDownloadHandlers() {
  //  PERFORMANCE: Clean up existing listeners first to prevent memory leaks
  document.querySelectorAll('.file-card a.download-btn').forEach(btn => {
    btn.replaceWith(btn.cloneNode(true));
  });

  document.querySelectorAll('.file-card a.download-btn').forEach(btn => {
    btn.addEventListener('click', async function handleDownloadClick(e) {
      e.preventDefault();

      const fileUrl = this.getAttribute('href');
      const fileName = this.closest('.file-card').querySelector('.file-name').textContent.trim();
      const isHTTPS = location.protocol === 'https:';

      //  Lanvan Direct Download Strategy - No Frontend Processing
      const CHUNK_THRESHOLD = LANVAN_CONFIG.CHUNK_THRESHOLD;
      const isEncFile = fileName.endsWith('.enc');

      // Quick file info check for strategy decision
      const startTime = Date.now();

      // Show single stable toast with blue progress bar
      showToast(' Initializing download...', 0);
      startProgressAnimation('blue', 2000);

      try {
        // HEAD request to get file info
        const headResponse = await fetch(fileUrl, { method: 'HEAD' });
        if (!headResponse.ok) throw new Error('File info request failed');

        const contentLength = headResponse.headers.get('Content-Length');
        let fileSize = contentLength ? parseInt(contentLength) : 0;

        //  If no Content-Length from server, try stored metadata
        if (!fileSize) {
          const storedMetadata = getFileMetadata(fileName);
          if (storedMetadata) {
            fileSize = storedMetadata.size;
          }
        }

        const fileSizeMB = (fileSize / 1024 / 1024).toFixed(2);
        const isLargeFile = fileSize >= CHUNK_THRESHOLD;

        //  ULTRA-FAST DIRECT DOWNLOAD STRATEGY:
        // No frontend processing, no chunking, no blob creation - just direct download

        const serverResponseTime = ((Date.now() - startTime) / 1000).toFixed(2);

        // Update toast with processing info - single stable message
        updateProgressToast(` Processing ${fileSizeMB} MB download...`);

        //  DIRECT DOWNLOAD - Let browser handle everything natively
        const link = document.createElement('a');
        link.href = fileUrl;
        link.download = fileName;
        link.style.display = 'none';
        document.body.appendChild(link);

        // Trigger immediate download
        const downloadStartTime = Date.now(); // Separate timing for processing vs total
        link.click();
        document.body.removeChild(link);

        //  Separate timing calculations for accuracy
        const totalTime = ((Date.now() - startTime) / 1000).toFixed(2);
        const processingTime = ((downloadStartTime - startTime) / 1000).toFixed(3); // Time before download trigger
        const downloadTime = ((Date.now() - downloadStartTime) / 1000).toFixed(3);  // Time for download trigger

        // Create accurate stats for direct download
        const downloadStats = {
          type: 'direct_download_ultra_fast',
          filename: fileName,
          size: fileSizeMB + ' MB',
          time: totalTime + 's',
          speed: (fileSizeMB / parseFloat(totalTime)).toFixed(2) + ' MB/s',
          serverResponseTime: serverResponseTime + 's',
          processingTime: processingTime + 's', // Accurate processing time (separate calculation)
          downloadTime: downloadTime + 's',     // Download trigger time
          totalTime: totalTime + 's',
          protocol: isHTTPS ? 'HTTPS' : 'HTTP',
          aesEnabled: isEncFile,
          downloadType: isEncFile ? 'direct-enc' : (isLargeFile ? 'direct-large' : 'direct-small'),
          strategy: 'zero-processing-direct',
          timestamp: new Date().toLocaleString('en-US', { hour: 'numeric', minute: 'numeric', second: 'numeric', hour12: true })
        };
        saveStatsToLog(downloadStats);

        // Success message with accurate timing
        const protocolMsg = isHTTPS ? 'HTTPS' : 'HTTP';
        const completionMessage = ` Download complete via ${protocolMsg} (${fileSizeMB} MB) • ${totalTime}s total • ${processingTime}s processing`;

        // Complete progress bar and show final success (safe for all devices)
        completeProgress('blue');
        setTimeout(() => {
          console.log(' Showing download completion toast:', completionMessage);
          console.log(' DOM_CACHE status:', {
            toast: !!DOM_CACHE.toast,
            toastId: DOM_CACHE.toast ? DOM_CACHE.toast.id : 'no-toast',
            cacheKeys: Object.keys(DOM_CACHE)
          });

          //  PERFORMANCE: Optimized fallback with DOM cache update
          if (!DOM_CACHE.toast) {
            console.warn(' DOM_CACHE.toast not available, trying direct selection');
            DOM_CACHE.toast = document.getElementById('toast');
            if (DOM_CACHE.toast) {
              console.log(' Found toast directly, updated DOM_CACHE');
            }
          }

          showToast(completionMessage, 0, downloadStats);
        }, 1500); // Brief delay to let download start

      } catch (error) {
        //  Safe fallback - ensure download still works even if progress fails
        console.log('Download error or fallback needed:', error.message);

        // Try basic download as fallback for guest devices
        try {
          const link = document.createElement('a');
          link.href = fileUrl;
          link.download = fileName;
          link.style.display = 'none';
          document.body.appendChild(link);
          link.click();
          document.body.removeChild(link);

          const fallbackTime = ((Date.now() - startTime) / 1000).toFixed(2);
          showToast(` Download initiated (fallback mode) • ${fallbackTime}s`, 3000);
        } catch (fallbackError) {
          showToast(` Download failed: ${error.message}`, 5000);
        }
        console.error('Direct download error:', error);
      }
    });
  });
}

// Set up download handlers after DOM cache is ready
document.addEventListener('DOMContentLoaded', () => {
  // Wait a bit to ensure DOM_CACHE is fully initialized
  setTimeout(() => {
    setupDownloadHandlers();
  }, 100);
});

//  ULTRA-FAST BACKUP FUNCTIONS (only used if direct download fails)

//  Minimal processing download for emergencies only
async function downloadFileMinimal(fileUrl, fileName, fileSizeMB, requestStartTime) {
  try {
    showToast(' Using minimal processing fallback...', 2000);

    // Create download link and trigger immediate download
    const link = document.createElement('a');
    link.href = fileUrl;
    link.download = fileName;
    link.style.display = 'none';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);

    const totalTime = ((Date.now() - requestStartTime) / 1000).toFixed(2);
    const protocolMsg = location.protocol === 'https:' ? 'HTTPS' : 'HTTP';

    // Create stats for minimal fallback download
    const downloadStats = {
      type: 'minimal_fallback_download',
      filename: fileName,
      size: fileSizeMB + ' MB',
      time: totalTime + 's',
      speed: (parseFloat(fileSizeMB) / parseFloat(totalTime)).toFixed(2) + ' MB/s',
      protocol: protocolMsg,
      strategy: 'minimal-fallback',
      timestamp: new Date().toLocaleString('en-US', { hour: 'numeric', minute: 'numeric', second: 'numeric', hour12: true })
    };

    setTimeout(() => {
      showToast(` Minimal fallback download complete via ${protocolMsg} (${fileSizeMB} MB) • ${totalTime}s • Click anywhere to dismiss`, 0, downloadStats);
    }, 1500);

  } catch (err) {
    showToast(' Fallback download error: ' + err.message + ' • Click anywhere to dismiss', 0);
  }
}

//  Ultra-optimized regular download function - supports HTTP & HTTPS (BACKUP ONLY)
async function downloadFileRegular(fileUrl, fileName, fileSizeMB, requestStartTime) {
  try {
    const stopPersistentToast = showPersistentToast('⏳ Requesting file from server...');

    const response = await fetch(fileUrl);
    if (!response.ok) throw new Error('Download failed');

    // Calculate actual server response time (time until headers received)
    const serverResponseTime = ((Date.now() - requestStartTime) / 1000).toFixed(2);

    // Start tracking processing time (not downloading time)
    const processingStartTime = Date.now();
    stopPersistentToast();

    // Get file size for progress tracking
    const contentLength = response.headers.get('Content-Length');
    let actualFileSizeMB;
    let processedBytes = 0;
    let totalBytes = contentLength ? parseInt(contentLength) : 0;

    //  If no Content-Length, try to get size from stored metadata
    if (!contentLength) {
      const storedMetadata = getFileMetadata(fileName);
      if (storedMetadata) {
        totalBytes = storedMetadata.size;
        actualFileSizeMB = (storedMetadata.size / (1024 * 1024)).toFixed(2);
      }
    } else {
      actualFileSizeMB = (parseInt(contentLength) / (1024 * 1024)).toFixed(2);
    }

    if (!contentLength && !totalBytes) {
      // If no content-length header and no stored metadata, ultra-fast download without size info
      const stopProcessingToast = showPersistentToast(' Ultra-fast processing...');

      const blob = await response.blob();
      actualFileSizeMB = (blob.size / (1024 * 1024)).toFixed(2);

      stopProcessingToast();
      showToast(' Finalizing ultra-fast download...', 1000);

      // Create blob URL and trigger download
      const blobUrl = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = blobUrl;
      a.download = fileName;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(blobUrl);
    } else {
      // We have size info - show optimized progress
      if (!actualFileSizeMB) {
        actualFileSizeMB = (totalBytes / (1024 * 1024)).toFixed(2);
      }

      //  Ultra-fast streaming with optimized progress tracking
      const reader = response.body.getReader();
      const chunks = [];
      let lastProgressUpdate = 0;
      const PROGRESS_UPDATE_INTERVAL = 250; // Update every 250ms for ultra-smooth progress

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        chunks.push(value);
        processedBytes += value.length;

        // Calculate progress percentage
        const progressPercent = totalBytes > 0 ? ((processedBytes / totalBytes) * 100).toFixed(1) : '0.0';
        const processingElapsed = ((Date.now() - processingStartTime) / 1000).toFixed(1);
        const processedMB = (processedBytes / 1024 / 1024).toFixed(1);
        const speed = processedBytes / (1024 * 1024) / ((Date.now() - processingStartTime) / 1000);

        // Update progress toast with speed tracking
        const now = Date.now();
        if (now - lastProgressUpdate >= PROGRESS_UPDATE_INTERVAL || done) {
          const sizeSource = contentLength ? "(server)" : "(stored)";
          showToast(` Ultra-fast processing ${progressPercent}% (${processedMB}/${actualFileSizeMB} MB) @ ${speed.toFixed(1)} MB/s ${sizeSource} • ${processingElapsed}s`, 100);
          lastProgressUpdate = now;
        }
      }

      // Combine chunks and finalize
      showToast(' Finalizing ultra-fast download...', 1000);
      const blob = new Blob(chunks);
      const blobUrl = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = blobUrl;
      a.download = fileName;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(blobUrl);
    }

    // Calculate total processing time (not download time)
    const totalProcessingTime = ((Date.now() - processingStartTime) / 1000).toFixed(2);
    const totalTime = ((Date.now() - requestStartTime) / 1000).toFixed(2);
    const avgSpeed = totalBytes > 0 ? (totalBytes / (1024 * 1024) / parseFloat(totalProcessingTime)).toFixed(1) : 'N/A';

    // Save download stats to logs with accurate timing
    const downloadStats = {
      type: 'ultra_optimized_download',
      filename: fileName,
      size: actualFileSizeMB + ' MB',
      time: totalTime + 's',
      speed: avgSpeed + ' MB/s',
      serverResponseTime: serverResponseTime + 's',
      processingTime: totalProcessingTime + 's',
      processingSpeed: avgSpeed + ' MB/s',
      totalTime: totalTime + 's',
      protocol: location.protocol === 'https:' ? 'HTTPS' : 'HTTP',
      aesEnabled: fileName.endsWith('.enc'),
      downloadType: 'ultra-optimized',
      timestamp: new Date().toLocaleString('en-US', { hour: 'numeric', minute: 'numeric', second: 'numeric', hour12: true }),
      startTime: new Date(requestStartTime).toLocaleString('en-US', { hour: 'numeric', minute: 'numeric', second: 'numeric', hour12: true }),
      endTime: new Date().toLocaleString('en-US', { hour: 'numeric', minute: 'numeric', second: 'numeric', hour12: true })
    };
    saveStatsToLog(downloadStats);

    // Enhanced completion toast with speed information
    const protocolMsg = location.protocol === 'https:' ? 'HTTPS' : 'HTTP';
    const completionMessage = ` Ultra-optimized download complete via ${protocolMsg} (${actualFileSizeMB} MB) • Server: ${serverResponseTime}s • Processing: ${totalProcessingTime}s @ ${avgSpeed} MB/s`;

    // Trigger-based download detection instead of time-based delay
    detectDownloadCompletion(completionMessage, downloadStats);

  } catch (err) {
    // Stop any running toasts on error
    if (typeof stopPersistentToast === 'function') stopPersistentToast();
    showToast(' Download error: ' + err.message + ' • Click anywhere to dismiss', 0);
    throw err; // Re-throw for parent handler
  }
}

//  High-performance chunked download function for large files (≥250MB) - supports HTTP & HTTPS
async function downloadFileChunked(fileUrl, fileName, fileSize, fileSizeMB, requestStartTime) {
  const isHTTPS = location.protocol === 'https:';
  const protocolMsg = isHTTPS ? "HTTPS" : "HTTP";
  const DOWNLOAD_CHUNK_SIZE = 16 * 1024 * 1024; // 16MB chunks (16x larger than before for much faster processing)
  const totalChunks = Math.ceil(fileSize / DOWNLOAD_CHUNK_SIZE);

  try {
    const stopInitialToast = showPersistentToast('⏳ Preparing high-performance chunked download...');

    // Start processing time tracking
    const processingStartTime = Date.now();
    let processedChunks = 0;
    const chunks = [];

    stopInitialToast();

    //  Process chunks with much larger sizes for faster performance
    for (let i = 0; i < totalChunks; i++) {
      const start = i * DOWNLOAD_CHUNK_SIZE;
      const end = Math.min(start + DOWNLOAD_CHUNK_SIZE, fileSize);

      // Calculate progress percentage
      const progressPercent = ((i + 1) / totalChunks * 100).toFixed(1);
      const processingElapsed = ((Date.now() - processingStartTime) / 1000).toFixed(1);
      const chunkSizeMB = ((end - start) / (1024 * 1024)).toFixed(1);

      // Show processing progress with chunk size info
      showToast(` Processing 16MB chunks ${progressPercent}% (${i + 1}/${totalChunks}) • Chunk: ${chunkSizeMB}MB • Processing: ${processingElapsed}s`, 100);

      try {
        const response = await fetch(fileUrl, {
          headers: {
            'Range': `bytes=${start}-${end - 1}`
          }
        });

        if (!response.ok) throw new Error(`Chunk ${i + 1} failed`);

        const chunkBlob = await response.blob();
        chunks.push(chunkBlob);
        processedChunks++;

      } catch (chunkError) {
        showToast(` Processing failed at chunk ${i + 1}: ${chunkError.message}`, 5000);
        return;
      }
    }

    // All chunks processed, now combine them
    const totalProcessingTime = ((Date.now() - processingStartTime) / 1000).toFixed(1);
    showToast(` Combining ${processedChunks} large chunks... (Processing: ${totalProcessingTime}s)`);

    // Combine all chunks into final blob
    const combinedBlob = new Blob(chunks);

    // Trigger download
    const blobUrl = window.URL.createObjectURL(combinedBlob);
    const a = document.createElement('a');
    a.href = blobUrl;
    a.download = fileName;
    document.body.appendChild(a);
    a.click();
    a.remove();
    window.URL.revokeObjectURL(blobUrl);

    // Calculate final stats
    const totalTime = ((Date.now() - requestStartTime) / 1000).toFixed(1);

    const downloadStats = {
      type: 'high_performance_chunked_download',
      filename: fileName,
      size: fileSizeMB + ' MB',
      time: totalTime + 's',
      speed: (fileSizeMB / parseFloat(totalTime)).toFixed(2) + ' MB/s',
      totalChunks: totalChunks,
      chunkSize: '16MB',
      processingTime: totalProcessingTime + 's',
      totalTime: totalTime + 's',
      protocol: protocolMsg,
      aesEnabled: fileName.endsWith('.enc'),
      timestamp: new Date().toLocaleString('en-US', { hour: 'numeric', minute: 'numeric', second: 'numeric', hour12: true })
    };
    saveStatsToLog(downloadStats);

    // Success message with performance info
    showToast(` High-performance chunked download complete via ${protocolMsg} (${fileSizeMB} MB) • Processing: ${totalProcessingTime}s • Total: ${totalTime}s • 16MB chunks • Click anywhere to dismiss`, 0, downloadStats);

  } catch (error) {
    showToast(` High-performance chunked download failed: ${error.message} • Click anywhere to dismiss`, 0);
    console.error('High-performance chunked download error:', error);
  }
}

//  Store file metadata for downloads (fixes "unknown size" issue)
function storeFileMetadata(files, totalSize) {
  const metadata = JSON.parse(localStorage.getItem('fileMetadata') || '{}');

  for (let file of files) {
    metadata[file.name] = {
      size: file.size,
      sizeFormatted: (file.size / (1024 * 1024)).toFixed(2) + ' MB',
      type: file.type || 'unknown',
      uploadDate: new Date().toISOString(),
      timestamp: Date.now()
    };
  }

  //  PERFORMANCE: Optimize metadata cleanup with for...in loop
  const thirtyDaysAgo = Date.now() - (30 * 24 * 60 * 60 * 1000);
  for (const filename in metadata) {
    if (metadata[filename].timestamp < thirtyDaysAgo) {
      delete metadata[filename];
    }
  }

  localStorage.setItem('fileMetadata', JSON.stringify(metadata));
}

//  Get stored file metadata (for downloads)
function getFileMetadata(filename) {
  const metadata = JSON.parse(localStorage.getItem('fileMetadata') || '{}');
  return metadata[filename] || null;
}

// Progress styling utilities for visual feedback
function setProgressColor(color) {
  try {
    // Use cached DOM element instead of repeated getElementById
    let progressBar = DOM_CACHE.toastProgress;
    if (!progressBar) {
      progressBar = document.getElementById('toast-progress');
      if (progressBar) DOM_CACHE.toastProgress = progressBar;
    }
    if (!progressBar) return; // Safe guard for guest devices

    if (color === 'blue') {
      progressBar.style.background = 'linear-gradient(90deg, #2196F3, #42A5F5)';
    } else if (color === 'green') {
      progressBar.style.background = 'linear-gradient(90deg, #4CAF50, #66BB6A)';
    } else {
      progressBar.style.background = color;
    }
  } catch (err) {
    console.log('Progress color update skipped on this device');
  }
}

function updateProgress(percentage, color = 'green') {
  try {
    // Use cached DOM element
    let progressBar = DOM_CACHE.toastProgress;
    if (!progressBar) {
      progressBar = document.getElementById('toast-progress');
      if (progressBar) DOM_CACHE.toastProgress = progressBar;
    }
    if (!progressBar) return; // Safe guard for guest devices

    setProgressColor(color);
    progressBar.style.width = Math.min(100, Math.max(0, percentage)) + '%';
  } catch (err) {
    console.log('Progress update skipped on this device');
  }
}

function startProgressAnimation(color = 'green', duration = 2000) {
  try {
    setProgressColor(color);
    // Use cached DOM element
    let progressBar = DOM_CACHE.toastProgress;
    if (!progressBar) {
      progressBar = document.getElementById('toast-progress');
      if (progressBar) DOM_CACHE.toastProgress = progressBar;
    }
    if (!progressBar) return; // Safe guard for guest devices

    progressBar.style.width = '0%';

    // Animate to 90% over the duration
    const startTime = Date.now();
    const animate = () => {
      const elapsed = Date.now() - startTime;
      const progress = Math.min(90, (elapsed / duration) * 90);
      if (progressBar) progressBar.style.width = progress + '%';

      if (progress < 90 && progressBar) {
        requestAnimationFrame(animate);
      }
    };
    requestAnimationFrame(animate);
  } catch (err) {
    console.log('Progress animation skipped on this device');
  }
}

function showPersistentToast(message) {
  showToast(message, -1); // -1 means indefinite
  return function stopPersistentToast() {
    hideToast();
  };
}

// Switch button dropdown and navigation logic (inlined to avoid 404 issues)
function showSwitchDropdown(event, dropdownId) {
  event.stopPropagation();
  const dropdown = document.getElementById(dropdownId);
  if (dropdown.style.display === 'block') {
    dropdown.style.display = 'none';
  } else {
    dropdown.style.display = 'block';
    // Hide dropdown if clicked outside
    document.addEventListener('click', function handler(e) {
      if (!dropdown.contains(e.target)) {
        dropdown.style.display = 'none';
        document.removeEventListener('click', handler);
      }
    });
  }
}
function switchToPage(page) {
  // Hide all switch dropdowns before switching
  var dropdowns = [
    document.getElementById('switchDropdownMain'),
    document.getElementById('switchDropdownClipboard')
  ];
  dropdowns.forEach(function (dd) {
    if (dd) dd.style.display = 'none';
  });

  // Get the sections by ID
  const fileTransferSection = document.getElementById('fileTransferSection');
  const fileListSection = document.getElementById('fileListSection');
  const clipboardSection = document.getElementById('clipboardSection');

  // If target section is missing, perform standard redirect instead of dynamic toggle
  if (page === 'clipboard' && !clipboardSection) {
    window.location.href = '/clipboard';
    return;
  }
  if (page === 'file' && (!fileTransferSection || !fileListSection)) {
    window.location.href = '/';
    return;
  }

  // Get all tick indicators (removed for cleaner UI)
  // const clipboardTickMain = document.getElementById('clipboardTickMain');
  // const fileTickClipboard = document.getElementById('fileTickClipboard');
  // const clipboardTickClipboard = document.getElementById('clipboardTickClipboard');

  // Add smooth transition effect with opacity
  const sections = [fileTransferSection, fileListSection, clipboardSection];
  sections.forEach(section => {
    if (section) section.style.opacity = '0.7';
  });

  // Use setTimeout to allow smooth transition
  setTimeout(() => {
    if (page === 'clipboard') {
      // Update current active section tracker
      currentActiveSection = 'clipboard';

      // Show clipboard section, hide file sections
      if (fileTransferSection) {
        fileTransferSection.style.display = 'none';
        fileTransferSection.style.opacity = '1';
      }
      if (fileListSection) {
        fileListSection.style.display = 'none';
        fileListSection.style.opacity = '1';
      }
      if (clipboardSection) {
        clipboardSection.style.display = 'block';
        clipboardSection.style.opacity = '1';
      }

      // Update tick indicators - removed for cleaner UI
      // if (fileTickClipboard) fileTickClipboard.style.display = 'none';
      // if (clipboardTickMain) clipboardTickMain.style.display = 'inline';
      // if (clipboardTickClipboard) clipboardTickClipboard.style.display = 'inline';

      // Update page title/URL without navigation (preserves uploads)
      history.pushState({ page: 'clipboard' }, 'Lanvan - Clipboard', '/clipboard');
      document.title = 'Lanvan - Clipboard';

    } else if (page === 'file') {
      // Update current active section tracker
      currentActiveSection = 'file';

      // Show file sections, hide clipboard section
      if (fileTransferSection) {
        fileTransferSection.style.display = 'block';
        fileTransferSection.style.opacity = '1';
      }
      if (fileListSection) {
        fileListSection.style.display = 'block';
        fileListSection.style.opacity = '1';
      }
      if (clipboardSection) {
        clipboardSection.style.display = 'none';
        clipboardSection.style.opacity = '1';
      }

      // Update tick indicators - removed for cleaner UI
      // if (fileTickClipboard) fileTickClipboard.style.display = 'inline';
      // if (clipboardTickMain) clipboardTickMain.style.display = 'none';
      // if (clipboardTickClipboard) clipboardTickClipboard.style.display = 'none';

      // Update page title/URL without navigation (preserves uploads)
      history.pushState({ page: 'file' }, 'Lanvan - File Transfer', '/');
      document.title = 'Lanvan - File Transfer';
    }
  }, 100); // Small delay for smooth transition

  // Trigger any necessary updates for the visible section
  setTimeout(() => {
    if (page === 'file') {
      // When switching back to file section, refresh the file list to show any new files
      if (typeof refreshFileList === 'function') {
        refreshFileList();
      } else if (typeof updateFileList === 'function') {
        updateFileList();
      }
    } else if (page === 'clipboard') {
      if (typeof refreshClipboardHistory === 'function') {
        refreshClipboardHistory();
      }
    }
  }, 150); // Slight delay to ensure sections are visible

  // Show a brief toast notification
  if (typeof showToast === 'function') {
    const sectionName = page === 'clipboard' ? 'Clipboard' : 'File Transfer';
    showToast(` Switched to ${sectionName}`, 1500);
  }
}

if (!window.__popstateWired) {
  window.__popstateWired = true;
  window.addEventListener('popstate', function (event) {
  if (event.state && event.state.page) {
    // Switch to the page without updating history (since we're handling popstate)
    const targetPage = event.state.page;

    // Update current active section tracker
    currentActiveSection = targetPage;
    console.log(` Browser navigation - active section: ${currentActiveSection}`);

    const fileTransferSection = document.getElementById('fileTransferSection');
    const fileListSection = document.getElementById('fileListSection');
    const clipboardSection = document.getElementById('clipboardSection');

    // Get all tick indicators (removed for cleaner UI)
    // const clipboardTickMain = document.getElementById('clipboardTickMain');
    // const fileTickClipboard = document.getElementById('fileTickClipboard');
    // const clipboardTickClipboard = document.getElementById('clipboardTickClipboard');

    if (targetPage === 'clipboard') {
      if (fileTransferSection) fileTransferSection.style.display = 'none';
      if (fileListSection) fileListSection.style.display = 'none';
      if (clipboardSection) clipboardSection.style.display = 'block';

      // Update tick indicators for clipboard (removed for cleaner UI)
      // if (fileTickClipboard) fileTickClipboard.style.display = 'none';
      // if (clipboardTickMain) clipboardTickMain.style.display = 'inline';
      // if (clipboardTickClipboard) clipboardTickClipboard.style.display = 'inline';

      document.title = 'Lanvan - Clipboard';
    } else {
      if (fileTransferSection) fileTransferSection.style.display = 'block';
      if (fileListSection) fileListSection.style.display = 'block';
      if (clipboardSection) clipboardSection.style.display = 'none';

      // Update tick indicators for file transfer (removed for cleaner UI)
      // if (fileTickClipboard) fileTickClipboard.style.display = 'inline';
      // if (clipboardTickMain) clipboardTickMain.style.display = 'none';
      // if (clipboardTickClipboard) clipboardTickClipboard.style.display = 'none';

      document.title = 'Lanvan - File Transfer';

      if (typeof refreshFileList === 'function') {
        setTimeout(() => refreshFileList(), 100);
      }
    }
  }
});
}

//  Save toggle state when user changes it
document.addEventListener('DOMContentLoaded', () => {
  const aesToggle = document.getElementById('enableEncryption');
  if (!aesToggle) return;

  const isHTTP = location.protocol === 'http:';

  //  NEW LOGIC: Allow AES over HTTP only with HTTP-Safe mode
  if (isHTTP) {
    // For HTTP, enable AES toggle but show warning about HTTP-Safe requirement
    aesToggle.disabled = false;
    const toggleContainer = aesToggle.closest('.toggle-switch').parentElement;
    toggleContainer.style.opacity = '1';
    toggleContainer.title = 'AES over HTTP requires HTTP-Safe Mode for security. Enable both toggles for secure encryption.';

    // Restore saved state
    const saved = localStorage.getItem('aes_enabled');
    if (saved !== null) {
      aesToggle.checked = saved === '1';
    }
  } else {
    // For HTTPS, restore saved state and enable toggle
    aesToggle.disabled = false;
    const saved = localStorage.getItem('aes_enabled');
    if (saved !== null) {
      aesToggle.checked = saved === '1';
    }
  }

  // Save state on change (for both HTTP and HTTPS)
  aesToggle.addEventListener('change', () => {
    localStorage.setItem('aes_enabled', aesToggle.checked ? '1' : '0');

    //  HTTP-Safe mode is now automatic - no toggle needed
    if (isHTTP && aesToggle.checked) {
      console.log(' HTTP-Safe mode automatically enabled for HTTP connection');
      showToast(' HTTP-Safe mode automatically enabled for secure encryption!', 4000);
    }
  });

  //  HTTP-Safe mode is now automatic - no toggle management needed

  //  Dark Mode Toggle Functionality
  // --- 3-Way Theme Preference Initializer ---
  window.applyThemePreference = function (themePref) {
    // Migrate legacy settings if themePref is not set
    if (!themePref) {
      themePref = localStorage.getItem('theme_preference');
      if (themePref === null) {
        const legacyDark = localStorage.getItem('dark_mode_enabled');
        if (legacyDark !== null) {
          themePref = legacyDark === '1' ? 'dark' : 'light';
        } else {
          themePref = 'system';
        }
        localStorage.setItem('theme_preference', themePref);
      }
    }

    let isDarkMode = false;
    if (themePref === 'dark') {
      isDarkMode = true;
    } else if (themePref === 'light') {
      isDarkMode = false;
    } else {
      isDarkMode = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
    }

    applyDarkMode(isDarkMode);

    // Update settings radio buttons
    const themeLightRadio = document.getElementById('themeLight');
    const themeDarkRadio = document.getElementById('themeDark');
    const themeSystemRadio = document.getElementById('themeSystem');

    if (themeLightRadio && themeDarkRadio && themeSystemRadio) {
      themeLightRadio.checked = themePref === 'light';
      themeDarkRadio.checked = themePref === 'dark';
      themeSystemRadio.checked = themePref === 'system';
    }

    // Keep legacy checkboxes in sync
    if (DOM_CACHE.darkModeToggle) {
      DOM_CACHE.darkModeToggle.checked = isDarkMode;
    }
    const settingsToggle = document.getElementById("darkThemeSettingToggle");
    if (settingsToggle) {
      settingsToggle.checked = isDarkMode;
    }

    // Dynamic label/icon/description updates
    const themeIcon = document.getElementById('themeSettingIcon');
    const themeTitle = document.getElementById('themeSettingTitle');
    const themeDesc = document.getElementById('themeSettingDesc');

    if (themeIcon && themeTitle && themeDesc) {
      if (themePref === 'light') {
        themeIcon.setAttribute('data-lucide', 'sun');
        themeTitle.textContent = 'Light Theme';
        themeDesc.textContent = 'Use clean light mode interface';
      } else if (themePref === 'dark') {
        themeIcon.setAttribute('data-lucide', 'moon');
        themeTitle.textContent = 'Dark Theme';
        themeDesc.textContent = 'Use sleek dark mode interface';
      } else {
        themeIcon.setAttribute('data-lucide', 'monitor');
        themeTitle.textContent = 'System Theme';
        themeDesc.textContent = "Follow device's theme settings";
      }
      if (window.refreshLucideIcons) {
        window.refreshLucideIcons(themeIcon ? themeIcon.parentElement : null);
      } else if (window.lucide && typeof window.lucide.createIcons === 'function') {
        window.lucide.createIcons();
      }
    }

    // Sync header toggle icon
    const headerToggleBtn = document.querySelector('button[onclick="toggleDarkMode()"]');
    if (headerToggleBtn) {
      const iconEl = headerToggleBtn.querySelector('i');
      if (iconEl) {
        let iconName = 'monitor';
        if (themePref === 'light') iconName = 'sun';
        else if (themePref === 'dark') iconName = 'moon';
        iconEl.setAttribute('data-lucide', iconName);
        if (window.refreshLucideIcons) {
          window.refreshLucideIcons(headerToggleBtn);
        } else if (window.lucide && typeof window.lucide.createIcons === 'function') {
          window.lucide.createIcons();
        }
      }
    }
  };

  // Run initialization
  window.applyThemePreference(null);

  // Listen for system theme changes dynamically
  if (window.matchMedia) {
    window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', (e) => {
      const themePref = localStorage.getItem('theme_preference') || 'system';
      if (themePref === 'system') {
        applyDarkMode(e.matches);
      }
    });
  }

  //  Apply Dark Mode Function
  function applyDarkMode(isDarkMode) {
    if (isDarkMode) {
      document.documentElement.setAttribute('data-theme', 'dark');
    } else {
      document.documentElement.setAttribute('data-theme', 'light');
    }

    // Update dark mode toggle text based on current mode
    const darkModeLabel = document.getElementById('darkModeLabel');
    if (darkModeLabel) {
      if (isDarkMode) {
        darkModeLabel.innerHTML = '<b> Dark Mode</b>';
      } else {
        darkModeLabel.innerHTML = '<b> Light Mode</b>';
      }
    }

    // Update protocol status hover colors for dark mode
    // Guard with typeof in case another DOMContentLoaded fires first
    if (typeof updateProtocolStatusHover === 'function') {
      updateProtocolStatusHover(isDarkMode);
    }

    // Fix any remaining hardcoded colors dynamically
    fixRemainingColors(isDarkMode);
  }

  // Fix remaining hardcoded colors that CSS might miss
  function fixRemainingColors(isDarkMode) {
    if (isDarkMode) {
      // Fix any elements with hardcoded #333 color
      const darkTextElements = document.querySelectorAll('[style*="color: #333"], [style*="color:#333"], [style*="color: #666"], [style*="color:#666"], [style*="color: #999"], [style*="color:#999"]');
      darkTextElements.forEach(el => {
        el.style.color = 'var(--text-color)';
      });

      // Fix any white background divs
      const whiteBgElements = document.querySelectorAll('[style*="background: #fff"], [style*="background-color: #fff"], [style*="background: #f8f9fa"], [style*="background: white"]');
      whiteBgElements.forEach(el => {
        el.style.backgroundColor = 'var(--section-bg)';
        el.style.color = 'var(--text-color)';
      });

      // Fix file names and clipboard items specifically
      const fileNameElements = document.querySelectorAll('.file-name, .upload-file-name');
      fileNameElements.forEach(el => {
        el.style.color = 'var(--text-color)';
      });

      // Fix clipboard items
      const clipboardElements = document.querySelectorAll('#clipboardHistoryContent div');
      clipboardElements.forEach(el => {
        if (el.style.color && (el.style.color.includes('#333') || el.style.color.includes('#666') || el.style.color.includes('#999'))) {
          el.style.color = 'var(--text-color)';
        }
      });

      // Fix labels and other text elements
      const textElements = document.querySelectorAll('label, span:not(.slider), .file-name, strong');
      textElements.forEach(el => {
        // Skip the mDNS hint text to preserve green color
        if (el.id === 'qrHintText' && el.innerHTML.includes('mDNS:')) {
          return;
        }
        if (!el.classList.contains('slider') && !el.classList.contains('toggle-text')) {
          if (el.style.color && (el.style.color.includes('#333') || el.style.color.includes('#666'))) {
            el.style.color = 'var(--text-color)';
          }
        }
      });
    } else {
      // Reset to light mode colors
      const allElements = document.querySelectorAll('*');
      allElements.forEach(el => {
        if (el.style.color && el.style.color.includes('var(--text-color)')) {
          el.style.color = '';
        }
        if (el.style.backgroundColor && el.style.backgroundColor.includes('var(--')) {
          el.style.backgroundColor = '';
        }
      });
    }
  }

  // Update protocol status hover behavior for dark mode
  function updateProtocolStatusHover(isDarkMode) {
    const protocolStatus = DOM_CACHE.protocolStatus;
    if (protocolStatus) {
      if (isDarkMode) {
        protocolStatus.onmouseover = function () { this.style.backgroundColor = '#1e40af'; };
        protocolStatus.onmouseout = function () { this.style.backgroundColor = 'var(--protocol-bg)'; };
      } else {
        protocolStatus.onmouseover = function () { this.style.backgroundColor = '#d0e9f7'; };
        protocolStatus.onmouseout = function () { this.style.backgroundColor = 'var(--protocol-bg)'; };
      }
    }
  }
});

  //  HTTP-Safe mode is now automatic - no toggle management needed



//  FOLDER UPLOAD FUNCTIONALITY
// Expose on window so all scripts (main-app.js, app-init.js) share the same state
window.currentUploadMode = 'files';
var currentUploadMode = window.currentUploadMode;

// Modern toggle function for single button mode switching
function toggleUploadMode() {
  const toggleBtn = document.getElementById('uploadModeToggle');
  const dropZoneText = document.getElementById('dropZoneText');

  if (currentUploadMode === 'files') {
    window.currentUploadMode = 'folder';
    currentUploadMode = 'folder';
    if (toggleBtn) {
      toggleBtn.innerHTML = ' Folders';
      toggleBtn.title = 'Currently in Folders mode - Click to switch to Files';
    }
    if (dropZoneText) dropZoneText.textContent = ' Drag & Drop folders here or click to select';
  } else {
    window.currentUploadMode = 'files';
    currentUploadMode = 'files';
    if (toggleBtn) {
      toggleBtn.innerHTML = ' Files';
      toggleBtn.title = 'Currently in Files mode - Click to switch to Folders';
    }
    if (dropZoneText) dropZoneText.textContent = ' Drag & Drop files here or click to select';
  }
}

// Backward compatibility function for existing code
function switchUploadMode(mode) {
  const toggleBtn = document.getElementById('uploadModeToggle');
  const dropZoneText = document.getElementById('dropZoneText');

  window.currentUploadMode = mode;
  currentUploadMode = mode;

  if (mode === 'files') {
    if (toggleBtn) {
      toggleBtn.innerHTML = ' Files';
      toggleBtn.title = 'Currently in Files mode - Click to switch to Folders';
    }
    if (dropZoneText) dropZoneText.textContent = ' Drag & Drop files here or click to select';
  } else {
    if (toggleBtn) {
      toggleBtn.innerHTML = ' Folders';
      toggleBtn.title = 'Currently in Folders mode - Click to switch to Files';
    }
    if (dropZoneText) dropZoneText.textContent = ' Drag & Drop folders here or click to select';
  }
}

// NEW: Beautiful Sliding Toggle Function
function toggleUploadModeNew() {
  const slider = document.getElementById('uploadModeSlider');
  const filesLabel = document.getElementById('filesLabel');
  const foldersLabel = document.getElementById('foldersLabel');
  const dropZoneText = document.getElementById('dropZoneText');

  if (slider && slider.checked) {
    window.currentUploadMode = 'folder';
    currentUploadMode = 'folder';
    if (filesLabel) filesLabel.classList.remove('active');
    if (foldersLabel) foldersLabel.classList.add('active');
    if (dropZoneText) dropZoneText.textContent = ' Drag & Drop folders here or click to select';
  } else {
    window.currentUploadMode = 'files';
    currentUploadMode = 'files';
    if (foldersLabel) foldersLabel.classList.remove('active');
    if (filesLabel) filesLabel.classList.add('active');
    if (dropZoneText) dropZoneText.textContent = ' Drag & Drop files here or click to select';
  }
}

// Initialize the toggle on page load
document.addEventListener('DOMContentLoaded', function () {
  const oldButton = document.getElementById('uploadModeToggle');
  if (oldButton && oldButton.parentElement) {
    oldButton.parentElement.style.display = 'none';
  }

  const newSliderContainer = document.getElementById('newSliderContainer');
  if (newSliderContainer) {
    newSliderContainer.style.display = 'flex';
  }
});

function handleDropZoneClick() {
  // Check the slider DOM state as primary source of truth
  const slider = document.getElementById('uploadModeSlider');
  const isFolder = (slider && slider.checked) ||
    window.currentUploadMode === 'folder' ||
    (typeof currentUploadMode !== 'undefined' && currentUploadMode === 'folder');

  if (isFolder) {
    const folderInput = document.getElementById('folderInput') || document.getElementById('hiddenFolderInput');
    if (folderInput) {
      // Re-assert folder attributes to ensure browser opens folder picker
      folderInput.setAttribute('webkitdirectory', '');
      folderInput.setAttribute('directory', '');
      folderInput.setAttribute('mozdirectory', '');
      folderInput.value = '';
      folderInput.click();
    }
  } else {
    const fileInput = document.getElementById('fileInput');
    if (fileInput) {
      fileInput.value = '';
      fileInput.click();
    }
  }
}
window.handleDropZoneClick = handleDropZoneClick;

// Main file upload handler
window.handleFiles = function (files) {
  if (!files || !files.length) return;
  // Ensure we only process valid File objects
  const validFiles = Array.from(files).filter(f => f && typeof f === 'object' && typeof f.name === 'string');
  if (validFiles.length === 0) return;

  console.log(' handleFiles called with:', validFiles.length, 'files');

  console.log(' Adding files to upload queue...');
  addToUploadQueue(validFiles);

  showUploadManager();
  startNextUpload();
};

function processSelectedFiles(files, type) {
  if (!files || !files.length) return;
  if (type === 'folder') {
    const folderSet = new Set();
    Array.from(files).forEach(file => {
      if (file && file.webkitRelativePath) {
        const rootFolder = file.webkitRelativePath.split('/')[0];
        folderSet.add(rootFolder);
      }
    });

    const folderCount = folderSet.size;
    const fileCount = files.length;

    if (folderCount > 1) {
      showToast(` Processing ${folderCount} folders with ${fileCount} files...`, 3000);
    } else if (folderCount === 1) {
      const folderName = Array.from(folderSet)[0];
      showToast(` Processing folder "${folderName}" with ${fileCount} files...`, 3000);
    }

    uploadFolder(files);
  } else {
    if (typeof window.handleFiles === 'function') {
      window.handleFiles(files);
    }
  }
}

// Export to window so main-app.js and other scripts can call it directly
window.handleFileSelection = handleFileSelection;

async function uploadFolder(files) {
  if (files.length === 0) {
    showToast(' No files selected!', 3000);
    return;
  }

  const folderGroups = new Map();
  const standaloneFiles = [];

  for (let file of files) {
    if (file.webkitRelativePath) {
      const rootFolder = file.webkitRelativePath.split('/')[0];
      if (!folderGroups.has(rootFolder)) {
        folderGroups.set(rootFolder, []);
      }
      folderGroups.get(rootFolder).push(file);
    } else {
      standaloneFiles.push(file);
    }
  }

  if (folderGroups.size > 1) {
    const uploadPromises = [];
    for (let [folderName, folderFiles] of folderGroups) {
      uploadPromises.push(uploadSingleFolder(folderName, folderFiles));
    }

    try {
      const results = await Promise.all(uploadPromises);
      const successCount = results.filter(r => r && r.success).length;
      const totalFolders = folderGroups.size;

      if (successCount === totalFolders) {
        showToast(` All ${totalFolders} folders uploaded successfully!`, 4000);
      } else {
        showToast(` ${successCount}/${totalFolders} folders uploaded successfully`, 4000);
      }

      if (typeof refreshFileListManually === 'function') {
        refreshFileListManually();
      }
      if (typeof fetchFilesData === 'function' && typeof renderPrototypeFileList === 'function') {
        fetchFilesData().then(function (fd) { renderPrototypeFileList(fd); });
      }
    } catch (error) {
      console.error('Multiple folder upload error:', error);
      showToast(' Multiple folder upload failed!', 4000);
    }
    return;
  }

  const folderName = folderGroups.size === 1 ?
    Array.from(folderGroups.keys())[0] : 'uploaded_folder';
  const folderFiles = folderGroups.size === 1 ?
    Array.from(folderGroups.values())[0] : files;

  await uploadSingleFolder(folderName, folderFiles);
}

async function uploadSingleFolder(folderName, files) {
  const formData = new FormData();
  formData.append('folder_name', folderName);

  const currentDir = (typeof window.getCurrentFolderPath === 'function') ? window.getCurrentFolderPath() : '';
  if (currentDir) {
    formData.append('parent_path', currentDir);
  }

  for (let file of files) {
    const relativePath = file.webkitRelativePath || file.name;
    const pathWithoutRoot = relativePath.includes('/') ? relativePath.substring(relativePath.indexOf('/') + 1) : file.name;
    formData.append('files', file, pathWithoutRoot);
  }

  try {
    const response = await fetch('/upload-folder', {
      method: 'POST',
      body: formData
    });

    const result = await response.json();

    if (result.status === 'success') {
      showToast(` Folder "${folderName}" uploaded successfully! (${result.files_uploaded.length} files)`, 4000);
      if (typeof refreshFileListManually === 'function') {
        refreshFileListManually();
      }
      if (typeof fetchFilesData === 'function' && typeof renderPrototypeFileList === 'function') {
        fetchFilesData().then(function (fd) { renderPrototypeFileList(fd); });
      }
      if (typeof loadFolders === 'function') loadFolders();
      return { success: true, folderName, fileCount: result.files_uploaded.length };
    } else {
      showToast(` Upload failed: ${result.msg}`, 4000);
      return { success: false, folderName, error: result.msg };
    }
  } catch (error) {
    console.error('Folder upload error:', error);
    showToast(` Folder "${folderName}" upload failed!`, 4000);
    return { success: false, folderName, error: error.message };
  }
}

async function loadFolders() {
  try {
    const response = await fetch('/api/folders');
    const result = await response.json();

    if (result.status === 'success') {
      displayFolders(result.folders);
    }
  } catch (error) {
    console.error('Error loading folders:', error);
  }
}

function displayFolders(folders) {
  const folderGrid = document.getElementById('folderGrid');
  const folderCount = document.getElementById('folderCount');

  if (!folderGrid) return;

  if (folders.length === 0) {
    folderGrid.innerHTML = '<p style="color: var(--text-color); text-align: center; padding: 2rem;">No folders uploaded yet.</p>';
    if (folderCount) folderCount.textContent = '(0)';
    return;
  }

  if (folderCount) folderCount.textContent = `(${folders.length})`;

  function escapeHtml(text) {
    if (!text) return '';
    return text
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  folderGrid.innerHTML = folders.map(folder => {
    const escName = escapeHtml(folder.name);
    const attrEscName = escName.replace(/'/g, '&#39;').replace(/"/g, '&quot;');
    const encodedName = encodeURIComponent(folder.name);
    return `
    <div class="file-card">
      <div class="file-icon"></div>
      <div class="file-name" title="${escName}">${escName}</div>
      <div class="file-size">${folder.file_count} files • ${folder.size_formatted}</div>
      <div class="file-actions">
        <a href="/download-folder/${encodedName}" class="download-btn"> Download</a>
        <button onclick="deleteFolder('${attrEscName}')" class="download-btn" style="background-color: #e74c3c;"></button>
      </div>
    </div>
  `;
  }).join('');
}

async function deleteFolder(folderName) {
  try {
    const response = await fetch(`/delete-folder/${encodeURIComponent(folderName)}`, { method: 'POST' });
    const result = await response.json();

    if (result.status === 'success') {
      showToast(` Folder "${folderName}" deleted successfully!`, 3000);
      loadFolders(); // Refresh folder list
    } else {
      showToast(` Failed to delete folder: ${result.msg}`, 4000);
    }
  } catch (error) {
    console.error('Error deleting folder:', error);
    showToast(' Error deleting folder!', 4000);
  }
}

async function refreshFolderList() {
  showToast(' Refreshing folders...', 1000);
  await loadFolders();
}

async function clearAllFolders() {
  try {
    const response = await fetch('/api/folders');
    const result = await response.json();

    if (result.status === 'success' && result.folders.length > 0) {
      for (const folder of result.folders) {
        await fetch(`/delete-folder/${folder.name}`, { method: 'POST' });
      }
      showToast(' All folders cleared!', 3000);
      loadFolders();
    }
  } catch (error) {
    console.error('Error clearing folders:', error);
    showToast(' Error clearing folders!', 4000);
  }
}

// Load folders when page loads
document.addEventListener('DOMContentLoaded', function () {
  setTimeout(loadFolders, 1000);
});

// Mark that the main page loaded successfully (for loading page optimization)
try {
  sessionStorage.setItem('Lanvan_page_loaded_successfully', Date.now().toString());
  // Also set a flag that resources are working
  sessionStorage.setItem('Lanvan_resources_ready', 'true');
} catch (e) {
  // Ignore storage errors
}
