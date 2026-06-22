import os
import re
import time
import logging
from dotenv import load_dotenv
import azure.cognitiveservices.speech as speechsdk

logger = logging.getLogger(__name__)

# Default acronym pronunciation map
ACRONYM_PRONUNCIATIONS = {
    "CUSIP": "Q Sip",
    "SEC": "S E C",
    "ISIN": "Eye-Sin",
    # Add more as needed
}


def _init_speech_config():
    load_dotenv()

    key = (
        os.getenv("AZURE_SPEECH_KEY")
        or os.getenv("AZURE_SPEECH_API_KEY")
        or os.getenv("AZURE_SPEECH_SUBSCRIPTION_KEY")
    )
    region = os.getenv("AZURE_SPEECH_REGION")
    endpoint = os.getenv("AZURE_SPEECH_ENDPOINT")
    default_voice = os.getenv("AZURE_SPEECH_VOICE")

    if not key:
        raise RuntimeError("Missing AZURE_SPEECH_KEY.")
    if not region and not endpoint:
        raise RuntimeError("Provide AZURE_SPEECH_REGION or AZURE_SPEECH_ENDPOINT.")

    if endpoint:
        speech_config = speechsdk.SpeechConfig(subscription=key, endpoint=endpoint)
    else:
        speech_config = speechsdk.SpeechConfig(subscription=key, region=region)

    # Output format (feel free to adjust to your needs)
    speech_config.set_speech_synthesis_output_format(
        speechsdk.SpeechSynthesisOutputFormat.Audio16Khz32KBitRateMonoMp3
    )

    # Default to a professional voice if none is set
    if default_voice:
        speech_config.speech_synthesis_voice_name = default_voice
    else:
        speech_config.speech_synthesis_voice_name = "en-US-AriaNeural"

    return speech_config


def escape_ssml(text: str) -> str:
    """
    Escape characters that are special in SSML.
    Only use on raw text segments, not on SSML tags.
    """
    if text is None:
        return ""
    # Normalize curly apostrophes to straight quotes first
    text = text.replace("’", "'")
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def apply_pronunciations(ssml_text: str, pronunciation_dict: dict) -> str:
    """
    Wrap acronyms in <sub alias="..."> tags to control pronunciation.
    Operates on SSML-containing text; it inserts tags without escaping them.
    """
    if not pronunciation_dict:
        return ssml_text

    def make_pattern(acronym: str) -> re.Pattern:
        # Match whole-word acronym, case-insensitive
        return re.compile(rf"\b{re.escape(acronym)}\b", flags=re.IGNORECASE)

    out = ssml_text
    for acronym, alias in pronunciation_dict.items():
        pattern = make_pattern(acronym)

        # Replace preserving original casing
        def _wrap(m: re.Match) -> str:
            original = m.group(0)
            return f'<sub alias="{escape_ssml(alias)}">{original}</sub>'

        out = pattern.sub(_wrap, out)
    return out


def _emphasize_key_terms(content: str, key_terms=None) -> str:
    """
    Emphasize key terms using SSML. Preserves original casing of matched text.
    Assumes content has already been SSML-escaped.
    """
    if not content:
        return content

    if key_terms is None:
        key_terms = ["tax", "investors", "flow-through", "PFIC", "CFC", "important", "critical", "key"]

    for term in key_terms:
        pattern = re.compile(re.escape(term), flags=re.IGNORECASE)

        def _wrap(m: re.Match) -> str:
            return f"<emphasis level='moderate'>{m.group(0)}</emphasis>"

        content = pattern.sub(_wrap, content)
    return content


def format_for_speech(text: str) -> str:
    """
    Convert text into presentation-style SSML (without the outer <speak> wrapper).
    - Title (first paragraph): read once, then pause
    - Content: natural flow, with light breaks after sentences
    - Applies emphasis to key terms
    - Keeps content SSML-safe (escapes special characters)
    """
    if not text:
        return ""

    # Normalize curly apostrophes early
    text = text.replace("’", "'")

    # Split into title and content by first blank line
    parts = text.split("\n\n", 1)
    title = parts[0].strip() if parts else ""
    content = parts[1].strip() if len(parts) > 1 else ""

    # Escape both title and content to prevent SSML issues
    title_esc = escape_ssml(title) if title else ""
    content_esc = escape_ssml(content) if content else ""

    # Normalize whitespace in content and add gentle breaks at sentence boundaries
    if content_esc:
        # Flatten newlines for smoother narration
        content_esc = re.sub(r"\s+", " ", content_esc).strip()
        # Insert short break after periods that precede a capital letter (likely new sentence)
        content_esc = re.sub(r"(\.\s+)(?=[A-Z])", r"\1<break time='300ms'/>", content_esc)

    # Emphasize key terms in the content
    content_esc = _emphasize_key_terms(content_esc)

    # Construct formatted block
    if title_esc and content_esc:
        formatted = f"{title_esc} <break time='1000ms'/> {content_esc}"
    elif title_esc:
        formatted = title_esc
    else:
        formatted = content_esc

    return formatted


def create_voiceover(
    text: str,
    filename: str,
    voice_name: str = None,
    rate_pct: str = "0%",
    pitch: str = "+1%",
    acronym_map: dict = None,
    sentence_boundary_silence: str = "800ms",
    max_retries: int = 3
):
    """
    Generate professional presentation voiceover from text with retry logic.

    Args:
        text: Voiceover content
        filename: Output audio file path
        voice_name: Azure voice to use (defaults to env or AriaNeural)
        rate_pct: Speech rate percentage (e.g., -10% for slightly slower)
        pitch: Pitch adjustment (e.g., +1%)
        acronym_map: Dict of acronym -> pronunciation alias for <sub> tags
        sentence_boundary_silence: Extra silence at natural sentence boundaries (mstts)
        max_retries: Maximum number of retry attempts (default: 3)
    """
    
    # Validate input text
    if not text or not text.strip():
        logger.warning(f"Empty text provided for voiceover: {filename}")
        return filename
    
    for attempt in range(max_retries):
        try:
            speech_config = _init_speech_config()

            if voice_name:
                speech_config.speech_synthesis_voice_name = voice_name

            voice = speech_config.speech_synthesis_voice_name
            logger.info(f"TTS synth configured with voice_name={voice_name}, resolved voice={voice}")
            if voice_name and voice != voice_name:
                logger.warning(
                    f"Requested voice '{voice_name}' but speech config resolved to '{voice}'. "
                    "This may indicate unsupported or unavailable voice in Azure subscription."
                )

            audio_config = speechsdk.audio.AudioOutputConfig(filename=filename)
            synthesizer = speechsdk.SpeechSynthesizer(
                speech_config=speech_config,
                audio_config=audio_config
            )

            # Prepare SSML-safe formatted content
            formatted_text = format_for_speech(text)

            # Apply acronym pronunciations
            pronunciation_dict = acronym_map if acronym_map is not None else ACRONYM_PRONUNCIATIONS
            formatted_text = apply_pronunciations(formatted_text, pronunciation_dict)

            # Build SSML with namespaces for mstts silence
            ssml = f"""
<speak version="1.0"
       xmlns="http://www.w3.org/2001/10/synthesis"
       xmlns:mstts="http://www.w3.org/2001/mstts"
       xml:lang="en-US">
  <voice name="{voice}">
    <prosody rate="{rate_pct}" pitch="{pitch}">
      {formatted_text}
      <mstts:silence type="Sentenceboundary" value="{sentence_boundary_silence}"/>
    </prosody>
  </voice>
</speak>
            """.strip()

            logger.debug(f"[Attempt {attempt + 1}/{max_retries}] Synthesizing voiceover: {filename} (Voice: {voice})")

            # Synthesize
            result = synthesizer.speak_ssml_async(ssml).get()

            if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
                logger.info(f"✓ Voiceover created successfully: {filename}")
                return filename
            else:
                details = result.cancellation_details
                error_msg = f"{details.reason} {details.error_details}"
                
                # Check if this is a transient error worth retrying
                is_transient = any(err in error_msg.lower() for err in [
                    'websocket', 'io_error', 'timeout', 'connection', 'network', 'internal error: 3'
                ])
                
                if is_transient and attempt < max_retries - 1:
                    wait_time = (2 ** attempt) + (0.1 * (attempt + 1))  # Exponential backoff
                    logger.warning(
                        f"⚠️  Transient error on attempt {attempt + 1}/{max_retries}: {error_msg}. "
                        f"Retrying in {wait_time:.1f}s..."
                    )
                    time.sleep(wait_time)
                    continue
                else:
                    raise RuntimeError(f"Speech synthesis failed: {error_msg}")

        except Exception as e:
            error_msg = str(e)
            
            # Check if error is transient
            is_transient = any(err in error_msg.lower() for err in [
                'websocket', 'io_error', 'timeout', 'connection', 'network', 'internal error'
            ])
            
            if is_transient and attempt < max_retries - 1:
                wait_time = (2 ** attempt) + (0.1 * (attempt + 1))
                logger.warning(
                    f"⚠️  Transient error on attempt {attempt + 1}/{max_retries}: {error_msg}. "
                    f"Retrying in {wait_time:.1f}s..."
                )
                time.sleep(wait_time)
                continue
            else:
                logger.error(f"❌ Speech synthesis failed after {attempt + 1} attempts: {error_msg}")
                raise

    # Should not reach here, but just in case
    raise RuntimeError(f"Speech synthesis failed after {max_retries} attempts")