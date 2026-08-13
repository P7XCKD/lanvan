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
import android.os.Parcelable
import android.os.PowerManager
import android.provider.Settings
import android.view.View
import android.widget.Button
import android.widget.EditText
import android.widget.ImageButton
import android.widget.ImageView
import android.widget.LinearLayout
import android.widget.RadioButton
import android.graphics.RectF
import android.view.Gravity
import android.widget.FrameLayout
import android.widget.TextView
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import androidx.appcompat.widget.SwitchCompat
import androidx.core.content.ContextCompat
import androidx.core.content.FileProvider
import com.chaquo.python.Python
import com.chaquo.python.android.AndroidPlatform
import com.google.android.material.bottomsheet.BottomSheetDialog
import com.android.billingclient.api.AcknowledgePurchaseParams
import com.android.billingclient.api.BillingClient
import com.android.billingclient.api.BillingClientStateListener
import com.android.billingclient.api.BillingFlowParams
import com.android.billingclient.api.BillingResult
import com.android.billingclient.api.ConsumeParams
import com.android.billingclient.api.ProductDetails
import com.android.billingclient.api.Purchase
import com.android.billingclient.api.PurchasesUpdatedListener
import com.android.billingclient.api.QueryProductDetailsParams
import com.android.billingclient.api.QueryPurchasesParams
import android.util.Log
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

        setupBillingClient()

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
                headerStatusText.text = "Stopping..."
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

        val appTitle = findViewById<TextView>(R.id.app_title)
        appTitle.setOnLongClickListener {
            val sharedPrefs = getSharedPreferences("lanvan_prefs", Context.MODE_PRIVATE)
            sharedPrefs.edit().remove("lanvan_onboarding_completed").apply()
            Toast.makeText(this, "Onboarding reset for testing", Toast.LENGTH_SHORT).show()
            startSpotlightWalkthrough()
            true
        }

        setupNetworkCallback()
        updateStorageUsage()
        initSpotlightWalkthrough()
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
        var totalBytes: Long = 0

        // Only count user data directories (uploads, temp_chunks, clipboard)
        val dataDirs = listOf("data/uploads", "data/temp_chunks", "data/clipboard")
        for (subPath in dataDirs) {
            val dir = File(filesDir, subPath)
            if (dir.exists()) totalBytes += getDirSize(dir)
        }

        // Count loose user data files in data/ root (clipboard json, tmp files)
        val dataRoot = File(filesDir, "data")
        if (dataRoot.exists()) {
            val rootFiles = dataRoot.listFiles()
            if (rootFiles != null) {
                for (f in rootFiles) {
                    if (f.isFile) totalBytes += f.length()
                }
            }
        }

        // Count external files directory (user-accessible storage)
        val extDir = getExternalFilesDir(null)
        if (extDir != null) totalBytes += getDirSize(extDir)

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

    private fun sendHttpRequest(url: java.net.URL, method: String) {
        try {
            val conn = url.openConnection() as java.net.HttpURLConnection
            if (conn is javax.net.ssl.HttpsURLConnection) {
                conn.sslSocketFactory = getTrustAllSSLSocketFactory()
                conn.hostnameVerifier = javax.net.ssl.HostnameVerifier { _, _ -> true }
            }
            conn.requestMethod = method
            conn.connectTimeout = 2000
            conn.readTimeout = 2000
            conn.responseCode
            conn.disconnect()
        } catch (_: Exception) {}
    }

    private fun getTrustAllSSLSocketFactory(): javax.net.ssl.SSLSocketFactory {
        val trustAllCerts = arrayOf<javax.net.ssl.TrustManager>(
            object : javax.net.ssl.X509TrustManager {
                override fun checkClientTrusted(chain: Array<out java.security.cert.X509Certificate>?, authType: String?) {}
                override fun checkServerTrusted(chain: Array<out java.security.cert.X509Certificate>?, authType: String?) {}
                override fun getAcceptedIssuers(): Array<java.security.cert.X509Certificate> = arrayOf()
            }
        )
        val sslContext = javax.net.ssl.SSLContext.getInstance("SSL")
        sslContext.init(null, trustAllCerts, java.security.SecureRandom())
        return sslContext.socketFactory
    }

    private fun clearStorageData() {
        try {
            Thread {
                val sharedPrefs = getSharedPreferences("lanvan_prefs", Context.MODE_PRIVATE)
                val useHttps = sharedPrefs.getBoolean("use_https", false)
                val scheme = if (useHttps) "https" else "http"

                val uri = try { Uri.parse(currentServerUrl) } catch (_: Exception) { null }
                val port = if (uri != null && uri.port != -1) uri.port else 5000

                val targets = listOf(
                    "$scheme://127.0.0.1:$port",
                    "http://127.0.0.1:5000",
                    "https://127.0.0.1:5000",
                    "http://127.0.0.1:5001",
                    "https://127.0.0.1:5001"
                ).distinct()

                for (target in targets) {
                    try {
                        sendHttpRequest(java.net.URL("$target/api/files/clear"), "POST")
                    } catch (_: Exception) {}
                    try {
                        sendHttpRequest(java.net.URL("$target/api/clipboard/clear"), "DELETE")
                    } catch (_: Exception) {}
                }
            }.start()

            try {
                if (com.chaquo.python.Python.isStarted()) {
                    val py = com.chaquo.python.Python.getInstance()
                    py.getModule("app.routers.clipboard").callAttr("clear_clipboard_data_sync")
                }
            } catch (_: Exception) {}

            val uploadsDir = File(filesDir, "data/uploads")
            if (uploadsDir.exists()) deleteContents(uploadsDir)

            val tempChunksDir = File(filesDir, "data/temp_chunks")
            if (tempChunksDir.exists()) deleteContents(tempChunksDir)

            val clipboardDir = File(filesDir, "data/clipboard")
            if (clipboardDir.exists()) deleteContents(clipboardDir)

            val dataDir = File(filesDir, "data")
            if (dataDir.exists()) {
                val files = dataDir.listFiles()
                if (files != null) {
                    for (f in files) {
                        if (f.isDirectory) {
                            deleteContents(f)
                            f.delete()
                        } else if (f.isFile && (f.name.contains("clipboard") || f.name.endsWith(".json") || f.name.endsWith(".tmp"))) {
                            f.delete()
                        }
                    }
                }
            }

            val extDir = getExternalFilesDir(null)
            if (extDir != null && extDir.exists()) deleteContents(extDir)

            val downloadsDir = getExternalFilesDir(android.os.Environment.DIRECTORY_DOWNLOADS)
            if (downloadsDir != null && downloadsDir.exists()) deleteContents(downloadsDir)
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
        val blockHttps = sharedPrefs.getBoolean("block_dangerous_https", true)
        txtSecuritySummary.text = "HTTP: ${if (blockHttp) "On" else "Off"} · HTTPS: ${if (blockHttps) "On" else "Off"}"

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
        val imgRadioHttp = view.findViewById<ImageView>(R.id.img_radio_http)
        val cardHttps = view.findViewById<LinearLayout>(R.id.card_option_https)
        val imgRadioHttps = view.findViewById<ImageView>(R.id.img_radio_https)

        val sharedPrefs = getSharedPreferences("lanvan_prefs", Context.MODE_PRIVATE)
        val currentHttps = sharedPrefs.getBoolean("use_https", false)

        val updateSelectionUI = { isHttps: Boolean ->
            if (isHttps) {
                cardHttps.setBackgroundResource(R.drawable.bg_card_active)
                imgRadioHttps.setImageResource(R.drawable.ic_radio_checked)
                cardHttp.setBackgroundResource(R.drawable.bg_card)
                imgRadioHttp.setImageResource(R.drawable.ic_radio_unchecked)
            } else {
                cardHttp.setBackgroundResource(R.drawable.bg_card_active)
                imgRadioHttp.setImageResource(R.drawable.ic_radio_checked)
                cardHttps.setBackgroundResource(R.drawable.bg_card)
                imgRadioHttps.setImageResource(R.drawable.ic_radio_unchecked)
            }
        }
        updateSelectionUI(currentHttps)

        btnClose.setOnClickListener { dialog.dismiss() }

        val selectProtocol = { isHttps: Boolean ->
            if (currentHttps != isHttps) {
                sharedPrefs.edit().putBoolean("use_https", isHttps).apply()
                if (currentState == ServerState.RUNNING) {
                    currentState = ServerState.STOPPING
                    btnStopServer.isEnabled = false
                    btnStopServer.text = "Stopping..."
                    headerStatusText.text = "Stopping..."
                    stopServerService()
                }
            }
            dialog.dismiss()
        }

        cardHttp.setOnClickListener {
            updateSelectionUI(false)
            selectProtocol(false)
        }
        cardHttps.setOnClickListener {
            updateSelectionUI(true)
            selectProtocol(true)
        }

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
        switchHttps.isChecked = sharedPrefs.getBoolean("block_dangerous_https", true)
        switchHttps.isEnabled = true

        switchHttp.setOnCheckedChangeListener { _, isChecked ->
            sharedPrefs.edit().putBoolean("block_dangerous_http", isChecked).apply()
            updateLiveBlockDangerous()
        }

        switchHttps.setOnCheckedChangeListener { _, isChecked ->
            sharedPrefs.edit().putBoolean("block_dangerous_https", isChecked).apply()
            updateLiveBlockDangerous()
        }

        btnClose.setOnClickListener { dialog.dismiss() }
        dialog.show()
    }

    private fun updateLiveBlockDangerous() {
        try {
            if (com.chaquo.python.Python.isStarted()) {
                val py = com.chaquo.python.Python.getInstance()
                val sharedPrefs = getSharedPreferences("lanvan_prefs", Context.MODE_PRIVATE)
                val useHttps = sharedPrefs.getBoolean("use_https", false)
                val blockHttp = sharedPrefs.getBoolean("block_dangerous_http", false)
                val blockHttps = sharedPrefs.getBoolean("block_dangerous_https", true)
                val activeBlock = if (useHttps) blockHttps else blockHttp
                py.getModule("os").get("environ")?.callAttr("__setitem__", "BLOCK_DANGEROUS", if (activeBlock) "true" else "false")
            }
        } catch (_: Exception) {}
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
            btnConfigure.visibility = View.GONE
        } else {
            txtTitle.text = "Restricted"
            txtTitle.setTextColor(ContextCompat.getColor(this, R.color.warning_amber))
            txtDesc.text = "Background optimization is active. The system may restrict Lanvan when the screen is off."
            btnConfigure.visibility = View.VISIBLE
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
            val confirmView = layoutInflater.inflate(R.layout.dialog_confirm_clear_storage, null)

            val btnCancelClear = confirmView.findViewById<Button>(R.id.btn_cancel_clear)
            val btnConfirmClearData = confirmView.findViewById<Button>(R.id.btn_confirm_clear_data)

            btnConfirmClearData.isEnabled = false
            btnConfirmClearData.text = "Clear (3s)"

            var count = 3
            val handler = android.os.Handler(android.os.Looper.getMainLooper())
            val runnable = object : Runnable {
                override fun run() {
                    count--
                    if (count > 0) {
                        btnConfirmClearData.text = "Clear (${count}s)"
                        handler.postDelayed(this, 1000)
                    } else {
                        btnConfirmClearData.text = "Clear Data"
                        btnConfirmClearData.isEnabled = true
                    }
                }
            }
            handler.postDelayed(runnable, 1000)

            confirmDialog.setOnDismissListener {
                handler.removeCallbacks(runnable)
            }

            btnCancelClear.setOnClickListener {
                handler.removeCallbacks(runnable)
                confirmDialog.dismiss()
            }

            btnConfirmClearData.setOnClickListener {
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
            val emailIntent: Intent

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

                val sanitizedLogs = sanitizeLogContent(capturedLogs)

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
                    appendLine("=== Application & Server Logs (Sanitized) ===")
                    appendLine(if (sanitizedLogs.trim().isEmpty()) "No logs captured yet." else sanitizedLogs.trim())
                    appendLine("=== End of Report ===")
                }.toString()

                reportFile.writeText(reportContent)

                val emailBody = """
                    Hello Lanvan team,

                    ${if (userFeedback.isNotEmpty()) userFeedback else "[Enter Your Feedback Here]"}

                    I've attached a diagnostic report to help investigate this issue.

                    Lanvan version: $appVersion

                    Thank you,
                    Lanvan user
                """.trimIndent()

                val contentUri = FileProvider.getUriForFile(this, "$packageName.fileprovider", reportFile)

                emailIntent = Intent(Intent.ACTION_SEND).apply {
                    type = "*/*"
                    putExtra(Intent.EXTRA_EMAIL, arrayOf("p7xckd@gmail.com"))
                    putExtra(Intent.EXTRA_SUBJECT, "Lanvan Feedback")
                    putExtra(Intent.EXTRA_TEXT, emailBody)
                    putExtra(Intent.EXTRA_STREAM, contentUri)
                    addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
                }
            } else {
                val emailBody = """
                    Hello Lanvan team,

                    ${if (userFeedback.isNotEmpty()) userFeedback else "[Enter Your Feedback Here]"}

                    Lanvan version: $appVersion

                    Thank you,
                    Lanvan user
                """.trimIndent()

                emailIntent = Intent(Intent.ACTION_SENDTO).apply {
                    data = Uri.parse("mailto:p7xckd@gmail.com")
                    putExtra(Intent.EXTRA_SUBJECT, "Lanvan Feedback")
                    putExtra(Intent.EXTRA_TEXT, emailBody)
                }
            }

            dialog.dismiss()

            // Open 3s Feedback Guidance Dialog before triggering share menu
            openFeedbackConfirmSheet(emailIntent, includeDiagnostics, reportFileName)
        }

        dialog.show()
    }

    private fun openFeedbackConfirmSheet(emailIntent: Intent, isDiagEnabled: Boolean, reportFileName: String) {
        val dialog = BottomSheetDialog(this, R.style.LanvanBottomSheetDialog)
        val view = layoutInflater.inflate(R.layout.sheet_feedback_confirm, null)
        dialog.setContentView(view)

        val txtTitle = view.findViewById<TextView>(R.id.txt_feedback_confirm_title)
        val txtMsg = view.findViewById<TextView>(R.id.txt_feedback_confirm_msg)
        val btnClose = view.findViewById<ImageButton>(R.id.btn_close_feedback_confirm)
        val btnAction = view.findViewById<Button>(R.id.btn_confirm_close_action)

        txtTitle.text = "Feedback ready"
        if (isDiagEnabled && reportFileName.isNotEmpty()) {
            txtMsg.text = "Your feedback has been added to an email draft.\n\nDiagnostic report created:\n$reportFileName\n\nYour email app should now open."
        } else {
            txtMsg.text = "Your feedback has been added to an email draft.\n\nYour email app should now open."
        }

        val launchEmailApp = {
            try {
                startActivity(Intent.createChooser(emailIntent, "Send Feedback"))
            } catch (_: Exception) {
                val fallbackIntent = Intent(Intent.ACTION_SEND).apply {
                    type = "text/plain"
                    putExtra(Intent.EXTRA_EMAIL, arrayOf("p7xckd@gmail.com"))
                    putExtra(Intent.EXTRA_SUBJECT, "Lanvan Feedback")
                    putExtra(Intent.EXTRA_TEXT, emailIntent.getStringExtra(Intent.EXTRA_TEXT) ?: "")
                    if (emailIntent.hasExtra(Intent.EXTRA_STREAM)) {
                        putExtra(Intent.EXTRA_STREAM, emailIntent.getParcelableExtra<Parcelable>(Intent.EXTRA_STREAM))
                        addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
                    }
                }
                try {
                    startActivity(Intent.createChooser(fallbackIntent, "Send Feedback"))
                } catch (_: Exception) {
                    Toast.makeText(this, "Could not open email app.", Toast.LENGTH_SHORT).show()
                }
            }
            dialog.dismiss()
        }

        var count = 3
        btnAction.text = "Open Email App (3s)"

        val handler = android.os.Handler(android.os.Looper.getMainLooper())
        val runnable = object : Runnable {
            override fun run() {
                count--
                if (count > 0) {
                    btnAction.text = "Open Email App (${count}s)"
                    handler.postDelayed(this, 1000)
                } else {
                    handler.removeCallbacks(this)
                    launchEmailApp()
                }
            }
        }
        handler.postDelayed(runnable, 1000)

        dialog.setOnDismissListener {
            handler.removeCallbacks(runnable)
        }

        btnClose.setOnClickListener {
            handler.removeCallbacks(runnable)
            dialog.dismiss()
        }

        btnAction.setOnClickListener {
            handler.removeCallbacks(runnable)
            launchEmailApp()
        }

        dialog.show()
    }

    // ==================================================
    // GOOGLE PLAY BILLING IMPLEMENTATION
    // ==================================================

    companion object {
        const val PRODUCT_SUPPORTER = "lanvan_supporter"
        const val PRODUCT_SPONSOR = "lanvan_sponsor"
        const val PRODUCT_PATRON = "lanvan_patron"
    }

    private lateinit var billingClient: BillingClient
    private val productDetailsMap = mutableMapOf<String, ProductDetails>()
    private var isBillingConnected = false

    private val purchasesUpdatedListener = PurchasesUpdatedListener { billingResult, purchases ->
        if (billingResult.responseCode == BillingClient.BillingResponseCode.OK && purchases != null) {
            for (purchase in purchases) {
                handlePurchase(purchase)
            }
        } else if (billingResult.responseCode == BillingClient.BillingResponseCode.USER_CANCELED) {
            Log.i("Billing", "User canceled Google Play purchase flow.")
        } else if (billingResult.responseCode == BillingClient.BillingResponseCode.ITEM_ALREADY_OWNED) {
            Log.i("Billing", "Item already owned. Consuming existing purchase...")
            queryAndConsumeExistingPurchases()
        } else {
            Log.e("Billing", "Purchase failed: ${billingResult.responseCode} (${billingResult.debugMessage})")
            Toast.makeText(this, "Purchase status: ${billingResult.debugMessage}", Toast.LENGTH_SHORT).show()
        }
    }

    private fun setupBillingClient() {
        billingClient = BillingClient.newBuilder(this)
            .setListener(purchasesUpdatedListener)
            .enablePendingPurchases()
            .build()

        billingClient.startConnection(object : BillingClientStateListener {
            override fun onBillingSetupFinished(billingResult: BillingResult) {
                if (billingResult.responseCode == BillingClient.BillingResponseCode.OK) {
                    isBillingConnected = true
                    Log.i("Billing", "BillingClient setup successful.")
                    queryProducts()
                    queryAndConsumeExistingPurchases()
                } else {
                    isBillingConnected = false
                    Log.w("Billing", "BillingClient setup failed: ${billingResult.debugMessage}")
                }
            }

            override fun onBillingServiceDisconnected() {
                isBillingConnected = false
                Log.w("Billing", "BillingClient service disconnected.")
            }
        })
    }

    private fun queryProducts() {
        val productList = listOf(
            QueryProductDetailsParams.Product.newBuilder()
                .setProductId(PRODUCT_SUPPORTER)
                .setProductType(BillingClient.ProductType.INAPP)
                .build(),
            QueryProductDetailsParams.Product.newBuilder()
                .setProductId(PRODUCT_SPONSOR)
                .setProductType(BillingClient.ProductType.INAPP)
                .build(),
            QueryProductDetailsParams.Product.newBuilder()
                .setProductId(PRODUCT_PATRON)
                .setProductType(BillingClient.ProductType.INAPP)
                .build()
        )

        val params = QueryProductDetailsParams.newBuilder()
            .setProductList(productList)
            .build()

        billingClient.queryProductDetailsAsync(params) { billingResult, productDetailsList ->
            if (billingResult.responseCode == BillingClient.BillingResponseCode.OK) {
                productDetailsMap.clear()
                for (details in productDetailsList) {
                    productDetailsMap[details.productId] = details
                    Log.i("Billing", "Loaded Play Product: ${details.productId} -> ${details.oneTimePurchaseOfferDetails?.formattedPrice}")
                }
            } else {
                Log.w("Billing", "Product query returned code: ${billingResult.responseCode}")
            }
        }
    }

    private fun handlePurchase(purchase: Purchase) {
        if (purchase.purchaseState == Purchase.PurchaseState.PURCHASED) {
            val consumeParams = ConsumeParams.newBuilder()
                .setPurchaseToken(purchase.purchaseToken)
                .build()

            billingClient.consumeAsync(consumeParams) { result, _ ->
                if (result.responseCode == BillingClient.BillingResponseCode.OK) {
                    Log.i("Billing", "Purchase successfully consumed & acknowledged!")
                } else if (!purchase.isAcknowledged) {
                    val ackParams = AcknowledgePurchaseParams.newBuilder()
                        .setPurchaseToken(purchase.purchaseToken)
                        .build()
                    billingClient.acknowledgePurchase(ackParams) { _ -> }
                }
                runOnUiThread {
                    showSupportSuccessDialog()
                }
            }
        } else if (purchase.purchaseState == Purchase.PurchaseState.PENDING) {
            Toast.makeText(this, "Support purchase pending confirmation.", Toast.LENGTH_SHORT).show()
        }
    }

    private fun queryAndConsumeExistingPurchases() {
        if (!isBillingConnected) return
        billingClient.queryPurchasesAsync(
            QueryPurchasesParams.newBuilder().setProductType(BillingClient.ProductType.INAPP).build()
        ) { billingResult, purchases ->
            if (billingResult.responseCode == BillingClient.BillingResponseCode.OK) {
                for (purchase in purchases) {
                    if (purchase.purchaseState == Purchase.PurchaseState.PURCHASED) {
                        val consumeParams = ConsumeParams.newBuilder()
                            .setPurchaseToken(purchase.purchaseToken)
                            .build()
                        billingClient.consumeAsync(consumeParams) { _, _ -> }
                    }
                }
            }
        }
    }

    private fun showSupportSuccessDialog() {
        val dialog = BottomSheetDialog(this, R.style.LanvanBottomSheetDialog)
        val view = layoutInflater.inflate(R.layout.sheet_feedback_confirm, null)
        dialog.setContentView(view)

        val txtTitle = view.findViewById<TextView>(R.id.txt_feedback_confirm_title)
        val txtMsg = view.findViewById<TextView>(R.id.txt_feedback_confirm_msg)
        val btnClose = view.findViewById<ImageButton>(R.id.btn_close_feedback_confirm)
        val btnAction = view.findViewById<Button>(R.id.btn_confirm_close_action)

        txtTitle.text = "Thank you for supporting Lanvan"
        txtMsg.text = "Your optional support helps keep Lanvan free and independent for everyone."
        btnAction.text = "Done"

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

        // Dynamically update displayed prices from Google Play ProductDetails if returned
        productDetailsMap[PRODUCT_SUPPORTER]?.oneTimePurchaseOfferDetails?.formattedPrice?.let {
            val49.text = it
        }
        productDetailsMap[PRODUCT_SPONSOR]?.oneTimePurchaseOfferDetails?.formattedPrice?.let {
            val159.text = it
        }
        productDetailsMap[PRODUCT_PATRON]?.oneTimePurchaseOfferDetails?.formattedPrice?.let {
            val399.text = it
        }

        var currentlySelectedTier = 149

        val selectTier = { selected: Int ->
            currentlySelectedTier = selected
            val activeColor = ContextCompat.getColor(this, R.color.primary_accent_blue)
            val primaryTextColor = ContextCompat.getColor(this, R.color.text_primary)
            val mutedColor = ContextCompat.getColor(this, R.color.text_muted)

            val isSelected39 = (selected == 39 || selected == 49)
            tier49.setBackgroundResource(if (isSelected39) R.drawable.bg_card_active else R.drawable.bg_card_sub)
            val49.setTextColor(if (isSelected39) activeColor else primaryTextColor)
            name49.setTextColor(if (isSelected39) activeColor else mutedColor)

            val isSelected149 = (selected == 149 || selected == 159)
            tier159.setBackgroundResource(if (isSelected149) R.drawable.bg_card_active else R.drawable.bg_card_sub)
            val159.setTextColor(if (isSelected149) activeColor else primaryTextColor)
            name159.setTextColor(if (isSelected149) activeColor else mutedColor)

            val isSelected399 = (selected == 399)
            tier399.setBackgroundResource(if (isSelected399) R.drawable.bg_card_active else R.drawable.bg_card_sub)
            val399.setTextColor(if (isSelected399) activeColor else primaryTextColor)
            name399.setTextColor(if (isSelected399) activeColor else mutedColor)
        }
        selectTier(149)

        tier49.setOnClickListener { selectTier(39) }
        tier159.setOnClickListener { selectTier(149) }
        tier399.setOnClickListener { selectTier(399) }

        btnClose.setOnClickListener { dialog.dismiss() }

        btnConfirm.setOnClickListener {
            val targetProductId = when (currentlySelectedTier) {
                39, 49 -> PRODUCT_SUPPORTER
                399 -> PRODUCT_PATRON
                else -> PRODUCT_SPONSOR
            }

            val productDetails = productDetailsMap[targetProductId]
            if (productDetails != null && isBillingConnected) {
                val productDetailsParamsList = listOf(
                    BillingFlowParams.ProductDetailsParams.newBuilder()
                        .setProductDetails(productDetails)
                        .build()
                )
                val billingFlowParams = BillingFlowParams.newBuilder()
                    .setProductDetailsParamsList(productDetailsParamsList)
                    .build()

                val result = billingClient.launchBillingFlow(this, billingFlowParams)
                if (result.responseCode == BillingClient.BillingResponseCode.OK) {
                    dialog.dismiss()
                } else {
                    Toast.makeText(this, "Could not launch Google Play billing flow: ${result.debugMessage}", Toast.LENGTH_SHORT).show()
                }
            } else {
                Log.w("Billing", "Product $targetProductId not yet returned by Play Console or Billing not connected.")
                Toast.makeText(this, "Thank you for supporting Lanvan!", Toast.LENGTH_SHORT).show()
                dialog.dismiss()
            }
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

    // =========================================================================
    // PRODUCTION SPOTLIGHT WALKTHROUGH ONBOARDING
    // =========================================================================

    private var spotlightOverlayContainer: FrameLayout? = null
    private var spotlightOverlayView: SpotlightOverlayView? = null
    private var spotlightTooltipCard: View? = null
    private var txtSpotlightTitle: TextView? = null
    private var txtSpotlightText: TextView? = null
    private var txtSpotlightNote: TextView? = null
    private var btnSpotlightSkip: TextView? = null
    private var btnSpotlightBack: Button? = null
    private var btnSpotlightNext: Button? = null
    private var btnSpotlightFinish: Button? = null
    private var dotStep1: View? = null
    private var dotStep2: View? = null
    private var dotStep3: View? = null
    private var dotStep4: View? = null
    private var dotStep5: View? = null

    private var currentSpotlightStep = 1
    private val TOTAL_SPOTLIGHT_STEPS = 5
    private var preTutorialStatus = ServerService.STATUS_STOPPED

    private data class SpotlightStepConfig(
        val step: Int,
        val title: String,
        val text: String,
        val note: String?,
        val forceRunningPreview: Boolean,
        val targetViewId: Int?,
        val paddingDp: Float,
        val radiusDp: Float
    )

    private fun initSpotlightWalkthrough() {
        spotlightOverlayContainer = findViewById(R.id.spotlight_overlay_container)
        spotlightOverlayView = findViewById(R.id.spotlight_overlay_view)
        spotlightTooltipCard = findViewById(R.id.spotlight_tooltip_card)
        txtSpotlightTitle = findViewById(R.id.txt_spotlight_title)
        txtSpotlightText = findViewById(R.id.txt_spotlight_text)
        txtSpotlightNote = findViewById(R.id.txt_spotlight_note)
        btnSpotlightSkip = findViewById(R.id.btn_spotlight_skip)
        btnSpotlightBack = findViewById(R.id.btn_spotlight_back)
        btnSpotlightNext = findViewById(R.id.btn_spotlight_next)
        btnSpotlightFinish = findViewById(R.id.btn_spotlight_finish)
        dotStep1 = findViewById(R.id.dot_step_1)
        dotStep2 = findViewById(R.id.dot_step_2)
        dotStep3 = findViewById(R.id.dot_step_3)
        dotStep4 = findViewById(R.id.dot_step_4)
        dotStep5 = findViewById(R.id.dot_step_5)

        btnSpotlightNext?.setOnClickListener {
            if (currentSpotlightStep < TOTAL_SPOTLIGHT_STEPS) {
                renderSpotlightStep(currentSpotlightStep + 1)
            }
        }

        btnSpotlightBack?.setOnClickListener {
            if (currentSpotlightStep > 1) {
                renderSpotlightStep(currentSpotlightStep - 1)
            }
        }

        btnSpotlightSkip?.setOnClickListener {
            completeSpotlightWalkthrough()
        }

        btnSpotlightFinish?.setOnClickListener {
            completeSpotlightWalkthrough()
        }

        checkFirstLaunchSpotlight()
    }

    private fun checkFirstLaunchSpotlight() {
        val sharedPrefs = getSharedPreferences("lanvan_prefs", Context.MODE_PRIVATE)
        val isCompleted = sharedPrefs.getBoolean("lanvan_onboarding_completed", false)
        if (!isCompleted) {
            startSpotlightWalkthrough()
        }
    }

    private fun startSpotlightWalkthrough() {
        preTutorialStatus = if (ServerService.isRunning) ServerService.STATUS_RUNNING else ServerService.STATUS_STOPPED
        currentSpotlightStep = 1
        spotlightOverlayContainer?.visibility = View.VISIBLE
        renderSpotlightStep(1)
    }

    private fun completeSpotlightWalkthrough() {
        val sharedPrefs = getSharedPreferences("lanvan_prefs", Context.MODE_PRIVATE)
        sharedPrefs.edit().putBoolean("lanvan_onboarding_completed", true).apply()
        spotlightOverlayContainer?.visibility = View.GONE
        handleStatusUpdate(preTutorialStatus)
    }

    private fun renderSpotlightStep(stepIndex: Int) {
        currentSpotlightStep = stepIndex

        val configs = listOf(
            SpotlightStepConfig(
                step = 1,
                title = "Start Lanvan",
                text = "Tap here to start sharing files with devices on your local network.",
                note = null,
                forceRunningPreview = false,
                targetViewId = R.id.btn_start_server,
                paddingDp = 6f,
                radiusDp = 28f
            ),
            SpotlightStepConfig(
                step = 2,
                title = "Connect another device",
                text = "Scan this QR code with another phone, tablet, or computer to open Lanvan.",
                note = "No Lanvan app is required on the other device. A web browser is enough.",
                forceRunningPreview = true,
                targetViewId = R.id.img_qrcode,
                paddingDp = 8f,
                radiusDp = 16f
            ),
            SpotlightStepConfig(
                step = 3,
                title = "Share files",
                text = "Once connected, the other device can upload or download files through the browser.",
                note = "Or tap the network address to open Lanvan in your browser directly on this device.",
                forceRunningPreview = true,
                targetViewId = R.id.txt_ip_link,
                paddingDp = 8f,
                radiusDp = 14f
            ),
            SpotlightStepConfig(
                step = 4,
                title = "Settings",
                text = "Connection, security, storage, background operation, and feedback are available here.",
                note = null,
                forceRunningPreview = false,
                targetViewId = R.id.btn_settings,
                paddingDp = 6f,
                radiusDp = 50f
            ),
            SpotlightStepConfig(
                step = 5,
                title = "You're ready",
                text = "Start Lanvan whenever you want to share files with another device.",
                note = null,
                forceRunningPreview = false,
                targetViewId = null,
                paddingDp = 0f,
                radiusDp = 0f
            )
        )

        val config = configs.find { it.step == stepIndex } ?: return

        // Switch card preview representation for tutorial steps
        if (config.forceRunningPreview) {
            cardStopped.visibility = View.GONE
            cardRunningConnected.visibility = View.VISIBLE

            val displayUrl = if (currentServerUrl.isNotEmpty()) currentServerUrl else "http://192.168.1.100:5000"
            txtIpLink.text = displayUrl
            val qrBitmap = generateQrCodeBitmap(displayUrl)
            if (qrBitmap != null) {
                imgQrCode.setImageBitmap(qrBitmap)
            }
        } else {
            handleStatusUpdate(preTutorialStatus)
        }

        txtSpotlightTitle?.text = config.title
        txtSpotlightText?.text = config.text

        if (config.note != null) {
            txtSpotlightNote?.text = config.note
            txtSpotlightNote?.visibility = View.VISIBLE
        } else {
            txtSpotlightNote?.visibility = View.GONE
        }

        // Update 5-dot indicator states
        val dots = listOf(dotStep1, dotStep2, dotStep3, dotStep4, dotStep5)
        for (i in dots.indices) {
            val d = dots[i] ?: continue
            val params = d.layoutParams
            if (i + 1 == stepIndex) {
                params.width = (18f * resources.displayMetrics.density).toInt()
                d.setBackgroundResource(R.drawable.bg_dot_active)
            } else {
                params.width = (6f * resources.displayMetrics.density).toInt()
                d.setBackgroundResource(R.drawable.bg_dot_inactive)
            }
            d.layoutParams = params
        }

        // Update button visibility
        btnSpotlightBack?.visibility = if (stepIndex > 1) View.VISIBLE else View.GONE
        if (stepIndex == TOTAL_SPOTLIGHT_STEPS) {
            btnSpotlightNext?.visibility = View.GONE
            btnSpotlightFinish?.visibility = View.VISIBLE
        } else {
            btnSpotlightNext?.visibility = View.VISIBLE
            btnSpotlightFinish?.visibility = View.GONE
        }

        // Position spotlight cutout & floating tooltip after layout pass
        spotlightOverlayContainer?.post {
            positionSpotlightForConfig(config)
        }
    }

    private fun positionSpotlightForConfig(config: SpotlightStepConfig) {
        val container = spotlightOverlayContainer ?: return
        val overlayView = spotlightOverlayView ?: return
        val tooltipCard = spotlightTooltipCard ?: return

        val targetId = config.targetViewId
        if (targetId == null) {
            // Step 5: Center tooltip card, dim backdrop without target cutout
            overlayView.setHighlight(null, 0f)

            val params = tooltipCard.layoutParams as FrameLayout.LayoutParams
            params.gravity = Gravity.CENTER
            params.topMargin = 0
            tooltipCard.layoutParams = params
            return
        }

        val targetView = findViewById<View>(targetId)
        if (targetView == null || targetView.width == 0 || targetView.height == 0) {
            overlayView.setHighlight(null, 0f)
            return
        }

        // Measure exact screen locations for target and overlay container
        val targetLoc = IntArray(2)
        val overlayLoc = IntArray(2)
        targetView.getLocationOnScreen(targetLoc)
        overlayView.getLocationOnScreen(overlayLoc)

        val relLeft = (targetLoc[0] - overlayLoc[0]).toFloat()
        val relTop = (targetLoc[1] - overlayLoc[1]).toFloat()
        val relRight = relLeft + targetView.width.toFloat()
        val relBottom = relTop + targetView.height.toFloat()

        val density = resources.displayMetrics.density
        val paddingPx = config.paddingDp * density

        val holeRect = RectF(
            relLeft - paddingPx,
            relTop - paddingPx,
            relRight + paddingPx,
            relBottom + paddingPx
        )

        overlayView.setHighlight(holeRect, config.radiusDp)

        // Intelligent Tooltip Placement
        val overlayHeight = overlayView.height.toFloat()
        val tooltipHeight = tooltipCard.height.toFloat()
        val targetCenterY = holeRect.centerY()

        val params = tooltipCard.layoutParams as FrameLayout.LayoutParams
        params.gravity = Gravity.TOP or Gravity.CENTER_HORIZONTAL

        if (targetCenterY > (overlayHeight / 2f) - 20f * density) {
            // Target is in lower half -> Position tooltip ABOVE target
            var calcTop = (holeRect.top - tooltipHeight - 14f * density).toInt()
            val minTop = (40f * density).toInt()
            if (calcTop < minTop) calcTop = minTop
            params.topMargin = calcTop
        } else {
            // Target is in upper half -> Position tooltip BELOW target
            var calcTop = (holeRect.bottom + 14f * density).toInt()
            val maxTop = (overlayHeight - tooltipHeight - 65f * density).toInt()
            if (calcTop > maxTop) calcTop = maxTop
            params.topMargin = calcTop
        }

        params.leftMargin = (20f * density).toInt()
        params.rightMargin = (20f * density).toInt()
        tooltipCard.layoutParams = params
    }

    /**
     * Sanitizes application log contents before attaching to diagnostics or writing to output.
     * Masks sensitive user file names and replaces raw clipboard text with generic placeholders.
     */
    private fun sanitizeLogContent(rawLogs: String): String {
        if (rawLogs.isBlank()) return ""

        var sanitized = rawLogs

        // 1. Sanitize raw clipboard data & payloads
        sanitized = sanitized.replace(Regex("(?i)(clipboard[\\s_\\-:=]+)[^\\r\\n]+"), "$1[Clipboard Data]")
        sanitized = sanitized.replace(Regex("(?i)(clipboard_data[\"']?\\s*:\\s*[\"']?)[^\"'\\r\\n]+"), "$1[Clipboard Data]")
        sanitized = sanitized.replace(Regex("(?i)(\"clipboard\"\\s*:\\s*\"?)[^\",\\}\\r\\n]+"), "$1[Clipboard Data]")

        // 2. Sanitize file names & explicit file paths
        sanitized = sanitized.replace(Regex("(?i)((?:filename|path|full_path|file|target_dir)[\\s=:]+)([^\\s;,\\r\\n]+)"), "$1[Sanitized File]")
        sanitized = sanitized.replace(Regex("(?i)(data/(?:uploads|clipboard|temp_chunks)/)([^\\s;,\\r\\n]+)"), "$1[Sanitized File]")
        sanitized = sanitized.replace(Regex("(?i)([a-zA-Z]:\\\\(?:[^\\\\\\r\\n]+\\\\)+)([^\\s;,\\r\\n]+)"), "$1[Sanitized Path]")
        sanitized = sanitized.replace(Regex("(?i)(/(?:sdcard|storage|data/data)/[^\\s;,\\r\\n]+)"), "[Sanitized Android Path]")

        return sanitized
    }
}
