# routers/documents.py

from typing import List, Optional
from pathlib import Path
import json
import re
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from moviepy.editor import VideoFileClip



from fastapi import Body
from db.database import get_db
from db.models import Document
from db.schema import DocumentsListResponse, DocumentOut, StatsResponse
from config import get_latest_project_version, parse_versioned_basename, get_pdf_workspace

router = APIRouter(prefix="/api/documents", tags=["documents"])


def determine_output_type(basename: str) -> str:
    latest = get_latest_project_version(basename) or basename
    paths = get_pdf_workspace(latest)
    if paths["video_file"].exists():
        return "pptx+video"
    if paths["ppt_file"].exists():
        return "pptx"
    return "pptx"


def get_video_duration_from_basename(basename: Optional[str]) -> Optional[float]:
    if not basename:
        return None

    latest = get_latest_project_version(basename) or basename
    paths = get_pdf_workspace(latest)

    video_path = paths.get("video_file")
    if not video_path or not video_path.exists():
        return None

    try:
        clip = VideoFileClip(str(video_path))
        duration = float(clip.duration)
        clip.close()
        return duration
    except Exception:
        return None


# Helper function to extract metadata from a version folder
def extract_version_metadata_for_document(basename: str) -> dict:
    """
    Extract metadata (template, persona, voice, slides) from a version's folder.
    
    Args:
        basename: Versioned basename (e.g., "MyProject_v1")
        
    Returns:
        dict: Metadata including template, persona, voice, slides_count
    """
    metadata = {
        "slides_count": None,
        "template": None,
        "persona": None,
        "voice": None,
    }
    
    base_name, version_str = parse_versioned_basename(basename)
    if not version_str:
        return metadata
    
    # Construct version folder path
    version_folder = Path("projects") / base_name / version_str
    if not version_folder.exists():
        return metadata
    
    # Try to get slides.json for slide count
    slides_json_path = version_folder / "slides.json"
    if slides_json_path.exists():
        try:
            with open(slides_json_path, 'r', encoding='utf-8') as f:
                slides_data = json.load(f)
                if isinstance(slides_data, dict) and "slides" in slides_data:
                    metadata["slides_count"] = len(slides_data["slides"])
        except Exception:
            pass
    
    # Try to get template from template_name.txt
    template_file = version_folder / "template_name.txt"
    if template_file.exists():
        try:
            metadata["template"] = template_file.read_text(encoding='utf-8').strip()
        except Exception:
            pass
    
    # Try to get persona and voice from metadata file (if it exists)
    metadata_file = version_folder / "metadata.json"
    if metadata_file.exists():
        try:
            with open(metadata_file, 'r', encoding='utf-8') as f:
                file_metadata = json.load(f)
                metadata["persona"] = file_metadata.get("persona")
                metadata["voice"] = file_metadata.get("voice")
        except Exception:
            pass
    
    # Check if audio folder exists (indicates voice was generated)
    audio_folder = version_folder / "audio"
    if audio_folder.exists() and not metadata["voice"]:
        audio_files = list(audio_folder.glob("*.mp3")) + list(audio_folder.glob("*.wav"))
        if audio_files:
            metadata["voice"] = "Generated"  # Default if not stored
    
    return metadata

# PATCH endpoint to update status (must be after router definition)
@router.patch("/{document_id}/status")
def update_document_status(document_id: str, status: str = Body(...), db: Session = Depends(get_db)):
    """
    Update the status of a document.
    """
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    doc.status = status
    db.commit()
    db.refresh(doc)
    return {"id": doc.id, "status": doc.status}


def bytes_to_human(b: int | None) -> str:
    if not b or b <= 0:
        return "—"
    units = ["B", "KB", "MB", "GB", "TB"]
    i = 0
    v = float(b)
    while v >= 1024 and i < len(units) - 1:
        v /= 1024
        i += 1
    return f"{v:.1f} {units[i]}" if i > 0 else f"{int(v)} {units[i]}"
def actions_for_status(status: str) -> list[str]:
    # Adjust as your UX evolves
    if status == "completed":
        return ["view", "download"]
    if status in ("processing", "new"):
        return ["view"]
    if status == "failed":
        return ["view"]
    return ["view"]


@router.get("/stats", response_model=StatsResponse)
def get_stats(db: Session = Depends(get_db)):
    total = db.query(Document).count()
    processing = db.query(Document).filter(Document.status == "processing").count()
    completed = db.query(Document).filter(Document.status == "completed").count()
    return {
        "total": total,
        "processing": processing,
        "completed": completed
    }


@router.get("", response_model=DocumentsListResponse)
def list_documents(
    page: int = 1,
    limit: int = 5,
    sortField: str = "created_at",  # or "updated_at"
    sortDir: str = "desc",
    db: Session = Depends(get_db)
):
    limit = min(max(limit, 1), 100)
    page = max(page, 1)
    offset = (page - 1) * limit

    sort_col = Document.updated_at if sortField == "updated_at" else Document.created_at
    sort_expr = sort_col.asc() if sortDir.lower() == "asc" else sort_col.desc()

    total = db.query(Document).count()
    rows: List[Document] = (
        db.query(Document)
        .order_by(sort_expr)
        .limit(limit)
        .offset(offset)
        .all()
    )

    items: List[DocumentOut] = []
    for r in rows:
        latest_basename = get_latest_project_version(r.basename) or r.basename
        
        # Extract metadata from the version folder
        metadata = extract_version_metadata_for_document(r.basename)
        
        items.append(DocumentOut(
            id=r.id,
            name=r.name,
            fileType=r.file_type,
            status=r.status,
            size=bytes_to_human(r.size_bytes),
            createdDate=r.created_at.isoformat() if r.created_at else None,
            updatedDate=r.updated_at.isoformat() if r.updated_at else None,
            slides_count=metadata.get("slides_count") or r.slides_count,
            generated_at=r.generated_at.isoformat() if r.generated_at else None,
            basename=r.basename,
            latest_basename=latest_basename,
            output_type=r.output_type or determine_output_type(r.basename),
            duration=r.duration if r.duration is not None else get_video_duration_from_basename(r.basename if r.basename else None),
            allowedActions=actions_for_status(r.status),
            template=metadata.get("template"),
            persona=metadata.get("persona"),
            voice=metadata.get("voice"),
        ))

    return {
        "items": items,
        "page": page,
        "pageSize": limit,
        "total": total
    }




@router.get("/{document_id}")
def get_document_by_id(
    document_id: str,
    db: Session = Depends(get_db)
):
    """
    Fetch a single document by ID.
    Used by ResultsPage & EditPage.
    """

    doc = db.query(Document).filter(Document.id == document_id).first()

    if not doc:
        raise HTTPException(
            status_code=404,
            detail="Document not found"
        )

    latest_basename = get_latest_project_version(doc.basename) or doc.basename
    duration = doc.duration if doc.duration is not None else get_video_duration_from_basename(doc.basename if doc.basename else None)

    return {
        "id": doc.id,
        "name": doc.name,
        "fileType": doc.file_type,
        "status": doc.status,
        "size": bytes_to_human(doc.size_bytes),
        "createdDate": doc.created_at.isoformat() if doc.created_at else None,
        "updatedDate": doc.updated_at.isoformat() if doc.updated_at else None,
        "allowedActions": actions_for_status(doc.status),
        "slides_count": doc.slides_count,
        "generated_at": doc.generated_at.isoformat() if doc.generated_at else None,
        "basename": doc.basename,
        "latest_basename": latest_basename,
        "output_type": doc.output_type or determine_output_type(doc.basename),
        "duration": duration,
        "outputs": {
            "pptxUrl": f"/api/results/pptx/{latest_basename}",
            "mp4Url": f"/api/results/video/{latest_basename}",
        },
    }
