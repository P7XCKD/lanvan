"""
Lanvan Clipboard Router
Handles real-time clipboard sharing operations via WebSocket and HTTP fallback APIs.
Includes persistence mechanisms to save clipboard logs onto disk.
"""

import json
import time
import io
import os
import asyncio
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
from app.core.logger import logger

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

class _DynamicCacheVersion:
    """Cache-busting version string that changes only on server restart, not every second."""
    def __init__(self):
        self._version = hex(int(time.time()))[2:10]
    def __str__(self):
        return self._version

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
                logger.info("CLIPBOARD", "Loaded history from storage", details={"Items": len(clipboard_history)})
        else:
            logger.info("CLIPBOARD", "No persistent history found, starting fresh")
    except Exception as e:
        logger.error("CLIPBOARD", "Error loading history", details={"Reason": str(e)})
        clipboard_history = []
        clipboard_id_counter = 0


def save_clipboard_history():
    """Save clipboard history to persistent storage"""
    global clipboard_history, clipboard_id_counter

    try:
        if len(clipboard_history) > 50:
            clipboard_history = clipboard_history[:50]

        save_data = {
            'items': [],
            'last_id': clipboard_id_counter
        }

        for item in clipboard_history:
            save_item = item.copy()
            if item['type'] == 'file' and 'data' in item:
                import base64
                save_item['data'] = base64.b64encode(item['data']).decode('utf-8')
                save_item['data_encoding'] = 'base64'
            save_data['items'].append(save_item)

        CLIPBOARD_FOLDER.mkdir(parents=True, exist_ok=True)
        temp_file = CLIPBOARD_HISTORY_FILE.with_suffix('.tmp')
        with open(temp_file, 'w', encoding='utf-8') as f:
            json.dump(save_data, f, indent=2, ensure_ascii=False)

        temp_file.replace(CLIPBOARD_HISTORY_FILE)

    except Exception as e:
        logger.error("CLIPBOARD", "Error saving history", details={"Reason": str(e)})


def restore_clipboard_data(items):
    """Restore clipboard data after loading from JSON (decode base64 data)"""
    for item in items:
        if item.get('data_encoding') == 'base64' and 'data' in item:
            import base64
            try:
                item['data'] = base64.b64decode(item['data'])
                del item['data_encoding']
            except Exception as e:
                logger.error("CLIPBOARD", "Error decoding item", details={"ID": item.get('id', 'unknown'), "Reason": str(e)})
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
        logger.info("CLIPBOARD", "Persistence initialized", details={"Items": len(clipboard_history)})
    except Exception as e:
        logger.error("CLIPBOARD", "Persistence initialization failed", details={"Reason": str(e)})
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
        if not file and not data:
            try:
                content_type_header = request.headers.get("content-type", "")
                if "application/json" in content_type_header:
                    json_body = await request.json()
                    data = json_body.get("data") or json_body.get("text")
                else:
                    form = await request.form()
                    if "file" in form:
                        file = form["file"]
                    elif "data" in form:
                        data = form["data"]
            except Exception:
                pass

        clipboard_id_counter += 1
        timestamp = time.time()

        if file and (isinstance(file, UploadFile) or hasattr(file, "filename")):
            filename = getattr(file, "filename", None) or f"clipboard-image-{int(timestamp)}.png"

            if not filename:
                return JSONResponse(
                    status_code=400,
                    content={"status": "error", "msg": "No filename provided"}
                )

            allowed_types = {
                'image': ['jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp', 'svg'],
                'text': ['txt', 'md', 'json', 'csv', 'xml'],
                'document': ['pdf', 'doc', 'docx'],
                'other': ['zip', 'rar', '7z']
            }

            file_ext = filename.split('.')[-1].lower() if '.' in filename else ''
            content_type = 'other'

            for type_name, extensions in allowed_types.items():
                if file_ext in extensions:
                    content_type = type_name
                    break

            CHUNK_SIZE = get_adaptive_chunk_size(1024 * 1024)
            MAX_SIZE = 10 * 1024 * 1024
            file_content = b""
            file_size = 0

            if hasattr(file, "read"):
                while True:
                    chunk = await file.read(CHUNK_SIZE) if asyncio.iscoroutinefunction(file.read) else file.read(CHUNK_SIZE)
                    if not chunk:
                        break
                    file_size += len(chunk)

                    if file_size > MAX_SIZE:
                        return JSONResponse(
                            status_code=400,
                            content={"status": "error", "msg": "File too large for clipboard (max 10MB)"}
                        )

                    file_content += chunk
            elif isinstance(file, bytes):
                file_content = file
                file_size = len(file)

            preview = generate_simple_file_preview(filename, file_content, content_type)

            clipboard_item = {
                "id": clipboard_id_counter,
                "type": "file",
                "content_type": content_type,
                "filename": filename,
                "size": file_size,
                "data": file_content,
                "timestamp": timestamp,
                "formatted_time": time.strftime("%I:%M:%S %p", time.localtime(timestamp)),
                "preview": preview,
                "is_image_preview": content_type == 'image' and preview.startswith('data:')
            }

            logger.log_clipboard("Add", item_type=content_type, size_bytes=file_size, status="SUCCESS")

        elif data and isinstance(data, str):
            content_size = len(data.encode('utf-8'))

            if data.startswith('data:image/'):
                content_type = 'image_base64'
                preview = "Base64 image data (no preview)"
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

            logger.log_clipboard("Add", item_type=content_type, size_bytes=content_size, status="SUCCESS")
        else:
            return JSONResponse(
                status_code=400,
                content={"status": "error", "msg": "No content provided"}
            )

        clipboard_history.insert(0, clipboard_item)

        if len(clipboard_history) > 50:
            clipboard_history = clipboard_history[:50]

        save_clipboard_history()

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
        logger.log_clipboard("Add", status="FAILED", reason=str(e))
        return JSONResponse(
            status_code=500,
            content={"status": "error", "msg": f"Failed to add to clipboard: {str(e)}"}
        )


@router.get("/api/clipboard/list", name="clipboard_list")
async def get_clipboard_history():
    """Get clipboard history for current session"""
    global clipboard_history

    try:
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

        logger.log_clipboard("Read", item_type=item.get("content_type", "TEXT"), size_bytes=item.get("size"))
        is_download = download is not None and str(download).lower() in ("1", "true", "yes")

        if item["type"] == "file":
            file_data = item["data"]
            filename = item["filename"]
            
            from app.core.validation import secure_filename
            from urllib.parse import quote
            
            safe_name = secure_filename(filename) or "file"
            encoded_filename = quote(safe_name)

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

def clear_clipboard_data_sync() -> None:
    """Clear all clipboard items from in-memory state and persistent storage synchronously."""
    global clipboard_history
    clipboard_history.clear()
    save_clipboard_history()

@router.delete("/api/clipboard/clear", name="clipboard_clear")
async def clear_clipboard():
    """Clear all clipboard items from history and persistent storage."""
    clear_clipboard_data_sync()
    logger.log_clipboard("Clear", status="SUCCESS")
    
    try:
        await clipboard_ws_manager.broadcast("refresh")
    except Exception:
        pass
    return {"status": "success", "msg": "Clipboard cleared", "message": "Clipboard cleared"}


@router.delete("/api/clipboard/remove/{item_id}", name="clipboard_remove")
@router.delete("/api/clipboard/delete/{item_id}", name="clipboard_delete_alias")
async def remove_clipboard_item(item_id: int):
    """Delete a single clipboard item from history."""
    global clipboard_history
    for idx, item in enumerate(clipboard_history):
        if item["id"] == item_id:
            clipboard_history.pop(idx)
            save_clipboard_history()
            logger.log_clipboard("Remove", status="SUCCESS")
            
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
    """Get simple clipboard status information."""
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
        return JSONResponse(
            status_code=500,
            content={"status": "error", "msg": f"Clipboard write failed: {str(e)}"}
        )
