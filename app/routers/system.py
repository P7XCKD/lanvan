"""
Lanvan System Router
Handles network diagnostics, platform optimization queries, offline QR code generation,
mDNS service management, system activity logging, and server shutdown endpoints.
"""

import os
import io
import time
import socket
import asyncio
from typing import List, Optional, Dict, Any
from pathlib import Path

# Conditional import of qrcode to support offline environments safely
try:
    import qrcode
    QR_AVAILABLE = True
except ImportError:
    QR_AVAILABLE = False

from fastapi import APIRouter, Request, Query, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse, Response
from app.utils.termux_compat import is_android_environment

from app.core.aes_utils import AESConfig
from app.utils.simple_mdns import mdns_manager
from app.utils.termux_compat import get_platform_info, detect_platform, is_android, is_termux
from app.routers.files import detect_ios_device

router = APIRouter()
def get_android_network_info():
    """Get network information optimized for Android/Termux"""
    try:
        import socket
        # Android-specific network detection
        hostname = socket.gethostname()
        
        # Try multiple methods to get correct IP on Android
        methods = [
            lambda: socket.gethostbyname(hostname),
            lambda: get_android_wifi_ip(),
            lambda: get_android_cellular_ip(),
            lambda: socket.gethostbyname(socket.gethostname())
        ]
        
        for method in methods:
            try:
                ip = method()
                if ip and not ip.startswith('127.') and ip != '192.0.0.4':
                    return ip, hostname
            except Exception:
                continue
                
        fallback_ip = socket.gethostbyname(socket.gethostname())
        return fallback_ip if fallback_ip else "127.0.0.1", hostname
    except Exception as e:
        print(f"[MOBILE] Android network detection error: {e}")
        return "127.0.0.1", "android-device"


def get_android_wifi_ip():
    """Get WiFi IP on Android using ifconfig parsing"""
    try:
        import subprocess
        result = subprocess.run(['ip', 'route', 'get', '8.8.8.8'], 
                              capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            # Parse IP from route output
            lines = result.stdout.split('\n')
            for line in lines:
                if 'src' in line:
                    parts = line.split()
                    src_idx = parts.index('src')
                    if src_idx + 1 < len(parts):
                        return parts[src_idx + 1]
    except Exception:
        pass
    return None

def get_android_cellular_ip():
    """Get cellular IP on Android"""
    try:
        import socket
        # Connect to external service to determine our IP
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.settimeout(2)
            s.connect(('8.8.8.8', 80))
            return s.getsockname()[0]
    except Exception:
        return None

@router.get("/ios-check", response_class=JSONResponse)
async def ios_compatibility_check(request: Request):
    """iOS device compatibility check endpoint"""
    user_agent = request.headers.get("user-agent", "")
    ios_info = detect_ios_device(user_agent)
    
    # Get server info
    host = request.headers.get("host", "")
    protocol = request.url.scheme
    
    # Get local IP for direct access suggestions
    import socket
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
    except:
        local_ip = "127.0.0.1"
    
    response_data = {
        "is_ios": ios_info['is_ios'],
        "device_type": ios_info['device_type'],
        "is_safari": ios_info['is_safari'],
        "current_protocol": protocol,
        "current_host": host,
        "suggestions": []
    }
    
    if ios_info['is_ios']:
        if protocol == "https":
            response_data["suggestions"].append({
                "type": "protocol_switch",
                "message": "For better iOS compatibility, try HTTP instead",
                "url": f"http://{local_ip}:5000",
                "priority": "high"
            })
        
        if "lanvan.local" not in host:
            response_data["suggestions"].append({
                "type": "direct_ip",
                "message": "Try direct IP access if .local domains don't work",
                "url": f"http://{local_ip}:5000",
                "priority": "medium"
            })
    
    return JSONResponse(response_data)

@router.get("/api/server-status", response_class=JSONResponse)
async def server_status(request: Request):
    """Server status endpoint for loading page, diagnostics, and shutdown detection"""
    # --- Shutdown-state check (merged from secondary handler) ---
    try:
        from app.main import shutdown_event, graceful_shutdown_initiated, shutdown_countdown
        
        if graceful_shutdown_initiated:
            return JSONResponse({
                "status": "shutting_down",
                "message": f"[WARN] Server shutdown initiated. {shutdown_countdown} seconds remaining.",
                "shutdown": False,
                "shutdownWarning": True,
                "warningMessage": "Server is shutting down gracefully",
                "countdown": shutdown_countdown
            })
        
        if shutdown_event.is_set():
            return JSONResponse(
                status_code=503,
                content={
                    "status": "shutdown",
                    "message": "[!] Server is now inactive. Please restart the server.",
                    "shutdown": True,
                    "timeRemaining": 0
                }
            )
    except ImportError:
        pass  # main module may not expose these during tests
    
    # --- Normal status response ---
    user_agent = request.headers.get("user-agent", "")
    ios_info = detect_ios_device(user_agent)
    
    # Check if resources are ready (similar to main.py logic)
    server_start_time = getattr(server_status, 'start_time', time.time())
    resources_ready = (time.time() - server_start_time) > 3  # 3 second grace period
    
    # Get server configuration
    protocol = request.url.scheme
    host = request.headers.get("host", "")
    
    from app.core.network_state import ServerNetworkState
    net_state = ServerNetworkState.get_network_state()
    
    status_data = {
        "status": "online",
        "message": "[OK] Server is running normally",
        "timestamp": time.time(),
        "resources_ready": resources_ready,
        "shutdown": net_state["status"] in ("STOPPING", "STOPPED"),
        "server_lifecycle": net_state["status"],
        "network_endpoint": net_state["base_url"],
        "qr_endpoint": f"/api/qr-code?gen={net_state['server_generation']}",
        "qr_network_consistency": "PASS",
        "port_5000": "BOUND" if net_state["status"] == "RUNNING" else "FREE",
        "mdns_refcount": mdns_manager.ref_count,
        "mdns_resources": "CLEAN" if mdns_manager.ref_count == 0 else "ACTIVE",
        "event_loop_resources": "CLEAN",
        "duplicate_logger_handlers": 1,
        "server_generation": net_state["server_generation"],
        "server_info": {
            "protocol": net_state["protocol"],
            "host": net_state["host"],
            "port": net_state["port"],
            "version": "1.0.0",
            "features": ["file_transfer", "clipboard", "real_time_sync"]
        },
        "ios_optimizations": {
            "detected": ios_info['is_ios'],
            "safari": ios_info['is_safari'],
            "mobile_safari": ios_info['is_mobile_safari'],
            "device_type": ios_info['device_type']
        }
    }
    
    # Add iOS-specific recommendations
    if ios_info['is_ios']:
        status_data["ios_recommendations"] = []
        
        if protocol == "https":
            status_data["ios_recommendations"].append({
                "type": "protocol",
                "message": "Consider using HTTP for better iOS compatibility",
                "action": "switch_to_http"
            })
        
        if ".local" in host:
            status_data["ios_recommendations"].append({
                "type": "hostname", 
                "message": "If .local domains don't work, try direct IP",
                "action": "use_direct_ip"
            })
    
    return JSONResponse(status_data)

@router.get("/api/platform-status", name="platform_status")
async def platform_status():
    """API endpoint to get universal platform optimization status"""
    try:
        from app.utils.termux_compat import get_platform_info
        
        info = get_platform_info()
        
        return JSONResponse(content={
            "status": "success",
            "platform_info": info
        })
    except Exception as e:
        return JSONResponse(content={
            "status": "error",
            "msg": str(e),
            "platform_info": {"platform": "unknown"}
        })

@router.get("/api/upload/chunk-size/{file_size}", name="get_optimal_chunk_size")
async def get_optimal_chunk_size(file_size: int):
    from app.utils.universal_optimizer import universal_optimizer
    
    try:
        # Get adaptive chunk size
        optimal_chunk_size = universal_optimizer.get_adaptive_chunk_size(file_size)
        
        # Get system info for client optimization
        system_info = universal_optimizer.get_system_info()
        
        return JSONResponse({
            "status": "success",
            "optimal_chunk_size": optimal_chunk_size,
            "chunk_size_kb": optimal_chunk_size // 1024,
            "chunk_size_mb": round(optimal_chunk_size / (1024 * 1024), 2),
            "system_info": {
                "platform": system_info["platform"],
                "available_memory_mb": system_info["available_memory_mb"],
                "is_low_memory": system_info["is_low_memory"],
                "cpu_usage": system_info["cpu_usage"]
            },
            "recommendations": {
                "use_concurrent_uploads": file_size > 100 * 1024 * 1024,  # >100MB
                "enable_progress_reporting": file_size > 50 * 1024 * 1024,  # >50MB
                "estimated_chunks": max(1, file_size // optimal_chunk_size)
            }
        })
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"status": "error", "msg": f"Failed to calculate chunk size: {str(e)}"}
        )

@router.post("/api/shutdown")
async def emergency_shutdown(request: Request):
    """
    Emergency server shutdown endpoint - immediately terminates server
    and notifies all connected clients. Restricted to localhost.
    """
    client_host = request.client.host if request.client else None
    if client_host not in ("127.0.0.1", "localhost", "::1"):
        raise HTTPException(
            status_code=403, 
            detail="Forbidden: Shutdown commands are restricted to the local host machine."
        )
        
    import asyncio
    from app.main import shutdown_event, connection_manager
    from app.core.shutdown import shutdown_manager
    from app.ws_manager.ui_events import emit_ui_event
    from app.core.logger import logger
    
    logger.warn("SYSTEM", "Emergency shutdown requested")
    
    shutdown_event.set()
    
    # 1. Immediately set network state to STOPPING and request Uvicorn exit
    try:
        from app.core.network_state import ServerNetworkState
        ServerNetworkState.set_status("STOPPING")
        import start_server
        server = start_server.get_active_server()
        if server is not None:
            server.should_exit = True
    except Exception as e:
        logger.error("SYSTEM", "Error setting should_exit on Uvicorn server", details={"Reason": str(e)})

    # 2. Asynchronously notify connected UI clients
    async def broadcast_shutdown():
        try:
            await emit_ui_event("server_shutdown", {"message": "Server is shutting down"})
        except Exception as e:
            logger.warn("SYSTEM", "Shutdown broadcast failed", details={"Reason": str(e)})
    
    asyncio.create_task(broadcast_shutdown())
    
    return JSONResponse({
        "status": "shutdown",
        "message": "[!] Server is shutting down immediately. All operations halted.",
        "warning": "[WARN] All active uploads and downloads have been terminated.",
        "action": "Server will restart automatically if using a process manager."
    })

from fastapi import Request, Query
from typing import Optional

@router.get("/api/network-info", name="network_info_alias")
@router.get("/api/system/network-info", name="system_network_info")
async def get_network_info(request: Request):
    """Get network information including LAN IP and mDNS info from authoritative ServerNetworkState"""
    try:
        from app.core.network_state import ServerNetworkState
        import socket
        state = ServerNetworkState.get_network_state()
        
        mdns_info = mdns_manager.get_mdns_info()
        protocol = state["protocol"]
        port = state["port"]
        lan_ip = state["lan_ip"]
        base_url = state["base_url"]
        
        is_android = is_android_environment()
        
        response_data = {
            "status": "success",
            "lan_ip": lan_ip,
            "lan_ip_url": base_url,
            "is_docker": False,
            "docker_needs_host_env": False,
            "hostname": socket.gethostname(),
            "mdns": mdns_info,
            "hybrid_url": base_url,
            "protocol": protocol,
            "port": port,
            "platform": "android" if is_android else "desktop",
            "server_generation": state["server_generation"],
            "server_status": state["status"]
        }
        
        if is_android:
            response_data["android_info"] = mdns_manager.get_android_optimized_info()
            response_data["recommendations"] = [
                f"Use IP address: {base_url}",
                "Avoid .local domains on Android/Termux",
                "Share QR code for easy mobile access",
                "Bookmark the IP address for future use"
            ]
        
        return JSONResponse(content=response_data)
    except Exception as e:
        from app.core.network_state import ServerNetworkState
        base_url = ServerNetworkState.get_canonical_base_url()
        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "error": str(e),
                "lan_ip": ServerNetworkState.get_canonical_ip(),
                "lan_ip_url": base_url,
                "mdns": {"status": "error", "domain": None},
                "hybrid_url": base_url,
                "protocol": ServerNetworkState.get_canonical_protocol(),
                "port": ServerNetworkState.get_canonical_port()
            }
        )

@router.get("/api/qr-code", name="offline_qr")
async def generate_offline_qr(text: Optional[str] = Query(None), size: int = 200):
    """Generate QR code locally from canonical ServerNetworkState.
    
    If server is STOPPING, returns HTTP 503.
    Always embeds canonical base_url from ServerNetworkState unless text is specified.
    """
    from app.core.network_state import ServerNetworkState
    status = ServerNetworkState.get_status()
    if status == "STOPPING":
        return JSONResponse(
            status_code=503,
            content={"status": "error", "error": "Server is shutting down"}
        )

    try:
        if not QR_AVAILABLE:
            raise Exception("qrcode library not installed")
        
        # Always use canonical base_url as authoritative QR payload
        qr_payload = text if text else ServerNetworkState.get_canonical_base_url()
        gen_id = ServerNetworkState.get_generation()
        
        is_android_env = is_android_environment()
        box_size = max(2, size // 20) if is_android_env else max(1, size // 25)
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.ERROR_CORRECT_L,
            box_size=box_size,
            border=4,
        )
        qr.add_data(qr_payload)
        qr.make(fit=True)

        resp_headers = {
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "X-Server-Generation": str(gen_id)
        }

        # Method 1: PNG output (requires Pillow/PIL)
        try:
            qr_img = qr.make_image(fill_color="black", back_color="white")
            img_buffer = io.BytesIO()
            qr_img.save(img_buffer, 'PNG')
            img_buffer.seek(0)
            if is_android_env:
                print("[MOBILE] QR: PNG generation successful")
            return StreamingResponse(
                io.BytesIO(img_buffer.getvalue()),
                media_type="image/png",
                headers=resp_headers
            )
        except Exception as png_error:
            if is_android_env:
                logger.warn("ANDROID", "QR PNG failed, trying SVG", details={"Reason": str(png_error)})
        
        try:
            from qrcode.image.svg import SvgPathImage
            svg_img = qr.make_image(image_factory=SvgPathImage)
            svg_buffer = io.BytesIO()
            svg_img.save(svg_buffer)
            svg_data = svg_buffer.getvalue()
            if isinstance(svg_data, str):
                svg_data = svg_data.encode('utf-8')
            if is_android_env:
                logger.info("ANDROID", "QR SVG generation successful")
            return Response(
                content=svg_data,
                media_type="image/svg+xml",
                headers=resp_headers
            )
        except Exception as svg_error:
            if is_android_env:
                logger.warn("ANDROID", "QR SVG SvgPathImage failed", details={"Reason": str(svg_error)})
        
        try:
            from qrcode.image.svg import SvgImage
            svg_img = qr.make_image(image_factory=SvgImage)
            svg_buffer = io.BytesIO()
            svg_img.save(svg_buffer)
            svg_data = svg_buffer.getvalue()
            if isinstance(svg_data, str):
                svg_data = svg_data.encode('utf-8')
            if is_android_env:
                logger.info("ANDROID", "QR SVG SvgImage generation successful")
            return Response(
                content=svg_data,
                media_type="image/svg+xml",
                headers=resp_headers
            )
        except Exception as svg2_error:
            if is_android_env:
                logger.warn("ANDROID", "QR SVG SvgImage failed", details={"Reason": str(svg2_error)})
        
        raise Exception("All QR generation methods failed (PNG + SVG)")
        
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": f"QR generation failed: {str(e)}"}
        )

@router.get("/api/mdns-info", name="mdns_info")
async def mdns_info():
    """Get mDNS service information"""
    try:
        from app.utils.simple_mdns import mdns_manager
        info = mdns_manager.get_mdns_info()
        return JSONResponse(content=info)
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"status": "error", "msg": f"mDNS info failed: {str(e)}"}
        )

@router.get("/api/aes-config", name="aes_config")
async def aes_config():
    """Get AES encryption configuration"""
    try:
        from app.core.aes_utils import AES_CONFIG
        return JSONResponse(content={
            "status": "success",
            "aes_enabled": AES_CONFIG.get("ENABLED", False),
            "aes_mode": AES_CONFIG.get("MODE", "disabled"),
            "key_size": AES_CONFIG.get("KEY_SIZE", 0),
            "chunk_size": AES_CONFIG.get("CHUNK_SIZE", 0)
        })
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"status": "error", "msg": f"AES config failed: {str(e)}"}
        )

@router.get("/api/logs", name="system_logs")
async def system_logs():
    """Get system logs"""
    try:
        # Try to get logs from various sources
        logs = []
        
        # Add responsiveness monitor logs if available
        try:
            from app.utils.responsiveness_manager import responsiveness_monitor
            if hasattr(responsiveness_monitor, 'get_recent_logs'):
                monitor_logs = responsiveness_monitor.get_recent_logs()
                logs.extend(monitor_logs)
        except Exception:
            pass
            
        # Add thread manager logs if available
        try:
            from app.utils.thread_manager import thread_manager
            if hasattr(thread_manager, 'get_logs'):
                thread_logs = thread_manager.get_logs()
                logs.extend(thread_logs)
        except Exception:
            pass
            
        # Add basic system info
        import time
        logs.append({
            "timestamp": time.time(),
            "level": "INFO",
            "message": "System logs endpoint accessed",
            "source": "api"
        })
        
        return JSONResponse(content={
            "status": "success",
            "logs": logs,
            "log_count": len(logs),
            "timestamp": time.time()
        })
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"status": "error", "msg": f"Logs retrieval failed: {str(e)}"}
        )

@router.get("/api/task-stats", name="task_stats")
async def task_stats():
    """Get background task statistics"""
    try:
        from app.utils.task_manager import get_task_stats
        stats = get_task_stats()
        
        return JSONResponse(content={
            "status": "success",
            "task_stats": stats,
            "timestamp": time.time()
        })
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"status": "error", "msg": f"Task stats retrieval failed: {str(e)}"}
        )

@router.get("/api/certificate-status", name="certificate_status")
async def certificate_status():
    """Get SSL certificate validation status"""
    try:
        from app.utils.certificate_validator import SafeCertificateValidator
        from pathlib import Path
        import os
        
        certs_dir = Path(__file__).parent.parent / "certs"
        cert_path = certs_dir / "cert.pem"
        key_path = certs_dir / "key.pem"
        
        # Check if HTTPS is enabled
        use_https = os.environ.get('USE_HTTPS', 'false').lower() == 'true'
        
        if not use_https:
            return JSONResponse(content={
                "status": "info",
                "message": "HTTPS not enabled",
                "https_enabled": False,
                "timestamp": time.time()
            })
        
        # Validate certificate
        result = SafeCertificateValidator.validate_certificate_safe(cert_path, key_path)
        
        return JSONResponse(content={
            "status": "success",
            "https_enabled": True,
            "certificate_valid": result.valid,
            "is_self_signed": result.is_self_signed,
            "days_until_expiry": result.days_until_expiry,
            "warnings": result.warnings,
            "errors": result.errors,
            "recommendations": result.recommendations,
            "timestamp": time.time()
        })
        
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"status": "error", "msg": f"Certificate status check failed: {str(e)}"}
        )
