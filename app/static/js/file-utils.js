/* Single Function Extraction - generateFileListHash */
/* Ultra-safe: zero external dependencies */

/**
 * Generate a hash string from a file list for deduplication
 * @param {FileList|Array} files - Files to generate hash from
 * @returns {string} Hash string
 */
function generateFileListHash(files) {
  if (!files || files.length === 0) return '';
  return Array.from(files).map(f => `${f.name}_${f.size}_${f.lastModified}`).join('|');
}
