package com.lanvan.app

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.graphics.Bitmap
import android.net.ConnectivityManager
import android.net.Network
import android.net.NetworkCapabilities
import android.net.NetworkRequest
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.os.PowerManager
import android.provider.Settings
import android.view.View
import android.widget.Button
import android.widget.EditText
import android.widget.ImageButton
import android.widget.ImageView
import android.widget.LinearLayout
import android.widget.RadioButton
import android.widget.TextView
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import androidx.appcompat.widget.SwitchCompat
import androidx.core.content.ContextCompat
import androidx.core.content.FileProvider
import com.chaquo.python.Python
import com.chaquo.python.android.AndroidPlatform
import com.google.android.material.bottomsheet.BottomSheetDialog
import java.io.File
import java.net.Inet4Address
import java.net.NetworkInterface
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

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

    // Main Activity UI Binding References
    private lateinit var headerStatusPill: LinearLayout
    private lateinit var statusDot: View
    private lateinit var headerStatusText: TextView
    private lateinit var btnSettings: ImageButton

    private lateinit var cardStoppedNetWarning: LinearLayout
    private lateinit var cardStopped: LinearLayout
    private lateinit var btnStartServer: Button

    private lateinit var cardRunningConnected: LinearLayout
    private lateinit var imgQrCode: ImageView
    private lateinit var txtIpLink: TextView
    private lateinit var btnCopyAddress: Button
    private lateinit var btnStopServer: Button

    private lateinit var cardRunningDegraded: LinearLayout
    private lateinit var btnReconnectWifi: Button

    private lateinit var txtStorageUsage: TextView
    private lateinit var btnManageStorage: Button
    private lateinit var cardSupportLanvan: LinearLayout
    private lateinit var btnSupportLanvan: Button

    private var connectivityManager: ConnectivityManager? = null
    private var networkCallback: ConnectivityManager.NetworkCallback? = null

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        // Request notifications permission (Android 13+)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            val permission = android.Manifest.permission.POST_NOTIFICATIONS
            if (ContextCompat.checkSelfPermission(this, permission) != android.content.pm.PackageManager.PERMISSION_GRANTED) {
                androidx.core.app.ActivityCompat.requestPermissions(this, arrayOf(permission), 101)
            }
        }

        // Initialize Python engine
        if (!Python.isStarted()) {
            Python.start(AndroidPlatform(this))
        }

        // Bind UI Elements
        headerStatusPill = findViewById(R.id.header_status_pill)
        statusDot = findViewById(R.id.status_dot)
        headerStatusText = findViewById(R.id.header_status_text)
        btnSettings = findViewById(R.id.btn_settings)

        cardStoppedNetWarning = findViewById(R.id.card_stopped_net_warning)
        cardStopped = findViewById(R.id.card_stopped)
        btnStartServer = findViewById(R.id.btn_start_server)

        cardRunningConnected = findViewById(R.id.card_running_connected)
        imgQrCode = findViewById(R.id.img_qrcode)
        txtIpLink = findViewById(R.id.txt_ip_link)
        btnCopyAddress = findViewById(R.id.btn_copy_address)
        btnStopServer = findViewById(R.id.btn_stop_server)

        cardRunningDegraded = findViewById(R.id.card_running_degraded)
        btnReconnectWifi = findViewById(R.id.btn_reconnect_wifi)

        txtStorageUsage = findViewById(R.id.txt_storage_usage)
        btnManageStorage = findViewById(R.id.btn_manage_storage)
        cardSupportLanvan = findViewById(R.id.card_support_lanvan)
        btnSupportLanvan = findViewById(R.id.btn_support_lanvan)

        val sharedPrefs = getSharedPreferences("lanvan_prefs", Context.MODE_PRIVATE)

        // Wire Main Screen Buttons
        btnStartServer.setOnClickListener {
            if (currentState == ServerState.STOPPED) {
                currentState = ServerState.STARTING
                btnStartServer.isEnabled = false
                btnStartServer.text = "Starting..."
                val useHttps = sharedPrefs.getBoolean("use_https", false)
                startServerService(useHttps)
            }
        }

        btnStopServer.setOnClickListener {
            if (currentState == ServerState.RUNNING) {
                currentState = ServerState.STOPPING
                btnStopServer.isEnabled = false
                btnStopServer.text = "Stopping..."
                stopServerService()
            }
        }

        btnCopyAddress.setOnClickListener {
            if (currentServerUrl.isNotEmpty()) {
                val clipboard = getSystemService(Context.CLIPBOARD_SERVICE) as android.content.ClipboardManager
                val clip = android.content.ClipData.newPlainText("Lanvan URL", currentServerUrl)
                clipboard.setPrimaryClip(clip)

                btnCopyAddress.text = "Copied!"
                btnCopyAddress.postDelayed({
                    btnCopyAddress.text = "Copy"
                }, 2000)
            }
        }

        btnReconnectWifi.setOnClickListener {
            try {
                startActivity(Intent(Settings.ACTION_WIFI_SETTINGS))
            } catch (_: Exception) {
                try {
                    startActivity(Intent(Settings.ACTION_SETTINGS))
                } catch (_: Exception) {
                    Toast.makeText(this, "Could not open network settings.", Toast.LENGTH_SHORT).show()
                }
            }
        }

        btnManageStorage.setOnClickListener {
            openStorageManagementSheet()
        }

        btnSupportLanvan.setOnClickListener {
            openSupportLanvanSheet()
        }

        btnSettings.setOnClickListener {
            openSettingsSheet()
        }

        // Click listeners to open server URL in browser
        val openBrowserListener = View.OnClickListener {
            if (currentServerUrl.isNotEmpty()) {
                val browserIntent = Intent(Intent.ACTION_VIEW, Uri.parse(currentServerUrl))
                startActivity(browserIntent)
            }
        }
        imgQrCode.setOnClickListener(openBrowserListener)
        txtIpLink.setOnClickListener(openBrowserListener)

        setupNetworkCallback()
        updateStorageUsage()
    }

    override fun onResume() {
        super.onResume()
        val filter = IntentFilter(ServerService.ACTION_STATUS_CHANGE)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            registerReceiver(statusReceiver, filter, RECEIVER_EXPORTED)
        } else {
            registerReceiver(statusReceiver, filter)
        }

        if (ServerService.isRunning) {
            currentState = ServerState.RUNNING
            handleStatusUpdate(ServerService.STATUS_RUNNING)
        } else {
            currentState = ServerState.STOPPED
            handleStatusUpdate(ServerService.STATUS_STOPPED)
        }

        updateStorageUsage()
    }

    override fun onPause() {
        super.onPause()
        try {
            unregisterReceiver(statusReceiver)
        } catch (_: Exception) {}
    }

    override fun onDestroy() {
        super.onDestroy()
        networkCallback?.let {
            connectivityManager?.unregisterNetworkCallback(it)
        }
    }

    private fun setupNetworkCallback() {
        connectivityManager = getSystemService(Context.CONNECTIVITY_SERVICE) as ConnectivityManager
        networkCallback = object : ConnectivityManager.NetworkCallback() {
            override fun onAvailable(network: Network) {
                runOnUiThread {
                    if (currentState == ServerState.RUNNING) {
                        handleStatusUpdate(ServerService.STATUS_RUNNING)
                    }
                }
            }

            override fun onLost(network: Network) {
                runOnUiThread {
                    if (currentState == ServerState.RUNNING) {
                        handleStatusUpdate(ServerService.STATUS_RUNNING)
                    }
                }
            }
        }
        val request = NetworkRequest.Builder()
            .addCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET)
            .build()
        connectivityManager?.registerNetworkCallback(request, networkCallback!!)
    }

    private fun startServerService(useHttps: Boolean) {
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
        val intent = Intent(this, ServerService::class.java).apply {
            action = ServerService.ACTION_STOP
        }
        startService(intent)

        val sharedPrefs = getSharedPreferences("lanvan_prefs", Context.MODE_PRIVATE)
        if (sharedPrefs.getBoolean("auto_clear_storage", false)) {
            clearStorageData()
            updateStorageUsage()
        }
    }

    private fun updateSupportCardVisibility() {
        val lanIp = getLocalIpAddress()
        val isStoppedAndConnected = (currentState == ServerState.STOPPED && lanIp != "127.0.0.1")
        cardSupportLanvan.visibility = if (isStoppedAndConnected) View.VISIBLE else View.GONE
    }

    private fun handleStatusUpdate(status: String) {
        when (status) {
            ServerService.STATUS_RUNNING -> {
                currentState = ServerState.RUNNING
                btnStartServer.isEnabled = true
                btnStartServer.text = "Start Lanvan"
                btnStopServer.isEnabled = true
                btnStopServer.text = "Stop Lanvan"

                cardStoppedNetWarning.visibility = View.GONE

                val lanIp = getLocalIpAddress()
                if (lanIp == "127.0.0.1") {
                    // DEGRADED STATE: Server is running but network is disconnected
                    currentServerUrl = ""

                    // Header pill = Unavailable (Amber)
                    headerStatusText.text = "Unavailable"
                    headerStatusText.setTextColor(ContextCompat.getColor(this, R.color.warning_amber))
                    statusDot.setBackgroundResource(R.drawable.bg_dot_warning)
                    statusDot.backgroundTintList = null

                    cardStopped.visibility = View.GONE
                    cardRunningConnected.visibility = View.GONE
                    cardRunningDegraded.visibility = View.VISIBLE
                } else {
                    // NORMAL RUNNING STATE: Network available
                    headerStatusText.text = "Running"
                    headerStatusText.setTextColor(ContextCompat.getColor(this, R.color.primary_accent_blue))
                    statusDot.setBackgroundResource(R.drawable.bg_dot_running)
                    statusDot.backgroundTintList = null

                    val serviceUrl = ServerService.currentUrl ?: ""
                    val scheme = if (serviceUrl.startsWith("https")) "https" else "http"
                    val port = ServerService.currentPort
                    currentServerUrl = "$scheme://$lanIp:$port"

                    txtIpLink.text = currentServerUrl

                    val bitmap = generateQrCodeBitmap(currentServerUrl)
                    if (bitmap != null) {
                        imgQrCode.setImageBitmap(bitmap)
                    }

                    cardStopped.visibility = View.GONE
                    cardRunningDegraded.visibility = View.GONE
                    cardRunningConnected.visibility = View.VISIBLE
                }
            }
            ServerService.STATUS_STOPPED, ServerService.STATUS_ERROR -> {
                currentState = ServerState.STOPPED
                currentServerUrl = ""

                btnStartServer.isEnabled = true
                btnStartServer.text = "Start Lanvan"
                btnStopServer.isEnabled = true
                btnStopServer.text = "Stop Lanvan"

                // Update Header Status Pill to STOPPED
                headerStatusText.text = "Stopped"
                headerStatusText.setTextColor(ContextCompat.getColor(this, R.color.text_muted))
                statusDot.setBackgroundResource(R.drawable.bg_dot_stopped)
                statusDot.backgroundTintList = null

                cardRunningConnected.visibility = View.GONE
                cardRunningDegraded.visibility = View.GONE
                cardStopped.visibility = View.VISIBLE

                val lanIp = getLocalIpAddress()
                if (lanIp == "127.0.0.1") {
                    cardStoppedNetWarning.visibility = View.VISIBLE
                } else {
                    cardStoppedNetWarning.visibility = View.GONE
                }
            }
        }

        updateSupportCardVisibility()
    }

    private fun generateQrCodeBitmap(data: String): Bitmap? {
        try {
            val py = Python.getInstance()
            val module = py.getModule("start_server")
            val matrixList = module.callAttr("get_qr_matrix", data).asList()

            val size = matrixList.size
            val scale = 8
            val width = size * scale
            val bitmap = Bitmap.createBitmap(width, width, Bitmap.Config.ARGB_8888)

            for (y in 0 until size) {
                val row = matrixList[y].asList()
                for (x in 0 until size) {
                    val isBlack = row[x].toBoolean()
                    val color = if (isBlack) 0xFF000000.toInt() else 0xFFFFFFFF.toInt()
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
            txtStorageUsage.text = String.format(Locale.US, "%.2f MB", totalMB)
        } catch (_: Exception) {
            txtStorageUsage.text = "0.00 MB"
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

    private fun getDirSize(dir: File): Long {
        var size: Long = 0
        if (dir.exists()) {
            val files = dir.listFiles()
            if (files != null) {
                for (file in files) {
                    size += if (file.isDirectory) getDirSize(file) else file.length()
                }
            }
        }
        return size
    }

    private fun clearStorageData() {
        try {
            Thread {
                try {
                    val url = java.net.URL("http://127.0.0.1:5000/clear")
                    val conn = url.openConnection() as java.net.HttpURLConnection
                    conn.requestMethod = "POST"
                    conn.connectTimeout = 1000
                    conn.readTimeout = 1000
                    conn.responseCode
                    conn.disconnect()
                } catch (_: Exception) {}
                try {
                    val url = java.net.URL("http://127.0.0.1:5000/api/clipboard/clear")
                    val conn = url.openConnection() as java.net.HttpURLConnection
                    conn.requestMethod = "DELETE"
                    conn.connectTimeout = 1000
                    conn.readTimeout = 1000
                    conn.responseCode
                    conn.disconnect()
                } catch (_: Exception) {}
            }.start()

            val uploadsDir = File(filesDir, "data/uploads")
            if (uploadsDir.exists()) deleteContents(uploadsDir)

            val tempChunksDir = File(filesDir, "data/temp_chunks")
            if (tempChunksDir.exists()) deleteContents(tempChunksDir)

            val dataDir = File(filesDir, "data")
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

    private fun deleteContents(dir: File) {
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

    // =========================================================================
    // SETTINGS BOTTOM SHEETS
    // =========================================================================

    private fun openSettingsSheet() {
        val dialog = BottomSheetDialog(this, R.style.LanvanBottomSheetDialog)
        val view = layoutInflater.inflate(R.layout.sheet_settings, null)
        dialog.setContentView(view)

        val btnClose = view.findViewById<ImageButton>(R.id.btn_close_settings)
        val rowProtocol = view.findViewById<LinearLayout>(R.id.row_connection_protocol)
        val txtProtocolSummary = view.findViewById<TextView>(R.id.txt_protocol_summary)
        val rowSecurity = view.findViewById<LinearLayout>(R.id.row_dangerous_file_protection)
        val txtSecuritySummary = view.findViewById<TextView>(R.id.txt_security_summary)
        val rowBackground = view.findViewById<LinearLayout>(R.id.row_background_operation)
        val txtBackgroundSummary = view.findViewById<TextView>(R.id.txt_background_summary)
        val btnFeedback = view.findViewById<Button>(R.id.btn_open_feedback)

        val sharedPrefs = getSharedPreferences("lanvan_prefs", Context.MODE_PRIVATE)

        // Update summaries
        val useHttps = sharedPrefs.getBoolean("use_https", false)
        txtProtocolSummary.text = if (useHttps) "HTTPS · Encrypted" else "HTTP · Default"

        val blockHttp = sharedPrefs.getBoolean("block_dangerous_http", false)
        txtSecuritySummary.text = "HTTP: ${if (blockHttp) "On" else "Off"} · HTTPS: On"

        val pm = getSystemService(Context.POWER_SERVICE) as PowerManager
        val isExempted = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
            pm.isIgnoringBatteryOptimizations(packageName)
        } else true
        txtBackgroundSummary.text = if (isExempted) "Allowed" else "Restricted"
        txtBackgroundSummary.setTextColor(ContextCompat.getColor(this, if (isExempted) R.color.primary_accent_blue else R.color.warning_amber))

        btnClose.setOnClickListener { dialog.dismiss() }

        rowProtocol.setOnClickListener {
            dialog.dismiss()
            openConnectionProtocolSheet()
        }

        rowSecurity.setOnClickListener {
            dialog.dismiss()
            openDangerousFileProtectionSheet()
        }

        rowBackground.setOnClickListener {
            dialog.dismiss()
            openBackgroundOperationSheet()
        }

        btnFeedback.setOnClickListener {
            dialog.dismiss()
            openSendFeedbackSheet()
        }

        dialog.show()
    }

    private fun openConnectionProtocolSheet() {
        val dialog = BottomSheetDialog(this, R.style.LanvanBottomSheetDialog)
        val view = layoutInflater.inflate(R.layout.sheet_connection_protocol, null)
        dialog.setContentView(view)

        val btnClose = view.findViewById<ImageButton>(R.id.btn_close_protocol)
        val cardHttp = view.findViewById<LinearLayout>(R.id.card_option_http)
        val radioHttp = view.findViewById<RadioButton>(R.id.radio_http)
        val cardHttps = view.findViewById<LinearLayout>(R.id.card_option_https)
        val radioHttps = view.findViewById<RadioButton>(R.id.radio_https)

        val sharedPrefs = getSharedPreferences("lanvan_prefs", Context.MODE_PRIVATE)
        val currentHttps = sharedPrefs.getBoolean("use_https", false)

        radioHttp.isChecked = !currentHttps
        radioHttps.isChecked = currentHttps

        btnClose.setOnClickListener { dialog.dismiss() }

        val selectProtocol = { isHttps: Boolean ->
            if (currentHttps != isHttps) {
                sharedPrefs.edit().putBoolean("use_https", isHttps).apply()
                if (currentState == ServerState.RUNNING) {
                    currentState = ServerState.STOPPING
                    stopServerService()
                }
            }
            dialog.dismiss()
        }

        cardHttp.setOnClickListener { selectProtocol(false) }
        cardHttps.setOnClickListener { selectProtocol(true) }

        dialog.show()
    }

    private fun openDangerousFileProtectionSheet() {
        val dialog = BottomSheetDialog(this, R.style.LanvanBottomSheetDialog)
        val view = layoutInflater.inflate(R.layout.sheet_dangerous_file_protection, null)
        dialog.setContentView(view)

        val btnClose = view.findViewById<ImageButton>(R.id.btn_close_security)
        val switchHttp = view.findViewById<SwitchCompat>(R.id.switch_block_http)
        val switchHttps = view.findViewById<SwitchCompat>(R.id.switch_block_https)

        val sharedPrefs = getSharedPreferences("lanvan_prefs", Context.MODE_PRIVATE)
        switchHttp.isChecked = sharedPrefs.getBoolean("block_dangerous_http", false)

        switchHttp.setOnCheckedChangeListener { _, isChecked ->
            sharedPrefs.edit().putBoolean("block_dangerous_http", isChecked).apply()
        }

        switchHttps.isChecked = true
        switchHttps.isEnabled = false

        btnClose.setOnClickListener { dialog.dismiss() }
        dialog.show()
    }

    private fun openBackgroundOperationSheet() {
        val dialog = BottomSheetDialog(this, R.style.LanvanBottomSheetDialog)
        val view = layoutInflater.inflate(R.layout.sheet_background_operation, null)
        dialog.setContentView(view)

        val btnClose = view.findViewById<ImageButton>(R.id.btn_close_background)
        val txtTitle = view.findViewById<TextView>(R.id.txt_background_detail_title)
        val txtDesc = view.findViewById<TextView>(R.id.txt_background_detail_desc)
        val btnConfigure = view.findViewById<Button>(R.id.btn_configure_battery)

        val pm = getSystemService(Context.POWER_SERVICE) as PowerManager
        val isExempted = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
            pm.isIgnoringBatteryOptimizations(packageName)
        } else true

        if (isExempted) {
            txtTitle.text = "Allowed"
            txtTitle.setTextColor(ContextCompat.getColor(this, R.color.primary_accent_blue))
            txtDesc.text = "Lanvan is allowed to run continuously in the background without battery restrictions."
        } else {
            txtTitle.text = "Restricted"
            txtTitle.setTextColor(ContextCompat.getColor(this, R.color.warning_amber))
            txtDesc.text = "Background optimization is active. The system may restrict Lanvan when the screen is off."
        }

        btnClose.setOnClickListener { dialog.dismiss() }

        btnConfigure.setOnClickListener {
            val intent = Intent().apply {
                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
                    action = Settings.ACTION_REQUEST_IGNORE_BATTERY_OPTIMIZATIONS
                    data = Uri.parse("package:$packageName")
                } else {
                    action = Settings.ACTION_SETTINGS
                }
            }
            try {
                startActivity(intent)
            } catch (_: Exception) {
                val fallbackIntent = Intent().apply {
                    action = Settings.ACTION_APPLICATION_DETAILS_SETTINGS
                    data = Uri.fromParts("package", packageName, null)
                }
                try {
                    startActivity(fallbackIntent)
                } catch (_: Exception) {
                    Toast.makeText(this, "Could not open background settings.", Toast.LENGTH_SHORT).show()
                }
            }
            dialog.dismiss()
        }

        dialog.show()
    }

    private fun openStorageManagementSheet() {
        val dialog = BottomSheetDialog(this, R.style.LanvanBottomSheetDialog)
        val view = layoutInflater.inflate(R.layout.sheet_storage_management, null)
        dialog.setContentView(view)

        val btnClose = view.findViewById<ImageButton>(R.id.btn_close_storage)
        val txtStorageVal = view.findViewById<TextView>(R.id.txt_storage_sheet_val)
        val btnClearStorage = view.findViewById<Button>(R.id.btn_clear_storage_now)
        val switchAutoclear = view.findViewById<SwitchCompat>(R.id.new_switch_autoclear)

        val sharedPrefs = getSharedPreferences("lanvan_prefs", Context.MODE_PRIVATE)
        val useAutoclear = sharedPrefs.getBoolean("auto_clear_storage", false)
        switchAutoclear.isChecked = useAutoclear

        switchAutoclear.setOnCheckedChangeListener { _, isChecked ->
            sharedPrefs.edit().putBoolean("auto_clear_storage", isChecked).apply()
        }

        val updateVal = {
            val totalBytes = calculateStorageBytes()
            val totalMB = totalBytes.toDouble() / (1024.0 * 1024.0)
            txtStorageVal.text = String.format(Locale.US, "%.2f MB", totalMB)
        }
        updateVal()

        btnClose.setOnClickListener { dialog.dismiss() }

        btnClearStorage.setOnClickListener {
            // Show 3-Second Countdown Storage Clear Confirmation Dialog
            val confirmDialog = BottomSheetDialog(this, R.style.LanvanBottomSheetDialog)
            val confirmView = layoutInflater.inflate(R.layout.sheet_feedback_confirm, null)

            val txtTitle = confirmView.findViewById<TextView>(R.id.txt_feedback_confirm_title)
            val txtMsg = confirmView.findViewById<TextView>(R.id.txt_feedback_confirm_msg)
            val btnConfirmClose = confirmView.findViewById<ImageButton>(R.id.btn_close_feedback_confirm)
            val btnAction = confirmView.findViewById<Button>(R.id.btn_confirm_close_action)

            txtTitle.text = "Clear Storage & Clipboard Data?"
            txtMsg.text = "This will permanently delete all uploaded files and saved clipboard history. This action cannot be undone."
            btnAction.setTextColor(ContextCompat.getColor(this, R.color.danger_red_text))
            btnAction.backgroundTintList = android.content.res.ColorStateList.valueOf(ContextCompat.getColor(this, R.color.danger_red))
            btnAction.isEnabled = false
            btnAction.text = "Clear Data (3s)"

            var count = 3
            val handler = android.os.Handler(android.os.Looper.getMainLooper())
            val runnable = object : Runnable {
                override fun run() {
                    count--
                    if (count > 0) {
                        btnAction.text = "Clear Data (${count}s)"
                        handler.postDelayed(this, 1000)
                    } else {
                        btnAction.text = "Clear Data"
                        btnAction.isEnabled = true
                    }
                }
            }
            handler.postDelayed(runnable, 1000)

            confirmDialog.setOnDismissListener {
                handler.removeCallbacks(runnable)
            }

            btnConfirmClose.setOnClickListener {
                handler.removeCallbacks(runnable)
                confirmDialog.dismiss()
            }

            btnAction.setOnClickListener {
                handler.removeCallbacks(runnable)
                clearStorageData()
                updateVal()
                updateStorageUsage()
                Toast.makeText(this, "Storage and clipboard data cleared!", Toast.LENGTH_SHORT).show()
                confirmDialog.dismiss()
                dialog.dismiss()
            }

            confirmDialog.setContentView(confirmView)
            confirmDialog.show()
        }

        dialog.show()
    }

    private fun openSendFeedbackSheet() {
        val dialog = BottomSheetDialog(this, R.style.LanvanBottomSheetDialog)
        val view = layoutInflater.inflate(R.layout.sheet_send_feedback, null)
        dialog.setContentView(view)

        val btnClose = view.findViewById<ImageButton>(R.id.btn_close_feedback)
        val editBody = view.findViewById<EditText>(R.id.edit_feedback_body)
        val switchDiagnostics = view.findViewById<SwitchCompat>(R.id.switch_include_diagnostics)
        val btnSubmit = view.findViewById<Button>(R.id.btn_submit_feedback)

        btnClose.setOnClickListener { dialog.dismiss() }

        btnSubmit.setOnClickListener {
            val userFeedback = editBody.text.toString().trim()
            val includeDiagnostics = switchDiagnostics.isChecked
            val appVersion = getAppVersionName()

            var reportFileName = ""
            var emailSuccess = false

            if (includeDiagnostics) {
                // Generate Safe Plain-Text Diagnostic Report File
                val timeStamp = SimpleDateFormat("yyyy-MM-dd-HHmmss", Locale.US).format(Date())
                reportFileName = "lanvan-diagnostics-$timeStamp.txt"
                val reportFile = File(cacheDir, reportFileName)

                val sharedPrefs = getSharedPreferences("lanvan_prefs", Context.MODE_PRIVATE)
                val useHttps = sharedPrefs.getBoolean("use_https", false)
                val blockHttp = sharedPrefs.getBoolean("block_dangerous_http", false)
                val pm = getSystemService(Context.POWER_SERVICE) as PowerManager
                val isExempted = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
                    pm.isIgnoringBatteryOptimizations(packageName)
                } else true

                var capturedLogs = ServerService.lastErrorLog
                val logFile = File(filesDir, "lanvan_app.log")
                if (logFile.exists()) {
                    try {
                        val logContent = logFile.readText()
                        capturedLogs = "$capturedLogs\n\n--- persistent lanvan_app.log ---\n$logContent"
                    } catch (e: Exception) {
                        capturedLogs = "$capturedLogs\n\nFailed to read lanvan_app.log: ${e.message}"
                    }
                }

                val reportContent = StringBuilder().apply {
                    appendLine("=== Lanvan Diagnostic Report ===")
                    appendLine("Report Generated: ${SimpleDateFormat("yyyy-MM-dd HH:mm:ss Z", Locale.US).format(Date())}")
                    appendLine("Lanvan Version: $appVersion")
                    appendLine("Android Version: ${Build.VERSION.RELEASE} (API ${Build.VERSION.SDK_INT})")
                    appendLine("Device Model: ${Build.MANUFACTURER} ${Build.MODEL}")
                    appendLine("Server State: ${if (currentState == ServerState.RUNNING) "RUNNING" else "STOPPED"}")
                    appendLine("Network LAN IP: ${getLocalIpAddress()}")
                    appendLine("Connection Protocol: ${if (useHttps) "HTTPS (Encrypted)" else "HTTP (Default)"}")
                    appendLine("Dangerous File Protection (HTTP): ${if (blockHttp) "ON" else "OFF"}")
                    appendLine("Dangerous File Protection (HTTPS): ON (Enforced)")
                    appendLine("Background Operation Access: ${if (isExempted) "Allowed" else "Restricted"}")
                    appendLine("App Storage Usage: ${txtStorageUsage.text}")
                    appendLine()
                    appendLine("=== Application & Server Logs ===")
                    appendLine(if (capturedLogs.trim().isEmpty()) "No logs captured yet." else capturedLogs.trim())
                    appendLine("=== End of Report ===")
                }.toString()

                reportFile.writeText(reportContent)

                val emailBody = """
                    Hello Lanvan team,

                    ${if (userFeedback.isNotEmpty()) userFeedback else "[USER FEEDBACK]"}

                    I've attached a diagnostic report to help investigate this issue.

                    Lanvan version: $appVersion

                    Thank you,
                    Lanvan user
                """.trimIndent()

                val contentUri = FileProvider.getUriForFile(this, "$packageName.fileprovider", reportFile)

                val intent = Intent(Intent.ACTION_SEND).apply {
                    type = "message/rfc822"
                    putExtra(Intent.EXTRA_EMAIL, arrayOf("p7xckd@gmail.com"))
                    putExtra(Intent.EXTRA_SUBJECT, "Lanvan Feedback")
                    putExtra(Intent.EXTRA_TEXT, emailBody)
                    putExtra(Intent.EXTRA_STREAM, contentUri)
                    addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
                }

                try {
                    startActivity(Intent.createChooser(intent, "Send Feedback"))
                    emailSuccess = true
                } catch (_: Exception) {
                    emailSuccess = false
                }
            } else {
                val emailBody = """
                    Hello Lanvan team,

                    ${if (userFeedback.isNotEmpty()) userFeedback else "[USER FEEDBACK]"}

                    Lanvan version: $appVersion

                    Thank you,
                    Lanvan user
                """.trimIndent()

                val intent = Intent(Intent.ACTION_SENDTO).apply {
                    data = Uri.parse("mailto:p7xckd@gmail.com")
                    putExtra(Intent.EXTRA_SUBJECT, "Lanvan Feedback")
                    putExtra(Intent.EXTRA_TEXT, emailBody)
                }

                try {
                    startActivity(intent)
                    emailSuccess = true
                } catch (_: Exception) {
                    val fallbackIntent = Intent(Intent.ACTION_SEND).apply {
                        type = "text/plain"
                        putExtra(Intent.EXTRA_EMAIL, arrayOf("p7xckd@gmail.com"))
                        putExtra(Intent.EXTRA_SUBJECT, "Lanvan Feedback")
                        putExtra(Intent.EXTRA_TEXT, emailBody)
                    }
                    try {
                        startActivity(Intent.createChooser(fallbackIntent, "Send Feedback"))
                        emailSuccess = true
                    } catch (_: Exception) {
                        emailSuccess = false
                    }
                }
            }

            dialog.dismiss()

            // Open Feedback Confirmation Dialog
            openFeedbackConfirmSheet(includeDiagnostics, reportFileName, emailSuccess)
        }

        dialog.show()
    }

    private fun openFeedbackConfirmSheet(isDiagEnabled: Boolean, reportFileName: String, emailOpened: Boolean) {
        val dialog = BottomSheetDialog(this, R.style.LanvanBottomSheetDialog)
        val view = layoutInflater.inflate(R.layout.sheet_feedback_confirm, null)
        dialog.setContentView(view)

        val txtTitle = view.findViewById<TextView>(R.id.txt_feedback_confirm_title)
        val txtMsg = view.findViewById<TextView>(R.id.txt_feedback_confirm_msg)
        val btnClose = view.findViewById<ImageButton>(R.id.btn_close_feedback_confirm)
        val btnAction = view.findViewById<Button>(R.id.btn_confirm_close_action)

        if (emailOpened) {
            txtTitle.text = "Feedback ready"
            if (isDiagEnabled && reportFileName.isNotEmpty()) {
                txtMsg.text = "Your feedback has been added to an email draft.\n\nDiagnostic report created:\n$reportFileName\n\nYour email app should now open."
            } else {
                txtMsg.text = "Your feedback has been added to an email draft.\n\nYour email app should now open."
            }
        } else {
            txtTitle.text = "Email app not available"
            txtMsg.text = "Could not open email app on this device."
        }

        btnClose.setOnClickListener { dialog.dismiss() }
        btnAction.setOnClickListener { dialog.dismiss() }

        dialog.show()
    }

    private fun openSupportLanvanSheet() {
        val dialog = BottomSheetDialog(this, R.style.LanvanBottomSheetDialog)
        val view = layoutInflater.inflate(R.layout.sheet_support_lanvan, null)
        dialog.setContentView(view)

        val btnClose = view.findViewById<ImageButton>(R.id.btn_close_support)
        val tier49 = view.findViewById<LinearLayout>(R.id.tier_card_49)
        val val49 = view.findViewById<TextView>(R.id.txt_tier_val_49)
        val name49 = view.findViewById<TextView>(R.id.txt_tier_name_49)

        val tier159 = view.findViewById<LinearLayout>(R.id.tier_card_159)
        val val159 = view.findViewById<TextView>(R.id.txt_tier_val_159)
        val name159 = view.findViewById<TextView>(R.id.txt_tier_name_159)

        val tier399 = view.findViewById<LinearLayout>(R.id.tier_card_399)
        val val399 = view.findViewById<TextView>(R.id.txt_tier_val_399)
        val name399 = view.findViewById<TextView>(R.id.txt_tier_name_399)

        val btnConfirm = view.findViewById<Button>(R.id.btn_confirm_support)

        val selectTier = { selected: Int ->
            val activeColor = ContextCompat.getColor(this, R.color.primary_accent_blue)
            val mutedColor = ContextCompat.getColor(this, R.color.text_muted)
            val secondaryColor = ContextCompat.getColor(this, R.color.text_secondary)

            val49.setTextColor(if (selected == 49) activeColor else secondaryColor)
            name49.setTextColor(if (selected == 49) activeColor else mutedColor)

            val159.setTextColor(if (selected == 159) activeColor else secondaryColor)
            name159.setTextColor(if (selected == 159) activeColor else mutedColor)

            val399.setTextColor(if (selected == 399) activeColor else secondaryColor)
            name399.setTextColor(if (selected == 399) activeColor else mutedColor)
        }

        tier49.setOnClickListener { selectTier(49) }
        tier159.setOnClickListener { selectTier(159) }
        tier399.setOnClickListener { selectTier(399) }

        btnClose.setOnClickListener { dialog.dismiss() }

        btnConfirm.setOnClickListener {
            Toast.makeText(this, "Thank you for supporting Lanvan!", Toast.LENGTH_SHORT).show()
            dialog.dismiss()
        }

        dialog.show()
    }

    private fun getAppVersionName(): String {
        return try {
            val pInfo = packageManager.getPackageInfo(packageName, 0)
            pInfo.versionName ?: "1.0.0"
        } catch (_: Exception) {
            "1.0.0"
        }
    }
}
