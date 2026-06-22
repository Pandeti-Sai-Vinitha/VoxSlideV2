from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from pathlib import Path
import re
import json
from datetime import datetime
from sqlalchemy.orm import Session
from typing import List, Optional

from db.database import get_db
from db.models import Document
from db.schema import VersionMetadata, AllVersionsResponse
from config import get_pdf_workspace, get_latest_project_version, get_versioned_pdf_workspace, parse_versioned_basename

router = APIRouter(prefix="/api/documents", tags=["documents"])


class VersionResponse(BaseModel):
    document_id: str
    base_name: str
    next_version: int
    next_basename: str
    message: str


class VersionInfo(BaseModel):
    version: int
    basename: str
    document_id: str
    status: str
    created_date: str


# Helper function to extract metadata from a version folder
def extract_version_metadata(version_dir: Path, version_num: int, basename: str, document: Optional[Document] = None) -> dict:
    """
    Extract metadata (template, persona, voice, slides) from a version folder.
    
    Args:
        version_dir: Path to version folder (e.g., projects/MyProject/v1)
        version_num: Version number (1, 2, etc.)
        basename: Versioned basename (e.g., "MyProject_v1")
        document: Optional Document model instance
        
    Returns:
        dict: Metadata including template, persona, voice, slides_count, status
    """
    metadata = {
        "version": version_num,
        "basename": basename,
        "slides_count": None,
        "template": None,
        "persona": None,
        "voice": None,
        "status": "new",
        "created_date": "",
    }
    
    # Try to get slides.json for slide count
    slides_json_path = version_dir / "slides.json"
    if slides_json_path.exists():
        try:
            with open(slides_json_path, 'r', encoding='utf-8') as f:
                slides_data = json.load(f)
                if isinstance(slides_data, dict) and "slides" in slides_data:
                    metadata["slides_count"] = len(slides_data["slides"])
                    # If slides.json exists, use its modification time as created_date fallback
                    try:
                        metadata["created_date"] = datetime.fromtimestamp(slides_json_path.stat().st_mtime).isoformat()
                    except Exception:
                        pass
        except Exception:
            pass
    
    # Try to get template from template_name.txt
    template_file = version_dir / "template_name.txt"
    if template_file.exists():
        try:
            metadata["template"] = template_file.read_text(encoding='utf-8').strip()
        except Exception:
            pass
    
    # Try to get persona and voice from metadata file (if it exists)
    metadata_file = version_dir / "metadata.json"
    if metadata_file.exists():
        try:
            with open(metadata_file, 'r', encoding='utf-8') as f:
                file_metadata = json.load(f)
                metadata["persona"] = file_metadata.get("persona")
                metadata["voice"] = file_metadata.get("voice")
        except Exception:
            pass
    
    # Get status from database if document exists
    if document:
        metadata["status"] = document.status
        try:
            if hasattr(document, 'created_at') and document.created_at:
                metadata["created_date"] = document.created_at.isoformat()
        except Exception:
            pass

    # If no document in DB, OR document status is "new", infer from filesystem
    # (filesystem evidence trumps DB "new" status, since old versions may have DB records with status="new")
    if not document or metadata["status"] == "new":
        # If slides were generated assume completed
        if metadata.get("slides_count") is not None and metadata.get("slides_count") > 0:
            metadata["status"] = "completed"
        else:
            # If PPT/MP4 exists assume completed
            ppt_path = version_dir / f"{basename}.pptx"
            video_path = version_dir / f"{basename}.mp4"
            if ppt_path.exists() or video_path.exists():
                metadata["status"] = "completed"
        # If created_date still empty, use folder mtime as a fallback
        if not metadata.get("created_date"):
            try:
                metadata["created_date"] = datetime.fromtimestamp(version_dir.stat().st_mtime).isoformat()
            except Exception:
                metadata["created_date"] = ""
    
    # Check if audio folder exists (indicates voice was generated)
    audio_folder = version_dir / "audio"
    if audio_folder.exists() and not metadata["voice"]:
        audio_files = list(audio_folder.glob("*.mp3")) + list(audio_folder.glob("*.wav"))
        if audio_files:
            metadata["voice"] = "Generated"  # Default if not stored
    
    return metadata


@router.get("/{doc_id}/new-version", response_model=VersionResponse)
def get_next_version(
    doc_id: str,
    db: Session = Depends(get_db)
):
    """
    Get next version basename for a document.
    
    Reads projects folder, finds max version for this document,
    and returns next version number with formatted basename.
    
    Example: If projects/MyPresentation/v1 exists, returns v2
    Returns: MyPresentation_v2
    """
    try:
        from config import parse_versioned_basename
        
        # ✅ Get document from database (ID is UUID string)
        doc = db.query(Document).filter(Document.id == doc_id).first()
        if not doc:
            raise HTTPException(
                status_code=404,
                detail=f"Document {doc_id} not found"
            )

        # ✅ Extract base name from document (could be versioned or plain)
        stored_basename = doc.basename
        base_name, current_version = parse_versioned_basename(stored_basename)
        
        # ✅ Check projects folder for existing versions
        projects_folder = Path("projects")
        base_folder = projects_folder / base_name
        
        max_version = 0
        
        # If folder exists, look for v1, v2, v3, etc.
        if base_folder.exists():
            # Find all version folders (v1, v2, etc.)
            version_pattern = re.compile(r'^v(\d+)$')
            for item in base_folder.iterdir():
                if item.is_dir():
                    match = version_pattern.match(item.name)
                    if match:
                        version_num = int(match.group(1))
                        max_version = max(max_version, version_num)
        
        # ✅ Calculate next version
        next_version = max_version + 1
        next_basename = f"{base_name}_v{next_version}"
        
        return VersionResponse(
            document_id=str(doc_id),
            base_name=base_name,
            next_version=next_version,
            next_basename=next_basename,
            message=f"Next version for {base_name} is v{next_version}"
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get version info: {str(e)}"
        )


@router.get("/{doc_id}/versions", response_model=AllVersionsResponse)
def get_all_versions(
    doc_id: str,
    db: Session = Depends(get_db)
):
    """
    Get all versions of a document with complete metadata.
    
    Returns all versions with their metadata including:
    - slides_count
    - template
    - persona
    - voice
    - status
    
    Example: If MyProject_v1 and MyProject_v2 exist in projects/MyProject/,
    returns both with their metadata.
    """
    try:
        # Get document from database
        doc = db.query(Document).filter(Document.id == doc_id).first()
        if not doc:
            raise HTTPException(
                status_code=404,
                detail=f"Document {doc_id} not found"
            )

        # Extract base name
        stored_basename = doc.basename
        base_name, _ = parse_versioned_basename(stored_basename)
        
        # Query all documents with this base name
        all_docs = db.query(Document).filter(
            Document.basename.like(f"{base_name}%")
        ).all()
        
        # Create a mapping of basename to document for quick lookup
        doc_map = {d.basename: d for d in all_docs}
        
        # Parse versions and extract metadata from filesystem
        versions_data = []
        projects_root = Path("projects") / base_name
        
        if projects_root.exists():
            # Iterate through version folders
            version_pattern = re.compile(r'^v(\d+)$')
            for version_folder in projects_root.iterdir():
                if version_folder.is_dir():
                    match = version_pattern.match(version_folder.name)
                    if match:
                        version_num = int(match.group(1))
                        versioned_basename = f"{base_name}_v{version_num}"
                        
                        # Get the document for this version (if exists)
                        version_doc = doc_map.get(versioned_basename)
                        
                        # Extract metadata from the version folder
                        metadata = extract_version_metadata(
                            version_folder, 
                            version_num, 
                            versioned_basename,
                            version_doc
                        )
                        
                        versions_data.append(VersionMetadata(
                            version=metadata["version"],
                            basename=metadata["basename"],
                            document_id=version_doc.id if version_doc else "",
                            status=metadata["status"],
                            created_date=metadata.get("created_date", "") or (version_doc.created_at.isoformat() if version_doc and version_doc.created_at else ""),
                            slides_count=metadata["slides_count"],
                            template=metadata["template"],
                            persona=metadata["persona"],
                            voice=metadata["voice"],
                        ))
        
        # Sort by version number ascending
        versions_data.sort(key=lambda x: x.version)
        
        return AllVersionsResponse(
            base_name=base_name,
            versions=versions_data,
            total_versions=len(versions_data)
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get versions: {str(e)}"
        )
