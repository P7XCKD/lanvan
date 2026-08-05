package com.lanvan.app

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Context
import android.content.Intent
import android.net.Uri
import android.net.wifi.WifiManager
import android.os.Build
import android.os.IBinder
import android.os.PowerManager
import androidx.core.app.NotificationCompat
import androidx.core.app.ServiceCompat
import com.chaquo.python.Python
import java.net.Inet4Address
import java.net.NetworkInterface

class ServerService : Service() {
    private var serverThread: Thread? = null
    private var wakeLock: PowerManager.WakeLock? = null
    private var wifiLock: WifiManager.WifiLock? = null
    
    private var instancePort = "5000"
    private var instanceUseHttps = "false"

    companion object {
        const val CHANNEL_ID = "lanvan_server_service_channel"
        const val NOTIFICATION_ID = 12001
        
        // Error logs accumulator
        var lastErrorLog = ""
        
        // Static state flags so MainActivity can read them on resume
        @Volatile var isRunning = false
            private set
        var currentPort = "5000"
            internal set
        var currentUrl = ""
            internal set
        
        // Actions to start/stop the service
        const val ACTION_START = "START_SERVER"
        const val ACTION_STOP = "STOP_SERVER"
        
        // Notification drawer button actions
        const val ACTION_NOTIFICATION_OPEN = "NOTIFICATION_OPEN_URL"
        const val ACTION_NOTIFICATION_SHUTDOWN = "NOTIFICATION_SHUTDOWN"
        const val ACTION_NOTIFICATION_DISMISSED = "NOTIFICATION_DISMISSED"
        
        // Status Broadcast Actions
        const val ACTION_STATUS_CHANGE = "com.lanvan.app.STATUS_CHANGE"
        const val EXTRA_STATUS = "status"
        
        const val STATUS_RUNNING = "running"
        const val STATUS_STOPPED = "stopped"
        const val STATUS_ERROR = "error"
    }

    override fun onCreate() {
        super.onCreate()
        createNotificationChannel()
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        val action = intent?.action ?: ACTION_START
        val port = intent?.getStringExtra("PORT") ?: instancePort
        val useHttps = intent?.getStringExtra("USE_HTTPS") ?: instanceUseHttps
        
        instancePort = port
        instanceUseHttps = useHttps
        currentPort = port

        when (action) {
            ACTION_STOP, ACTION_NOTIFICATION_SHUTDOWN -> {
                stopServer()
                return START_NOT_STICKY
            }
            ACTION_NOTIFICATION_DISMISSED -> {
                if (isRunning) {
                    val notification = buildServiceNotification(instancePort, instanceUseHttps)
                    if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
                        var serviceType = android.content.pm.ServiceInfo.FOREGROUND_SERVICE_TYPE_SPECIAL_USE
                        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.UPSIDE_DOWN_CAKE) {
                            serviceType = serviceType or android.content.pm.ServiceInfo.FOREGROUND_SERVICE_TYPE_DATA_SYNC
                        }
                        startForeground(NOTIFICATION_ID, notification, serviceType)
                    } else {
                        startForeground(NOTIFICATION_ID, notification)
                    }
                }
                return START_STICKY
            }
            ACTION_NOTIFICATION_OPEN -> {
                val url = intent?.getStringExtra("URL")
                if (!url.isNullOrEmpty()) {
                    try {
                        val browserIntent = Intent(Intent.ACTION_VIEW, Uri.parse(url)).apply {
                            addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                        }
                        startActivity(browserIntent)
                    } catch (e: Exception) {
                        e.printStackTrace()
                    }
                }
                return START_STICKY
            }
        }

        // Guard: prevent double-start if server is already running
        if (isRunning && action != ACTION_STOP && action != ACTION_NOTIFICATION_SHUTDOWN && action != ACTION_NOTIFICATION_OPEN) {
            return START_STICKY
        }

        // Acquire WakeLocks to keep CPU and WiFi active
        acquireLocks()

        // Build status notification
        val notification = buildServiceNotification(port, useHttps)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            var serviceType = android.content.pm.ServiceInfo.FOREGROUND_SERVICE_TYPE_SPECIAL_USE
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.UPSIDE_DOWN_CAKE) {
                serviceType = serviceType or android.content.pm.ServiceInfo.FOREGROUND_SERVICE_TYPE_DATA_SYNC
            }
            startForeground(NOTIFICATION_ID, notification, serviceType)
        } else {
            startForeground(NOTIFICATION_ID, notification)
        }

        // Recursively extract app/static and app/templates assets to filesDir.
        // Skip extraction if a version marker exists matching the current versionCode,
        // avoiding 1-5 seconds of redundant I/O on every service start.
        val markerFile = java.io.File(filesDir, ".asset_version")
        val currentVersion = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.P) {
            packageManager.getPackageInfo(packageName, 0).longVersionCode.toString()
        } else {
            @Suppress("DEPRECATION")
            packageManager.getPackageInfo(packageName, 0).versionCode.toString()
        }
        val cachedVersion = if (markerFile.exists()) {
            try { markerFile.readText().trim() } catch (_: Exception) { "" }
        } else { "" }

        if (cachedVersion != currentVersion) {
            copyAssetsToFilesDir("app")
            copyAssetsToFilesDir("certs")
            try {
                markerFile.writeText(currentVersion)
            } catch (_: Exception) { /* best-effort */ }
        }

        val oldThread = serverThread
        // Launch Python FastAPI thread
        serverThread = Thread {
            if (oldThread != null && oldThread.isAlive) {
                try {
                    oldThread.join(3000) // Wait up to 3 seconds in the background
                } catch (e: InterruptedException) {
                    e.printStackTrace()
                }
            }
            try {
                if (!Python.isStarted()) {
                    // Start python context if it hasn't started yet
                    Python.start(com.chaquo.python.android.AndroidPlatform(this))
                }
                
                val py = Python.getInstance()
                val module = py.getModule("start_server")
                
                // Broadcast that server is starting/running
                sendServerStatus(STATUS_RUNNING)
                
                // Call uvicorn bootstrapper blocking method
                // Pass filesDir absolute path and isDebug flag to Python environment
                val isDebug = (applicationInfo.flags and android.content.pm.ApplicationInfo.FLAG_DEBUGGABLE) != 0
                module.callAttr("run_fastapi_server", instancePort, instanceUseHttps, filesDir.absolutePath, isDebug)


            } catch (e: Exception) {
                var isCleanShutdown = false
                if (e is com.chaquo.python.PyException) {
                    val msg = e.message ?: ""
                    // Uvicorn internally remaps sys.exit(0) to SystemExit: 1 at the runner level
                    // so we need to catch any SystemExit as a clean shutdown signal
                    if (msg.contains("SystemExit")) {
                        isCleanShutdown = true
                    }
                }
                
                if (isCleanShutdown) {
                    // Clean thread exit - do not log error or change state to STATUS_ERROR
                    sendServerStatus(STATUS_STOPPED)
                } else {
                    val sw = java.io.StringWriter()
                    e.printStackTrace(java.io.PrintWriter(sw))
                    lastErrorLog = "Kotlin Exception: " + e.message + "\n" + sw.toString()
                    e.printStackTrace()
                    sendServerStatus(STATUS_ERROR)
                }
            } finally {
                sendServerStatus(STATUS_STOPPED)
                // Now that the Python server is actually dead, clean up locks and stop the service
                // only if this thread is still the active server thread (prevents overlapping restart races)
                if (serverThread == Thread.currentThread()) {
                    releaseLocks()
                    stopSelf()
                }
            }
        }
        serverThread?.start()

        return START_STICKY
    }

    override fun onDestroy() {
        stopServer()
        super.onDestroy()
    }    private fun stopServer() {
        // 1. Force exit Uvicorn directly via Python reference to avoid zombied loops
        try {
            if (Python.isStarted()) {
                val py = Python.getInstance()
                val module = py.getModule("start_server")
                module.callAttr("force_stop_uvicorn_server")
            }
        } catch (e: Exception) {
            e.printStackTrace()
        }

        // 2. Fallback localhost shutdown API request to trigger clean cleanup sequence.
        //    Use plain HTTP to 127.0.0.1 — the shutdown endpoint already enforces localhost-only
        //    at the application layer (system.py:282). TLS is unnecessary for a local loopback call
        //    and avoids the need for a trust-all SSL context (which is a security risk).
        Thread {
            try {
                val url = java.net.URL("http://127.0.0.1:$instancePort/api/shutdown")
                val conn = url.openConnection() as java.net.HttpURLConnection
                conn.requestMethod = "POST"
                conn.connectTimeout = 1500
                conn.readTimeout = 1500
                conn.responseCode
            } catch (e: Exception) {
                // Ignore
            }
        }.start()
    }

    override fun onBind(intent: Intent?): IBinder? = null

    private fun acquireLocks() {
        // CPU Wake Lock — 30-minute safety timeout prevents battery drain on crash
        val powerManager = getSystemService(Context.POWER_SERVICE) as PowerManager
        wakeLock = powerManager.newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, "Lanvan::ServerWakelock").apply {
            acquire(30 * 60 * 1000L) // 30-minute timeout
        }

        // WiFi Lock — use FULL_LOW_LATENCY on API 29+, fallback to HIGH_PERF
        val wifiManager = applicationContext.getSystemService(Context.WIFI_SERVICE) as WifiManager
        val wifiLockMode = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            WifiManager.WIFI_MODE_FULL_LOW_LATENCY
        } else {
            @Suppress("DEPRECATION")
            WifiManager.WIFI_MODE_FULL_HIGH_PERF
        }
        wifiLock = wifiManager.createWifiLock(wifiLockMode, "Lanvan::ServerWifiLock").apply {
            acquire()
        }
    }

    private fun releaseLocks() {
        try {
            if (wakeLock?.isHeld == true) wakeLock?.release()
            if (wifiLock?.isHeld == true) wifiLock?.release()
        } catch (e: Exception) {
            e.printStackTrace()
        }
    }

    private fun buildServiceNotification(port: String, useHttps: String): Notification {
        val scheme = if (useHttps == "true") "https" else "http"
        val lanIp = getLocalIpAddress()
        val serverUrl = "$scheme://$lanIp:$port"
        
        // Open main activity when notification is clicked (bring existing to front)
        val notificationIntent = Intent(this, MainActivity::class.java).apply {
            addFlags(Intent.FLAG_ACTIVITY_SINGLE_TOP or Intent.FLAG_ACTIVITY_CLEAR_TOP)
        }
        val pendingIntent = PendingIntent.getActivity(
            this, 0, notificationIntent,
            PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT
        )

        // Action 1: Open Browser
        val openBrowserIntent = Intent(this, ServerService::class.java).apply {
            action = ACTION_NOTIFICATION_OPEN
            putExtra("URL", serverUrl)
        }
        val openBrowserPendingIntent = PendingIntent.getService(
            this, 1, openBrowserIntent,
            PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT
        )

        // Action 2: Stop Server
        val shutdownIntent = Intent(this, ServerService::class.java).apply {
            action = ACTION_NOTIFICATION_SHUTDOWN
        }
        val shutdownPendingIntent = PendingIntent.getService(
            this, 2, shutdownIntent,
            PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT
        )

        // Action 3: Re-post on Dismiss
        val dismissIntent = Intent(this, ServerService::class.java).apply {
            action = ACTION_NOTIFICATION_DISMISSED
        }
        val dismissPendingIntent = PendingIntent.getService(
            this, 3, dismissIntent,
            PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT
        )

        val builder = NotificationCompat.Builder(this, CHANNEL_ID)
            .setContentIntent(pendingIntent)
            .setDeleteIntent(dismissPendingIntent)
            .setOngoing(true)
            .setCategory(NotificationCompat.CATEGORY_SERVICE)
            .setPriority(NotificationCompat.PRIORITY_DEFAULT)
            .setForegroundServiceBehavior(NotificationCompat.FOREGROUND_SERVICE_IMMEDIATE)
            .setSmallIcon(R.drawable.ic_launcher) // Use custom Lanvan logo icon
            .setContentTitle("Lanvan Server Running")
            .setContentText("Access server at $serverUrl")
            .addAction(android.R.drawable.ic_menu_view, "Open Browser", openBrowserPendingIntent)
            .addAction(android.R.drawable.ic_menu_close_clear_cancel, "Stop Server", shutdownPendingIntent)

        val notification = builder.build()
        notification.flags = notification.flags or Notification.FLAG_NO_CLEAR or Notification.FLAG_ONGOING_EVENT
        return notification
    }

    private fun createNotificationChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val serviceChannel = NotificationChannel(
                CHANNEL_ID,
                "Lanvan Server Background Service Channel",
                NotificationManager.IMPORTANCE_DEFAULT
            )
            val manager = getSystemService(NotificationManager::class.java)
            manager.createNotificationChannel(serviceChannel)
        }
    }

    private fun sendServerStatus(status: String) {
        // Update static flags so MainActivity can read state synchronously
        isRunning = (status == STATUS_RUNNING)
        if (status == STATUS_RUNNING) {
            val scheme = if (instanceUseHttps == "true") "https" else "http"
            val lanIp = getLocalIpAddress()
            currentUrl = "$scheme://$lanIp:$instancePort"
        } else if (status == STATUS_STOPPED || status == STATUS_ERROR) {
            currentUrl = ""
        }
        
        val intent = Intent(ACTION_STATUS_CHANGE).apply {
            putExtra(EXTRA_STATUS, status)
        }
        sendBroadcast(intent)
    }

    private fun copyAssetsToFilesDir(path: String) {
        val assetManager = assets
        var files: Array<String>? = null
        try {
            files = assetManager.list(path)
        } catch (e: java.io.IOException) {
            e.printStackTrace()
        }
        if (files.isNullOrEmpty()) {
            copyFile(path)
        } else {
            val dir = java.io.File(filesDir, path)
            if (!dir.exists()) {
                dir.mkdirs()
            }
            for (filename in files) {
                copyAssetsToFilesDir(if (path.isEmpty()) filename else "$path/$filename")
            }
        }
    }

    private fun copyFile(filename: String) {
        val assetManager = assets
        var inStream: java.io.InputStream? = null
        var outStream: java.io.OutputStream? = null
        try {
            inStream = assetManager.open(filename)
            val outFile = java.io.File(filesDir, filename)
            outFile.parentFile?.mkdirs()
            outStream = java.io.FileOutputStream(outFile)
            val buffer = ByteArray(1024)
            var read: Int
            while (inStream.read(buffer).also { read = it } != -1) {
                outStream.write(buffer, 0, read)
            }
        } catch (e: Exception) {
            e.printStackTrace()
        } finally {
            inStream?.close()
            outStream?.close()
        }
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
