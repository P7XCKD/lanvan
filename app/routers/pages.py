"""
Lanvan Pages Router
Handles UI rendering endpoints, iOS Safari device detection redirects,
loading states, and standard static favicon resolution.
"""

from fastapi import APIRouter, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse
from fastapi.templating import Jinja2Templates

from app.utils.simple_mdns import mdns_manager
from app.routers.files import detect_ios_device, get_file_list, UPLOAD_FOLDER

# Initialize router and Jinja2 templates engine
router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

@router.get("/", response_class=HTMLResponse, name="home") 
async def home(request: Request):
    """
    Universal mDNS Redirect + Main Page Handler with iOS Detection.
    Handles lanvan.local access regardless of port/protocol with smart redirects.
    """
    host = request.headers.get("host", "").lower()
    user_agent = request.headers.get("user-agent", "")
    
    # iOS Device Detection for tailored page optimizations
    ios_info = detect_ios_device(user_agent)
    
    # Universal mDNS Redirect Logic for lanvan.local
    if "lanvan.local" in host:
        actual_port = mdns_manager.actual_port
        actual_protocol = mdns_manager.actual_protocol
        current_scheme = request.url.scheme
        
        # iOS Safari Special Handling - Prefer HTTP for better compatibility
        if ios_info['is_mobile_safari'] and current_scheme == "https":
            http_port = 5000  # Our HTTP fallback port
            redirect_url = f"http://lanvan.local:{http_port}{request.url.path}"
            if request.url.query:
                redirect_url += f"?{request.url.query}"
            
            print(f"iOS Safari detected - redirecting to HTTP for compatibility: {redirect_url}")
            return RedirectResponse(url=redirect_url, status_code=302)
        
        # Standard redirect logic for non-iOS devices to match server configuration
        if current_scheme == "http" and actual_protocol == "https" and not ios_info['is_mobile_safari']:
            if actual_port == 443:
                redirect_url = f"https://lanvan.local{request.url.path}"
            else:
                redirect_url = f"https://lanvan.local:{actual_port}{request.url.path}"
            
            if request.url.query:
                redirect_url += f"?{request.url.query}"
            
            return RedirectResponse(url=redirect_url, status_code=302)
    
    # Main page logic - direct access, no redirects
    files = get_file_list()
    protocol = request.url.scheme
    host = request.headers.get("host", "unknown")
    
    template_context = {
        "request": request,
        "msg": "Lanvan",
        "files": [f["name"] for f in files],
        "debug_info": {
            "protocol": protocol,
            "host": host,
            "port": "5000" if ":5000" in host else "5001" if ":5001" in host else "unknown"
        },
        "show_both_sections": True,
        "default_view": "file",
        "ios_info": ios_info,  # Pass iOS detection info to template
        "is_ios_device": ios_info['is_ios'],
        "is_mobile_safari": ios_info['is_mobile_safari']
    }
    
    if ios_info['is_ios']:
        print(f"iOS device detected: {ios_info['device_type']} - Safari: {ios_info['is_safari']} - Protocol: {protocol} - Host: {host}")
    
    return templates.TemplateResponse("index.html", template_context)


@router.get("/ios-help", response_class=HTMLResponse)
async def ios_help_page(request: Request):
    """iOS Safari troubleshooting and help page."""
    return templates.TemplateResponse("ios-help.html", {"request": request})


@router.get("/loading", response_class=HTMLResponse, name="loading")
async def loading_page(request: Request, redirect: str = "/"):
    """Loading page shown while resources are being prepared."""
    return templates.TemplateResponse("loading.html", {
        "request": request,
        "redirect_url": redirect
    })


@router.get("/favicon.ico", name="favicon")
async def favicon():
    """Serve favicon.ico from static directory."""
    try:
        favicon_path = UPLOAD_FOLDER.parent / "static" / "favicon.ico"
        if favicon_path.exists():
            return FileResponse(
                path=str(favicon_path),
                media_type="image/x-icon",
                headers={"Cache-Control": "public, max-age=86400"}  # Cache for 1 day
            )
        else:
            # Fallback to static/images/icon.png if favicon.ico is missing
            png_favicon_path = UPLOAD_FOLDER.parent / "static" / "images" / "icon.png"
            if png_favicon_path.exists():
                return FileResponse(
                    path=str(png_favicon_path),
                    media_type="image/png",
                    headers={"Cache-Control": "public, max-age=86400"}
                )
            return Response(status_code=204)
    except Exception:
        return Response(status_code=204)
