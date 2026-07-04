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

from app.aes_utils import AESConfig
from app.simple_mdns import mdns_manager
from app.termux_compat import get_platform_info, detect_platform, is_android, is_termux
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
            lambda: "192.168.1.100"  # Fallback
        ]
        
        for method in methods:
            try:
                ip = method()
                if ip and not ip.startswith('127.') and ip != '192.0.0.4':
                    return ip, hostname
            except Exception:
                continue
                
        return "192.168.1.100", hostname  # Ultimate fallback
    except Exception as e:
        print(f"[MOBILE] Android network detection error: {e}")
        return "192.168.1.100", "android-device"

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
    
    status_data = {
        "status": "online",
        "message": "[OK] Server is running normally",
        "timestamp": time.time(),
        "resources_ready": resources_ready,
        "shutdown": False,
        "server_info": {
            "protocol": protocol,
            "host": host,
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
        from app.termux_compat import get_platform_info
        
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
    """Get optimal chunk size for a file upload based on system capabilities"""
    from app.universal_optimizer import get_adaptive_chunk_size
    
    try:
        # Get adaptive chunk size
        optimal_chunk_size = get_adaptive_chunk_size(file_size)
        
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
async def emergency_shutdown():
    """
    Emergency server shutdown endpoint - immediately terminates server
    and notifies all connected clients.
    """
    import asyncio
    from app.main import shutdown_event, connection_manager
    
    print("[!] EMERGENCY SHUTDOWN REQUESTED!")
    print("[WARN] Notifying all connected clients...")
    
    # Set the shutdown flag immediately
    shutdown_event.set()
    
    # Send shutdown notifications to all active clients
    async def notify_clients():
        await connection_manager.disconnect_all()
        print("[OK] All clients notified and disconnected")
    
    # Schedule client notification in background
    asyncio.create_task(notify_clients())
    
    # Force server shutdown after brief delay for response
    async def force_shutdown():
        await asyncio.sleep(0.5)  # Allow response to be sent
        print("[HOT] FORCING SERVER SHUTDOWN...")
        import os
        os._exit(0)  # Force immediate shutdown
    
    asyncio.create_task(force_shutdown())
    
    return JSONResponse({
        "status": "shutdown",
        "message": "[!] Server is shutting down immediately. All operations halted.",
        "warning": "[WARN] All active uploads and downloads have been terminated.",
        "action": "Server will restart automatically if using a process manager."
    })

@router.get("/api/network-info", name="network_info")
async def get_network_info():
    """Get network information including LAN IP and mDNS info"""
    try:
        import socket
        import os
        
        # Check if we're on Android/Termux
        is_android = ("ANDROID_STORAGE" in os.environ or 
                     os.path.exists("/data/data/com.termux") or 
                     "TERMUX_VERSION" in os.environ)
        
        # Use mDNS manager's offline-capable method to get LAN IP
        lan_ip = mdns_manager.get_lan_ip()
        
        # Get mDNS info
        mdns_info = mdns_manager.get_mdns_info()
        
        # Get hybrid URL (IP-optimized for Android/Termux)
        hybrid_url = mdns_manager.get_hybrid_url()
        
        # Also provide separate URL components for QR code generation
        protocol = "https" if mdns_manager.use_https else "http"
        port = mdns_manager.port
        
        # Format LAN IP URL using the same logic as mDNS URLs
        if (port == 80 and protocol == "http") or (port == 443 and protocol == "https"):
            lan_ip_url = f"{protocol}://{lan_ip}"
        else:
            lan_ip_url = f"{protocol}://{lan_ip}:{port}"
        
        response_data = {
            "status": "success",
            "lan_ip": lan_ip,
            "lan_ip_url": lan_ip_url,
            "hostname": socket.gethostname(),
            "mdns": mdns_info,
            "hybrid_url": hybrid_url,
            "protocol": protocol,
            "port": port,
            "platform": "android" if is_android else "desktop"
        }
        
        # Add Android/Termux specific recommendations
        if is_android:
            response_data["android_info"] = mdns_manager.get_android_optimized_info()
            response_data["recommendations"] = [
                f"Use IP address: {lan_ip_url}",
                "Avoid .local domains on Android/Termux",
                "Share QR code for easy mobile access",
                "Bookmark the IP address for future use"
            ]
        
        return JSONResponse(content=response_data)
    except Exception as e:
        # Create fallback URL using the same format logic as mdns_manager
        protocol = "https" if mdns_manager.use_https else "http"
        port = mdns_manager.port
        if (port == 80 and protocol == "http") or (port == 443 and protocol == "https"):
            fallback_url = f"{protocol}://127.0.0.1"
            lan_ip_fallback = f"{protocol}://127.0.0.1"
        else:
            fallback_url = f"{protocol}://127.0.0.1:{port}"
            lan_ip_fallback = f"{protocol}://127.0.0.1:{port}"
        
        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "error": str(e),
                "lan_ip": "127.0.0.1",
                "lan_ip_url": lan_ip_fallback,
                "mdns": {"status": "error", "domain": None},
                "hybrid_url": fallback_url,
                "protocol": protocol,
                "port": port
            }
        )

@router.get("/api/qr-code", name="offline_qr")
async def generate_offline_qr(text: str, size: int = 200):
    """Generate QR code locally without internet dependency - Android/Termux optimized"""
    try:
        # Android/Termux detection
        is_android = ("ANDROID_STORAGE" in os.environ or 
                     os.path.exists("/data/data/com.termux") or 
                     "TERMUX_VERSION" in os.environ)
        
        if is_android:
            print("[MOBILE] Android/Termux QR generation - using optimized settings")
        
        # Create QR code with Android-optimized settings
        box_size = max(1, size // 25) if not is_android else max(2, size // 20)  # Larger boxes for Android
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.ERROR_CORRECT_L,
            box_size=box_size,
            border=4,
        )
        qr.add_data(text)
        qr.make(fit=True)

        # Create image with Android fallbacks
        try:
            qr_img = qr.make_image(fill_color="black", back_color="white")
        except Exception as img_error:
            if is_android:
                print(f"[MOBILE] Android QR image creation fallback: {img_error}")
                # Try simpler image creation for Android
                qr_img = qr.make_image()
            else:
                raise img_error
        
        # Convert to bytes with Android-specific handling
        img_buffer = io.BytesIO()
        
        # Enhanced save method with multiple fallbacks
        save_success = False
        
        # Method 1: Standard PNG save
        if not save_success:
            try:
                qr_img.save(img_buffer, 'PNG')
                save_success = True
                if is_android:
                    print("[MOBILE] Android QR: PNG save successful")
            except Exception as png_error:
                if is_android:
                    print(f"[MOBILE] Android QR PNG save failed: {png_error}")
        
        # Method 2: Format-less save (Android fallback)
        if not save_success:
            try:
                img_buffer = io.BytesIO()  # Reset buffer
                qr_img.save(img_buffer)
                save_success = True
                if is_android:
                    print("[MOBILE] Android QR: Fallback save successful")
            except Exception as fallback_error:
                if is_android:
                    print(f"[MOBILE] Android QR fallback save failed: {fallback_error}")
        
        # Method 3: Text-based QR for Android (ultimate fallback)
        if not save_success and is_android:
            try:
                # Generate ASCII QR code for Android as last resort
                qr_text = qr.get_matrix()
                ascii_qr = "\n".join(["".join(["██" if cell else "  " for cell in row]) for row in qr_text])
                return JSONResponse({
                    "status": "text_fallback",
                    "qr_text": ascii_qr,
                    "url": text,
                    "message": "QR generated as text for Android compatibility"
                })
            except Exception as text_error:
                print(f"[MOBILE] Android QR text fallback failed: {text_error}")
        
        if not save_success:
            raise Exception(f"All QR generation methods failed")
        
        img_buffer.seek(0)

        return StreamingResponse(
            io.BytesIO(img_buffer.getvalue()),
            media_type="image/png",
            headers={"Cache-Control": "public, max-age=3600"}
        )
    except Exception as e:
        # Return a simple text-based error response
        return JSONResponse(
            status_code=500,
            content={"error": f"QR generation failed: {str(e)}"}
        )

@router.get("/api/mdns-info", name="mdns_info")
async def mdns_info():
    """Get mDNS service information"""
    try:
        from app.simple_mdns import mdns_manager
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
        from app.aes_utils import AES_CONFIG
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
            from app.responsiveness_manager import responsiveness_monitor
            if hasattr(responsiveness_monitor, 'get_recent_logs'):
                monitor_logs = responsiveness_monitor.get_recent_logs()
                logs.extend(monitor_logs)
        except Exception:
            pass
            
        # Add thread manager logs if available
        try:
            from app.thread_manager import thread_manager
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
        from app.task_manager import get_task_stats
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
        from app.certificate_validator import SafeCertificateValidator
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
