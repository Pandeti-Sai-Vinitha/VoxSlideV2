from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from config import get_pdf_workspace, get_latest_project_version
from pathlib import Path

router = APIRouter()

@router.get("/api/download/pptx/{folder}/{filename}")
def download_pptx(folder: str, filename: str):
    # Sanitize user-supplied values to avoid path traversal issues.
    folder = folder.replace("../", "").replace("..\\", "")
    filename = filename.replace("../", "").replace("..\\", "")

    # If a base project name has a later version, serve the latest versioned file.
    latest = get_latest_project_version(folder)
    if latest:
        folder = latest

    # Resolve workspace paths for the requested basename.
    try:
        paths = get_pdf_workspace(folder)
        file_path = paths["ppt_file"]
    except Exception:
        file_path = Path("outputs") / folder / f"{filename}.pptx"

    print("📥 Folder:", folder)
    print("📄 Filename:", filename)
    print("📂 Resolved path:", file_path)

    if not file_path.exists():
        print("❌ File NOT found")
        raise HTTPException(status_code=404, detail=f"File not found: {file_path}")

    print("✅ File found, downloading...")

    return FileResponse(
        path=file_path,
        filename=f"{filename}.pptx",
        media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation"
    )
