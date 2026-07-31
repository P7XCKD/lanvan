import logging
import urllib.parse
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Optional, NamedTuple
from fastapi import HTTPException
from app.core.validation import secure_filename

logger = logging.getLogger(__name__)


class ResolvedUploadPath(NamedTuple):
    target_directory: Path
    filename: str
    full_path: Path
    relative_path: Path


class UploadPathResolver:
    """
    Decoupled, stateless service for resolving upload file destinations safely.
    Strictly enforces security bounds, explicit traversal rejection, and nested folder preservation.
    """

    @staticmethod
    def resolve(
        parent_path: Optional[str],
        raw_filename: str,
        base_dir: Path
    ) -> ResolvedUploadPath:
        if not raw_filename:
            raise HTTPException(status_code=400, detail="Filename cannot be empty")

        # 1. URL Decoding & Slash Normalization
        clean_parent = urllib.parse.unquote(parent_path or "").replace('\\', '/')
        clean_filename = urllib.parse.unquote(raw_filename).replace('\\', '/')

        # 2. Reject Absolute Paths
        if PurePosixPath(clean_filename).is_absolute() or PureWindowsPath(clean_filename).is_absolute():
            raise HTTPException(status_code=400, detail="Absolute paths are prohibited")

        # 3. Explicit Path Traversal Rejection on Raw Segments BEFORE PurePosixPath normalization
        raw_filename_segments = [s for s in clean_filename.split('/') if s]
        raw_parent_segments = [s for s in clean_parent.split('/') if s]

        if any(segment in ('.', '..') for segment in raw_filename_segments) or \
           any(segment in ('.', '..') for segment in raw_parent_segments):
            raise HTTPException(status_code=400, detail="Path traversal components ('.' or '..') are prohibited")

        # 4. Extract Path Parts via PurePosixPath
        filename_parts = list(PurePosixPath(clean_filename).parts)
        parent_parts = list(PurePosixPath(clean_parent).parts) if clean_parent else []

        if not filename_parts:
            raise HTTPException(status_code=400, detail="Invalid filename path")

        # 5. Clean & Exact Prefix Stripping
        # Strips redundant root prefix ONLY if filename_parts has MORE components than parent_parts
        if parent_parts and len(filename_parts) > len(parent_parts):
            if filename_parts[:len(parent_parts)] == parent_parts:
                filename_parts = filename_parts[len(parent_parts):]

        # 5b. Recursive Upload Root Stripping
        # When the frontend's recursive resolver has already renamed the root folder
        # (e.g. "Folder" → "Folder (1)"), parent_parts contains the renamed root but
        # filename_parts still carries the original root name from webkitRelativePath.
        # Strip only the duplicated root component while preserving all nested subfolders.
        # Condition: filename starts with the same first component as parent_parts,
        # but the full prefix doesn't match (otherwise step 5 would have handled it),
        # and filename has at least 2 components (root + something else).
        if (parent_parts and len(filename_parts) >= 2
            and filename_parts[0] == parent_parts[0]
            and filename_parts[:len(parent_parts)] != parent_parts):
            # The first component is the old root name that parent_parts already replaces.
            # Strip it to avoid creating an extra nested folder.
            filename_parts = filename_parts[1:]

        # 6. Single-Pass Component Sanitization
        safe_parent_parts = []
        for part in parent_parts:
            cleaned = secure_filename(part)
            if cleaned:
                safe_parent_parts.append(cleaned)

        safe_filename_parts = []
        for part in filename_parts:
            cleaned = secure_filename(part)
            if cleaned:
                safe_filename_parts.append(cleaned)

        if not safe_filename_parts:
            safe_filename_parts = ["unnamed_file"]

        # 7. Reconstruct Target Directory and Paths
        target_dir = base_dir
        for part in safe_parent_parts:
            target_dir = target_dir / part

        for part in safe_filename_parts[:-1]:
            target_dir = target_dir / part

        final_file = safe_filename_parts[-1]
        final_path = target_dir / final_file

        # 8. Path Traversal Safety Guard (non-strict resolution)
        try:
            resolved_target = final_path.resolve(strict=False)
            resolved_base = base_dir.resolve(strict=False)
            rel_path = resolved_target.relative_to(resolved_base)
        except ValueError:
            raise HTTPException(status_code=403, detail="Path traversal attempt detected")

        logger.debug("Upload path resolved: parent=%r filename=%r -> %s", parent_path, raw_filename, final_path)
        
        return ResolvedUploadPath(
            target_directory=target_dir,
            filename=final_file,
            full_path=final_path,
            relative_path=rel_path
        )
