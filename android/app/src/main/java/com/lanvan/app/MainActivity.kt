package com.lanvan.app

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.view.View
import android.widget.Button
import android.widget.ImageView
import android.widget.LinearLayout
import android.widget.TextView
import androidx.appcompat.app.AppCompatActivity
import com.chaquo.python.android.AndroidPlatform
import com.chaquo.python.Python
import java.net.Inet4Address
import java.net.NetworkInterface

class MainActivity : AppCompatActivity() {
    enum class ServerState {
        STOPPED,
        STARTING,
        RUNNING,
        STOPPING
    }

    private var currentState = ServerState.STOPPED
    private var currentServerUrl = ""
    private val isServerRunning: Boolean
        get() = currentState == ServerState.RUNNING

    private val statusReceiver = object : BroadcastReceiver() {
        override fun onReceive(context: Context?, intent: Intent?) {
            val status = intent?.getStringExtra(ServerService.EXTRA_STATUS) ?: return
            handleStatusUpdate(status)
        }
    }
    private lateinit var toggleButton: Button
    private lateinit var statusText: TextView
    private lateinit var qrContainer: LinearLayout
    private lateinit var inactiveContainer: LinearLayout
    private lateinit var imgQrCode: ImageView
    private lateinit var txtIpLink: TextView
    private lateinit var txtMdnsLink: TextView
    private lateinit var txtStorageUsage: TextView

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        // Initialize UI Elements
        toggleButton = findViewById(R.id.btn_toggle)
        statusText = findViewById(R.id.txt_status)

        // Request notifications permission (required on Android 13+)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            val permission = android.Manifest.permission.POST_NOTIFICATIONS
            if (androidx.core.content.ContextCompat.checkSelfPermission(this, permission) != android.content.pm.PackageManager.PERMISSION_GRANTED) {
                androidx.core.app.ActivityCompat.requestPermissions(this, arrayOf(permission), 101)
            }
        }

        // Note: Battery optimization exemption is not directly requested
        // (Play Store policy restriction). The foreground service already
        // prevents the OS from killing the server during active transfers.

        qrContainer = findViewById(R.id.qr_container)
        inactiveContainer = findViewById(R.id.inactive_container)
        imgQrCode = findViewById(R.id.img_qrcode)
        txtIpLink = findViewById(R.id.txt_ip_link)
        txtMdnsLink = findViewById(R.id.txt_mdns_link)
        txtStorageUsage = findViewById(R.id.txt_storage_usage)
        
        val btnSettings: android.widget.ImageButton = findViewById(R.id.btn_settings)
        val sharedPrefs = getSharedPreferences("lanvan_prefs", Context.MODE_PRIVATE)

        // Initialize Python engine
        if (!Python.isStarted()) {
            Python.start(AndroidPlatform(this))
        }

        toggleButton.setOnClickListener {
            if (currentState == ServerState.RUNNING) {
                currentState = ServerState.STOPPING
                toggleButton.isEnabled = false
                toggleButton.text = "Stopping..."
                stopServerService()
            } else if (currentState == ServerState.STOPPED) {
                currentState = ServerState.STARTING
                toggleButton.isEnabled = false
                toggleButton.text = "Starting..."
                val useHttps = sharedPrefs.getBoolean("use_https", false)
                startServerService(useHttps)
            }
        }

        var activeDialog: androidx.appcompat.app.AlertDialog? = null

        btnSettings.setOnClickListener {
            val builder = androidx.appcompat.app.AlertDialog.Builder(this)
            builder.setTitle("Settings")
            
            val layout = LinearLayout(this).apply {
                orientation = LinearLayout.VERTICAL
                setPadding(50, 40, 50, 40)
            }

            // 1. Battery Optimization Status & Button
            val batteryTitle = TextView(this).apply {
                text = "Battery Optimization Status"
                textSize = 16f
                setTypeface(null, android.graphics.Typeface.BOLD)
                setTextColor(0xFFFFFFFF.toInt())
                layoutParams = LinearLayout.LayoutParams(
                    LinearLayout.LayoutParams.MATCH_PARENT,
                    LinearLayout.LayoutParams.WRAP_CONTENT
                ).apply { bottomMargin = 10 }
            }
            layout.addView(batteryTitle)

            val powerManager = getSystemService(Context.POWER_SERVICE) as android.os.PowerManager
            val isExempted = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
                powerManager.isIgnoringBatteryOptimizations(packageName)
            } else {
                true
            }

            val batteryStatus = TextView(this).apply {
                tag = "battery_status_text"
                text = if (isExempted) "Status: Allowed to run in background (Not Optimized)" else "Status: Background restricted (Optimized)"
                setTextColor(if (isExempted) 0xFF00FF00.toInt() else 0xFFFF9800.toInt())
                textSize = 14f
                layoutParams = LinearLayout.LayoutParams(
                    LinearLayout.LayoutParams.MATCH_PARENT,
                    LinearLayout.LayoutParams.WRAP_CONTENT
                ).apply { bottomMargin = 20 }
            }
            layout.addView(batteryStatus)

            if (!isExempted) {
                val btnBatteryRedirect = Button(this).apply {
                    text = "Configure Background Access"
                    isAllCaps = false
                    textSize = 14f
                    layoutParams = LinearLayout.LayoutParams(
                        LinearLayout.LayoutParams.WRAP_CONTENT,
                        LinearLayout.LayoutParams.WRAP_CONTENT
                    ).apply { bottomMargin = 40 }
                    setOnClickListener {
                        val intent = Intent().apply {
                            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
                                action = android.provider.Settings.ACTION_REQUEST_IGNORE_BATTERY_OPTIMIZATIONS
                                data = Uri.parse("package:$packageName")
                            } else {
                                action = android.provider.Settings.ACTION_SETTINGS
                            }
                        }
                        try {
                            startActivity(intent)
                        } catch (e: Exception) {
                            // Fallback to direct application settings details page which highlights the app
                            val fallbackIntent = Intent().apply {
                                action = android.provider.Settings.ACTION_APPLICATION_DETAILS_SETTINGS
                                data = Uri.fromParts("package", packageName, null)
                            }
                            try {
                                startActivity(fallbackIntent)
                            } catch (fallbackEx: Exception) {
                                android.widget.Toast.makeText(this@MainActivity, "Could not open settings.", android.widget.Toast.LENGTH_LONG).show()
                            }
                        }
                    }
                }
                layout.addView(btnBatteryRedirect)
            }

            // Divider
            val divider = View(this).apply {
                setBackgroundColor(0xFF444444.toInt())
                layoutParams = LinearLayout.LayoutParams(
                    LinearLayout.LayoutParams.MATCH_PARENT,
                    2
                ).apply { bottomMargin = 40 }
            }
            layout.addView(divider)

            // 2. Protocol Switch
            val protocolTitle = TextView(this).apply {
                text = "Server Protocol"
                textSize = 16f
                setTypeface(null, android.graphics.Typeface.BOLD)
                setTextColor(0xFFFFFFFF.toInt())
                layoutParams = LinearLayout.LayoutParams(
                    LinearLayout.LayoutParams.MATCH_PARENT,
                    LinearLayout.LayoutParams.WRAP_CONTENT
                ).apply { bottomMargin = 10 }
            }
            layout.addView(protocolTitle)

            val switchHttps = android.widget.Switch(this).apply {
                text = "Use HTTPS Protocol"
                setTextColor(0xFFBBBBBB.toInt())
                isChecked = sharedPrefs.getBoolean("use_https", false)
                layoutParams = LinearLayout.LayoutParams(
                    LinearLayout.LayoutParams.WRAP_CONTENT,
                    LinearLayout.LayoutParams.WRAP_CONTENT
                ).apply { bottomMargin = 20 }
                setOnCheckedChangeListener { _, isChecked ->
                    val oldVal = sharedPrefs.getBoolean("use_https", false)
                    if (oldVal != isChecked) {
                        sharedPrefs.edit().putBoolean("use_https", isChecked).apply()
                        if (currentState == ServerState.RUNNING) {
                            currentState = ServerState.STOPPING
                            toggleButton.isEnabled = false
                            toggleButton.text = "Stopping..."
                            stopServerService()
                            activeDialog?.dismiss()
                        }
                    }
                }
            }
            layout.addView(switchHttps)

            // Divider 2
            val divider2 = View(this).apply {
                setBackgroundColor(0xFF444444.toInt())
                layoutParams = LinearLayout.LayoutParams(
                    LinearLayout.LayoutParams.MATCH_PARENT,
                    2
                ).apply { bottomMargin = 40 }
            }
            layout.addView(divider2)

            // Security Section: Block Dangerous Files
            val securityTitle = TextView(this).apply {
                text = "Security (Block Dangerous Files)"
                textSize = 16f
                setTypeface(null, android.graphics.Typeface.BOLD)
                setTextColor(0xFFFFFFFF.toInt())
                layoutParams = LinearLayout.LayoutParams(
                    LinearLayout.LayoutParams.MATCH_PARENT,
                    LinearLayout.LayoutParams.WRAP_CONTENT
                ).apply { bottomMargin = 10 }
            }
            layout.addView(securityTitle)

            val isHttpsActive = sharedPrefs.getBoolean("use_https", false)
            val securityDesc = TextView(this).apply {
                text = if (isHttpsActive)
                    "HTTPS Protocol: Dangerous executable blocking is enforced by default."
                else
                    "HTTP Protocol: Block known dangerous executable files (.exe, .bat, .dll, etc.)."
                setTextColor(0xFF888888.toInt())
                textSize = 12f
                layoutParams = LinearLayout.LayoutParams(
                    LinearLayout.LayoutParams.MATCH_PARENT,
                    LinearLayout.LayoutParams.WRAP_CONTENT
                ).apply { bottomMargin = 10 }
            }
            layout.addView(securityDesc)

            val switchBlockDangerous = android.widget.Switch(this).apply {
                text = "Block Dangerous Files (HTTP)"
                setTextColor(0xFFBBBBBB.toInt())
                if (isHttpsActive) {
                    isChecked = true
                    isEnabled = false
                } else {
                    isChecked = sharedPrefs.getBoolean("block_dangerous_http", false)
                    isEnabled = true
                }
                layoutParams = LinearLayout.LayoutParams(
                    LinearLayout.LayoutParams.WRAP_CONTENT,
                    LinearLayout.LayoutParams.WRAP_CONTENT
                ).apply { bottomMargin = 20 }
                setOnCheckedChangeListener { _, isChecked ->
                    if (!isHttpsActive) {
                        sharedPrefs.edit().putBoolean("block_dangerous_http", isChecked).apply()
                    }
                }
            }
            layout.addView(switchBlockDangerous)

            // Divider Sec
            val dividerSec = View(this).apply {
                setBackgroundColor(0xFF444444.toInt())
                layoutParams = LinearLayout.LayoutParams(
                    LinearLayout.LayoutParams.MATCH_PARENT,
                    2
                ).apply { bottomMargin = 40 }
            }
            layout.addView(dividerSec)

            // 3. Storage Management Section
            val storageTitle = TextView(this).apply {
                text = "Storage Management"
                textSize = 16f
                setTypeface(null, android.graphics.Typeface.BOLD)
                setTextColor(0xFFFFFFFF.toInt())
                layoutParams = LinearLayout.LayoutParams(
                    LinearLayout.LayoutParams.MATCH_PARENT,
                    LinearLayout.LayoutParams.WRAP_CONTENT
                ).apply { bottomMargin = 10 }
            }
            layout.addView(storageTitle)

            val txtStorageDialog = TextView(this).apply {
                val totalBytes = calculateStorageBytes()
                val totalMB = totalBytes.toDouble() / (1024.0 * 1024.0)
                text = String.format("Storage Used: %.2f MB", totalMB)
                setTextColor(0xFFBBBBBB.toInt())
                textSize = 14f
                layoutParams = LinearLayout.LayoutParams(
                    LinearLayout.LayoutParams.MATCH_PARENT,
                    LinearLayout.LayoutParams.WRAP_CONTENT
                ).apply { bottomMargin = 15 }
            }
            layout.addView(txtStorageDialog)

            val btnClearStorage = Button(this).apply {
                text = "Clear Storage Data"
                isAllCaps = false
                textSize = 14f
                layoutParams = LinearLayout.LayoutParams(
                    LinearLayout.LayoutParams.WRAP_CONTENT,
                    LinearLayout.LayoutParams.WRAP_CONTENT
                ).apply { bottomMargin = 40 }
                setOnClickListener {
                    val confirmDialog = androidx.appcompat.app.AlertDialog.Builder(this@MainActivity)
                        .setTitle("Clear Storage & Clipboard Data?")
                        .setMessage("This will permanently delete all uploaded files and saved clipboard history. This action cannot be undone.")
                        .setPositiveButton("Clear (3s)", null)
                        .setNegativeButton("Cancel", null)
                        .create()

                    confirmDialog.show()

                    val positiveButton = confirmDialog.getButton(androidx.appcompat.app.AlertDialog.BUTTON_POSITIVE)
                    positiveButton?.isEnabled = false

                    val timer = object : android.os.CountDownTimer(3000, 1000) {
                        override fun onTick(millisUntilFinished: Long) {
                            val secondsLeft = (millisUntilFinished / 1000) + 1
                            positiveButton?.text = "Clear (${secondsLeft}s)"
                        }

                        override fun onFinish() {
                            positiveButton?.text = "Clear Data"
                            positiveButton?.isEnabled = true
                        }
                    }
                    timer.start()

                    confirmDialog.setOnDismissListener {
                        timer.cancel()
                    }

                    positiveButton?.setOnClickListener {
                        clearStorageData()
                        val newBytes = calculateStorageBytes()
                        val newMB = newBytes.toDouble() / (1024.0 * 1024.0)
                        txtStorageDialog.text = String.format("Storage Used: %.2f MB", newMB)
                        updateStorageUsage()
                        android.widget.Toast.makeText(this@MainActivity, "Storage and clipboard data cleared!", android.widget.Toast.LENGTH_SHORT).show()
                        confirmDialog.dismiss()
                    }
                }
            }
            layout.addView(btnClearStorage)

            // Divider Storage
            val dividerStorage = View(this).apply {
                setBackgroundColor(0xFF444444.toInt())
                layoutParams = LinearLayout.LayoutParams(
                    LinearLayout.LayoutParams.MATCH_PARENT,
                    2
                ).apply { bottomMargin = 40 }
            }
            layout.addView(dividerStorage)

            // 3. Copy Logs Button inside settings
            val btnCopyLogsDialog = Button(this).apply {
                text = "Copy Server Logs"
                isAllCaps = false
                textSize = 14f
                layoutParams = LinearLayout.LayoutParams(
                    LinearLayout.LayoutParams.WRAP_CONTENT,
                    LinearLayout.LayoutParams.WRAP_CONTENT
                )
                setOnClickListener {
                    var logs = ServerService.lastErrorLog
                    val logFile = java.io.File(filesDir, "lanvan_app.log")
                    if (logFile.exists()) {
                        try {
                            val logContent = logFile.readText()
                            logs = "$logs\n\n--- persistent lanvan_app.log ---\n$logContent"
                        } catch (e: Exception) {
                            logs = "$logs\n\nFailed to read lanvan_app.log: ${e.message}"
                        }
                    }
                    val clipboard = getSystemService(Context.CLIPBOARD_SERVICE) as android.content.ClipboardManager
                    val clip = android.content.ClipData.newPlainText("Lanvan Logs", if (logs.trim().isEmpty()) "No logs captured yet." else logs)
                    clipboard.setPrimaryClip(clip)
                    android.widget.Toast.makeText(this@MainActivity, "Logs copied to clipboard!", android.widget.Toast.LENGTH_SHORT).show()
                }
            }
            layout.addView(btnCopyLogsDialog)

            builder.setView(layout)
            builder.setPositiveButton("Close", null)
            
            val dialog = builder.create()
            dialog.show()
            dialog.getWindow()?.setBackgroundDrawable(android.graphics.drawable.ColorDrawable(0xFF1E1E1E.toInt()))
            
            activeDialog = dialog
        }

        // Dialog state persistence reference hook
        this.lifecycle.addObserver(object : androidx.lifecycle.LifecycleEventObserver {
            override fun onStateChanged(source: androidx.lifecycle.LifecycleOwner, event: androidx.lifecycle.Lifecycle.Event) {
                if (event == androidx.lifecycle.Lifecycle.Event.ON_RESUME) {
                    activeDialog?.let { dialog ->
                        if (dialog.isShowing) {
                            // Search the entire dialog view hierarchy for the battery status text
                            val statusTxtView = dialog.window?.decorView?.findViewWithTag<TextView>("battery_status_text")
                            statusTxtView?.let { tv ->
                                val pm = getSystemService(Context.POWER_SERVICE) as android.os.PowerManager
                                val currentExempted = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
                                    pm.isIgnoringBatteryOptimizations(packageName)
                                } else {
                                    true
                                }
                                tv.text = if (currentExempted) "Status: Allowed to run in background (Not Optimized)" else "Status: Background restricted (Optimized)"
                                tv.setTextColor(if (currentExempted) 0xFF00FF00.toInt() else 0xFFFF9800.toInt())
                            }
                        }
                    }
                }
            }
        })

        // Click listeners to open links in the system's default web browser
        val openBrowserListener = View.OnClickListener {
            if (currentServerUrl.isNotEmpty()) {
                val browserIntent = Intent(Intent.ACTION_VIEW, Uri.parse(currentServerUrl))
                startActivity(browserIntent)
            }
        }
        imgQrCode.setOnClickListener(openBrowserListener)
        txtIpLink.setOnClickListener(openBrowserListener)
        
        txtMdnsLink.setOnClickListener {
            val mdnsUrl = txtMdnsLink.text.toString()
            if (mdnsUrl.isNotEmpty()) {
                val browserIntent = Intent(Intent.ACTION_VIEW, Uri.parse(mdnsUrl))
                startActivity(browserIntent)
            }
        }
        
        // Update storage tracker
        updateStorageUsage()
    }

    override fun onResume() {
        super.onResume()
        // Register receiver for server status broadcasts
        val filter = IntentFilter(ServerService.ACTION_STATUS_CHANGE)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            registerReceiver(statusReceiver, filter, RECEIVER_EXPORTED)
        } else {
            registerReceiver(statusReceiver, filter)
        }
        
        // Sync UI with current server state immediately (covers relaunch from notification)
        if (ServerService.isRunning) {
            currentState = ServerState.RUNNING
            handleStatusUpdate(ServerService.STATUS_RUNNING)
            // Update URL from the static value
            if (ServerService.currentUrl.isNotEmpty()) {
                currentServerUrl = ServerService.currentUrl
                statusText.setBackgroundColor(0xFF00CC00.toInt())
                statusText.setTextColor(0xFFFFFFFF.toInt())
                statusText.text = "Server active"
            }
        } else {
            currentState = ServerState.STOPPED
        }
        
        // Refresh storage tracker stats on resume
        updateStorageUsage()
    }

    override fun onPause() {
        super.onPause()
        unregisterReceiver(statusReceiver)
    }

    private fun startServerService(useHttps: Boolean) {
        statusText.text = "Starting server..."
        val intent = Intent(this, ServerService::class.java).apply {
            action = ServerService.ACTION_START
            val port = if (useHttps) "5001" else "5000"
            putExtra("PORT", port)
            putExtra("USE_HTTPS", useHttps.toString())
        }
        
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            startForegroundService(intent)
        } else {
            startService(intent)
        }
    }

    private fun stopServerService() {
        statusText.text = "Stopping server..."
        val intent = Intent(this, ServerService::class.java).apply {
            action = ServerService.ACTION_STOP
        }
        startService(intent)
    }

    private fun handleStatusUpdate(status: String) {
        val sharedPrefs = getSharedPreferences("lanvan_prefs", Context.MODE_PRIVATE)
        when (status) {
            ServerService.STATUS_RUNNING -> {
                currentState = ServerState.RUNNING
                toggleButton.isEnabled = true
                toggleButton.text = "Stop Server"
                toggleButton.backgroundTintList = android.content.res.ColorStateList.valueOf(0xFFE74C3C.toInt()) // Red color
                
                val lanIp = getLocalIpAddress()
                
                val serviceUrl = ServerService.currentUrl ?: ""
                val scheme = if (serviceUrl.startsWith("https")) "https" else "http"
                val port = ServerService.currentPort
                currentServerUrl = "$scheme://$lanIp:$port"
                
                // Set green status banner background and simplify text
                statusText.setBackgroundColor(0xFF00CC00.toInt())
                statusText.setTextColor(0xFFFFFFFF.toInt())
                statusText.text = "Server active"
 
                txtIpLink.text = currentServerUrl
                
                // Show links and QR container
                inactiveContainer.visibility = View.GONE
                qrContainer.visibility = View.VISIBLE
 
                // Show mdns link if enabled
                val mdnsPort = ServerService.currentPort
                val mdnsScheme = if (serviceUrl.startsWith("https")) "https" else "http"
                txtMdnsLink.text = "$mdnsScheme://lanvan.local:$mdnsPort"
                txtMdnsLink.visibility = View.VISIBLE
 
                // Generate QR Bitmap using Python and set to ImageView
                val bitmap = generateQrCodeBitmap(currentServerUrl)
                if (bitmap != null) {
                    imgQrCode.setImageBitmap(bitmap)
                }
            }
            ServerService.STATUS_STOPPED -> {
                currentState = ServerState.STOPPED
                currentServerUrl = ""
                
                toggleButton.isEnabled = true
                toggleButton.text = "Start Server"
                toggleButton.backgroundTintList = android.content.res.ColorStateList.valueOf(0xFF6200EE.toInt()) // Purple color
                
                // Reset to standard dark grey banner background
                statusText.setBackgroundColor(0xFF252525.toInt())
                statusText.setTextColor(0xFFBBBBBB.toInt())
                statusText.text = "Server is inactive."
                
                // Toggle visibility containers
                qrContainer.visibility = View.GONE
                inactiveContainer.visibility = View.VISIBLE
            }
            ServerService.STATUS_ERROR -> {
                currentState = ServerState.STOPPED
                currentServerUrl = ""
                toggleButton.isEnabled = true
                toggleButton.text = "Start Server"
                toggleButton.backgroundTintList = android.content.res.ColorStateList.valueOf(0xFF6200EE.toInt())
                
                // Reset to standard dark grey banner background
                statusText.setBackgroundColor(0xFF252525.toInt())
                statusText.setTextColor(0xFFBBBBBB.toInt())
                statusText.text = "Server error occurred during startup."
 
                // Toggle visibility containers
                qrContainer.visibility = View.GONE
                inactiveContainer.visibility = View.VISIBLE
            }
        }
    }

    private fun generateQrCodeBitmap(data: String): android.graphics.Bitmap? {
        try {
            val py = Python.getInstance()
            val module = py.getModule("start_server")
            val matrixList = module.callAttr("get_qr_matrix", data).asList()
            
            val size = matrixList.size
            val scale = 8 // Scale up each QR pixel to 8x8 bitmap pixels for sharp rendering
            val width = size * scale
            val bitmap = android.graphics.Bitmap.createBitmap(width, width, android.graphics.Bitmap.Config.ARGB_8888)
            
            for (y in 0 until size) {
                val row = matrixList[y].asList()
                for (x in 0 until size) {
                    val isBlack = row[x].toBoolean()
                    val color = if (isBlack) 0xFF000000.toInt() else 0xFFFFFFFF.toInt()
                    // Draw a scale x scale block of pixels
                    for (dy in 0 until scale) {
                        for (dx in 0 until scale) {
                            bitmap.setPixel(x * scale + dx, y * scale + dy, color)
                        }
                    }
                }
            }
            return bitmap
        } catch (e: Exception) {
            e.printStackTrace()
        }
        return null
    }

    private fun getLocalIpAddress(): String {
        try {
            val interfaces = NetworkInterface.getNetworkInterfaces()
            while (interfaces.hasMoreElements()) {
                val networkInterface = interfaces.nextElement()
                if (networkInterface.isLoopback || !networkInterface.isUp) continue
                
                val addresses = networkInterface.inetAddresses
                while (addresses.hasMoreElements()) {
                    val addr = addresses.nextElement()
                    if (addr is Inet4Address && !addr.isLoopbackAddress) {
                        val host = addr.hostAddress
                        if (host.startsWith("192.168.") || host.startsWith("10.") || host.startsWith("172.")) {
                            return host
                        }
                    }
                }
            }
        } catch (e: Exception) {
            e.printStackTrace()
        }
        return "127.0.0.1"
    }

    private fun updateStorageUsage() {
        try {
            val totalBytes = calculateStorageBytes()
            val totalMB = totalBytes.toDouble() / (1024.0 * 1024.0)
            txtStorageUsage.text = String.format("App Storage: %.2f MB", totalMB)
        } catch (e: Exception) {
            txtStorageUsage.text = "App Storage: Error calculating"
        }
    }

    private fun calculateStorageBytes(): Long {
        var totalBytes = getDirSize(filesDir)
        val extDir = getExternalFilesDir(null)
        if (extDir != null) {
            totalBytes += getDirSize(extDir)
        }
        return totalBytes
    }

    private fun clearStorageData() {
        try {
            val uploadsDir = java.io.File(filesDir, "data/uploads")
            if (uploadsDir.exists()) deleteContents(uploadsDir)

            val tempChunksDir = java.io.File(filesDir, "data/temp_chunks")
            if (tempChunksDir.exists()) deleteContents(tempChunksDir)

            val dataDir = java.io.File(filesDir, "data")
            if (dataDir.exists()) {
                val files = dataDir.listFiles()
                if (files != null) {
                    for (f in files) {
                        if (f.isFile && (f.name.contains("clipboard") || f.name.endsWith(".json") || f.name.endsWith(".tmp"))) {
                            f.delete()
                        }
                    }
                }
            }

            val extDir = getExternalFilesDir(null)
            if (extDir != null && extDir.exists()) deleteContents(extDir)
        } catch (e: Exception) {
            e.printStackTrace()
        }
    }

    private fun deleteContents(dir: java.io.File) {
        val files = dir.listFiles() ?: return
        for (f in files) {
            if (f.isDirectory) {
                deleteContents(f)
                f.delete()
            } else {
                f.delete()
            }
        }
    }

    private fun getDirSize(dir: java.io.File): Long {
        var size: Long = 0
        if (dir.exists()) {
            val files = dir.listFiles()
            if (files != null) {
                for (file in files) {
                    size += if (file.isDirectory) {
                        getDirSize(file)
                    } else {
                        file.length()
                    }
                }
            }
        }
        return size
    }
}
