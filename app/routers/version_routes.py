"""
Lanvan Version Routes Router (version_routes.py)
Provides REST API endpoints for native logical file version history,
version restoration, and specific version downloading.
"""

from pathlib import Path
from typing import Optional
from fastapi import APIRouter, Request, HTTPException, Query
from fastapi.responses import JSONResponse, FileResponse, StreamingResponse

from app.core.version_manager import VersionManager, load_metadata, DATA_DIR

router = APIRouter(prefix="/api/files", tags=["file-versioning"])


@router.get("/{logical_file_id}/history", name="get_version_history")
async def get_version_history(logical_file_id: str):
    """
    Lazy-loads the full version history timeline for a given logical file ID.
    Returns version list sorted from newest to oldest.
    """
    try:
        lf = VersionManager.get_logical_file_by_id(logical_file_id)
        if not lf:
            # Fallback: check if logical_file_id was passed as path or filename
            raise HTTPException(status_code=404, detail="Logical file not found")

        versions = VersionManager.get_version_history(logical_file_id)
        return JSONResponse(content={
            "status": "success",
            "logicalFileId": logical_file_id,
            "displayName": lf.get("displayName", ""),
            "folder": lf.get("folder", ""),
            "versionCount": lf.get("versionCount", 1),
            "versions": versions
        })
    except HTTPException:
        raise
    except Exception as e:
        return JSONResponse(status_code=500, content={"status": "error", "message": str(e)})


@router.post("/{logical_file_id}/restore", name="restore_file_version")
async def restore_file_version(logical_file_id: str, request: Request):
    """
    Restores a specific historical version ID as a brand-new version (N+1).
    Broadcasts WebSocket file_updated notification.
    """
    try:
        body = await request.json()
        version_id = body.get("versionId")
        if not version_id:
            raise HTTPException(status_code=400, detail="Missing versionId in request body")

        success, msg = VersionManager.restore_version(logical_file_id, version_id)
        if not success:
            return JSONResponse(status_code=400, content={"status": "error", "message": msg})

        # Broadcast WebSocket event
        try:
            from app.ws_manager.file_events import broadcast_file_event_sync
            lf = VersionManager.get_logical_file_by_id(logical_file_id)
            folder_name = lf.get("folder") if lf else ""
            display_name = lf.get("displayName") if lf else ""
            broadcast_file_event_sync("restore", folder_name, display_name)
        except Exception as ws_err:
            print(f"[VERSION_ROUTES] WS broadcast warning: {ws_err}")

        return JSONResponse(content={
            "status": "success",
            "message": msg,
            "logicalFileId": logical_file_id
        })
    except HTTPException:
        raise
    except Exception as e:
        return JSONResponse(status_code=500, content={"status": "error", "message": str(e)})


@router.get("/{logical_file_id}/download", name="download_file_version")
async def download_file_version(logical_file_id: str, version_id: Optional[str] = Query(None)):
    """
    Stream-downloads a specific version binary (version_id) or latest version if omitted.
    """
    try:
        meta = load_metadata()
        lf = meta["logicalFiles"].get(logical_file_id)
        if not lf:
            raise HTTPException(status_code=404, detail="Logical file not found")

        target_v_id = version_id or lf.get("latestVersionId")
        v_meta = meta["versions"].get(target_v_id)
        if not v_meta or v_meta.get("logicalFileId") != logical_file_id:
            raise HTTPException(status_code=404, detail="Requested version record not found")

        rel_path = v_meta.get("storagePath", "")
        file_path = DATA_DIR / rel_path
        if not file_path.exists():
            raise HTTPException(status_code=404, detail=f"Version binary file missing on disk: {rel_path}")

        file_name = lf.get("displayName", file_path.name)
        mime_type = v_meta.get("mimeType", "application/octet-stream")

        return FileResponse(
            path=file_path,
            filename=file_name,
            media_type=mime_type
        )
    except HTTPException:
        raise
    except Exception as e:
        return JSONResponse(status_code=500, content={"status": "error", "message": str(e)})
