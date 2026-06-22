import json
import logging
import time
import threading
from pathlib import Path
from typing import Dict, Optional, List
from concurrent.futures import ThreadPoolExecutor, as_completed

from components.extractor import (
    extract_text_and_images_from_pdf,
    extract_text_and_images_from_docx,
    extract_with_hierarchy,
)

from .llm_prompt import (
    build_hierarchical_slide_prompt,
    parse_single_slide_response,
)

from .ppt_voice import create_voiceover
from .ppt_video import pptx_to_images_via_powerpoint, create_video_from_images_and_audio
from .create_ppt import create_ppt

from llm.azure_llm import evaluate_with_azure_llm
from config import get_pdf_workspace
from logger_utils import setup_logger

from .semantic_chunker import SemanticChunker, ChunkValidator, count_tokens_tiktoken
from .summarization import SummarizationPipeline
from .slide_planner import SlidePlanner
from .rag_context_builder import RAGContextBuilder
from .cache_manager import CacheManager
from .context_optimizer import ContextOptimizer



class AzureLLMServiceWrapper:
    def __init__(self, cache_path: Optional[str] = None):
        self.cache_path = cache_path
        self.logger = logging.getLogger(__name__)

    def call_azure_llm(self, prompt: str) -> str:
        self.logger.debug(f"Calling Azure LLM with prompt length: {len(prompt)} chars, cache: {self.cache_path}")
        try:
            response = evaluate_with_azure_llm(prompt, cache_path=self.cache_path)
            response_str = json.dumps(response) if isinstance(response, dict) else response
            self.logger.debug(f"Azure LLM response received, length: {len(response_str)} chars")
            return response_str
        except Exception as e:
            self.logger.error(f"Azure LLM call failed: {str(e)}", exc_info=True)
            raise


def _deduplicate_images_across_slides(slides: List[Dict], logger) -> List[Dict]:
    """
    Ensure no image appears in multiple slides.
    Each image can be used in at most one slide.

    🔒 RULE: Same image in different slides = NOT ALLOWED

    If multiple slides reference the same image_index:
    - Keep it in the FIRST slide that uses it
    - Remove it from all subsequent slides

    Args:
        slides: List of slide dictionaries
        logger: Logger instance

    Returns:
        Modified slides list with deduplicated images (each image used max once)
    """
    used_images = {}  # Track: {image_index: slide_number_where_used}
    duplicates_removed = 0

    for slide_idx, slide in enumerate(slides):
        image_index = slide.get("image_index")
        slide_number = slide_idx + 1

        if image_index is not None and isinstance(image_index, int):
            if image_index in used_images:
                # ❌ This image is already used in another slide - REMOVE IT
                first_use_slide = used_images[image_index]
                logger.warning(
                    f"  ❌ Slide {slide_number}: Image index {image_index} DUPLICATE! "
                    f"(already used in slide {first_use_slide}) - REMOVING from slide {slide_number}"
                )
                slide["image_index"] = None
                duplicates_removed += 1
            else:
                # ✅ First use of this image - keep it
                used_images[image_index] = slide_number
                logger.info(f"  ✓ Slide {slide_number}: Image index {image_index} assigned")
        else:
            logger.debug(f"  Slide {slide_number}: No image")

    logger.info(f"  ✅ Image deduplication complete: {duplicates_removed} duplicates removed")
    logger.info(f"  ✅ Image distribution: {len(used_images)} unique images in {len([s for s in slides if s.get('image_index') is not None])} slides")

    return slides


def _distribute_unused_images(slides: List[Dict], available_images: List[str], logger) -> List[Dict]:
    """
    Distribute unused images to slides that don't have images.
    Ensures all available images are used in the presentation.
    ⚠️ SKIPS FIRST SLIDE: First slide is always title-only with NO image.

    Args:
        slides: List of slide dictionaries
        available_images: List of image filenames
        logger: Logger instance

    Returns:
        Modified slides list with all images distributed (except first slide)
    """
    num_images = len(available_images)
    if num_images == 0:
        return slides

    # Find which image indices are already used
    used_images = set()
    for slide in slides:
        image_index = slide.get("image_index")
        if image_index is not None and isinstance(image_index, int):
            used_images.add(image_index)

    # Find unused images
    unused_images = [i for i in range(num_images) if i not in used_images]

    if not unused_images:
        logger.info(f"  ✓ All {num_images} images are already distributed")
        return slides

    # Find slides without images (SKIP FIRST SLIDE - it's always title-only)
    slides_without_images = [
        (idx, slide) for idx, slide in enumerate(slides)
        if slide.get("image_index") is None and idx > 0  # ✅ Skip first slide (idx == 0)
    ]

    logger.info(f"  Distributing {len(unused_images)} unused images to {len(slides_without_images)} slides without images")
    logger.info(f"  ⚠️  First slide skipped (always title-only, no image)")

    # Assign unused images to slides without images
    for (slide_idx, slide), image_idx in zip(slides_without_images, unused_images):
        slide["image_index"] = image_idx
        logger.info(f"  Slide {slide_idx + 1}: Assigned unused image index {image_idx}")

    return slides

def generate_slides_from_pdf(
    input_file: str,
    pdf_basename: Optional[str] = None,
    token_usage: Optional[dict] = None,
    persona: Optional[str] = None,
    num_slides: Optional[int] = None,
    domain: Optional[str] = None,
    prompt_instructions: Optional[str] = None,
    voice_name: Optional[str] = None,
    template_name: Optional[str] = None,
) -> dict:

    if pdf_basename is None:
        pdf_basename = Path(input_file).stem

    paths = get_pdf_workspace(pdf_basename)
    logger = setup_logger(pdf_basename, str(paths["log_file"]))

    if token_usage is None:
        token_usage = {"total_tokens": 0, "details": []}

    # Use default persona if none provided
    if not persona:
        persona = "trainee"

    # Use default number of slides if not provided
    if not num_slides:
        num_slides = 8

    try:
        logger.info("=" * 80)
        logger.info(f"STARTING HIERARCHICAL SLIDE GENERATION: {pdf_basename}")
        logger.info("=" * 80)
        logger.info(f"Input file: {input_file}")
        logger.info(f"Persona: {persona}")
        logger.info(f"Target slides: {num_slides}")

        # ✅ FORCE hierarchical pipeline
        logger.info("Pipeline: HIERARCHICAL (forced mode)")

        result = _generate_slides_hierarchical(
            input_file,
            pdf_basename,
            paths,
            logger,
            token_usage,
            persona,
            num_slides,
            domain=domain,
            prompt_instructions=prompt_instructions,
            voice_name=voice_name,
            template_name=template_name
        )

        result["token_usage"] = token_usage

        logger.info("=" * 80)
        logger.info("SLIDE GENERATION COMPLETED SUCCESSFULLY")
        logger.info(f"Total tokens used: {token_usage['total_tokens']}")
        logger.info(f"Slides output: {result.get('slides_json')}")
        logger.info("=" * 80)

        return result

    except Exception as e:
        logger.error("=" * 80)
        logger.error("SLIDE GENERATION FAILED", exc_info=True)
        logger.error("=" * 80)

        return {
            "status": "error",
            "pdf_basename": pdf_basename,
            "error": str(e),
            "log_file": str(paths["log_file"]),
        }


def _generate_slides_hierarchical(input_file, pdf_basename, paths, logger, token_usage, persona, num_slides,
                                  domain=None, prompt_instructions=None, voice_name=None, template_name=None):
    logger.info("-" * 80)
    logger.info("HIERARCHICAL PIPELINE: STARTING")
    logger.info("-" * 80)

    try:
        cache_mgr = CacheManager("./cache")
        logger.info("Cache manager initialized")

        llm = AzureLLMServiceWrapper(cache_path=str(paths["cache_file"]))
        logger.info("Azure LLM wrapper initialized")

        ext = Path(input_file).suffix.lower().lstrip(".")
        logger.info(f"File type: {ext}")

        logger.info("PHASE 1: EXTRACTING HIERARCHICAL STRUCTURE")
        blocks, hierarchy, image_paths = extract_with_hierarchy(input_file, ext)
        logger.info(f"  ✓ Extracted {len(blocks)} blocks")
        logger.info(f"  ✓ Extracted {len(image_paths)} images")
        logger.info(f"  ✓ Hierarchy depth: {len(hierarchy.get_flat_sections())} sections")

        # ✅ Get image filenames for LLM selection
        available_images = [Path(img).name for img in image_paths] if image_paths else []
        if available_images:
            logger.info(f"  ✓ Available images for slide selection: {', '.join(available_images)}")

        logger.info("PHASE 2: SEMANTIC CHUNKING")
        chunker = SemanticChunker()
        chunks = chunker.chunk_document(hierarchy)
        logger.info(f"  ✓ Created {len(chunks)} semantic chunks")

        logger.info("PHASE 3: CHUNK SUMMARIZATION (parallel)")
        summarizer = SummarizationPipeline(llm)
        chunk_summaries = []

        rate_lock = threading.Lock()
        token_lock = threading.Lock()
        last_call = [0.0]

        def rate_limited(fn, *args):
            with rate_lock:
                elapsed = time.time() - last_call[0]
                if elapsed < 0.25:
                    time.sleep(0.25 - elapsed)
                last_call[0] = time.time()
            return fn(*args)

        def summarize_chunk(chunk):
            logger.debug(f"Summarizing chunk: {chunk.chunk_id}")
            summary = rate_limited(summarizer.summarize_chunk, chunk)
            summary_tokens = count_tokens_tiktoken(summary.summary)
            with token_lock:
                token_usage["total_tokens"] += summary_tokens
                token_usage["details"].append({
                    "stage": "chunk_summarization",
                    "chunk_id": chunk.chunk_id,
                    "tokens": summary_tokens
                })
            logger.debug(f"  ✓ Chunk {chunk.chunk_id} summarized ({summary_tokens} tokens)")
            return summary

        with ThreadPoolExecutor() as executor:
            futures = [executor.submit(summarize_chunk, c) for c in chunks]
            completed = 0
            for f in as_completed(futures):
                chunk_summaries.append(f.result())
                completed += 1
                if completed % max(1, len(chunks) // 10) == 0:
                    logger.info(f"  Progress: {completed}/{len(chunks)} chunks summarized")
        logger.info(f"  ✓ All {len(chunk_summaries)} chunks summarized")

        logger.info("PHASE 4: SECTION SUMMARIZATION")
        section_summaries = []
        for section in hierarchy.get_flat_sections():
            relevant = [c for c in chunk_summaries if c.section_id == section.section_id]
            if relevant:
                logger.debug(f"Summarizing section: {section.title}")
                section_summary = summarizer.summarize_section(section.title, relevant)
                section_summaries.append(section_summary)
                logger.debug(f"  ✓ Section '{section.title}' summarized")
        logger.info(f"  ✓ All {len(section_summaries)} sections summarized")

        logger.info("PHASE 5: GLOBAL DOCUMENT SUMMARIZATION")
        global_summary = summarizer.summarize_document(section_summaries)
        global_tokens = count_tokens_tiktoken(global_summary.summary if hasattr(global_summary, 'summary') else str(global_summary))
        token_usage["total_tokens"] += global_tokens
        logger.info(f"  ✓ Global summary created ({global_tokens} tokens)")

        logger.info("PHASE 6: SLIDE PLANNING")
        planner = SlidePlanner(llm)
        slide_plans = planner.plan_slides(global_summary, section_summaries, chunks, num_target_slides=num_slides)
        logger.info(f"  ✓ Planned {len(slide_plans)} slides (target: {num_slides})")

        logger.info("PHASE 7: BUILDING RAG INDEX")
        rag = RAGContextBuilder("mock")
        rag.build_index(chunk_summaries, section_summaries)
        logger.info(f"  ✓ RAG index built with {len(chunk_summaries)} chunks and {len(section_summaries)} sections")

        logger.info("PHASE 8: INITIALIZING CONTEXT OPTIMIZER")
        optimizer = ContextOptimizer(max_tokens=3000)
        logger.info(f"  ✓ Context optimizer initialized (max_tokens=3000)")

        logger.info("PHASE 9: GENERATING SLIDES (parallel)")
        slides_with_order = []

        def generate_slide(plan):
            logger.debug(f"Generating slide {plan.slide_number}: {plan.objective}")
            context = rag.retrieve_context(
                plan.objective,
                plan.slide_number,
                plan.section_id,
                plan.source_chunk_ids,
                global_summary,
                None,
            )
            context = optimizer.optimize_context(context, buffer=1000)
            prompt = build_hierarchical_slide_prompt(
                plan,
                context,
                available_images=available_images,  # ✅ Pass images to LLM
                template_name=template_name
            )
            # Inject persona-specific instructions and extra instructions
            from components.persona_config import build_persona_aware_prompt
            prompt = build_persona_aware_prompt(prompt, persona, extra_instructions=prompt_instructions, domain=domain)
            response = rate_limited(llm.call_azure_llm, prompt)
            slide = parse_single_slide_response(response)
            slide_tokens = count_tokens_tiktoken(response)
            with token_lock:
                token_usage["details"].append({
                    "stage": "slide_generation",
                    "slide_number": plan.slide_number,
                    "tokens": slide_tokens
                })
            logger.debug(f"  ✓ Slide {plan.slide_number} generated ({slide_tokens} tokens)")
            return plan.slide_number, slide

        with ThreadPoolExecutor() as executor:
            futures = [executor.submit(generate_slide, p) for p in slide_plans]
            completed = 0
            for f in as_completed(futures):
                slides_with_order.append(f.result())
                completed += 1
                if completed % max(1, len(slide_plans) // 10) == 0:
                    logger.info(f"  Progress: {completed}/{len(slide_plans)} slides generated")

        slides_with_order.sort(key=lambda x: x[0])
        slides = [s for _, s in slides_with_order]
        logger.info(f"  ✓ All {len(slides)} slides generated and ordered")

        logger.info("PHASE 10: DEDUPLICATING IMAGES ACROSS SLIDES")
        # Ensure no image appears in multiple slides
        slides = _deduplicate_images_across_slides(slides, logger)
        logger.info(f"  ✓ Image distribution deduplicated - each image used at most once")

        logger.info("PHASE 11: DISTRIBUTING UNUSED IMAGES")
        # Distribute any unused images to slides without images
        slides = _distribute_unused_images(slides, available_images, logger)
        logger.info(f"  ✓ All available images distributed to slides")

        logger.info("PHASE 12: SAVING SLIDES JSON")
        slides_json_data = {"slides": slides}
        if template_name:
            slides_json_data["template_name"] = template_name
        with open(paths["slides_json"], "w", encoding="utf-8") as f:
            json.dump(slides_json_data, f, indent=2)
        logger.info(f"  ✓ Slides saved to: {paths['slides_json']}")

        logger.info("-" * 80)
        logger.info(f"HIERARCHICAL PIPELINE: COMPLETED SUCCESSFULLY")
        logger.info(f"  Total slides: {len(slides)}")
        logger.info(f"  Total tokens used: {token_usage['total_tokens']}")
        logger.info("-" * 80)

        return {
            "status": "success",
            "pdf_basename": pdf_basename,
            "slides_json": str(paths["slides_json"]),
            "num_slides": len(slides),
            "mode": "hierarchical",
        }
    except Exception as e:
        logger.error(f"HIERARCHICAL PIPELINE FAILED: {str(e)}", exc_info=True)
        raise

def create_media_from_slides(pdf_basename: str) -> dict:
    """
    Create voiceovers, PPT, images, and video from slides.json.
    Assumes slides.json already exists in outputs/{pdf_basename}/.

    CRITICAL: Video is created from images EXPORTED from the PPT,
    which ensures the video matches exactly what's shown in the PPT preview.

    Returns:
        dict: Status and output file paths
    """
    paths = get_pdf_workspace(pdf_basename)
    logger = setup_logger(pdf_basename, str(paths["log_file"]))
    try:
        logger.info("=" * 80)
        logger.info(f"STARTING MEDIA CREATION FOR: {pdf_basename}")
        logger.info("=" * 80)
        logger.info("✅ VIDEO will be created from PPT-exported images (matches PPT preview exactly)")
        logger.info("")

        if not paths["slides_json"].exists():
            raise FileNotFoundError(f"slides.json not found: {paths['slides_json']}")
        logger.info(f"Loading slides from {paths['slides_json']}")
        with open(paths['slides_json'], 'r', encoding='utf-8') as f:
            slides_data = json.load(f)
        slides = slides_data.get('slides', [])
        logger.info(f"  ✓ Loaded {len(slides)} slides from slides.json")

        # Log slide details for verification
        for idx, slide in enumerate(slides, 1):
            logger.debug(f"    Slide {idx}: {slide.get('title', 'No title')}")
            logger.debug(f"      - Content type: {slide.get('content_type', 'bullets')}")
            logger.debug(f"      - Has image: {slide.get('image_index') is not None}")
            logger.debug(f"      - Voiceover length: {len(slide.get('voiceover', ''))} chars")
        # Create voiceovers
        logger.info("-" * 60)
        logger.info("PHASE 2: GENERATING VOICEOVERS")
        logger.info("-" * 60)
        logger.info(f"Creating audio narration for {len(slides)} slides...")
        for idx, slide in enumerate(slides, 1):
            audio_path = paths["audio_folder"] / f"slide_{idx}.mp3"
            logger.info(f"  [{idx}/{len(slides)}] Creating voiceover: {audio_path}")
            create_voiceover(slide['voiceover'], str(audio_path))
            logger.info(f"    ✓ Voiceover created ({slide.get('title', 'Slide ' + str(idx))})")
        logger.info(f"  ✓ All {len(slides)} voiceovers created")
        # Create PPT
        logger.info("-" * 60)
        logger.info("PHASE 3: CREATING POWERPOINT PRESENTATION")
        logger.info("-" * 60)
        logger.info(f"Creating PowerPoint presentation: {paths['ppt_file']}")

        # Determine if a template was selected and saved during upload
        template_name = None
        tpl_file = paths["pdf_folder"] / "template_name.txt"
        if tpl_file.exists():
            try:
                template_name = tpl_file.read_text(encoding="utf-8").strip()
                logger.info(f"  ✓ Using template: {template_name}")
            except Exception as e:
                logger.warning(f"  ⚠️  Could not read template_name: {e}")
                template_name = None

        # ✅ Get extracted images folder if it exists
        import os as os_module
        from config import parse_versioned_basename

        base_name, version_dir = parse_versioned_basename(pdf_basename)
        candidates = []
        if version_dir:
            candidates.append(os_module.path.join("extracted_images_docx", base_name, version_dir))
        candidates.extend([
            os_module.path.join("extracted_images_docx", pdf_basename),
            os_module.path.join("extracted_images_docx", base_name)
        ])

        images_folder = next((candidate for candidate in candidates if os_module.path.exists(candidate)), None)

        final_ppt_slide_count = create_ppt(
            slides,
            str(paths["audio_folder"]),
            str(paths["ppt_file"]),
            template_name=template_name,
            images_folder=images_folder
        )

        logger.info(f"  ✓ PowerPoint presentation created successfully")

        logger.info("PHASE 4: EXPORTING SLIDES AS IMAGES FROM PPT")
        logger.info("-" * 80)
        logger.info(f"Converting PowerPoint to images: {paths['slides_images_folder']}")
        logger.info("⚠️  IMPORTANT: These images are exported from the rendered PPT")
        logger.info("   Video will be created from these exported images")
        logger.info("   This ensures video content matches PPT preview exactly")

        slide_images = pptx_to_images_via_powerpoint(
            str(paths["ppt_file"]),
            str(paths["slides_images_folder"])
        )
        logger.info(f"  ✓ Exported {len(slide_images)} slide images from PPT")

        # VALIDATION: Check that exported image count matches slide count
        if len(slide_images) != len(slides):
            logger.warning(f"  ⚠️  Mismatch: slides.json has {len(slides)} slides but PPT exported {len(slide_images)} images")
            logger.warning(f"      Using {len(slide_images)} images for video (PPT export count)")
        else:
            logger.info(f"  ✓ Image count matches slide count ({len(slide_images)} == {len(slides)})")

        for i, img_path in enumerate(slide_images, 1):
            logger.debug(f"    Image {i}: {Path(img_path).name}")

        # Create video
        logger.info("-" * 80)
        logger.info("PHASE 5: CREATING VIDEO FROM PPT IMAGES")
        logger.info("-" * 80)
        logger.info(f"Creating video with synced audio: {paths['video_file']}")
        logger.info(f"  Source: {len(slide_images)} images exported from PPT")
        logger.info(f"  Audio: {len(slides)} voiceovers from slides.json")

        create_video_from_images_and_audio(
            slide_images,
            str(paths["audio_folder"]),
            str(paths["video_file"])
        )
        logger.info(f"  ✓ Video created successfully")
        logger.info("")
        logger.info("=" * 80)
        logger.info(f"MEDIA CREATION COMPLETED FOR: {pdf_basename}")
        logger.info("=" * 80)
        logger.info(f"Summary:")
        logger.info(f"  - Slides in slides.json: {len(slides)}")
        logger.info(f"  - Images exported from PPT: {len(slide_images)}")
        logger.info(f"  - Voiceovers created: {len(slides)}")
        logger.info(f"")
        logger.info(f"Output files:")
        logger.info(f"  - PowerPoint: {paths['ppt_file']}")
        logger.info(f"  - Video: {paths['video_file']} (FROM PPT-EXPORTED IMAGES)")
        logger.info(f"  - Audio folder: {paths['audio_folder']} ({len(slides)} files)")
        logger.info(f"  - Images folder: {paths['slides_images_folder']} ({len(slide_images)} files)")
        logger.info("=" * 80)

        return {
            "status": "success",
            "pdf_basename": pdf_basename,
            "ppt_file": str(paths["ppt_file"]),
            "video_file": str(paths["video_file"]),
            "audio_folder": str(paths["audio_folder"]),
            "slides_images_folder": str(paths["slides_images_folder"]),
            "log_file": str(paths["log_file"]),
            "num_slides": final_ppt_slide_count
        }
    except Exception as e:
        logger.error(f"ERROR during media creation: {str(e)}", exc_info=True)
        return {
            "status": "error",
            "pdf_basename": pdf_basename,
            "error": str(e),
            "log_file": str(paths["log_file"])
        }

