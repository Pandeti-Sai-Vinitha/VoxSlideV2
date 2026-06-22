# routers/voiceover.py

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
import json
from logger_utils import setup_logger
from components.ppt_voice import create_voiceover
from components.voice_config import DEFAULT_VOICE, is_valid_voice
from config import get_pdf_workspace
import time
import uuid

router = APIRouter(prefix="/api/voiceover", tags=["voiceover"])

class VoiceoverRequest(BaseModel):
    document_basename: str
    slide_number: int
    audio_script: str
    voice_name: Optional[str] = None
    voice: Optional[str] = None
    voice_id: Optional[str] = None

@router.post("/generate")
def generate_or_retry_voiceover(req: VoiceoverRequest):
    logger = setup_logger(
        req.document_basename,
        f"logs/{req.document_basename}.log"
    )

    MAX_RETRIES = 3
    MAX_SCRIPT_LEN = 1000
    import time

    script = (req.audio_script or "").strip()

    if not script:
        raise HTTPException(400, "Audio script is empty")

    if len(script) > MAX_SCRIPT_LEN:
        logger.warning(
            f"Audio script too long ({len(script)} chars), truncating"
        )
        script = script[:MAX_SCRIPT_LEN]

    requested_voice = req.voice_name or req.voice or req.voice_id
    logger.info(f"Voiceover request body: {req.dict()}")
    if requested_voice and not is_valid_voice(requested_voice):
        raise HTTPException(400, f"Invalid voice selected: {requested_voice}")

    voice_name = requested_voice or DEFAULT_VOICE
    logger.info(f"Requested voice: {requested_voice}; Using voice_name: {voice_name}")

    # ✅ Persist voice_name to slides.json metadata so it can be reused
    paths = get_pdf_workspace(req.document_basename)
    slides_json = paths["slides_json"]
    if slides_json.exists():
        try:
            with open(slides_json, "r", encoding="utf-8") as f:
                slides_data = json.load(f)
            if slides_data.get("voice_name") != voice_name:
                slides_data["voice_name"] = voice_name
                with open(slides_json, "w", encoding="utf-8") as f:
                    json.dump(slides_data, f, indent=2, ensure_ascii=False)
                logger.info(f"Saved voice_name to slides.json: {voice_name}")
        except Exception as e:
            logger.warning(f"Could not save voice_name to slides.json: {e}")

    audio_folder = paths["audio_folder"]
    audio_folder.mkdir(parents=True, exist_ok=True)
    output_file = audio_folder / f"slide_{req.slide_number}.mp3"
    temp_output_file = audio_folder / f"slide_{req.slide_number}_{voice_name}_{uuid.uuid4().hex}.mp3"

    if output_file.exists():
        logger.info(f"Removing stale audio file before regeneration: {output_file}")
        try:
            output_file.unlink()
        except Exception as e:
            logger.warning(f"Could not remove old audio file: {e}")

    for attempt in range(MAX_RETRIES):
        try:
            logger.info(
                f"Generating voiceover for slide {req.slide_number} "
                f"(attempt {attempt + 1}/{MAX_RETRIES})"
            )

            audio_url = create_voiceover(
                text=script,
                filename=str(temp_output_file),
                voice_name=voice_name
            )
            if temp_output_file.exists() and output_file.exists():
                try:
                    output_file.unlink()
                except Exception:
                    pass
            if temp_output_file.exists():
                temp_output_file.rename(output_file)
                audio_url = str(output_file)

            if audio_url or output_file.exists():
                logger.info(f"Voiceover generated successfully for slide {req.slide_number}")
                # Return relative path for frontend
                return {
                    "status": "success",
                    "audio_url": f"/{output_file.as_posix()}",
                    "voice_name": voice_name,
                    "requested_voice": requested_voice,
                    "fallback": False,
                }

        except Exception as e:
            logger.warning(f"Attempt {attempt+1} failed: {str(e)}")
            if attempt < MAX_RETRIES - 1:
                # Exponential backoff: 1s, 2s, 4s
                wait_time = 2 ** attempt
                logger.info(f"Retrying in {wait_time} seconds...")
                time.sleep(wait_time)
            continue

    logger.error(
        f"Voiceover generation failed after {MAX_RETRIES} attempts for slide {req.slide_number}."
    )
    raise HTTPException(
        status_code=500,
        detail=(
            f"Voiceover generation failed for slide {req.slide_number}. "
            f"Requested voice: {requested_voice or DEFAULT_VOICE}"
        )
    )