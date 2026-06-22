from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel
from pathlib import Path
import json
import os
import shutil
import time
from tempfile import TemporaryDirectory
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from db.database import get_db
from db.models import Document
from components.pipeline import generate_slides_from_pdf, create_media_from_slides
from components.persona_config import get_persona_slide_settings, validate_slide_count, DEFAULT_PERSONA, \
    is_valid_persona
from components.voice_config import is_valid_voice
from components.ppt_video import pptx_to_images_via_powerpoint
from logger_utils import setup_logger
from config import get_pdf_workspace, get_next_versioned_basename

router = APIRouter(prefix="/api/process", tags=["process"])
UPLOADS_DIR = Path("uploads")


def _is_valid_template_file(path: Path) -> bool:
    return path.exists() and path.suffix.lower() in (".pptx", ".potx")


def _is_temporary_template_file(path: Path) -> bool:
    name = path.name
    return "~$" in name or ".~$" in name or name.startswith(".")


def _sanitize_template_name(name: str) -> str:
    if not name:
        return name
    cleaned = name.strip().strip('"\'"')
    return cleaned


def _resolve_template_path(templates_dir: Path, template_name: str) -> Path:
    template_name = _sanitize_template_name(template_name)
    candidate = templates_dir / template_name
    if candidate.exists():
        return candidate
    for ext in (".pptx", ".potx"):
        candidate = templates_dir / f"{template_name}{ext}"
        if candidate.exists():
            return candidate
    return templates_dir / template_name


# ============================
# Request Models
# ============================

class GenerateRequest(BaseModel):
    document_id: str
    voice: Optional[str] = None
    persona: Optional[str] = None
    domain: Optional[str] = None
    template: Optional[str] = None
    slides: Optional[int] = None
    prompt_instructions: Optional[str] = None
    basename: Optional[str] = None  # ✅ Optional versioned basename (e.g., "MyPresentation_v2")
    mode: Optional[str] = "video"


class ProcessRequest(BaseModel):
    basename: str  # PDF basename (must have slides.json already generated)


class CombinedWorkflowResponse(BaseModel):
    document_id: str
    filename: str
    basename: Optional[str] = None
    status: str
    stage: str
    message: Optional[str] = None
    slides: Optional[list] = None
    slides_json_path: Optional[str] = None
    error: Optional[str] = None
    output_type: Optional[str] = None  # ✅ Include output_type in response


class MediaGenerationResponse(BaseModel):
    status: str
    stage: str
    message: Optional[str] = None
    pptx_path: Optional[str] = None
    mp4_path: Optional[str] = None
    num_slides: Optional[int] = None


# ============================
# Helper Functions
# ============================

def run_combined_pipeline(doc_id: int, pdf_basename: str, file_path: str, voice_name: str = None, persona: str = None,
                          template_name: str = None, num_slides: int = None, domain: str = None,
                          prompt_instructions: str = None, mode: str = "video", version_dir: str = None):
    """
    Run the background slide generation pipeline for a document.
    This stage generates slides, PPT, slide images, and when mode is video it also generates voiceover audio and quiz content.
    """
    
    from db.database import SessionLocal
    db = SessionLocal()


    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)

    logger = setup_logger(pdf_basename, str(log_dir / f"{pdf_basename}.log"))

    try:
        logger.info("🚀 Background pipeline started")
        logger.info(f"📢 Using voice: {voice_name}")
        logger.info(f"🎯 Using persona: {persona}")
        logger.info(f"📊 Generating {num_slides} slides")
        logger.info(f"📌 Domain: {domain}")
        logger.info(f"🎨 Using template: {template_name}")
        if prompt_instructions:
            logger.info(f"🧭 Additional prompt instructions: {prompt_instructions}")

        # ✅ Handle versioning: determine output folder
        paths = get_pdf_workspace(pdf_basename)
        output_base = paths["pdf_folder"]
        output_base.mkdir(parents=True, exist_ok=True)
        logger.info(f"📌 Output folder: {output_base}")

        doc = db.get(Document, doc_id)

        if not doc:
            logger.error(f"Document {doc_id} not found")
            return

        # ✅ STEP 1: Generate slides
        logger.info("Generating slides...")
        doc.stage = "generating_slides"
        db.commit()
        db.refresh(doc)  # ✅ Refresh after commit to avoid expired state

        gen_result = generate_slides_from_pdf(
            file_path,
            pdf_basename=pdf_basename,
            persona=persona,
            num_slides=num_slides,
            domain=domain,
            prompt_instructions=prompt_instructions,
            voice_name=voice_name,
            template_name=template_name
        )

        if gen_result.get("status") == "error":
            error_msg = gen_result.get("error", "Unknown error")
            doc.status = "failed"
            doc.error_message = error_msg
            db.commit()
            db.refresh(doc)  # ✅ Refresh after commit
            logger.error(error_msg)
            return

        doc.stage = "slides_generated"
        db.commit()
        db.refresh(doc)  # ✅ Refresh after commit

        logger.info("✅ Slides generated successfully")

        # ✅ STEP 2: GENERATE VOICEOVERS IF VIDEO MODE IS SELECTED
        logger.info("=" * 60)
        mode_value = str(mode).lower() if mode is not None else ''
        voice_name = voice_name.strip() if isinstance(voice_name, str) else voice_name
        logger.info(f"Mode: {mode!r} -> {mode_value}; Voice: {voice_name!r}")

        if mode_value == "video":
            active_voice = voice_name or None
            logger.info("STEP 2: GENERATING VOICEOVERS AND QUIZ FOR VIDEO MODE")
            logger.info(f"Voice: {active_voice or 'default'}")
            logger.info("=" * 60)
            
            try:
                from components.ppt_voice import create_voiceover
                from Agent.quiz_agent import generate_quiz
                
                # Load slides.json
                slides_json = paths["slides_json"]
                with open(slides_json, "r", encoding="utf-8") as f:
                    slides_data = json.load(f)
                
                slides = slides_data.get("slides", [])
                paths["audio_folder"].mkdir(parents=True, exist_ok=True)
                
                logger.info(f"Generating voiceovers for {len(slides)} slides...")
                for idx, slide in enumerate(slides, 1):
                    audio_path = paths["audio_folder"] / f"slide_{idx}.mp3"
                    voiceover_text = slide.get('voiceover') or slide.get('audio_script') or slide.get('audioScript') or ''
                    
                    if voiceover_text:
                        logger.info(f"  Slide {idx}: Generating audio with voice {active_voice or 'default'}...")
                        try:
                            create_voiceover(voiceover_text, str(audio_path), voice_name=active_voice)
                            logger.info(f"    ✓ Audio created: {slide.get('title', 'Slide ' + str(idx))}")
                        except Exception as e:
                            logger.error(f"    ❌ Failed to generate audio for slide {idx}: {str(e)}")
                            raise
                    else:
                        logger.warning(f"  Slide {idx}: No voiceover text found, skipping")
                
                logger.info("Generating quiz for slides...")
                quiz_file = paths["pdf_folder"] / "quiz.json"
                quiz = generate_quiz(slides, quiz_type='test', num_questions=5)
                with open(quiz_file, 'w', encoding='utf-8') as f:
                    json.dump(quiz, f, ensure_ascii=False, indent=2)
                logger.info(f"    ✓ Quiz created: {quiz_file}")
                logger.info(f"✅ Voiceovers and quiz generated successfully")
            except Exception as voice_error:
                logger.error(f"❌ Voiceover generation failed: {str(voice_error)}")
                raise
        else:
            logger.info("STEP 2: SKIPPING VOICEOVER GENERATION")
            if mode_value != "video":
                logger.info("Reason: PPTX-only mode selected (no video/audio needed)")
            else:
                logger.info("Reason: No voice supplied")
        
        logger.info("=" * 60)

        # ✅ STEP 3: CREATE PPT IMMEDIATELY
        logger.info("=" * 60)
        logger.info("STEP 3: CREATING PPT FROM SLIDES")
        logger.info("=" * 60)

        try:
            from components.create_ppt import create_ppt

            # Load slides.json
            slides_json = paths["slides_json"]
            with open(slides_json, "r", encoding="utf-8") as f:
                slides_data = json.load(f)

            slides = slides_data.get("slides", [])

            # ✅ Detect extracted images folder (already used in your Phase 2)
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

            logger.info(f"Using images folder: {images_folder}")

            # ✅ Create PPT
            create_ppt(
                slides,
                str(paths["audio_folder"]),  # audio already generated ✅
                str(paths["ppt_file"]),  # OUTPUT → outputs/{basename}/{basename}.pptx ✅
                template_name=template_name,
                images_folder=images_folder
            )

            logger.info(f"✅ PPT created successfully: {paths['ppt_file']}")

            # ✅ AFTER PPT CREATION → GENERATE SLIDE IMAGES
            from components.ppt_video import pptx_to_images_via_powerpoint

            logger.info("📸 Generating slide images from PPT...")

            slide_images = pptx_to_images_via_powerpoint(
                str(paths["ppt_file"]),
                str(paths["slides_images_folder"])
            )

            logger.info(f"✅ Generated {len(slide_images)} slide images")


        except Exception as ppt_error:
            logger.error(f"❌ PPT generation failed: {str(ppt_error)}")

        logger.info("=" * 60)
        logger.info("✅ Pipeline completed successfully (slides + PPT ready)")
        logger.info("=" * 60)

        # ✅ Mark as ready for processing (not completed yet)
        doc.status = "ready_for_processing"
        doc.stage = "waiting_for_processing"
        doc.output_type = "pptx+video" if mode == "video" else "pptx"
        db.commit()
        db.refresh(doc)

        logger.info(f"✅ Pipeline completed successfully - awaiting user to process")
        logger.info(f"📺 Output type set to: {doc.output_type}")

    except Exception as e:
        logger.error(f"❌ Pipeline crashed: {str(e)}", exc_info=True)
        if doc:
            doc.status = "failed"
            doc.error_message = str(e)
            db.commit()


    finally:
        db.close()


@router.post("/document", response_model=CombinedWorkflowResponse)
async def upload_generate_process(
        file: UploadFile = File(...),
        voice: str = Form(None),
        persona: str = Form(None),
        template: str = Form(None),
        slides: str = Form(None),
        mode: str = Form("pptx"),
        db: Session = Depends(get_db),
        background_tasks: BackgroundTasks = None
):
    ext = file.filename.split('.')[-1].lower()

    if ext not in ("pdf", "docx", "html"):
        raise HTTPException(
            status_code=400,
            detail="Only PDF, DOCX, or HTML files supported."
        )

    # Validate voice if provided
    if voice and not is_valid_voice(voice):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid voice: {voice}. Use /api/voices endpoint to get available options."
        )

    # Validate persona if provided
    if persona and not is_valid_persona(persona):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid persona: {persona}. Use /api/personas endpoint to get available options."
        )

    # Parse and validate slides count
    num_slides = None
    if slides:
        try:
            num_slides = int(slides)
            if persona:
                num_slides = validate_slide_count(persona, num_slides)
            else:
                # If no persona, use default persona's constraints
                num_slides = validate_slide_count(DEFAULT_PERSONA, num_slides)
        except (ValueError, TypeError):
            raise HTTPException(
                status_code=400,
                detail="Invalid slides value. Must be an integer."
            )

    pdf_basename = Path(file.filename).stem
    versioned_basename = get_next_versioned_basename(pdf_basename)

    # Validate template if provided
    if template:
        template = _sanitize_template_name(template)
        templates_dir = Path(__file__).parent.parent / "sample_ppt"
        template_path = _resolve_template_path(templates_dir, template)
        if not _is_valid_template_file(template_path):
            raise HTTPException(
                status_code=400,
                detail=f"Invalid template: {template}. Use /api/process/templates endpoint to get available options."
            )

    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)

    try:
        # ✅ AGGRESSIVE CLEANUP FOR RE-UPLOADS (BEFORE logger is created)
        # This ensures old files don't interfere with new upload
        old_log_path = log_dir / f"{pdf_basename}.log"
        old_outputs_path = get_pdf_workspace(pdf_basename)["pdf_folder"]
        old_cache_path = Path("cache") / f"{pdf_basename}_llm.json"

        # Remove old log file
        if old_log_path.exists():
            try:
                old_log_path.unlink()
                print(f"✅ Deleted old log: {old_log_path}")
            except PermissionError as e:
                print(f"⚠️  Could not delete log (in use): {e}")
            except Exception as e:
                print(f"⚠️  Error deleting log: {e}")

        # Remove old outputs folder
        if old_outputs_path.exists():
            try:
                shutil.rmtree(old_outputs_path)
                print(f"✅ Deleted old outputs: {old_outputs_path}")
            except PermissionError as e:
                print(f"⚠️  Could not delete outputs (in use): {e}")
            except Exception as e:
                print(f"⚠️  Error deleting outputs: {e}")

        # Remove old cache file
        if old_cache_path.exists():
            try:
                old_cache_path.unlink()
                print(f"✅ Deleted old cache: {old_cache_path}")
            except Exception as e:
                print(f"⚠️  Error deleting cache: {e}")

        # Add small delay to ensure file system has released handles
        time.sleep(0.5)

        # Now create the logger for this NEW upload
        logger = setup_logger(pdf_basename, str(log_dir / f"{pdf_basename}.log"))
        logger.info("=" * 60)
        logger.info(f"🚀 FRESH UPLOAD STARTED: {pdf_basename}")
        logger.info("=" * 60)

        # ✅ Save file
        UPLOADS_DIR.mkdir(exist_ok=True)
        dest_path = UPLOADS_DIR / file.filename

        with open(dest_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        size_bytes = dest_path.stat().st_size

        # ✅ DB record
        doc = Document(
            name=file.filename,
            file_type=ext,
            status="uploading",
            stage="uploading",
            size_bytes=size_bytes,
            path=str(dest_path),
            basename=versioned_basename
        )

        db.add(doc)
        db.commit()
        db.refresh(doc)

        logger.info(f"✅ File uploaded: {dest_path} (doc_id={doc.id})")
        logger.info(f"📌 Using versioned basename: {versioned_basename}")
        logger.info(f"📣 Upload request settings: mode={mode!r}, voice={voice!r}, persona={persona!r}, slides={num_slides}")

        # ✅ BACKGROUND TASK (CRITICAL FIX)
        background_tasks.add_task(
            run_combined_pipeline,
            doc.id,
            versioned_basename,
            str(dest_path),
            voice,  # Pass selected voice
            persona,  # Pass selected persona
            template,  # Pass selected template
            num_slides,  # Pass selected number of slides
            None,  # domain (not provided during raw upload)
            None,  # prompt_instructions (not provided during raw upload)
            mode  # Pass the selected output mode (pptx or video)
        )

        # Save chosen template name to outputs workspace so later stages can read it
        try:
            paths = get_pdf_workspace(pdf_basename)
            if template:
                tpl_file = paths["pdf_folder"] / "template_name.txt"
                tpl_file.write_text(template, encoding="utf-8")
                logger.info(f"Saved selected template to {tpl_file}")
        except Exception as e:
            logger.warning(f"Could not save template_name: {e}")

        # ✅ RETURN IMMEDIATELY
        return CombinedWorkflowResponse(
            document_id=str(doc.id),
            filename=file.filename,
            basename=versioned_basename,
            status="processing",
            stage="uploading",
            message=(
                "Phase 1: Generating slides and slide images in background. "
                "Voiceover and quiz generation will happen during processing."
            ) if mode != "video" else
            "Phase 1: Generating slides, narration, and quiz in background for video mode.",
            slides=[],
            slides_json_path=None,
            error=None,
            output_type=None  # Will be set after pipeline runs
        )

    except Exception as e:
        db.rollback()
        logger.error(f"❌ Upload failed: {str(e)}", exc_info=True)

        raise HTTPException(
            status_code=500,
            detail=f"Upload failed: {str(e)}"
        )


@router.post("/upload-file", response_model=dict)
async def upload_file_only(
        file: UploadFile = File(...),
        db: Session = Depends(get_db)
):
    """
    Upload and save a file to database without processing.
    Returns document_id for later processing.
    """
    ext = file.filename.split('.')[-1].lower()

    if ext not in ("pdf", "docx", "html"):
        raise HTTPException(
            status_code=400,
            detail="Only PDF, DOCX, or HTML files supported."
        )

    pdf_basename = Path(file.filename).stem

    try:
        # ✅ Save file
        UPLOADS_DIR.mkdir(exist_ok=True)
        dest_path = UPLOADS_DIR / file.filename

        contents = await file.read()
        file_size = len(contents)

        with open(dest_path, "wb") as buffer:
            buffer.write(contents)

        size_bytes = dest_path.stat().st_size

        # ✅ DB record
        doc = Document(
            name=file.filename,
            file_type=ext,
            status="uploaded",
            stage="uploaded",
            size_bytes=size_bytes,
            path=str(dest_path),
            basename=pdf_basename
        )

        db.add(doc)
        db.commit()
        db.refresh(doc)

        return {
            "status": "success",
            "document_id": str(doc.id),
            "filename": file.filename,
            "basename": pdf_basename,
            "message": "File uploaded successfully"
        }

    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Upload failed: {str(e)}"
        )


@router.post("/generate", response_model=CombinedWorkflowResponse)
async def generate_presentation(
        request: GenerateRequest,
        db: Session = Depends(get_db),
        background_tasks: BackgroundTasks = None
):
    """
    Generate presentation slides for an already-uploaded document.
    Accepts JSON body with document_id, voice, persona, template, slides, and optional basename for versioning.

    If basename is provided (e.g., "MyPresentation_v2"), outputs go to projects/MyPresentation/v2/.
    If no basename is provided and the document basename is unversioned, a next versioned name
    (for example "MyPresentation_v1") is selected automatically and outputs are saved under projects/.
    """

    try:
        # ✅ Get document from database (ID is UUID string)
        doc = db.query(Document).filter(Document.id == request.document_id).first()
        if not doc:
            raise HTTPException(
                status_code=404,
                detail=f"Document {request.document_id} not found"
            )

        # ✅ Validate file still exists
        file_path = Path(doc.path)
        if not file_path.exists():
            raise HTTPException(
                status_code=400,
                detail="Document file not found on disk"
            )

        # ✅ Validate voice if provided
        if request.voice and not is_valid_voice(request.voice):
            raise HTTPException(
                status_code=400,
                detail=f"Invalid voice: {request.voice}. Use /api/voices endpoint to get available options."
            )

        # ✅ Validate persona if provided
        if request.persona and not is_valid_persona(request.persona):
            raise HTTPException(
                status_code=400,
                detail=f"Invalid persona: {request.persona}. Use /api/personas endpoint to get available options."
            )

        # ✅ Validate slides count
        num_slides = None
        if request.slides:
            if request.slides < 1:
                raise HTTPException(
                    status_code=400,
                    detail="Slides must be at least 1"
                )
            num_slides = request.slides

        # ✅ Validate template if provided
        if request.template:
            request.template = _sanitize_template_name(request.template)
            templates_dir = Path(__file__).parent.parent / "sample_ppt"
            template_path = _resolve_template_path(templates_dir, request.template)
            if not _is_valid_template_file(template_path):
                raise HTTPException(
                    status_code=400,
                    detail=f"Template {request.template} not found"
                )

        # ✅ Handle versioning: if basename provided (e.g., "Project_v2"), extract version
        version_dir = None
        if request.basename:
            # Parse basename like "Project_v2" -> version = "v2"
            parts = request.basename.rsplit("_", 1)
            if len(parts) == 2 and parts[1].startswith("v"):
                version_dir = parts[1]  # e.g., "v2"

        pdf_basename = request.basename if request.basename else doc.basename
        if not request.basename:
            pdf_basename = get_next_versioned_basename(doc.basename)
            if pdf_basename != doc.basename:
                doc.basename = pdf_basename

        # ✅ Persist chosen template for later media processing
        try:
            paths = get_pdf_workspace(pdf_basename)
            if request.template:
                tpl_file = paths["pdf_folder"] / "template_name.txt"
                tpl_file.write_text(request.template, encoding="utf-8")
        except Exception as e:
            # Don't fail generation if saving the template metadata fails
            print(f"⚠️ Could not persist selected template for {pdf_basename}: {e}")

        log_dir = Path("logs")
        log_dir.mkdir(exist_ok=True)

        try:
            # ✅ Create logger
            logger_inst = setup_logger(pdf_basename, str(log_dir / f"{pdf_basename}.log"))
            logger_inst.info("=" * 60)
            logger_inst.info(f"🚀 GENERATION STARTED: {pdf_basename}")
            if version_dir:
                logger_inst.info(f"📌 Version: {version_dir}")
            logger_inst.info("=" * 60)

            # ✅ Update document status and basename (if versioned)
            doc.status = "uploading"
            doc.stage = "generating_slides"
            if request.basename:
                doc.basename = request.basename  # ✅ Update to versioned basename
            db.commit()
            db.refresh(doc)

            logger_inst.info(f"📄 Document: {doc.name} (id={doc.id})")

            # ✅ BACKGROUND TASK
            background_tasks.add_task(
                run_combined_pipeline,
                doc.id,
                pdf_basename,
                str(file_path),
                request.voice,
                request.persona,
                request.template,
                num_slides,
                request.domain,
                request.prompt_instructions,
                request.mode,
                version_dir
            )
            logger_inst.info(f"📣 Generate request settings: mode={request.mode!r}, voice={request.voice!r}, persona={request.persona!r}, slides={num_slides}")

            # ✅ RETURN IMMEDIATELY
            output_type = "pptx+video" if request.mode == "video" else "pptx"
            return CombinedWorkflowResponse(
                document_id=str(doc.id),
                filename=doc.name,
                basename=pdf_basename,
                status="processing",
                stage="generating_slides",
                message=(
                    "Generating slides and slide images in background. "
                    "Voiceover and quiz generation will happen during processing."
                ) if request.mode != "video" else
                "Generating slides, narration, and quiz in background for video mode.",
                slides=[],
                slides_json_path=None,
                error=None,
                output_type=output_type
            )

        except Exception as e:
            doc.status = "failed"
            doc.error_message = str(e)
            db.commit()
            logger_inst.error(f"❌ Generation failed: {str(e)}", exc_info=True)

            raise HTTPException(
                status_code=500,
                detail=f"Generation failed: {str(e)}"
            )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Request failed: {str(e)}"
        )


def generate_template_preview(template_path: Path, preview_path: Path):
    preview_path.parent.mkdir(parents=True, exist_ok=True)
    if preview_path.exists():
        return preview_path

    with TemporaryDirectory(dir=preview_path.parent) as temp_dir:
        temp_dir_path = Path(temp_dir)
        slide_images = pptx_to_images_via_powerpoint(str(template_path), str(temp_dir_path))
        if not slide_images:
            raise Exception("No preview images generated")
        first_image_path = Path(slide_images[0])
        first_image_path.rename(preview_path)
        return preview_path


@router.get("/templates")
def list_templates():
    """List available .pptx and .potx templates from backend/sample_ppt"""
    try:
        templates_dir = Path(__file__).parent.parent / "sample_ppt"
        preview_dir = templates_dir / "previews"
        preview_dir.mkdir(exist_ok=True)
        if not templates_dir.exists():
            return {"templates": []}

        templates = []
        for p in templates_dir.iterdir():
            if p.suffix.lower() not in (".pptx", ".potx"):
                continue
            if _is_temporary_template_file(p):
                continue
            preview_file = preview_dir / f"{p.stem}.png"
            try:
                generate_template_preview(p, preview_file)
            except Exception:
                preview_file = None

            templates.append({
                "name": p.name,
                "previewUrl": f"/api/process/template-preview/{p.name}" if preview_file and preview_file.exists() else None,
            })

        return {"templates": templates}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/template-preview/{template_name}")
def get_template_preview(template_name: str):
    templates_dir = Path(__file__).parent.parent / "sample_ppt"
    template_name = _sanitize_template_name(template_name)
    template_path = _resolve_template_path(templates_dir, template_name)
    if not _is_valid_template_file(template_path):
        raise HTTPException(status_code=404, detail="Template not found")

    preview_dir = templates_dir / "previews"
    preview_file = preview_dir / f"{template_path.stem}.png"
    if not preview_file.exists():
        try:
            generate_template_preview(template_path, preview_file)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Unable to generate preview: {e}")

    return FileResponse(str(preview_file), media_type="image/png")

def run_media_generation(pdf_basename: str):
    from db.database import SessionLocal
    db = SessionLocal()

    doc = None  # ✅ important

    try:
        doc = db.query(Document).filter_by(basename=pdf_basename).first()

        if not doc:
            return

        doc.status = "processing"
        doc.stage = "processing_media"
        db.commit()

        result = create_media_from_slides(pdf_basename)

        if result.get("status") == "error":
            doc.status = "failed"
            db.commit()
            return

        doc.status = "completed"
        doc.stage = "media_generated"
        if doc.output_type == "pptx":
            doc.output_type = "pptx+video"

        doc.generated_at = func.now()
        db.commit()

    except Exception as e:
        if doc:
            doc.status = "failed"
            db.commit()
    finally:
        db.close()

@router.post("/generate-media", response_model=MediaGenerationResponse)
async def generate_media_endpoint(
        request: dict,
        background_tasks: BackgroundTasks,
        db: Session = Depends(get_db)
):
    pdf_basename = request.get("document_basename")

    logger = setup_logger(pdf_basename, str(Path("logs") / f"{pdf_basename}.log"))

    try:
        logger.info(f"Starting media generation for {pdf_basename}")

        doc = db.query(Document).filter_by(basename=pdf_basename).first()

        if not doc:
            raise HTTPException(404, "Document not found")

        

        paths = get_pdf_workspace(pdf_basename)

        # ✅ STEP 1: Ensure quiz exists before creating media
        quiz_file = paths["pdf_folder"] / "quiz.json"
        logger.info("=" * 60)
        logger.info("ENSURING QUIZ EXISTS")
        logger.info("=" * 60)
        if not quiz_file.exists():
            try:
                logger.info("⚠️ Quiz file missing, generating quiz...")
                with open(paths["slides_json"], "r", encoding="utf-8") as f:
                    slides_data = json.load(f)
                slides = slides_data.get("slides", [])
                from Agent.quiz_agent import generate_quiz
                quiz = generate_quiz(slides, quiz_type='test', num_questions=5)
                with open(quiz_file, 'w', encoding='utf-8') as f:
                    json.dump(quiz, f, ensure_ascii=False, indent=2)
                logger.info(f"✅ Quiz saved: {quiz_file}")
            except Exception as quiz_error:
                logger.warning(f"⚠️ Quiz generation failed: {quiz_error}")
        else:
            logger.info(f"✅ Quiz already exists: {quiz_file}")

        # ✅ STEP 2: Verify voiceovers exist (should be generated during initial pipeline)
        logger.info("=" * 60)
        logger.info("VERIFYING VOICEOVERS")
        logger.info("=" * 60)

        audio_folder = paths["audio_folder"]
        audio_files = []

        if audio_folder.exists():
            audio_files = [f for f in audio_folder.iterdir() if f.suffix.lower() == ".mp3"]

        if not audio_files:
            logger.warning("⚠️  No audio files found. Voiceovers should have been generated during slide generation.")
            logger.info("Attempting to generate missing voiceovers...")

            try:
                # Load slides.json
                slides_json = paths["slides_json"]
                if not slides_json.exists():
                    raise Exception(f"slides.json not found at {slides_json}")

                with open(slides_json, "r", encoding="utf-8") as f:
                    slides_data = json.load(f)

                slides = slides_data.get("slides", [])
                # Get voice from slides.json metadata (if saved)
                voice_name = slides_data.get("voice_name")
                logger.info(f"Generating voiceovers for {len(slides)} slides (voice: {voice_name or 'default'})...")

                # Ensure audio folder exists
                paths["audio_folder"].mkdir(parents=True, exist_ok=True)

                # Generate voiceovers for each slide
                from components.ppt_voice import create_voiceover
                for idx, slide in enumerate(slides, 1):
                    audio_path = paths["audio_folder"] / f"slide_{idx}.mp3"

                    # Extract voiceover text from slide
                    voiceover_text = slide.get('voiceover') or slide.get('audio_script') or slide.get(
                        'audioScript') or ''

                    if voiceover_text:
                        logger.info(f"    Generating slide {idx} audio with voice: {voice_name or 'default (Aria)'}")
                        try:
                            create_voiceover(voiceover_text, str(audio_path), voice_name=voice_name)
                            logger.info(f"    ✓ Voiceover created ({slide.get('title', 'Slide ' + str(idx))})")
                        except Exception as e:
                            logger.error(f"    ❌ Failed to generate slide {idx} with voice {voice_name}: {str(e)}")
                            raise
                    else:
                        logger.warning(f"    ⚠️  No voiceover text found for slide {idx}, skipping")

                logger.info(f"  ✓ All {len(slides)} voiceovers processed")
                logger.info("✅ Voiceovers regenerated successfully")
            except Exception as voice_error:
                logger.warning(f"⚠️ Voiceover regeneration failed: {voice_error}")
        else:
            logger.info(f"✅ Found {len(audio_files)} audio files, using existing voiceovers")
            logger.info("(Audio was already generated during initial pipeline with selected voice)")

        logger.info("=" * 60)

        # ✅ STEP 2: Create media (PPT and Video)
        logger.info("Creating PowerPoint and Video...")
        background_tasks.add_task(
            run_media_generation,
            pdf_basename
        )

        return MediaGenerationResponse(
            status="processing",
            stage="processing_media",
            message="Media generation started in background"
        )
    except Exception as e:
        db.rollback()
        logger.error(str(e), exc_info=True)
        raise HTTPException(500, str(e))


@router.get("/slides/{basename}")
def get_slides(basename: str):
    import json
    from config import get_pdf_workspace

    paths = get_pdf_workspace(basename)
    slides_path = paths["slides_json"]

    # ✅ If file not ready yet
    if not slides_path.exists():
        return {
            "status": "processing",
            "slides": []
        }

    try:
        with open(slides_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        slides = data.get("slides", [])

        return {
            "status": "completed",
            "slides": slides
        }

    except Exception as e:
        return {
            "status": "error",
            "slides": [],
            "error": str(e)
        }