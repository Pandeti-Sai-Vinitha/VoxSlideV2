"""
Azure Speech voices configuration for presentation generation.
Includes popular professional voices for business presentations.
"""

# Available Azure Speech voices for English (US)
AVAILABLE_VOICES = {
    # Professional Female Voices (3)
    "en-US-AriaNeural": {
        "display_name": "Aria (Professional Female)",
        "language": "English (US)",
        "gender": "Female",
        "description": "Professional, clear, and engaging voice - recommended for business presentations"
    },
    "en-US-AmberNeural": {
        "display_name": "Amber (Warm Female)",
        "language": "English (US)",
        "gender": "Female",
        "description": "Warm and friendly tone, great for storytelling"
    },
    "en-US-ElizabethNeural": {
        "display_name": "Elizabeth (Professional Female)",
        "language": "English (US)",
        "gender": "Female",
        "description": "Polished and professional tone"
    },

    # Professional Male Voices (3)
    "en-US-GuyNeural": {
        "display_name": "Guy (Professional Male)",
        "language": "English (US)",
        "gender": "Male",
        "description": "Professional and authoritative voice - ideal for corporate presentations"
    },
    "en-US-BrianNeural": {
        "display_name": "Brian (Friendly Male)",
        "language": "English (US)",
        "gender": "Male",
        "description": "Warm and conversational male voice"
    },
    "en-US-EricNeural": {
        "display_name": "Eric (Executive Male)",
        "language": "English (US)",
        "gender": "Male",
        "description": "Executive-level professional tone"
    },
}

# Default voice if none selected
DEFAULT_VOICE = "en-US-AriaNeural"

# Voice settings for presentation
VOICE_SETTINGS = {
    "rate": "0%",      # Speech rate (0% = normal speed)
    "pitch": "+1%",    # Pitch adjustment
    "sentence_boundary_silence": "800ms"  # Silence at sentence boundaries
}


def get_available_voices():
    """Return list of available voices with display names"""
    return [
        {
            "id": voice_id,
            "name": voice_info["display_name"],
            "gender": voice_info["gender"],
            "description": voice_info["description"]
        }
        for voice_id, voice_info in AVAILABLE_VOICES.items()
    ]


def is_valid_voice(voice_id: str) -> bool:
    """Check if voice_id is valid"""
    return voice_id in AVAILABLE_VOICES


def get_voice_info(voice_id: str) -> dict:
    """Get detailed info about a voice"""
    return AVAILABLE_VOICES.get(voice_id, AVAILABLE_VOICES[DEFAULT_VOICE])
