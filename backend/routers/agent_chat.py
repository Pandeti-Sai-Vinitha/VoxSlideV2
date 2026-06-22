from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import os
from typing import Any, Optional

import json
import re
from config import get_latest_project_version, get_pdf_workspace
from llm.azure_llm import evaluate_with_azure_llm
from llm.azure_llm_service import build_llm_config
from openai import AzureOpenAI
import time
import hashlib
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Simple in-memory rate limiter: track timestamps per doc_id
RATE_LIMITS: dict = {}
RATE_LIMIT_MAX = 10  # max requests
RATE_LIMIT_WINDOW = 60  # seconds

# Cache TTL in seconds
CACHE_TTL = 3600  # 1 hour


class ChatRequest(BaseModel):
    doc_id: str
    message: str
    video_time: Optional[float] = 0.0  # Current video time in seconds


class QuizRequest(BaseModel):
    doc_id: str
    quiz_type: str = "test"  # 'test' or 'assignment'
    num_questions: int = 5


router = APIRouter(prefix="/agent", tags=["agent"])


def format_slide_content(slide: dict) -> str:
    """
    Format slide content properly, handling both string and list formats.
    """
    title = slide.get('title', '')
    
    # Handle content as list or string
    content = slide.get('content', '')
    if isinstance(content, list):
        content = '\n- ' + '\n- '.join(str(item) for item in content)
    else:
        content = str(content) if content else ''
    
    # Handle voiceover
    voiceover = slide.get('voiceover', '')
    if isinstance(voiceover, list):
        voiceover = ' '.join(str(item) for item in voiceover)
    else:
        voiceover = str(voiceover) if voiceover else ''
    
    return f"""Title: {title}
Content: {content}
Voiceover: {voiceover}"""


def get_slide_timings(audio_folder: str) -> list:
    """
    Get audio duration for each slide to establish timing boundaries.
    Returns a list of tuples: [(start_time, end_time), ...]
    """
    import json
    slide_timings = []
    current_time = 0.0
    total_duration = 0.0
    slide_index = 1
    logger.info(f"📂 Reading audio from: {audio_folder}")
    while True:
        audio_path = os.path.join(audio_folder, f"slide_{slide_index}.mp3")
        if not os.path.exists(audio_path):
            break
        try:
            from moviepy.editor import AudioFileClip
            audio = AudioFileClip(audio_path)
            duration = audio.duration
            slide_timings.append((current_time, current_time + duration))
            logger.info(f"   🎵 Slide {slide_index}: {current_time:.1f}s - {current_time + duration:.1f}s ({duration:.1f}s)")
            current_time += duration
            total_duration += duration
            audio.close()
        except Exception as e:
            logger.error(f"❌ Error reading audio for slide {slide_index}: {e}")
            break
        slide_index += 1
    logger.info(f"✅ Total presentation duration: {current_time:.1f}s")
    # Save total duration to outputs/{doc_id}/audio_duration.json if possible
    try:
        # audio_folder = outputs/{doc_id}/audio
        doc_dir = os.path.dirname(audio_folder)
        duration_path = os.path.join(doc_dir, "audio_duration.json")
        with open(duration_path, "w", encoding="utf-8") as f:
            json.dump({"total_audio_duration": total_duration}, f)
        logger.info(f"💾 Saved total audio duration: {total_duration:.1f}s to {duration_path}")
    except Exception as e:
        logger.error(f"❌ Could not save audio duration: {e}")
    return slide_timings


def normalize_assistant_answer(answer: str) -> str:
    """Normalize answer output to ensure separate numbered bullet lines and remove slide references."""
    if not answer or not isinstance(answer, str):
        return answer

    # Force numbered bullets to start on their own line (cover multiple numbering formats)
    answer = re.sub(r'\s*Key points include:\s*', 'Key points include:\n', answer, flags=re.IGNORECASE)
    # Match formats like '1.', '1)', '(1)', '1 -', '1 –', etc., when not already at line start
    answer = re.sub(r'(?<!\n)(?<!\d)(\(?\d+[\.|\)])\s*', r'\n\1 ', answer)
    answer = re.sub(r'(?<!\n)(?<!\d)(\d+)\s*[-–—]\s*', lambda m: '\n' + m.group(1) + '. ', answer)

    # Remove explicit slide references like (Slide 2), Slides 3 and 4, etc.
    answer = re.sub(r'\s*\(Slide[s]?\s*[^)]+\)', '', answer, flags=re.IGNORECASE)
    answer = re.sub(r'\bSlides?\s*\d+(?:\s*(?:and|,)\s*\d+)*\b', '', answer, flags=re.IGNORECASE)

    # Collapse accidental multiple newlines and trim whitespace
    answer = re.sub(r'\n{2,}', '\n', answer).strip()

    # Enforce brevity: keep first paragraph (up to 2 sentences) and up to 3 numbered bullets
    lines = answer.split('\n')
    para_lines = []
    bullets = []
    for ln in lines:
        if re.match(r'^\s*\d+\.', ln):
            bullets.append(ln.strip())
        elif bullets:
            # ignore any non-bullet after bullets
            continue
        else:
            para_lines.append(ln.strip())

    # Build paragraph: join para_lines until the first blank or bullet
    paragraph = ' '.join([l for l in para_lines if l])
    # Limit paragraph to 2 sentences
    sentences = re.split(r'(?<=[.!?])\s+', paragraph)
    short_paragraph = ' '.join(sentences[:2]).strip()

    # Keep up to 3 bullets and trim them to reasonable length (approx 25 words)
    short_bullets = []
    for b in bullets[:3]:
        # remove leading number
        m = re.match(r'^(\s*\d+\.\s*)(.*)$', b)
        text = m.group(2).strip() if m else b.strip()
        # Remove empty or invalid bullets
        if not text:
            continue
        if len(text.split()) < 3:
            continue
        if re.search(r'\b(?:and|or|but|until|because|so|then|which|where|when|if)$', text, flags=re.IGNORECASE):
            continue
        words = text.split()
        if len(words) > 25:
            text = ' '.join(words[:25]).rstrip(' ,.;:') + '...'
        short_bullets.append(text)

    # Reconstruct answer
    out = short_paragraph
    if short_bullets:
        out += '\n' + '\n'.join(f"{i+1}. {bl}" for i, bl in enumerate(short_bullets))

    return out


def identify_current_slide(video_time: float, slide_timings: list) -> int:
    """
    Identify which slide is currently being viewed based on video time.
    Returns the 0-based slide index.
    """
    for idx, (start_time, end_time) in enumerate(slide_timings):
        if start_time <= video_time < end_time:
            logger.info(f"   ✓ Video time {video_time:.1f}s falls in slide {idx + 1} range ({start_time:.1f}s - {end_time:.1f}s)")
            return idx
    
    # If time is beyond all slides, return last slide
    last_idx = len(slide_timings) - 1 if slide_timings else 0
    logger.warning(f"   ⚠️ Video time {video_time:.1f}s beyond all slides, returning last slide {last_idx + 1}")
    return last_idx


def detect_query_mode(user_question: str, slides_data: list = None) -> str:
    """
    Use LLM to intelligently determine if question is about:
    - 'slide-specific': Current slide only
    - 'full-video': Entire presentation
    """
    logger.info(f"🔍 Analyzing question: {user_question[:100]}...")
    
    # Build slides summary for context
    slides_summary = ""
    if slides_data:
        for i, slide in enumerate(slides_data, 1):
            title = slide.get('title', 'Untitled')
            slides_summary += f"Slide {i}: {title}\n"
    
    llm_config = build_llm_config(temperature=0)
    azure_client = AzureOpenAI(
        api_key=llm_config['api_key'],
        api_version=llm_config['api_version'],
        base_url=f"{llm_config['endpoint']}/openai/deployments/{llm_config['model']}"
    )
    
    analysis_prompt = f"""Analyze this user question and determine if they're asking about:
1. Current/specific slide they're viewing RIGHT NOW
2. The entire presentation/video as a whole

Question: "{user_question}"

Presentation Structure:
{slides_summary}

Respond with ONLY one word:
- "slide-specific" if asking about the current/specific slide
- "full-video" if asking about the entire presentation, outcomes, summary, comparison across slides, or overall learning

Your response:"""

    try:
        response = azure_client.chat.completions.create(
            model=llm_config['model'],
            temperature=0,
            max_tokens=20,
            messages=[
                {"role": "user", "content": analysis_prompt}
            ]
        )
        
        mode = response.choices[0].message.content.strip().lower()
        
        # Validate response
        if mode not in ['slide-specific', 'full-video']:
            logger.warning(f"⚠️ Invalid mode response: {mode}, defaulting to slide-specific")
            mode = 'slide-specific'
        
        logger.info(f"✅ Query mode detected: {mode}")
        return mode
        
    except Exception as e:
        logger.error(f"❌ Error in query mode detection: {e}, defaulting to slide-specific")
        return 'slide-specific'


@router.post("/chat")
def chat_endpoint(req: ChatRequest) -> Any:
    """Return an assistant answer based on query mode (slide-specific or full-video)."""
    logger.info(f"\n{'#'*60}")
    logger.info(f"🚀 CHAT API REQUEST")
    logger.info(f"{'#'*60}")
    logger.info(f"📢 User Question: {req.message}")
    logger.info(f"📁 Document ID: {req.doc_id}")
    logger.info(f"⏱️ Video Time: {req.video_time}s (from request)")
    
    # Check if video_time is 0.0 (default) - likely frontend not sending it
    if req.video_time == 0.0:
        logger.warning(f"⚠️ WARNING: video_time is 0.0 (default). Frontend may not be sending current video time!")
        logger.warning(f"   Make sure your frontend passes video_time as the current video player time")
    
    logger.info(f"{'#'*60}")
    now = time.time()
    times = RATE_LIMITS.get(req.doc_id, [])
    # keep only timestamps within window
    times = [t for t in times if now - t < RATE_LIMIT_WINDOW]
    if len(times) >= RATE_LIMIT_MAX:
        logger.warning(f"⚠️ Rate limit exceeded for {req.doc_id}")
        raise HTTPException(status_code=429, detail="Too many requests for this document. Try again later.")
    if not req.doc_id:
        logger.error("❌ Missing doc_id in chat request")
        raise HTTPException(status_code=400, detail="Missing doc_id")

    times.append(now)
    RATE_LIMITS[req.doc_id] = times
    paths = get_pdf_workspace(req.doc_id)
    slides_path = paths["slides_json"]

    if not slides_path.exists():
        latest_version = get_latest_project_version(req.doc_id)
        if latest_version:
            logger.info(f"🔎 Fallback to latest project version: {latest_version}")
            paths = get_pdf_workspace(latest_version)
            slides_path = paths["slides_json"]

    if not slides_path.exists():
        logger.error(f"❌ Slides not found at {slides_path}")
        raise HTTPException(status_code=404, detail=f"Slides not found for doc_id: {req.doc_id}")

    try:
        with open(slides_path, 'r', encoding='utf-8') as f:
            payload = json.load(f)
            slides = payload.get('slides') or payload.get('data') or []
    except Exception as e:
        logger.error(f"❌ Error loading slides: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to load slides.json: {e}")

    logger.info(f"📚 Loaded {len(slides)} slides")

    # Detect query mode using LLM (intelligent analysis)
    query_mode = detect_query_mode(req.message, slides)
    logger.info(f"🎯 Query Mode: {query_mode.upper()}")
    
    # Get audio folder path from workspace mapping
    audio_folder = paths["audio_folder"]
    
    # Get slide timings based on audio durations
    slide_timings = []
    if audio_folder.exists():
        logger.info(f"📂 Loading audio timings from {audio_folder}...")
        slide_timings = get_slide_timings(str(audio_folder))
        logger.info(f"✅ Audio timings loaded: {len(slide_timings)} slides")
    else:
        logger.warning(f"⚠️ Audio folder not found at: {audio_folder}")
    
    # Identify current slide based on video time (only for slide-specific mode)
    if slide_timings and query_mode == 'slide-specific':
        logger.info(f"🔍 Identifying slide for video time {req.video_time}s...")
        current_slide_idx = identify_current_slide(req.video_time, slide_timings)
        logger.info(f"🎬 → Identified Slide #{current_slide_idx + 1}")
    else:
        current_slide_idx = 0
        if query_mode == 'full-video':
            logger.info(f"🎥 Full-video mode: analyzing all {len(slides)} slides")
        elif not slide_timings:
            logger.warning(f"⚠️ No slide timings available, using slide #1")
    
    # Build context based on query mode
    if query_mode == 'slide-specific':
        # Single Slide Mode
        logger.info(f"📊 MODE: SLIDE-SPECIFIC - Analyzing slide #{current_slide_idx + 1} only")
        
        current_slide = slides[current_slide_idx] if current_slide_idx < len(slides) else None
        
        if not current_slide:
            logger.warning(f"⚠️ Could not identify current slide at index {current_slide_idx}")
            raise HTTPException(status_code=400, detail="Could not identify current slide")

        formatted_slide = format_slide_content(current_slide)
        logger.info(f"📌 Slide Title: {current_slide.get('title', 'N/A')}")
        
        system_prompt = """
    You are a helpful assistant that answers questions about the current slide being viewed.

    Rules:
    - Answer questions about the current slide content provided
    - Use information from the slide's title, content, and voiceover
    - Answer in simple, clear business language
    - If the user asks to "list", "identify", or "what are", provide ALL relevant items explicitly without summarizing
    - Do not group multiple items into one when listing; each item must be separate
    - If you don't have information to answer the question, say so clearly
    - Focus on being helpful and providing accurate information
    - Return only valid JSON like: {"answer": "..."} (no extra text or markdown)

    """
        user_context = f"Current Slide Information (Slide #{current_slide_idx + 1}):\n{formatted_slide}"
        
    else:
        # Full Video Mode
        logger.info(f"📊 MODE: FULL-VIDEO - Analyzing all {len(slides)} slides")
        
        slides_text = ""
        for i, slide in enumerate(slides, 1):
            formatted_slide = format_slide_content(slide)
            slides_text += f"""Slide {i}:
{formatted_slide}
---
"""

        system_prompt = """

    You are a helpful assistant that analyzes and answers questions about an entire presentation.

    Rules:
    - Analyze all slides provided to answer questions comprehensively
    - Provide clear, business-appropriate answers
    - When asked for comparisons, relationships, or overviews, explain connections between slides
    - Use specific information from multiple slides when relevant
    - If the user asks to "list", "identify", or "what are", provide ALL relevant items explicitly without summarizing
    - Do not group multiple items into one when listing; each item must be separate
    - If you don't have information to answer the question, say so clearly
    - Focus on being helpful and providing accurate information
    - Return only valid JSON like: {"answer": "..."} (no extra text or markdown).

    """
        user_context = f"Presentation Content (Total {len(slides)} slides):\n{slides_text}"
        current_slide_idx = -1  # Indicate full-video mode

    prompt = f"""{system_prompt}

{user_context}

User question: {req.message}
"""

    # Compute cache key
    try:
        slides_mtime = os.path.getmtime(slides_path)
    except Exception:
        slides_mtime = now

    key_raw = f"{req.message}\n{int(slides_mtime)}\n{query_mode}\n{current_slide_idx}"
    key = hashlib.sha256(key_raw.encode("utf-8")).hexdigest()
    cache_dir = os.path.join("cache", req.doc_id)
    os.makedirs(cache_dir, exist_ok=True)
    cache_file = os.path.join(cache_dir, f"{key}.json")

    # Return cached response if fresh
    if os.path.exists(cache_file):
        try:
            stat = os.stat(cache_file)
            if now - stat.st_mtime < CACHE_TTL:
                with open(cache_file, 'r', encoding='utf-8') as cf:
                    cached = json.load(cf)
                    if isinstance(cached, dict) and 'answer' in cached:
                        logger.info(f"💾 Returning cached response")
                        logger.info(f"{'#'*60}\n")
                        return {
                            'answer': cached['answer'], 
                            'cached': True, 
                            'query_mode': query_mode,
                            'slide_index': current_slide_idx if current_slide_idx >= 0 else None
                        }
        except Exception:
            pass

    # Call LLM and cache
    logger.info(f"🔄 Calling LLM for response...")
    resp = evaluate_with_azure_llm(prompt, cache_file)

    # If resp is dict and contains answer, write to cache_file
    try:
        if isinstance(resp, dict) and 'answer' in resp:
            with open(cache_file, 'w', encoding='utf-8') as cf:
                json.dump(resp, cf, ensure_ascii=False)
    except Exception:
        pass

    # Extract answer
    if isinstance(resp, dict) and "answer" in resp:
        answer = resp["answer"]
    else:
        answer = str(resp)

    # Handle array responses from LLM - convert to numbered list
    if isinstance(answer, list):
        answer = '\n'.join(f"{i+1}. {str(item)}" for i, item in enumerate(answer))
    else:
        answer = str(answer)

    # Preserve the full LLM output so the frontend displays the complete response
    raw_answer = answer
    # Disabled normalization to keep the backend response intact
    # answer = normalize_assistant_answer(answer)

    logger.info(f"✅ Response generated (length: {len(answer)} chars)")
    logger.info(f"{'#'*60}\n")

    return {
        "answer": answer,
        "raw_answer": raw_answer,
        "query_mode": query_mode,
        "slide_index": current_slide_idx if current_slide_idx >= 0 else None
    }


# ==============================
# ✅ Fetch Pre-Generated Quiz Endpoint (FAST)
# ==============================
@router.post("/get-quiz")
def get_quiz_endpoint(req: QuizRequest):
    """
    Fetch pre-generated quiz for a document (generated during upload).
    Much faster than generating on-demand after video ends.
    """
    logger.info(f"📖 Fetching pre-generated quiz - Doc: {req.doc_id}")
    
    try:
        # Resolve workspace path for the requested document
        paths = get_pdf_workspace(req.doc_id)
        quiz_file = paths["pdf_folder"] / 'quiz.json'
        slides_file = paths["slides_json"]

        if not quiz_file.exists():
            logger.error(f"❌ Pre-generated quiz not found: {quiz_file}")
            # Fallback: generate now (shouldn't happen but safety measure)
            logger.info("⚠️ Quiz not pre-generated, generating on-demand...")

            if not slides_file.exists():
                latest_version = get_latest_project_version(req.doc_id)
                if latest_version:
                    logger.info(f"🔎 Fallback to latest project version: {latest_version}")
                    paths = get_pdf_workspace(latest_version)
                    slides_file = paths["slides_json"]
                    quiz_file = paths["pdf_folder"] / 'quiz.json'

            if not slides_file.exists():
                raise HTTPException(status_code=404, detail="Document not found")

            with open(slides_file, 'r', encoding='utf-8') as f:
                slides_data = json.load(f)

            from Agent.quiz_agent import generate_quiz
            quiz_result = generate_quiz(slides_data, req.quiz_type, req.num_questions)
            return quiz_result

        # Load pre-generated quiz
        with open(quiz_file, 'r', encoding='utf-8') as f:
            quiz_data = json.load(f)
        
        logger.info(f"✅ Quiz fetched successfully - {len(quiz_data.get('questions', []))} questions")
        return quiz_data
    
    except Exception as e:
        logger.error(f"❌ Error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ==============================
# ✅ Generate Quiz On-Demand (LEGACY - slower but as fallback)
# ==============================

@router.post("/generate-quiz")
def generate_quiz_endpoint(req: QuizRequest):
    """Generate quiz questions for a document"""
    logger.info(f"📝 Quiz Generation Request - Doc: {req.doc_id}, Type: {req.quiz_type}, Questions: {req.num_questions}")
    
    try:
        # Resolve workspace path for the requested document
        paths = get_pdf_workspace(req.doc_id)
        slides_file = paths["slides_json"]

        if not slides_file.exists():
            latest_version = get_latest_project_version(req.doc_id)
            if latest_version:
                logger.info(f"🔎 Fallback to latest project version: {latest_version}")
                paths = get_pdf_workspace(latest_version)
                slides_file = paths["slides_json"]

        if not slides_file.exists():
            logger.error(f"❌ Slides file not found: {slides_file}")
            raise HTTPException(status_code=404, detail="Document not found")

        with open(slides_file, 'r', encoding='utf-8') as f:
            slides_data = json.load(f)
        
        logger.info(f"✅ Loaded {len(slides_data)} slides")
        
        # Import quiz generator
        from Agent.quiz_agent import generate_quiz
        
        # Generate quiz
        quiz_result = generate_quiz(slides_data, req.quiz_type, req.num_questions)
        
        logger.info(f"✅ Quiz generated with {quiz_result['total_questions']} questions")
        
        return quiz_result
    
    except Exception as e:
        logger.error(f"❌ Error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

