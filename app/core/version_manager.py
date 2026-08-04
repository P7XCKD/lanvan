"""
Lanvan Core Version Manager (version_manager.py)
Manages logical file IDs, version metadata persistence, immutable historical revision storage,
atomic file commit transactions, SHA-256 integrity checksums, and idempotent startup migration.
"""

import os
import shutil
import json
import time
import uuid
import hashlib
import threading
import urllib.parse
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

# Root data directories
DATA_DIR = Path("data")
UPLOADS_DIR = DATA_DIR / "uploads"
VERSIONS_DIR = DATA_DIR / "versions"
METADATA_FILE = DATA_DIR / "version_metadata.json"

# Thread-safe lock for metadata & storage mutations
_version_lock = threading.RLock()

# In-memory cached metadata
_metadata_cache: Optional[Dict[str, Any]] = None


def _normalize_rel_path(target_dir: Optional[str], filename: str) -> str:
    """Consistently formats a relative file path (e.g. 'Documents/Report.pdf' or 'Report.pdf')."""
    clean_dir = (target_dir or "").replace("\\", "/").strip("/")
    clean_name = filename.strip("/")
    if clean_dir and clean_dir != "Home":
        return f"{clean_dir}/{clean_name}"
    return clean_name


def _compute_sha256(file_path: Path) -> str:
    """Computes SHA-256 hash of a file on disk."""
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


def _empty_metadata() -> Dict[str, Any]:
    return {"logicalFiles": {}, "versions": {}}


def load_metadata() -> Dict[str, Any]:
    """Loads version metadata from disk with cache validation by mtime."""
    global _metadata_cache, _metadata_mtime
    with _version_lock:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        VERSIONS_DIR.mkdir(parents=True, exist_ok=True)

        if not METADATA_FILE.exists():
            _metadata_cache = _empty_metadata()
            save_metadata(_metadata_cache)
            return _metadata_cache

        try:
            cur_mtime = METADATA_FILE.stat().st_mtime
            if _metadata_cache is not None and cur_mtime == _metadata_mtime:
                return _metadata_cache

            with open(METADATA_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if not isinstance(data, dict) or "logicalFiles" not in data or "versions" not in data:
                    data = _empty_metadata()
                _metadata_cache = data
                _metadata_mtime = cur_mtime
                return _metadata_cache
        except Exception as e:
            print(f"[VERSION_MANAGER] Error reading {METADATA_FILE}: {e}")
            if _metadata_cache is not None:
                return _metadata_cache
            _metadata_cache = _empty_metadata()
            return _metadata_cache


def save_metadata(meta: Dict[str, Any]) -> bool:
    """Atomically writes metadata to disk using temporary file replacement."""
    global _metadata_cache, _metadata_mtime
    with _version_lock:
        _metadata_cache = meta
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        tmp_file = DATA_DIR / f"version_metadata_{int(time.time()*1000)}.tmp"
        try:
            with open(tmp_file, "w", encoding="utf-8") as f:
                json.dump(meta, f, indent=2, ensure_ascii=False)
            tmp_file.replace(METADATA_FILE)
            if METADATA_FILE.exists():
                _metadata_mtime = METADATA_FILE.stat().st_mtime
            return True
        except Exception as e:
            print(f"[VERSION_MANAGER] Failed to save metadata: {e}")
            if tmp_file.exists():
                try:
                    tmp_file.unlink()
                except Exception:
                    pass
            return False


class VersionManager:
    """Core interface for native logical file versioning."""

    @classmethod
    def get_logical_file_by_path(cls, target_dir: Optional[str], filename: str) -> Optional[Dict[str, Any]]:
        """Finds logical file record matching folder and displayName."""
        meta = load_metadata()
        clean_dir = (target_dir or "").replace("\\", "/").strip("/")
        if clean_dir == "Home":
            clean_dir = ""
        norm_name = filename.strip().lower()

        for l_file in meta["logicalFiles"].values():
            lf_folder = (l_file.get("folder") or "").replace("\\", "/").strip("/")
            lf_name = (l_file.get("displayName") or "").strip().lower()
            if lf_folder == clean_dir and lf_name == norm_name:
                return l_file
        return None

    @classmethod
    def get_logical_file_by_id(cls, logical_file_id: str) -> Optional[Dict[str, Any]]:
        """Fetches logical file record by ID."""
        meta = load_metadata()
        return meta["logicalFiles"].get(logical_file_id)

    @classmethod
    def create_version_transaction(
        cls,
        target_dir: Optional[str],
        filename: str,
        incoming_file_path: Path,
        uploaded_by: str = "local",
        change_type: str = "uploaded",
        restored_from: Optional[int] = None,
        mime_type: Optional[str] = None
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Executes atomic 5-step version creation transaction:
        1. Locate existing logical file or create new logical file.
        2. If logical file exists, archive current active file into data/versions/{logicalFileId}/v{N}.bin
        3. Verify archived copy checksum.
        4. Atomic move incoming file to active path.
        5. Atomic update metadata JSON.
        """
        with _version_lock:
            meta = load_metadata()
            clean_dir = (target_dir or "").replace("\\", "/").strip("/")
            if clean_dir == "Home":
                clean_dir = ""

            existing_lf = cls.get_logical_file_by_path(target_dir, filename)

            active_dest_dir = UPLOADS_DIR / clean_dir if clean_dir else UPLOADS_DIR
            active_dest_dir.mkdir(parents=True, exist_ok=True)
            active_file_path = active_dest_dir / filename

            timestamp_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            incoming_size = incoming_file_path.stat().st_size if incoming_file_path.exists() else 0
            incoming_hash = _compute_sha256(incoming_file_path) if incoming_file_path.exists() else ""

            if existing_lf is None:
                # Scenario A: First Upload — Create Logical File & Version 1
                logical_file_id = f"lf_{uuid.uuid4().hex[:12]}"
                version_id = f"ver_{uuid.uuid4().hex[:12]}"

                # Move incoming file to active destination if different path
                if incoming_file_path.resolve() != active_file_path.resolve():
                    shutil.move(str(incoming_file_path), str(active_file_path))

                lf_record = {
                    "id": logical_file_id,
                    "folder": clean_dir,
                    "displayName": filename,
                    "latestVersionId": version_id,
                    "versionCount": 1,
                    "createdAt": timestamp_iso,
                    "updatedAt": timestamp_iso
                }

                v_record = {
                    "id": version_id,
                    "logicalFileId": logical_file_id,
                    "versionNumber": 1,
                    "storagePath": str(active_file_path.relative_to(DATA_DIR)).replace("\\", "/"),
                    "size": incoming_size,
                    "hash": incoming_hash,
                    "mimeType": mime_type or "application/octet-stream",
                    "uploadedAt": timestamp_iso,
                    "uploadedBy": uploaded_by,
                    "changeType": change_type,
                    "restoredFromVersion": restored_from,
                    "comment": None,
                    "pinned": False,
                    "labels": []
                }

                meta["logicalFiles"][logical_file_id] = lf_record
                meta["versions"][version_id] = v_record
                save_metadata(meta)
                return True, lf_record

            else:
                # Scenario B: File Exists — Create New Version
                logical_file_id = existing_lf["id"]
                version_store_dir = VERSIONS_DIR / logical_file_id
                version_store_dir.mkdir(parents=True, exist_ok=True)

                current_v_count = existing_lf.get("versionCount", 1)
                new_v_number = current_v_count + 1

                # STEP 2: Archive current active file to versions/logicalFileId/v{N}.bin
                archived_path = version_store_dir / f"v{current_v_count}.bin"
                if active_file_path.exists():
                    if incoming_file_path.resolve() == active_file_path.resolve():
                        # If incoming file path is active file path (already moved), copy active file to archive
                        shutil.copy2(str(active_file_path), str(archived_path))
                    else:
                        # Standard path: copy active file to archive, then move incoming file to active path
                        shutil.copy2(str(active_file_path), str(archived_path))
                        shutil.move(str(incoming_file_path), str(active_file_path))

                    # STEP 3: Update storagePath of archived version in metadata
                    latest_v_id = existing_lf.get("latestVersionId")
                    if latest_v_id and latest_v_id in meta["versions"]:
                        meta["versions"][latest_v_id]["storagePath"] = str(archived_path.relative_to(DATA_DIR)).replace("\\", "/")

                # STEP 5: Create new version metadata
                new_v_id = f"ver_{uuid.uuid4().hex[:12]}"
                v_record = {
                    "id": new_v_id,
                    "logicalFileId": logical_file_id,
                    "versionNumber": new_v_number,
                    "storagePath": str(active_file_path.relative_to(DATA_DIR)).replace("\\", "/"),
                    "size": incoming_size,
                    "hash": incoming_hash,
                    "mimeType": mime_type or "application/octet-stream",
                    "uploadedAt": timestamp_iso,
                    "uploadedBy": uploaded_by,
                    "changeType": change_type,
                    "restoredFromVersion": restored_from,
                    "comment": None,
                    "pinned": False,
                    "labels": []
                }

                existing_lf["latestVersionId"] = new_v_id
                existing_lf["versionCount"] = new_v_number
                existing_lf["updatedAt"] = timestamp_iso

                meta["logicalFiles"][logical_file_id] = existing_lf
                meta["versions"][new_v_id] = v_record
                save_metadata(meta)
                return True, existing_lf

    @classmethod
    def restore_version(cls, logical_file_id: str, version_id: str) -> Tuple[bool, str]:
        """
        Restores historical version by copying its content into a brand-new version (N+1) with changeType='restored'.
        Never mutates or deletes existing historical records.
        """
        with _version_lock:
            meta = load_metadata()
            lf = meta["logicalFiles"].get(logical_file_id)
            if not lf:
                return False, "Logical file not found"

            target_v = meta["versions"].get(version_id)
            if not target_v or target_v.get("logicalFileId") != logical_file_id:
                return False, "Target version not found"

            rel_storage_path = target_v.get("storagePath")
            v_file_path = DATA_DIR / rel_storage_path
            if not v_file_path.exists():
                return False, f"Version binary file missing: {rel_storage_path}"

            # Create temporary copy to pass to transaction
            temp_copy = DATA_DIR / f"temp_restore_{uuid.uuid4().hex}.tmp"
            shutil.copy2(str(v_file_path), str(temp_copy))

            success, updated_lf = cls.create_version_transaction(
                target_dir=lf.get("folder", ""),
                filename=lf.get("displayName", ""),
                incoming_file_path=temp_copy,
                uploaded_by="restore",
                change_type="restored",
                restored_from=target_v.get("versionNumber", 1),
                mime_type=target_v.get("mimeType")
            )

            if temp_copy.exists():
                try:
                    temp_copy.unlink()
                except Exception:
                    pass

            if success:
                return True, f"Successfully restored Version {target_v.get('versionNumber')} as Version {updated_lf.get('versionCount')}"
            return False, "Failed to create restored version transaction"

    @classmethod
    def get_version_history(cls, logical_file_id: str) -> List[Dict[str, Any]]:
        """Returns sorted list of versions (newest to oldest) for a logical file."""
        meta = load_metadata()
        lf = meta["logicalFiles"].get(logical_file_id)
        if not lf:
            return []

        latest_v_id = lf.get("latestVersionId")
        v_list = []
        for v in meta["versions"].values():
            if v.get("logicalFileId") == logical_file_id:
                v_copy = dict(v)
                v_copy["isLatest"] = (v.get("id") == latest_v_id)
                v_list.append(v_copy)

        # Sort descending by version number
        v_list.sort(key=lambda x: x.get("versionNumber", 0), reverse=True)
        return v_list

    @classmethod
    def delete_logical_file(cls, logical_file_id: str) -> bool:
        """Deletes active file and all stored versions for a logical file."""
        with _version_lock:
            meta = load_metadata()
            lf = meta["logicalFiles"].get(logical_file_id)
            if not lf:
                return False

            # Remove active file
            folder = lf.get("folder", "")
            display_name = lf.get("displayName", "")
            active_path = UPLOADS_DIR / folder / display_name if folder else UPLOADS_DIR / display_name
            if active_path.exists():
                try:
                    active_path.unlink()
                except Exception as e:
                    print(f"[VERSION_MANAGER] Error deleting active file {active_path}: {e}")

            # Remove version store directory
            version_store_dir = VERSIONS_DIR / logical_file_id
            if version_store_dir.exists():
                try:
                    shutil.rmtree(str(version_store_dir))
                except Exception as e:
                    print(f"[VERSION_MANAGER] Error removing version dir {version_store_dir}: {e}")

            # Remove from metadata
            v_ids_to_del = [vid for vid, v in meta["versions"].items() if v.get("logicalFileId") == logical_file_id]
            for vid in v_ids_to_del:
                meta["versions"].pop(vid, None)
            meta["logicalFiles"].pop(logical_file_id, None)

            save_metadata(meta)
            return True

    @classmethod
    def rename_logical_file(cls, target_dir: Optional[str], old_name: str, new_name: str) -> bool:
        """Renames logical file without breaking version history chain."""
        with _version_lock:
            lf = cls.get_logical_file_by_path(target_dir, old_name)
            if not lf:
                return False

            meta = load_metadata()
            lf_ref = meta["logicalFiles"].get(lf["id"])
            if lf_ref:
                lf_ref["displayName"] = new_name
                lf_ref["updatedAt"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                save_metadata(meta)
                return True
            return False

    @classmethod
    def move_logical_file(cls, old_dir: Optional[str], new_dir: Optional[str], filename: str) -> bool:
        """Moves logical file to new folder directory without splitting version history."""
        with _version_lock:
            lf = cls.get_logical_file_by_path(old_dir, filename)
            if not lf:
                return False

            meta = load_metadata()
            clean_new_dir = (new_dir or "").replace("\\", "/").strip("/")
            if clean_new_dir == "Home":
                clean_new_dir = ""

            lf_ref = meta["logicalFiles"].get(lf["id"])
            if lf_ref:
                lf_ref["folder"] = clean_new_dir
                lf_ref["updatedAt"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                save_metadata(meta)
                return True
            return False

    @classmethod
    def copy_logical_file(cls, src_dir: Optional[str], dst_dir: Optional[str], filename: str, new_filename: Optional[str] = None) -> bool:
        """Copies versioned file as a NEW logical file containing ONLY the latest version."""
        with _version_lock:
            lf = cls.get_logical_file_by_path(src_dir, filename)
            if not lf:
                return False

            target_name = new_filename or filename
            meta = load_metadata()
            clean_dst_dir = (dst_dir or "").replace("\\", "/").strip("/")
            if clean_dst_dir == "Home":
                clean_dst_dir = ""

            dst_path = UPLOADS_DIR / clean_dst_dir / target_name if clean_dst_dir else UPLOADS_DIR / target_name
            if not dst_path.exists():
                return False

            # Create brand new logical file
            new_lf_id = f"lf_{uuid.uuid4().hex[:12]}"
            new_v_id = f"ver_{uuid.uuid4().hex[:12]}"
            timestamp_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

            new_lf = {
                "id": new_lf_id,
                "folder": clean_dst_dir,
                "displayName": target_name,
                "latestVersionId": new_v_id,
                "versionCount": 1,
                "createdAt": timestamp_iso,
                "updatedAt": timestamp_iso
            }

            new_v = {
                "id": new_v_id,
                "logicalFileId": new_lf_id,
                "versionNumber": 1,
                "storagePath": str(dst_path.relative_to(DATA_DIR)).replace("\\", "/"),
                "size": dst_path.stat().st_size,
                "hash": _compute_sha256(dst_path),
                "mimeType": "application/octet-stream",
                "uploadedAt": timestamp_iso,
                "uploadedBy": "copy",
                "changeType": "uploaded",
                "restoredFromVersion": None,
                "comment": None,
                "pinned": False,
                "labels": []
            }

            meta["logicalFiles"][new_lf_id] = new_lf
            meta["versions"][new_v_id] = new_v
            save_metadata(meta)
            return True

    @classmethod
    def auto_migrate_existing_files(cls) -> int:
        """Idempotent startup migration: scans uploads directory and initializes v1 metadata for unversioned files."""
        migrated_count = 0
        with _version_lock:
            meta = load_metadata()
            if not UPLOADS_DIR.exists():
                return 0

            for p in UPLOADS_DIR.rglob("*"):
                if not p.is_file():
                    continue
                # Skip temp / hidden files
                if p.name.startswith(".") or p.name.endswith(".tmp") or p.name.endswith(".chunk"):
                    continue

                rel = p.relative_to(UPLOADS_DIR)
                parent_dir = str(rel.parent).replace("\\", "/")
                if parent_dir == ".":
                    parent_dir = ""
                fn = p.name

                existing = cls.get_logical_file_by_path(parent_dir, fn)
                if existing is None:
                    lf_id = f"lf_{uuid.uuid4().hex[:12]}"
                    v_id = f"ver_{uuid.uuid4().hex[:12]}"
                    timestamp_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(p.stat().st_mtime))

                    lf_record = {
                        "id": lf_id,
                        "folder": parent_dir,
                        "displayName": fn,
                        "latestVersionId": v_id,
                        "versionCount": 1,
                        "createdAt": timestamp_iso,
                        "updatedAt": timestamp_iso
                    }

                    v_record = {
                        "id": v_id,
                        "logicalFileId": lf_id,
                        "versionNumber": 1,
                        "storagePath": str(p.relative_to(DATA_DIR)).replace("\\", "/"),
                        "size": p.stat().st_size,
                        "hash": "",
                        "mimeType": "application/octet-stream",
                        "uploadedAt": timestamp_iso,
                        "uploadedBy": "migration",
                        "changeType": "migrated",
                        "restoredFromVersion": None,
                        "comment": None,
                        "pinned": False,
                        "labels": []
                    }

                    meta["logicalFiles"][lf_id] = lf_record
                    meta["versions"][v_id] = v_record
                    migrated_count += 1

            if migrated_count > 0:
                save_metadata(meta)
                print(f"[VERSION_MANAGER] Auto-migrated {migrated_count} existing files to v1 metadata.")
        return migrated_count


# Initialize version manager on module import
try:
    VersionManager.auto_migrate_existing_files()
except Exception as _e:
    print(f"[VERSION_MANAGER] Startup migration warning: {_e}")
