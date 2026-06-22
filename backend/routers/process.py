from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

import json
from sqlalchemy.orm import Session
from sqlalchemy.sql import func
from logger_utils import setup_logger
from components.ppt_video import pptx_to_images_via_powerpoint, create_video_from_images_and_audio
from components.create_ppt import create_ppt
from config import get_pdf_workspace
from db.database import get_db, SessionLocal
from db.models import Document

router = APIRouter(prefix="/process", tags=["process"])


class ProcessRequest(BaseModel):
    """Request to create media from slides."""
    basename: str  # PDF basename (must have slides.json already generated)


@router.post("/")
def process_slides(request: ProcessRequest, db: Session = Depends(get_db)):
    """
    Phase 2: Create PPT and video from slides.json and audio files.
    Requires: Phase 1 (/api/process/document) to be called first to create slides.json and voiceovers

    This endpoint:
    1. Creates PowerPoint from slides
    2. Exports slides as images
    3. Creates video synced with audio
    4. Updates document status to 'completed'
    """
    pdf_basename = request.basename
    paths = get_pdf_workspace(pdf_basename)
    logger = setup_logger(pdf_basename, str(paths["log_file"]))

    # ✅ Get document from DB and update status
    doc = db.query(Document).filter_by(basename=pdf_basename).first()
    if not doc:
        logger.error(f"Document not found: {pdf_basename}")
        raise HTTPException(404, f"Document not found: {pdf_basename}")

    try:
        logger.info("=" * 60)
        logger.info(f"PHASE 2: STARTING MEDIA GENERATION FOR: {pdf_basename}")
        logger.info("=" * 60)

        # ✅ Update document status
        doc.status = "processing"
        doc.stage = "generating_media"
        db.commit()

        if not paths["slides_json"].exists():
            raise FileNotFoundError(f"slides.json not found: {paths['slides_json']}")

        logger.info(f"Loading slides from {paths['slides_json']}")
        with open(paths['slides_json'], 'r', encoding='utf-8') as f:
            slides_data = json.load(f)

        slides = slides_data.get('slides', [])
        logger.info(f"  ✓ Loaded {len(slides)} slides")

        # ✅ PHASE 3: Create PPT from slides
        logger.info("=" * 60)
        logger.info("PHASE 3: CREATING POWERPOINT PRESENTATION")
        logger.info("=" * 60)
        logger.info(f"Creating PowerPoint presentation: {paths['ppt_file']}")

        doc.stage = "creating_ppt"
        db.commit()

        # If a template name was saved during upload, use it
        template_name = None
        tpl_file = paths["pdf_folder"] / "template_name.txt"
        if tpl_file.exists():
            try:
                template_name = tpl_file.read_text(encoding="utf-8").strip()
            except Exception:
                template_name = None

        # ✅ Get extracted images folder if it exists (versioned and fallback to base name)
        import os
        from config import parse_versioned_basename

        base_name, version_dir = parse_versioned_basename(pdf_basename)
        candidates = []
        if version_dir:
            candidates.append(os.path.join("extracted_images_docx", base_name, version_dir))
        candidates.extend([
            os.path.join("extracted_images_docx", pdf_basename),
            os.path.join("extracted_images_docx", base_name)
        ])

        images_folder = next((candidate for candidate in candidates if os.path.exists(candidate)), None)

        final_ppt_slide_count = create_ppt(
            slides,
            str(paths["audio_folder"]),
            str(paths["ppt_file"]),
            template_name=template_name,
            images_folder=images_folder
        )
        logger.info(f"  ✓ PowerPoint presentation created successfully ({final_ppt_slide_count} slides)")

        # ✅ STEP 1: Export slides as images
        logger.info("-" * 60)
        logger.info("STEP 1: EXPORTING SLIDES AS IMAGES")
        logger.info("-" * 60)
        logger.info(f"Converting PowerPoint slides to images: {paths['slides_images_folder']}")

        doc.stage = "exporting_images"
        db.commit()

        slide_images = pptx_to_images_via_powerpoint(
            str(paths["ppt_file"]),
            str(paths["slides_images_folder"])
        )
        logger.info(f"  ✓ Exported {len(slide_images)} slide images")
        for i, img_path in enumerate(slide_images, 1):
            logger.info(f"    Image {i}: {img_path}")

        # ✅ STEP 2: Create video
        logger.info("-" * 60)
        logger.info("STEP 2: CREATING VIDEO")
        logger.info("-" * 60)
        logger.info(f"Creating video with synced audio: {paths['video_file']}")

        doc.stage = "creating_video"
        db.commit()

        video_duration = create_video_from_images_and_audio(
            slide_images,
            str(paths["audio_folder"]),
            str(paths["video_file"])
        )
        logger.info(f"  ✓ Video created successfully")

        # ✅ Mark as completed
        doc.status = "completed"
        doc.stage = "completed"
        doc.generated_at = func.now()
        if video_duration is not None:
            doc.duration = video_duration
            logger.info(f"  ✓ Video duration: {video_duration:.2f} seconds")
        db.commit()

        logger.info("=" * 60)
        logger.info(f"PHASE 2: MEDIA GENERATION COMPLETED SUCCESSFULLY")
        logger.info(f"Total slides: {len(slides)}")
        logger.info(f"Output files:")
        logger.info(f"  - PowerPoint: {paths['ppt_file']}")
        logger.info(f"  - Video: {paths['video_file']}")
        logger.info(f"  - Images folder: {paths['slides_images_folder']} ({len(slide_images)} files)")
        logger.info("=" * 60)

        return {
            "status": "success",
            "basename": pdf_basename,
            "ppt_file": str(paths["ppt_file"]),
            "video_file": str(paths["video_file"]),
            "slides_images_folder": str(paths["slides_images_folder"]),
            "num_slides": final_ppt_slide_count,
            "message": "PPT and video generated successfully"
        }

    except Exception as e:
        logger.error(f"ERROR during media generation: {str(e)}", exc_info=True)
        doc.status = "failed"
        doc.error_message = str(e)
        db.commit()
        raise HTTPException(
            status_code=500,
            detail=f"Processing failed: {str(e)}. See logs: {paths.get('log_file')}"
        )