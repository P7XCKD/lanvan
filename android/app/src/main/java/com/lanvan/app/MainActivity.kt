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
    private lateinit var toggleButton: Button
    private lateinit var statusText: TextView
    private lateinit var qrContainer: LinearLayout
    private lateinit var inactiveContainer: LinearLayout
    private lateinit var imgQrCode: ImageView
    private lateinit var txtIpLink: TextView
    private lateinit var txtMdnsLink: TextView
    
    private var isServerRunning = false
    private var currentServerUrl = ""

    private val statusReceiver = object : BroadcastReceiver() {
        override fun onReceive(context: Context?, intent: Intent?) {
            val status = intent?.getStringExtra(ServerService.EXTRA_STATUS) ?: return
            handleStatusUpdate(status)
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        // Initialize UI Elements
        toggleButton = findViewById(R.id.btn_toggle)
        statusText = findViewById(R.id.txt_status)
        val copyLogsButton: Button = findViewById(R.id.btn_copy_logs)

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

        // Initialize Python engine
        if (!Python.isStarted()) {
            Python.start(AndroidPlatform(this))
        }

        toggleButton.setOnClickListener {
            if (isServerRunning) {
                stopServerService()
            } else {
                startServerService()
            }
        }

        copyLogsButton.setOnClickListener {
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
            android.widget.Toast.makeText(this, "Logs copied to clipboard!", android.widget.Toast.LENGTH_SHORT).show()
        }

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
            handleStatusUpdate(ServerService.STATUS_RUNNING)
            // Update URL from the static value
            if (ServerService.currentUrl.isNotEmpty()) {
                currentServerUrl = ServerService.currentUrl
                statusText.text = "Server active: $currentServerUrl"
            }
        }
    }

    override fun onPause() {
        super.onPause()
        unregisterReceiver(statusReceiver)
    }

    private fun startServerService() {
        statusText.text = "Starting server..."
        val intent = Intent(this, ServerService::class.java).apply {
            action = ServerService.ACTION_START
            putExtra("PORT", "5000")
            putExtra("USE_HTTPS", "false")
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
        when (status) {
            ServerService.STATUS_RUNNING -> {
                isServerRunning = true
                toggleButton.text = "Stop Server"
                toggleButton.backgroundTintList = android.content.res.ColorStateList.valueOf(0xFFE74C3C.toInt()) // Red color
                
                val lanIp = getLocalIpAddress()
                currentServerUrl = "http://$lanIp:5000"
                statusText.text = "Server active: $currentServerUrl"

                txtIpLink.text = currentServerUrl
                
                // Show links and QR container
                inactiveContainer.visibility = View.GONE
                qrContainer.visibility = View.VISIBLE

                // Show mdns link if enabled
                txtMdnsLink.text = "http://lanvan.local:5000"
                txtMdnsLink.visibility = View.VISIBLE

                // Generate QR Bitmap using Python and set to ImageView
                val bitmap = generateQrCodeBitmap(currentServerUrl)
                if (bitmap != null) {
                    imgQrCode.setImageBitmap(bitmap)
                }
            }
            ServerService.STATUS_STOPPED -> {
                isServerRunning = false
                currentServerUrl = ""
                toggleButton.text = "Start Server"
                toggleButton.backgroundTintList = android.content.res.ColorStateList.valueOf(0xFF6200EE.toInt()) // Purple color
                statusText.text = "Server is inactive."
                
                // Toggle visibility containers
                qrContainer.visibility = View.GONE
                inactiveContainer.visibility = View.VISIBLE
            }
            ServerService.STATUS_ERROR -> {
                isServerRunning = false
                currentServerUrl = ""
                toggleButton.text = "Start Server"
                toggleButton.backgroundTintList = android.content.res.ColorStateList.valueOf(0xFF6200EE.toInt())
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
}
