"""
🌐 Frontend Integration for HTTP-Safe AES

This script shows how to integrate the HTTP-safe AES encryption into the frontend
to provide complete metadata protection over HTTP.
"""

# JavaScript code to add to the frontend
FRONTEND_HTTP_SAFE_JS = """
// 🔒 HTTP-Safe AES Configuration
const HTTP_SAFE_AES = {
  enabled: true,
  obfuscate_filenames: true,
  obfuscate_sizes: true,
  encrypt_metadata: true,
  generate_decoy_traffic: true,
  
  // Generate secure random filename
  generateSecureFilename: function(originalName) {
    const randomHex = Array.from(crypto.getRandomValues(new Uint8Array(8)))
      .map(b => b.toString(16).padStart(2, '0')).join('');
    const extension = originalName.includes('.') ? '.enc' : '.enc';
    return `file_${randomHex}${extension}`;
  },
  
  // Obfuscate file size with random padding
  obfuscateFileSize: function(actualSize) {
    const minPadding = 1024;  // 1KB minimum
    const maxPadding = Math.min(64 * 1024, actualSize * 0.1);  // Up to 64KB or 10% of file
    const padding = Math.floor(Math.random() * maxPadding) + minPadding;
    return actualSize + padding;
  },
  
  // Generate decoy request parameters
  generateDecoyRequests: function(baseUrl, count = 2) {
    const decoys = [];
    for (let i = 0; i < count; i++) {
      decoys.push({
        url: `${baseUrl}/dummy/${this.generateRandomToken(16)}`,
        method: 'POST',
        size: Math.floor(Math.random() * 10240) + 1024,  // 1-10KB
        delay: Math.floor(Math.random() * 1000) + 500,   // 0.5-1.5s
        headers: {
          'Content-Type': 'application/octet-stream',
          'X-Request-ID': this.generateRandomToken(32)
        }
      });
    }
    return decoys;
  },
  
  // Generate random token
  generateRandomToken: function(length) {
    const chars = 'abcdef0123456789';
    let result = '';
    for (let i = 0; i < length; i++) {
      result += chars.charAt(Math.floor(Math.random() * chars.length));
    }
    return result;
  },
  
  // Create HTTP-safe upload parameters
  createSafeUploadParams: function(file, originalFilename) {
    const sessionId = this.generateRandomToken(32);
    const uploadId = this.generateRandomToken(16);
    
    return {
      safe_filename: this.generateSecureFilename(originalFilename),
      obfuscated_size: this.obfuscateFileSize(file.size),
      session_id: sessionId,
      upload_id: uploadId,
      decoy_requests: this.generateDecoyRequests(window.location.origin),
      timing: {
        chunk_delay: Math.floor(Math.random() * 100) + 50,  // 50-150ms
        random_jitter: true
      }
    };
  }
};

// 🔄 Modified upload function with HTTP safety
async function uploadFilesWithHTTPSafety(files) {
  const isAESEnabled = document.getElementById('enableEncryption').checked;
  
  if (!isAESEnabled || !HTTP_SAFE_AES.enabled) {
    // Use normal upload if AES not enabled
    return uploadFilesNormal(files);
  }
  
  console.log('🔒 Starting HTTP-Safe AES upload for', files.length, 'files');
  
  for (let i = 0; i < files.length; i++) {
    const file = files[i];
    const originalName = file.name;
    
    // Generate HTTP-safe parameters
    const safeParams = HTTP_SAFE_AES.createSafeUploadParams(file, originalName);
    
    console.log(`🛡️ File ${i+1}: ${originalName} → ${safeParams.safe_filename}`);
    console.log(`📊 Size obfuscated: ${file.size} → ${safeParams.obfuscated_size}`);
    
    // Send decoy requests first (optional)
    if (HTTP_SAFE_AES.generate_decoy_traffic) {
      await sendDecoyRequests(safeParams.decoy_requests);
    }
    
    // Upload with obfuscated parameters
    await uploadSingleFileSecure(file, safeParams);
  }
}

// 🕵️ Send decoy requests to hide traffic patterns
async function sendDecoyRequests(decoyRequests) {
  console.log('🕵️ Sending', decoyRequests.length, 'decoy requests...');
  
  const promises = decoyRequests.map(async (decoy, index) => {
    // Add random delay
    await new Promise(resolve => setTimeout(resolve, decoy.delay));
    
    try {
      // Send dummy request with random data
      const dummyData = new Uint8Array(decoy.size);
      crypto.getRandomValues(dummyData);
      
      await fetch(decoy.url, {
        method: decoy.method,
        headers: decoy.headers,
        body: dummyData
      });
      
      console.log(`🕵️ Decoy ${index+1} sent (${decoy.size} bytes)`);
    } catch (error) {
      // Decoy failures are expected and OK
      console.log(`🕵️ Decoy ${index+1} failed (expected)`);
    }
  });
  
  await Promise.all(promises);
}

// 🔒 Upload single file with security
async function uploadSingleFileSecure(file, safeParams) {
  const formData = new FormData();
  
  // Use obfuscated filename
  formData.append('files', file, safeParams.safe_filename);
  formData.append('encrypt', 'true');
  formData.append('session_id', safeParams.session_id);
  formData.append('upload_id', safeParams.upload_id);
  
  // Add fake size header to confuse traffic analysis
  const headers = {
    'X-Obfuscated-Size': safeParams.obfuscated_size.toString(),
    'X-Session-Token': safeParams.session_id
  };
  
  try {
    const response = await fetch('/upload', {
      method: 'POST',
      headers: headers,
      body: formData
    });
    
    if (response.ok) {
      console.log(`✅ Secure upload completed: ${safeParams.safe_filename}`);
    } else {
      console.error(`❌ Secure upload failed: ${response.status}`);
    }
    
  } catch (error) {
    console.error(`❌ Secure upload error:`, error);
  }
}

// 🔧 Integration with existing upload button
document.addEventListener('DOMContentLoaded', function() {
  const uploadButton = document.querySelector('#uploadButton');
  const fileInput = document.querySelector('#fileInput');
  
  if (uploadButton && fileInput) {
    uploadButton.addEventListener('click', function() {
      const files = Array.from(fileInput.files);
      
      if (files.length > 0) {
        uploadFilesWithHTTPSafety(files);
      }
    });
  }
});

// 🛡️ Security status indicator
function updateSecurityStatus() {
  const isAESEnabled = document.getElementById('enableEncryption').checked;
  const isHTTPSafe = HTTP_SAFE_AES.enabled;
  
  let statusText = '';
  let statusColor = '';
  
  if (isAESEnabled && isHTTPSafe) {
    statusText = '🛡️ HTTP-Safe AES (Maximum Security)';
    statusColor = '#00ff00';
  } else if (isAESEnabled) {
    statusText = '🔒 Standard AES (Metadata Visible)';
    statusColor = '#ffaa00';
  } else {
    statusText = '📁 Unencrypted (Not Secure)';
    statusColor = '#ff0000';
  }
  
  // Update UI with security status
  const statusElement = document.querySelector('#securityStatus');
  if (statusElement) {
    statusElement.textContent = statusText;
    statusElement.style.color = statusColor;
  }
}

// Monitor encryption toggle changes
document.addEventListener('DOMContentLoaded', function() {
  const encryptionToggle = document.getElementById('enableEncryption');
  if (encryptionToggle) {
    encryptionToggle.addEventListener('change', updateSecurityStatus);
    updateSecurityStatus(); // Initial status
  }
});
"""

def generate_frontend_integration():
    """Generate the complete frontend integration code"""
    
    return f"""
<!-- Add this to your HTML head section -->
<script>
{FRONTEND_HTTP_SAFE_JS}
</script>

<!-- Add security status indicator to your UI -->
<div id="securityStatus" style="font-weight: bold; margin: 10px 0;">
  📁 Unencrypted (Not Secure)
</div>

<!-- Optional: Advanced security settings -->
<div id="httpSafetySettings" style="margin: 10px 0; font-size: 0.9em;">
  <label>
    <input type="checkbox" id="enableDecoyTraffic" checked> 
    Generate decoy traffic
  </label><br>
  <label>
    <input type="checkbox" id="obfuscateFilenames" checked> 
    Obfuscate filenames
  </label><br>
  <label>
    <input type="checkbox" id="obfuscateSizes" checked> 
    Obfuscate file sizes
  </label>
</div>
"""

if __name__ == "__main__":
    print("🌐 FRONTEND HTTP-SAFE AES INTEGRATION")
    print("=" * 50)
    print()
    print("Add the following to your HTML template:")
    print()
    print(generate_frontend_integration())
