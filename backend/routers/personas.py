from fastapi import APIRouter
from components.persona_config import get_available_personas

router = APIRouter(prefix="/api/personas", tags=["personas"])


@router.get("")
def list_personas():
    """
    Get list of available content generation personas.
    Each persona has different prompt instructions that affect how content is generated.
    """
    personas = get_available_personas()
    return {
        "personas": personas,
        "total": len(personas),
        "message": "Available personas for content generation customization"
    }
