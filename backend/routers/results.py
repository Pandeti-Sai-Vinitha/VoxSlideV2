from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pathlib import Path
import logging

from config import get_pdf_workspace, get_latest_project_version

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/results", tags=["results"])

@router.get("/pptx/{basename}")
def download_pptx(basename: str):
    """
    Serve PowerPoint file for download.
    Expected location: outputs/{basename}/{basename}.pptx or projects/{basename}/vN/{basename}.pptx
    """
    # Sanitize basename to prevent path traversal
    basename = basename.replace("../", "").replace("..\\", "")

    latest = get_latest_project_version(basename)
    if latest:
        basename = latest
    
    paths = get_pdf_workspace(basename)
    pptx_path = paths["ppt_file"]
    
    logger.info(f"Requested PPTX: {pptx_path}")
    logger.info(f"Path exists: {pptx_path.exists()}")
    
    if not pptx_path.exists():
        logger.error(f"PPTX not found: {pptx_path}")
        raise HTTPException(404, f"PPTX file not found: {pptx_path}")
    
    return FileResponse(
        pptx_path,
        media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        filename=f"{basename}.pptx"
    )

@router.get("/video/{basename}")
def download_video(basename: str):
    """
    Serve video file for preview/download.
    Expected location: outputs/{basename}/{basename}.mp4 or projects/{basename}/vN/{basename}.mp4
    
    ✅ Validates:
    - Basename sanitization (no path traversal)
    - Exact file exists at expected location
    - Returns correct video for the document
    """
    # Sanitize basename to prevent path traversal attacks
    basename = basename.replace("../", "").replace("..\\", "")

    latest = get_latest_project_version(basename)
    if latest:
        basename = latest
    
    paths = get_pdf_workspace(basename)
    output_dir = paths["pdf_folder"]
    video_path = paths["video_file"]
    
    logger.info(f"Video request - basename: {basename}")
    logger.info(f"Expected video path: {video_path}")
    logger.info(f"Output directory exists: {output_dir.exists()}")
    logger.info(f"Video file exists: {video_path.exists()}")
    
    # Validate directory exists
    if not output_dir.exists():
        logger.error(f"Output directory not found: {output_dir}")
        raise HTTPException(404, f"Document folder not found: {basename}")
    
    # Validate specific video file exists
    if not video_path.exists():
        logger.error(f"Video file not found at: {video_path}")
        # List what's actually in the directory for debugging
        try:
            contents = list(output_dir.glob("*.mp4"))
            logger.warning(f"Available MP4 files in {output_dir}: {contents}")
            if contents:
                logger.warning(f"Found {len(contents)} MP4 file(s), but none matching {basename}.mp4")
        except Exception as e:
            logger.warning(f"Could not list directory contents: {e}")
        
        raise HTTPException(404, f"Video file not found: {basename}.mp4")
    
    logger.info(f"✅ Serving video: {video_path}")
    return FileResponse(
        video_path,
        media_type="video/mp4",
        filename=f"{basename}.mp4"
    )