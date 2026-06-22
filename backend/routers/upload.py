# routers/upload.py
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from pathlib import Path
import shutil
from config import UPLOADS_DIR
from logger_utils import setup_logger
from sqlalchemy.orm import Session

from db.database import get_db
from db.models import Document

router = APIRouter(prefix="/upload", tags=["upload"])


@router.get("/files")
async def list_uploaded_files():
    """
    List all available files in the uploads directory.
    Returns the filename, path, and basename for each file.
    """
    try:
        UPLOADS_DIR.mkdir(exist_ok=True)

        files = [f for f in UPLOADS_DIR.iterdir() if f.is_file()]

        file_list = [
            {
                "filename": f.name,
                "path": str(f),
                "basename": f.stem,
                "extension": f.suffix.lstrip('.'),
                "file_size": f.stat().st_size
            }
            for f in sorted(files)
        ]

        return {
            "total_files": len(file_list),
            "files": file_list
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list files: {str(e)}")


@router.post("/")
async def upload_file(
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """
    Upload a PDF, DOCX, or HTML file and create a DB record with status='new'.
    """
    ext = file.filename.split('.')[-1].lower()
    if ext not in ("pdf", "docx", "html"):
        raise HTTPException(status_code=400, detail="Only PDF, DOCX, or HTML files supported.")

    pdf_basename = Path(file.filename).stem

    logger = setup_logger(pdf_basename, str(Path("logs") / f"{pdf_basename}.log"))

    try:
        UPLOADS_DIR.mkdir(exist_ok=True)
        dest_path = UPLOADS_DIR / file.filename

        with open(dest_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        size_bytes = dest_path.stat().st_size

        # Create a document record (status=new)
        doc = Document(
            name=file.filename,
            file_type=ext,
            status="new",
            size_bytes=size_bytes,
            path=str(dest_path),
            basename=pdf_basename
        )
        db.add(doc)
        db.commit()
        db.refresh(doc)

        logger.info(f"File uploaded and recorded: {dest_path} (doc_id={doc.id})")

        return {
            "id": doc.id,
            "filename": file.filename,
            "path": str(dest_path),
            "basename": pdf_basename,
            "file_size": size_bytes,
            "status": doc.status,
            "created_at": doc.created_at.isoformat() if doc.created_at else None
        }
    except Exception as e:
        db.rollback()
        logger.error(f"Upload failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")

