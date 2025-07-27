// file-worker.js - Web Worker for large file processing
// Handles file chunking in background thread to prevent UI blocking

self.onmessage = function(e) {
  const { action, data } = e.data;
  
  switch (action) {
    case 'chunk-file':
      chunkFile(data);
      break;
    case 'calculate-hash':
      calculateHash(data);
      break;
    case 'optimize-chunks':
      optimizeChunks(data);
      break;
    default:
      self.postMessage({ error: 'Unknown action' });
  }
};

// Chunk file processing in worker thread
function chunkFile({ file, chunkSize, startIndex = 0 }) {
  try {
    const chunks = [];
    const totalChunks = Math.ceil(file.size / chunkSize);
    
    for (let i = startIndex; i < Math.min(startIndex + 10, totalChunks); i++) {
      const start = i * chunkSize;
      const end = Math.min(start + chunkSize, file.size);
      const chunk = file.slice(start, end);
      
      chunks.push({
        index: i,
        data: chunk,
        size: chunk.size,
        start: start,
        end: end
      });
    }
    
    self.postMessage({
      action: 'chunk-file-result',
      chunks: chunks,
      nextIndex: Math.min(startIndex + 10, totalChunks),
      isComplete: startIndex + 10 >= totalChunks
    });
    
  } catch (error) {
    self.postMessage({ 
      action: 'chunk-file-error',
      error: error.message 
    });
  }
}

// Calculate file hash for integrity checking
function calculateHash({ chunk, algorithm = 'SHA-256' }) {
  // Note: crypto.subtle is not available in Web Workers in all browsers
  // This is a placeholder for hash calculation
  try {
    const reader = new FileReader();
    reader.onload = function(e) {
      // Simple checksum calculation (not cryptographically secure)
      const arrayBuffer = e.target.result;
      const uint8Array = new Uint8Array(arrayBuffer);
      let hash = 0;
      
      for (let i = 0; i < uint8Array.length; i++) {
        hash = ((hash << 5) - hash + uint8Array[i]) & 0xffffffff;
      }
      
      self.postMessage({
        action: 'calculate-hash-result',
        hash: hash.toString(16)
      });
    };
    reader.readAsArrayBuffer(chunk);
    
  } catch (error) {
    self.postMessage({
      action: 'calculate-hash-error',
      error: error.message
    });
  }
}

// Optimize chunk sizes based on connection performance
function optimizeChunks({ fileSize, connectionSpeed, currentChunkSize }) {
  try {
    let optimalChunkSize = currentChunkSize;
    
    // Optimize based on connection speed (MB/s)
    if (connectionSpeed > 50) {
      optimalChunkSize = Math.min(20 * 1024 * 1024, fileSize / 20); // Up to 20MB chunks
    } else if (connectionSpeed > 10) {
      optimalChunkSize = Math.min(10 * 1024 * 1024, fileSize / 50); // Up to 10MB chunks
    } else if (connectionSpeed > 1) {
      optimalChunkSize = Math.min(5 * 1024 * 1024, fileSize / 100); // Up to 5MB chunks
    } else {
      optimalChunkSize = Math.min(1 * 1024 * 1024, fileSize / 200); // Up to 1MB chunks
    }
    
    // Ensure minimum chunk size
    optimalChunkSize = Math.max(512 * 1024, optimalChunkSize); // Minimum 512KB
    
    self.postMessage({
      action: 'optimize-chunks-result',
      optimalChunkSize: Math.floor(optimalChunkSize),
      recommendedParallelism: Math.min(4, Math.max(1, Math.floor(connectionSpeed / 5)))
    });
    
  } catch (error) {
    self.postMessage({
      action: 'optimize-chunks-error',
      error: error.message
    });
  }
}
