package com.probz.lanvan

import android.content.Context
import android.net.ConnectivityManager
import android.net.NetworkCapabilities
import android.os.Build
import android.util.Log
import java.net.Inet4Address
import java.net.NetworkInterface

/**
 * Shared network state model for a usable local-area network interface.
 * A "shareable" LAN interface is one through which another device on the
 * same local network can reach the Lanvan server (Wi-Fi, Ethernet, Hotspot).
 * Cellular-only connections are explicitly excluded.
 */
data class LanNetworkState(
    val available: Boolean,
    val ipAddress: String?,
    val interfaceName: String?,
    val transport: String,
    val reason: String
)

/**
 * Detect the best LAN interface through which another device can reach the
 * Lanvan server. Interfaces are evaluated in priority order:
 *  1. Wi-Fi (wlan*) — requires Wi-Fi hardware enabled AND active Wi-Fi transport
 *  2. Wi-Fi Hotspot / Tethering (ap*, swlan*, rndis*)
 *  3. Ethernet (eth*)
 *
 * Cellular-only and loopback interfaces are explicitly rejected.
 */
private var cachedNetworkState: LanNetworkState? = null
private var lastNetworkCheckTime: Long = 0L

fun invalidateLanNetworkCache() {
    cachedNetworkState = null
    lastNetworkCheckTime = 0L
}

fun detectShareableLanNetwork(context: Context): LanNetworkState {
    val now = System.currentTimeMillis()
    val cached = cachedNetworkState
    if (cached != null && (now - lastNetworkCheckTime) < 3000L) {
        return cached
    }

    try {
        val cm = context.getSystemService(Context.CONNECTIVITY_SERVICE) as ConnectivityManager

        // Determine which transports the active network carries
        var hasEthernetTransport = false

        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
            val activeNet = cm.activeNetwork
            if (activeNet != null) {
                val caps = cm.getNetworkCapabilities(activeNet)
                if (caps != null) {
                    hasEthernetTransport = caps.hasTransport(NetworkCapabilities.TRANSPORT_ETHERNET)
                }
            }
        }

        // Walk all active network interfaces and bucket their IPv4 addresses by type
        val interfaces = NetworkInterface.getNetworkInterfaces()
        var candidateWlanIp: String? = null
        var candidateWlanName: String? = null
        var candidateHotspotIp: String? = null
        var candidateHotspotName: String? = null
        var candidateEthIp: String? = null
        var candidateEthName: String? = null
        var foundCellularOnlyIp: String? = null
        var foundCellularName: String? = null

        while (interfaces.hasMoreElements()) {
            val iface = interfaces.nextElement()
            if (!iface.isUp || iface.isLoopback) continue
            val name = iface.name.lowercase()

            // Skip VPN, virtual, loopback, and p2p interfaces — these are not shareable
            if (name.contains("tun") || name.contains("tap") ||
                name.contains("dummy") || name.contains("p2p") || name.contains("lo")
            ) continue

            val addrs = iface.inetAddresses
            while (addrs.hasMoreElements()) {
                val addr = addrs.nextElement()
                if (addr is Inet4Address && !addr.isLoopbackAddress &&
                    addr.hostAddress != "0.0.0.0"
                ) {
                    val host = addr.hostAddress ?: continue
                    // Skip loopback and link-local addresses
                    if (host == "127.0.0.1" || host.startsWith("169.254.")) continue

                    when {
                        name.contains("wlan") -> {
                            candidateWlanIp = host
                            candidateWlanName = iface.name
                        }
                        name.contains("ap") || name.contains("swlan") || name.contains("rndis") -> {
                            candidateHotspotIp = host
                            candidateHotspotName = iface.name
                        }
                        name.contains("eth") -> {
                            candidateEthIp = host
                            candidateEthName = iface.name
                        }
                        name.contains("rmnet") || name.contains("ccmni") || name.contains("pdp") -> {
                            foundCellularOnlyIp = host
                            foundCellularName = iface.name
                        }
                    }
                }
            }
        }

        val state = when {
            candidateWlanIp != null -> LanNetworkState(true, candidateWlanIp, candidateWlanName, "WIFI", "WIFI_CONNECTED")
            candidateHotspotIp != null -> LanNetworkState(true, candidateHotspotIp, candidateHotspotName, "HOTSPOT", "HOTSPOT_ACTIVE")
            hasEthernetTransport && candidateEthIp != null -> LanNetworkState(true, candidateEthIp, candidateEthName, "ETHERNET", "ETHERNET_CONNECTED")
            foundCellularOnlyIp != null -> LanNetworkState(false, null, foundCellularName, "CELLULAR", "CELLULAR_ONLY")
            else -> LanNetworkState(false, null, null, "NONE", "NO_LAN_INTERFACE")
        }

        Log.d("LANVAN_NETWORK", "[LANVAN NETWORK] available=${state.available} interface=${state.interfaceName} transport=${state.transport} ip=${state.ipAddress} reason=${state.reason}")
        cachedNetworkState = state
        lastNetworkCheckTime = now
        return state

    } catch (e: Exception) {
        Log.e("LANVAN_NETWORK", "[LANVAN NETWORK] Exception during detection: ${e.message}")
    }

    val errState = LanNetworkState(
        available = false,
        ipAddress = null,
        interfaceName = null,
        transport = "NONE",
        reason = "ERROR"
    )
    cachedNetworkState = errState
    lastNetworkCheckTime = now
    return errState
}
