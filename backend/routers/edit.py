# ============================
# SLIDES EDIT ROUTER (CORRECTED)
# ============================

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from pathlib import Path
import json

from config import get_pdf_workspace

router = APIRouter(prefix="/api/slides", tags=["slides"])


@router.get("/{basename}")
def get_slides(basename: str):
    """
    Retrieve all slides for a document.
    """
    slides_path = get_pdf_workspace(basename)["slides_json"]

    if not slides_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"slides.json not found for document: {basename}"
        )

    try:
        with open(slides_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        slides = data.get("slides", [])
        
        # Transform slides to match frontend interface
        transformed_slides = []
        for idx, slide in enumerate(slides):
            transformed_slides.append({
                "id": str(idx + 1),
                "title": slide.get("title", ""),
                "content": slide.get("content", ""),
                "audioScript": slide.get("voiceover", ""),
                "audioUrl": slide.get("audio_url", ""),
                "status": slide.get("status", "pending"),
                "imagePrompt": slide.get("image_prompt", ""),
                "imageIndex": slide.get("image_index", None),
            })
        
        return {"slides": transformed_slides}

    except json.JSONDecodeError:
        raise HTTPException(
            status_code=500,
            detail="slides.json is corrupted or invalid"
        )


class EditSlideRequest(BaseModel):
    document_basename: str
    slide_number: int
    title: str
    content: str | list[str]
    audio_script: str
    image_index: int | None = Field(default=None)
    image_prompt: str | None = Field(default=None)


@router.post("/edit")
def edit_slide(req: EditSlideRequest):
    """
    Edit slide title, content, and voiceover.
    Preserves all other fields (content_type, image_prompt, etc).
    """

    slides_path = get_pdf_workspace(req.document_basename)["slides_json"]

    if not slides_path.exists():
        raise HTTPException(
            status_code=404,
            detail="slides.json not found for document"
        )

    try:
        with open(slides_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        slides = data.get("slides", [])
        idx = req.slide_number - 1

        if idx < 0 or idx >= len(slides):
            raise HTTPException(
                status_code=400,
                detail="Invalid slide number"
            )

        slide = slides[idx]

        # ✅ Update only editable fields
        slide["title"] = req.title
        slide["content"] = req.content

        # ✅ Map audio_script → voiceover (IMPORTANT)
        slide["voiceover"] = req.audio_script

        # ✅ Update image metadata when the client provides it
        slide["image_index"] = req.image_index
        if req.image_prompt is not None:
            slide["image_prompt"] = req.image_prompt

        # ✅ Set status safely
        slide["status"] = "editing"

        slides[idx] = slide

        with open(slides_path, "w", encoding="utf-8") as f:
            json.dump(
                {"slides": slides},
                f,
                indent=2,
                ensure_ascii=False
            )

        return {
            "status": "success",
            "slide_number": req.slide_number,
            "message": f"Slide {req.slide_number} updated successfully"
        }

    except json.JSONDecodeError:
        raise HTTPException(
            status_code=500,
            detail="slides.json is corrupted or invalid"
        )

