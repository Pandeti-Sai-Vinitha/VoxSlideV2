from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from pathlib import Path
import json
from logger_utils import setup_logger
from config import get_pdf_workspace

router = APIRouter(prefix="/modify", tags=["modify"])


# --- Models ---
class Slide(BaseModel):
    title: str
    bullets: list[str]
    voiceover: str


class SlidesPayload(BaseModel):
    slides: list[Slide]


class ModifyRequest(BaseModel):
    """Request to get or modify slides for a PDF."""
    basename: str  # PDF basename without extension


@router.get("/{basename}", response_model=SlidesPayload)
def get_slides(basename: str):
    """
    Get slides for a specific PDF.
    """
    paths = get_pdf_workspace(basename)
    slides_json_path = paths["slides_json"]
    logger = setup_logger(basename, str(Path("logs") / f"{basename}.log"))
    
    if not slides_json_path.exists():
        logger.error(f"Slides not found at: {slides_json_path}")
        raise HTTPException(
            status_code=404,
            detail=f"Slides not found for '{basename}'. Process the file first."
        )
    
    try:
        with open(slides_json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        logger.info(f"Retrieved {len(data.get('slides', []))} slides")
        return data
    except Exception as e:
        logger.error(f"Error reading slides: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error reading slides: {str(e)}")


@router.put("/{basename}", response_model=SlidesPayload)
def update_slides(basename: str, payload: SlidesPayload):
    """
    Update slides for a specific PDF.
    """
    paths = get_pdf_workspace(basename)
    slides_json_path = paths["slides_json"]
    logger = setup_logger(basename, str(Path("logs") / f"{basename}.log"))
    
    try:
        slides_json_path.parent.mkdir(parents=True, exist_ok=True)
        with open(slides_json_path, "w", encoding="utf-8") as f:
            json.dump(payload.dict(), f, indent=2, ensure_ascii=False)
        logger.info(f"Updated {len(payload.slides)} slides")
        return payload
    except Exception as e:
        logger.error(f"Error updating slides: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error updating slides: {str(e)}")