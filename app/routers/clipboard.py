"""
Lanvan Clipboard Router
Handles real-time clipboard sharing operations via WebSocket and HTTP fallback APIs.
Includes persistence mechanisms to save clipboard logs onto disk.
"""

import json
import time
import io
from pathlib import Path
from typing import Optional
from mimetypes import guess_type

from fastapi import APIRouter, Request, Form, File, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from starlette.status import HTTP_400_BAD_REQUEST

from app.ws_manager import clipboard_ws_manager
from app.routers.files import generate_simple_file_preview
from app.utils.universal_optimizer import get_adaptive_chunk_size

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")
class _DynamicCacheVersion:
    def __str__(self):
        return str(int(time.time()))

templates.env.globals["cache_version"] = _DynamicCacheVersion()

try:
    from app.utils.android_compat import get_base_data_dir
    CLIPBOARD_FOLDER = get_base_data_dir() / "data/clipboard"
except ImportError:
    CLIPBOARD_FOLDER = Path("data/clipboard")

CLIPBOARD_HISTORY_FILE = CLIPBOARD_FOLDER / "clipboard_history.json"
clipboard_history = []
clipboard_id_counter = 1


def load_clipboard_history():
    """Load clipboard history from persistent storage on startup"""
    global clipboard_history, clipboard_id_counter

    try:
        if CLIPBOARD_HISTORY_FILE.exists():
            with open(CLIPBOARD_HISTORY_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                clipboard_history = data.get('items', [])
                clipboard_id_counter = data.get('last_id', 0)
                print(f"[INFO] Loaded {len(clipboard_history)} clipboard items from persistent storage")
        else:
            print("[INFO] No persistent clipboard history found, starting fresh")
    except Exception as e:
        print(f"[ERR] Error loading clipboard history: {e}")
        clipboard_history = []
        clipboard_id_counter = 0


def save_clipboard_history():
    """Save clipboard history to persistent storage"""
    global clipboard_history, clipboard_id_counter

    try:
        # Enforce history limit to prevent file bloating
        if len(clipboard_history) > 50:
            clipboard_history = clipboard_history[:50]

        # Prepare data for saving (convert binary data to base64 for JSON serialization)
        save_data = {
            'items': [],
            'last_id': clipboard_id_counter
        }

        for item in clipboard_history:
            save_item = item.copy()

            # Handle binary data for files
            if item['type'] == 'file' and 'data' in item:
                import base64
                save_item['data'] = base64.b64encode(item['data']).decode('utf-8')
                save_item['data_encoding'] = 'base64'

            save_data['items'].append(save_item)

        # Ensure directory exists before writing
        CLIPBOARD_FOLDER.mkdir(parents=True, exist_ok=True)

        # Write to file atomically
        temp_file = CLIPBOARD_HISTORY_FILE.with_suffix('.tmp')
        with open(temp_file, 'w', encoding='utf-8') as f:
            json.dump(save_data, f, indent=2, ensure_ascii=False)

        # Atomic rename
        temp_file.replace(CLIPBOARD_HISTORY_FILE)

    except Exception as e:
        print(f"[ERR] Error saving clipboard history: {e}")


def restore_clipboard_data(items):
    """Restore clipboard data after loading from JSON (decode base64 data)"""
    for item in items:
        if item.get('data_encoding') == 'base64' and 'data' in item:
            import base64
            try:
                item['data'] = base64.b64decode(item['data'])
                del item['data_encoding']  # Remove the encoding marker
            except Exception as e:
                print(f"[ERR] Error decoding clipboard item {item.get('id', 'unknown')}: {e}")
                # Remove corrupted item
                continue

    return items


def initialize_clipboard_persistence():
    """Initialize clipboard persistence after all imports are complete"""
    try:
        CLIPBOARD_FOLDER.mkdir(parents=True, exist_ok=True)
        load_clipboard_history()
        global clipboard_history
        if clipboard_history:
            clipboard_history = restore_clipboard_data(clipboard_history)
        print(f"[INFO] Clipboard persistence initialized successfully with {len(clipboard_history)} items")
    except Exception as e:
        print(f"[ERR] Error initializing clipboard persistence: {e}")
        clipboard_history.clear()
        global clipboard_id_counter
        clipboard_id_counter = 0


def safe_template_response(templates, request, name, context):
    context = dict(context)
    if "request" not in context:
        context["request"] = request
    try:
        return templates.TemplateResponse(request, name, context)
    except (TypeError, ValueError):
        return templates.TemplateResponse(name, context)


@router.get("/clipboard", response_class=HTMLResponse)
async def clipboard_page(request: Request):
    """Serve clipboard management page."""
    return safe_template_response(templates, request, "clipboard.html", {
        "clipboard_history": clipboard_history
    })


@router.post("/api/clipboard/add", name="clipboard_add")
async def add_to_clipboard(
    request: Request,
    data: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None)
):
    """Add content to clipboard - supports text and files (no image preview)"""
    global clipboard_id_counter, clipboard_history

    try:
        clipboard_id_counter += 1
        timestamp = time.time()

        if file and isinstance(file, UploadFile):

            # Handle file upload to clipboard
            if not file.filename:
                return JSONResponse(
                    status_code=400,
                    content={"status": "error", "msg": "No filename provided"}
                )

            # Validate file type for clipboard
            allowed_types = {
                'image': ['jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp', 'svg'],
                'text': ['txt', 'md', 'json', 'csv', 'xml'],
                'document': ['pdf', 'doc', 'docx'],
                'other': ['zip', 'rar', '7z']
            }

            file_ext = file.filename.split('.')[-1].lower() if '.' in file.filename else ''
            content_type = 'other'

            for type_name, extensions in allowed_types.items():
                if file_ext in extensions:
                    content_type = type_name
                    break

            # Get platform-optimal chunk size
            CHUNK_SIZE = get_adaptive_chunk_size(1024 * 1024)
            MAX_SIZE = 10 * 1024 * 1024  # 10MB limit
            file_content = b""
            file_size = 0

            while True:
                chunk = await file.read(CHUNK_SIZE)
                if not chunk:
                    break
                file_size += len(chunk)

                # Check size limit as we read
                if file_size > MAX_SIZE:
                    return JSONResponse(
                        status_code=400,
                        content={"status": "error", "msg": "File too large for clipboard (max 10MB)"}
                    )

                file_content += chunk

            # Create clipboard item for file (with base64 image preview)
            preview = generate_simple_file_preview(file.filename, file_content, content_type)

            clipboard_item = {
                "id": clipboard_id_counter,
                "type": "file",
                "content_type": content_type,
                "filename": file.filename,
                "size": file_size,
                "data": file_content,
                "timestamp": timestamp,
                "formatted_time": time.strftime("%I:%M:%S %p", time.localtime(timestamp)),
                "preview": preview,
                "is_image_preview": content_type == 'image' and preview.startswith('data:')
            }

        elif data and isinstance(data, str):

            # Handle text/data content
            content_size = len(data.encode('utf-8'))

            # Detect content type
            if data.startswith('data:image/'):
                content_type = 'image_base64'
                preview = "Base64 image data (no preview)"  # No image preview
            elif data.startswith('http://') or data.startswith('https://'):
                content_type = 'url'
                preview = data[:100] + "..." if len(data) > 100 else data
            else:
                content_type = 'text'
                preview = data[:200] + "..." if len(data) > 200 else data

            clipboard_item = {
                "id": clipboard_id_counter,
                "type": "text",
                "content_type": content_type,
                "data": data,
                "size": content_size,
                "timestamp": timestamp,
                "formatted_time": time.strftime("%I:%M:%S %p", time.localtime(timestamp)),
                "preview": preview
            }
        else:
            return JSONResponse(
                status_code=400,
                content={"status": "error", "msg": "No content provided"}
            )

        # Add to clipboard history (newest first)
        clipboard_history.insert(0, clipboard_item)

        # Keep only last 50 items to prevent memory bloat
        if len(clipboard_history) > 50:
            clipboard_history = clipboard_history[:50]

        # Save to persistent storage
        save_clipboard_history()

        # Notify all websocket clients (real-time clipboard update)
        try:
            await clipboard_ws_manager.broadcast("refresh")
        except Exception:
            pass

        return JSONResponse(content={
            "status": "success",
            "msg": f"Added to clipboard: {clipboard_item['type']}",
            "item": {
                "id": clipboard_item["id"],
                "type": clipboard_item["type"],
                "content_type": clipboard_item["content_type"],
                "size": clipboard_item["size"],
                "timestamp": clipboard_item["formatted_time"],
                "preview": clipboard_item["preview"],
                "is_image_preview": clipboard_item.get("is_image_preview", False)
            }
        })

    except Exception as e:
        import traceback
        traceback.print_exc()

        return JSONResponse(
            status_code=500,
            content={"status": "error", "msg": f"Failed to add to clipboard: {str(e)}"}
        )


@router.get("/api/clipboard/list", name="clipboard_list")
async def get_clipboard_history():
    """Get clipboard history for current session"""
    global clipboard_history

    try:
        # Return sanitized clipboard history (without large data but with image previews)
        history = []
        for item in clipboard_history:
            sanitized_item = {
                "id": item["id"],
                "type": item["type"],
                "content_type": item["content_type"],
                "size": item["size"],
                "timestamp": item.get("formatted_time", ""),
                "preview": item.get("preview", ""),
                "is_image_preview": item.get("is_image_preview", False)
            }

            # Add filename for file items
            if item["type"] == "file":
                sanitized_item["filename"] = item["filename"]

            history.append(sanitized_item)

        return JSONResponse(content={
            "status": "success",
            "items": history,
            "count": len(history)
        })

    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"status": "error", "msg": f"Failed to get clipboard history: {str(e)}"}
        )


@router.get("/api/clipboard/get/{item_id}", name="clipboard_get")
async def get_clipboard_item(item_id: int, request: Request, download: Optional[str] = None):
    """Retrieve a single clipboard item by ID, or download as file/attachment."""
    try:
        item = next((i for i in clipboard_history if i["id"] == item_id), None)
        if not item:
            return JSONResponse(
                status_code=404,
                content={"status": "error", "msg": "Clipboard item not found"}
            )

        is_download = download is not None and str(download).lower() in ("1", "true", "yes")

        if item["type"] == "file":
            # Return file as download or inline preview

            file_data = item["data"]
            filename = item["filename"]
            
            from app.core.validation import secure_filename
            from urllib.parse import quote
            
            safe_name = secure_filename(filename) or "file"
            encoded_filename = quote(safe_name)

            # Determine MIME type
            mime_type, _ = guess_type(safe_name)
            if not mime_type:
                mime_type = "application/octet-stream"

            disposition = "attachment" if (is_download or not mime_type.startswith("image/")) else "inline"

            return StreamingResponse(
                io.BytesIO(file_data),
                media_type=mime_type,
                headers={
                    "Content-Disposition": f'{disposition}; filename="{safe_name}"; filename*=UTF-8\'\'{encoded_filename}',
                    "Content-Length": str(len(file_data))
                }
            )

        else:
            if is_download:
                raw_text = item.get("data") or ""
                text_bytes = raw_text.encode("utf-8")
                filename = f"pasted-text-{item_id}.txt"
                from urllib.parse import quote
                encoded_filename = quote(filename)
                return StreamingResponse(
                    io.BytesIO(text_bytes),
                    media_type="text/plain; charset=utf-8",
                    headers={
                        "Content-Disposition": f'attachment; filename="{filename}"; filename*=UTF-8\'\'{encoded_filename}',
                        "Content-Length": str(len(text_bytes))
                    }
                )

            # Return text content JSON for non-download API callers

            return JSONResponse(content={
                "status": "success",
                "item": {
                    "id": item["id"],
                    "type": item["type"],
                    "content_type": item["content_type"],
                    "data": item["data"],
                    "size": item["size"],
                    "timestamp": item["formatted_time"]
                }
            })

    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"status": "error", "msg": f"Failed to get clipboard item: {str(e)}"}
        )


@router.post("/api/clipboard/download-zip", name="clipboard_download_zip")
async def download_clipboard_zip(request: Request):
    """Download multiple selected clipboard items packaged into a single ZIP archive."""
    try:
        data = await request.json()
        raw_ids = data.get("item_ids", [])
        if not raw_ids:
            return JSONResponse(status_code=400, content={"status": "error", "msg": "No item_ids provided"})

        valid_ids = set()
        for val in raw_ids:
            try:
                valid_ids.add(int(val))
            except (ValueError, TypeError):
                pass

        if not valid_ids:
            return JSONResponse(status_code=400, content={"status": "error", "msg": "Invalid item_ids"})

        target_items = [item for item in clipboard_history if item["id"] in valid_ids]
        if not target_items:
            return JSONResponse(status_code=404, content={"status": "error", "msg": "No matching clipboard items found"})

        import zipfile
        zip_buffer = io.BytesIO()
        used_filenames = set()

        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            for item in target_items:
                item_id = item["id"]
                if item["type"] == "file":
                    fname = item.get("filename") or f"file-{item_id}"
                    file_data = item.get("data") or b""
                else:
                    text_str = item.get("data") or ""
                    file_data = text_str.encode("utf-8")
                    fname = f"clipboard-text-{item_id}.txt"

                base_name = fname
                counter = 1
                while fname in used_filenames:
                    name_part, ext_part = os.path.splitext(base_name)
                    fname = f"{name_part}_{counter}{ext_part}"
                    counter += 1
                used_filenames.add(fname)

                zf.writestr(fname, file_data)

        zip_buffer.seek(0)
        zip_bytes = zip_buffer.getvalue()

        from urllib.parse import quote
        filename = "clipboard_selection.zip"
        encoded_filename = quote(filename)

        return StreamingResponse(
            io.BytesIO(zip_bytes),
            media_type="application/zip",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"; filename*=UTF-8\'\'{encoded_filename}',
                "Content-Length": str(len(zip_bytes))
            }
        )

    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"status": "error", "msg": f"Failed to create ZIP archive: {str(e)}"}
        )

@router.delete("/api/clipboard/clear", name="clipboard_clear")
async def clear_clipboard():
    """Clear all clipboard items from history and persistent storage."""
    global clipboard_history
    clipboard_history.clear()
    save_clipboard_history()
    
    # Broadcast clear action to active WebSocket listeners
    try:
        await clipboard_ws_manager.broadcast("refresh")
    except Exception:
        pass
    return {"status": "success", "msg": "Clipboard cleared", "message": "Clipboard cleared"}


@router.delete("/api/clipboard/remove/{item_id}", name="clipboard_remove")
async def remove_clipboard_item(item_id: int):
    """Delete a single clipboard item from history."""
    global clipboard_history
    for idx, item in enumerate(clipboard_history):
        if item["id"] == item_id:
            clipboard_history.pop(idx)
            save_clipboard_history()
            
            # Broadcast delete action to active WebSocket listeners
            try:
                await clipboard_ws_manager.broadcast("refresh")
            except Exception:
                pass
            return {"status": "success", "msg": f"Item {item_id} deleted", "message": f"Item {item_id} deleted"}
            
    return JSONResponse(
        status_code=404,
        content={"status": "error", "msg": "Item not found", "message": "Item not found"}
    )



@router.get("/api/clipboard", name="clipboard_status")
async def clipboard_status():
    """Get simple clipboard status status information."""
    return {"status": "success", "count": len(clipboard_history)}


@router.post("/api/clipboard", name="clipboard_write")
async def clipboard_write(request: Request):
    """Direct API endpoint for writing text data to clipboard."""
    try:
        content_type = request.headers.get("content-type", "").lower()

        if "application/json" in content_type:
            payload = await request.json()
            data = payload.get("data")
            if not isinstance(data, str):
                return JSONResponse(
                    status_code=HTTP_400_BAD_REQUEST,
                    content={"status": "error", "msg": "JSON clipboard writes must include a text 'data' field"}
                )
            return await add_to_clipboard(request, data=data)

        form = await request.form()
        data = form.get("data")
        if isinstance(data, str) and data:
            return await add_to_clipboard(request, data=data)

        return JSONResponse(
            status_code=HTTP_400_BAD_REQUEST,
            content={"status": "error", "msg": "No clipboard data provided"}
        )
    except Exception as e:
        import traceback
        traceback.print_exc()

        return JSONResponse(
            status_code=500,
            content={"status": "error", "msg": f"Clipboard write failed: {str(e)}"}
        )
