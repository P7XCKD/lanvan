package com.lanvan.app

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
fun detectShareableLanNetwork(context: Context): LanNetworkState {
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

        // Priority 1: Wi-Fi — candidateWlanIp present on active wlan interface
        if (candidateWlanIp != null) {
            val state = LanNetworkState(
                available = true,
                ipAddress = candidateWlanIp,
                interfaceName = candidateWlanName,
                transport = "WIFI",
                reason = "WIFI_CONNECTED"
            )
            Log.d("LANVAN_NETWORK", "[LANVAN NETWORK] available=true interface=${state.interfaceName} transport=${state.transport} ip=${state.ipAddress} reason=${state.reason}")
            return state
        }

        // Priority 2: Wi-Fi Hotspot / Tethering
        if (candidateHotspotIp != null) {
            val state = LanNetworkState(
                available = true,
                ipAddress = candidateHotspotIp,
                interfaceName = candidateHotspotName,
                transport = "HOTSPOT",
                reason = "HOTSPOT_ACTIVE"
            )
            Log.d("LANVAN_NETWORK", "[LANVAN NETWORK] available=true interface=${state.interfaceName} transport=${state.transport} ip=${state.ipAddress} reason=${state.reason}")
            return state
        }

        // Priority 3: Ethernet
        if (hasEthernetTransport && candidateEthIp != null) {
            val state = LanNetworkState(
                available = true,
                ipAddress = candidateEthIp,
                interfaceName = candidateEthName,
                transport = "ETHERNET",
                reason = "ETHERNET_CONNECTED"
            )
            Log.d("LANVAN_NETWORK", "[LANVAN NETWORK] available=true interface=${state.interfaceName} transport=${state.transport} ip=${state.ipAddress} reason=${state.reason}")
            return state
        }

        // No usable LAN interface — cellular only or nothing
        if (foundCellularOnlyIp != null) {
            val state = LanNetworkState(
                available = false,
                ipAddress = null,
                interfaceName = foundCellularName,
                transport = "CELLULAR",
                reason = "CELLULAR_ONLY"
            )
            Log.d("LANVAN_NETWORK", "[LANVAN NETWORK] available=false interface=${state.interfaceName} transport=${state.transport} ip=REDACTED reason=${state.reason}")
            return state
        }

        val state = LanNetworkState(
            available = false,
            ipAddress = null,
            interfaceName = null,
            transport = "NONE",
            reason = "NO_LAN_INTERFACE"
        )
        Log.d("LANVAN_NETWORK", "[LANVAN NETWORK] available=false interface=none transport=NONE ip=null reason=${state.reason}")
        return state

    } catch (e: Exception) {
        Log.e("LANVAN_NETWORK", "[LANVAN NETWORK] Exception during detection: ${e.message}")
    }

    return LanNetworkState(
        available = false,
        ipAddress = null,
        interfaceName = null,
        transport = "NONE",
        reason = "ERROR"
    )
}
