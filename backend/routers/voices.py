from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pathlib import Path
import logging
from components.voice_config import get_available_voices

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/voices", tags=["voices"])

# Directory containing pre-generated voice samples
VOICE_SAMPLES_DIR = Path(__file__).parent.parent / "voice_samples"


@router.get("")
def list_voices():
    """
    Get list of available Azure Speech voices for presentation generation.
    Returns voice ID, display name, gender, and description.
    """
    voices = get_available_voices()
    return {
        "voices": voices,
        "total": len(voices),
        "message": "Available voices for presentation narration"
    }


@router.get("/preview/{voice_id}")
def get_voice_preview(voice_id: str):
    """
    Return a pre-generated voice sample (MP3).
    Samples must be pre-generated using the generate_voice_samples.py script.
    
    Args:
        voice_id: Azure voice ID (e.g., "en-US-AriaNeural")
        
    Returns:
        MP3 audio file
        
    Raises:
        HTTPException: If voice sample not found or voice ID is invalid
    """
    try:
        # Validate voice_id exists
        sample_file = VOICE_SAMPLES_DIR / f"{voice_id}.mp3"
        
        if not sample_file.exists():
            logger.warning(f"Voice sample not found: {sample_file}")
            raise HTTPException(
                status_code=404,
                detail=f"Voice sample for '{voice_id}' not found. "
                       f"Please run the voice sample generation script: "
                       f"python backend/scripts/generate_voice_samples.py"
            )
        
        logger.debug(f"Serving voice preview: {voice_id}")
        return FileResponse(
            sample_file,
            media_type="audio/mpeg",
            filename=f"{voice_id}_preview.mp3"
        )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error serving voice preview: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error serving voice preview: {str(e)}"
        )
