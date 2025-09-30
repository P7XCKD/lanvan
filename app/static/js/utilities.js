/* Utilities - Extracted from index.html template */
/* Pure JavaScript functions with no template dependencies */

/**
 * Generate a hash string from a file list for deduplication
 * @param {FileList|Array} files - Files to generate hash from
 * @returns {string} Hash string
 */
function generateFileListHash(files) {
  if (!files || files.length === 0) return '';
  return Array.from(files).map(f => `${f.name}_${f.size}_${f.lastModified}`).join('|');
}

/**
 * Get system resource usage information
 * @returns {Object} Resource usage data
 */
function getSystemResourceUsage() {
  const usage = {
    memory: 50, // Default fallback
    connection: 'unknown'
  };
  
  try {
    // Check memory if available
    if (navigator.deviceMemory) {
      const totalMemory = navigator.deviceMemory * 1024; // Convert to MB
      usage.memory = Math.min(100, (4096 / totalMemory) * 100); // Estimate usage
    }
    
    // Check connection type if available
    if (navigator.connection) {
      usage.connection = navigator.connection.effectiveType || 'unknown';
      usage.downlink = navigator.connection.downlink || 0;
    }
  } catch (e) {
    console.log('Resource monitoring not available');
  }
  
  return usage;
}
