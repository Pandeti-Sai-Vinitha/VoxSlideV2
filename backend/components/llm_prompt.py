"""
LLM Prompt Builder

Generates prompts for hierarchical context-aware slide generation.

Supports:
- Full-document mode (backward compatible, single call)
- Hierarchical mode (per-slide, uses selective context from RAG)
"""

import os
import json
from pathlib import Path
from typing import Dict, Any, List, Optional

def build_hierarchical_slide_prompt(
    slide_plan_item: 'SlidePlanItem',
    context: 'RetrievedContext',
    module_name: str = "Enterprise Training",
    available_images: Optional[List[str]] = None,
    template_name: Optional[str] = None
) -> str:
    """
    Build context-aware prompt for a single slide (HIERARCHICAL MODE)

    This is the NEW approach: build targeted prompt for ONE slide
    using only relevant summaries from the document.

    Args:
        slide_plan_item: Planned slide (from slide_planner)
        context: Retrieved context (from RAG builder)
        module_name: Training module name
        available_images: List of image filenames available for this document

    Returns:
        Prompt string for LLM to generate single slide
    """
    # Build context section
    context_sections = []

    # 1. Global document context
    if context.global_summary:
        context_sections.append(
            f"DOCUMENT OVERVIEW:\n"
            f"Purpose: {context.global_summary.document_purpose}\n"
            f"Narrative: {context.global_summary.overall_narrative}\n"
            f"Key themes: {', '.join(context.global_summary.important_themes)}"
        )

    # 2. Previous slide (for continuity)
    if context.previous_slide_summary:
        context_sections.append(
            f"PREVIOUS SLIDE CONTEXT:\n{context.previous_slide_summary}"
        )

    # 3. Relevant content chunks
    if context.relevant_chunk_summaries:
        chunk_context = []
        for chunk in context.relevant_chunk_summaries:
            chunk_context.append(
                f"[From section: {chunk.section_title}]\n"
                f"{chunk.summary}\n"
                f"Key points: {', '.join(chunk.key_points[:3])}"
            )
        context_sections.append(
            f"RELEVANT CONTENT:\n" + "\n\n".join(chunk_context)
        )

    # 4. Section summary (if available)
    if context.relevant_section_summary:
        context_sections.append(
            f"SECTION SUMMARY:\n"
            f"{context.relevant_section_summary.summary}"
        )

    context_text = "\n\n---\n\n".join(context_sections)
    
    template_instructions = ""
    if template_name:
        template_instructions = f"""
TEMPLATE INSTRUCTIONS:
- Use the selected PowerPoint template: \"{template_name}\"
- Align the slide title, bullets, and voiceover with the template's layout, style, fonts, and colors
- Keep the slide structure professional and consistent with the template design
- Prefer concise, template-friendly text that fits cleanly on the slide
"""

    # Build available images section
    images_text = ""
    if available_images:
        images_list = "\n".join([f"  {i}: {img}" for i, img in enumerate(available_images)])
        images_text = f"""
AVAILABLE IMAGES (choose one that best matches the slide content):
{images_list}

IMAGE SELECTION RULES:
- Analyze the slide title and content to determine if an image is relevant
- Return the image_index (0-based) of the best matching image
- If no image is appropriate, return null (don't force an irrelevant image)
- Consider context: Charts for data, diagrams for processes, photos for concepts"""

    # ✅ Check if this is the first slide (cover slide)
    is_first_slide = slide_plan_item.slide_number == 1
    first_slide_instruction = ""
    image_selection_rules = images_text  # Default: include image selection
    
    if is_first_slide:
        first_slide_instruction = """
IMPORTANT: This is the FIRST SLIDE (cover/title slide). 
- Set content_type to "title"
- Set content to empty string "" (NO content, NO bullets)
- Set image_index to null (NO IMAGE on first slide)
- Only include the title
- The voiceover should just be the title repeated once"""
        image_selection_rules = ""  # No image selection for first slide

    # Build slide-specific prompt
    prompt = f"""You are a PowerPoint slide generation expert. Generate a single slide following the given context and slide plan.
 
MODULE: {module_name}
 
DOCUMENT CONTEXT:
{context_text}
{template_instructions}
{image_selection_rules}
{first_slide_instruction}
 
SLIDE PLAN (Slide {slide_plan_item.slide_number}):
- Title: {slide_plan_item.title}
- Objective: {slide_plan_item.objective}
- Content type: {slide_plan_item.content_type}
- Required topics: {', '.join(slide_plan_item.required_topics)}
 
GENERATION RULES (MANDATORY - VIOLATIONS WILL BE REJECTED):
1. Generate ONLY this single slide (not multiple slides)
2. Slide title: must match or closely follow the planned title
3. Content must address the stated objective

⚠️  CRITICAL - CONTENT LENGTH LIMITS (HARD REQUIREMENTS - NO EXCEPTIONS):
IF you select image_index (not null):
   ✓ MUST have EXACTLY 2-3 bullets (not 1, not 4+)
   ✓ MUST have MAXIMUM 400 total characters
   ✓ MUST count characters: bullet1 + bullet2 + bullet3 = total ≤ 400
   ✓ Each individual bullet ≤ 100 characters
   ✗ VIOLATION: Selecting image with 4+ bullets = INVALID
   ✗ VIOLATION: Selecting image with >400 chars = INVALID

IF you do NOT select an image (image_index = null):
   ✓ CAN have UP TO 5 bullets
   ✓ CAN have UP TO 650 total characters
   ✓ Should use 3-5 bullets for good readability
   ✗ VIOLATION: Returning >5 bullets = INVALID
   ✗ VIOLATION: Returning >650 characters = INVALID

CHARACTER COUNTING METHOD:
- Count every character in every bullet (spaces, punctuation, all)
- Add all bullets together for total
- Example: "Bullet one." (11 chars) + "Bullet two." (11 chars) = 22 chars total

4. Content type rules:
   - "content": Standard single-column text or bullet points.
   - "two_column": Use for comparing concepts or when you have many bullets that should be split into two columns.
   - "title": Just title (no content)
   - "summary": Summarize key points from context (as bullet points)

5. Bullet content requirements (MANDATORY):
   - Each bullet MUST be a complete, grammatically correct sentence or a short, self-contained phrase that conveys a full idea.
   - NO single words, fragments, or incomplete thoughts.
   - Prefer bullets with 2+ words and end them with a period.
   - Count your bullets before responding - MUST match requirements above

6. Voice-over must rephrase only the slide content in a presentation style narration:
   STRUCTURE:
   - START: Repeat the slide title verbatim
   - PAUSE: (system will add 1-second pause after title)
   - CONTENT: Rephrase each bullet point into a spoken sentence or short paragraph
   - LENGTH: Enough to cover the slide content, but do not add extra facts
   
   REQUIREMENTS:
   - MUST use only the information already present in the slide content
   - MUST not introduce new examples, concepts, or background beyond the bullets
   - MUST keep the same meaning as the bullet content
   - MUST cover every bullet point without skipping any
   - Sound natural and presentation-ready
   - Use short sentences that flow together
   
   RULES:
   - Avoid "This slide shows" or "In this slide"
   - Do not invent facts or add unrelated commentary
   - Do not expand beyond the content provided

8. IMAGE SELECTION (MANDATORY RULES):
   - Choose the MOST relevant image from the available list (if any)
   - Return image_index (0-based integer) OR null if no image is suitable
   - CRITICAL DECISION POINT:
     * Selecting image = ACCEPTING tight constraints (2-3 bullets, ≤400 chars)
     * If you select an image but have 4+ bullets or >400 chars, RESPONSE WILL BE INVALID
     * Better to return null than select image and violate constraints
   - Only select images that are HIGHLY relevant to the slide content
   - Generic or vaguely related images should be null

✅ VALID EXAMPLE (with image, 2 bullets):
  "content": ["US funds use flow-through taxation, reporting income directly to investors.", "Management fees have limited deductibility until 2026."]
  Characters: 74 + 61 = 135 chars ✓ (under 400)
  Bullets: 2 ✓ (between 2-3)
  image_index: 0 ✓

❌ INVALID EXAMPLE (with image, 4 bullets):
  "content": ["First bullet.", "Second bullet.", "Third bullet.", "Fourth bullet."]
  Bullets: 4 ✗ (exceeds max 3)
  RESPONSE REJECTED

❌ INVALID EXAMPLE (with image, >400 chars):
  "content": ["This is a very long bullet point that exceeds the character limit when added together with other bullets in the slide...", "Another long bullet..."]
  Characters: 450+ ✗ (exceeds 400)
  RESPONSE REJECTED

✅ VALID EXAMPLE (no image, 5 bullets):
  "content": ["Blocker corporations shield tax-exempt investors from unrelated business taxable income.", "They own partnership interests and pay corporate tax first.", "This reduces direct tax exposure from operating partnerships.", "Debt-financed income creates fewer UBTI challenges.", "Strategic structuring enhances overall tax efficiency for investors."]
  Bullets: 5 ✓ (between 4-6)
  image_index: null ✓

9. Professional, clear, enterprise-appropriate tone
10. Do not reference slide numbers
11. Do not invent facts - stick to context provided
12. FINAL VALIDATION BEFORE RESPONDING:
    - Count your bullets: ___
    - Count your characters: ___
    - Selected image? YES/NO
    - If YES to image: bullets ≤ 3? YES/NO, chars ≤ 400? YES/NO
    - If NO to image: bullets ≤ 7? YES/NO, chars ≤ 650? YES/NO
    - Only respond if all checks pass
 
Return ONLY valid JSON (no markdown, no code blocks):
{{
  "slide": {{
    "title": "Slide title",
    "content_type": "content|two_column|title|summary",
    "content": ["bullet 1", "bullet 2"] or "" for title,
    "voiceover": "Voice-over script starting with title, then detailed explanation of all bullets (4-6 sentences minimum)",
    "image_prompt": "",
    "image_index": 0 or null
  }}
}}
 
Respond with only the JSON object, no additional text."""

    return prompt


def enforce_content_character_limit(
    content: List[str],
    has_image: bool = False
) -> List[str]:
    """
    Enforce character limits on slide content, truncating cleanly at sentence boundaries.
    
    Args:
        content: List of bullet points or content items
        has_image: Whether the slide has an image (affects limit)
    
    Returns:
        Truncated content list that respects character limits
    """
    # Align with prompt guidance: tighter limit when an image is present
    max_chars = 400 if has_image else 650
    # Limit bullet count when image present to keep slides concise
    max_bullets = 3 if has_image else 5
    total_chars = 0
    result = []
    
    for item in content:
        item_str = str(item).strip()
        if not item_str:
            continue
        
        item_chars = len(item_str)
        
        if total_chars + item_chars <= max_chars:
            # Item fits completely
            result.append(item_str)
            total_chars += item_chars
        elif total_chars < max_chars:
            # Item doesn't fit - truncate at sentence boundary
            remaining = max_chars - total_chars
            if remaining > 10:  # Only truncate if we have enough room
                # Try to find a sentence boundary (. ! ?)
                truncated = item_str[:remaining]
                
                # Find last sentence ending
                last_period = truncated.rfind('.')
                last_exclaim = truncated.rfind('!')
                last_question = truncated.rfind('?')
                
                last_sentence_end = max(last_period, last_exclaim, last_question)
                
                if last_sentence_end != -1:
                    # Use the sentence boundary
                    truncated = truncated[:last_sentence_end + 1]
                else:
                    # No good sentence boundary, try to end at space
                    last_space = truncated.rfind(' ')
                    if last_space != -1:
                        truncated = truncated[:last_space] + "."
                    else:
                        # Just truncate and add period if it doesn't already have one
                        if not truncated.endswith(('.', '!', '?')):
                            truncated = truncated.rstrip() + "."
                
                result.append(truncated)
            # Don't add this item if there's no space
            break
        else:
            # Already at limit
            break
    
    # Enforce maximum number of bullets (truncate extra bullets)
    if len(result) > max_bullets:
        return result[:max_bullets]
    return result

def filter_single_word_bullets(content: List[str]) -> List[str]:
    """
    Remove single-word bullet points so content remains sentence-based.
    """
    filtered = []
    for item in content:
        item_str = str(item).strip()
        if not item_str:
            continue
        if len(item_str.split()) <= 1:
            continue
        filtered.append(item_str)
    return filtered

def build_multi_slide_generation_prompt(
    slide_plans: List['SlidePlanItem'],
    contexts: List['RetrievedContext'],
    module_name: str = "Enterprise Training"
) -> List[str]:
    """
    Build prompts for batch slide generation

    Args:
        slide_plans: List of planned slides
        contexts: List of retrieved contexts (one per slide)
        module_name: Training module name

    Returns:
        List of prompts (one per slide)
    """
    prompts = []
    for plan, context in zip(slide_plans, contexts):
        prompt = build_hierarchical_slide_prompt(plan, context, module_name)
        prompts.append(prompt)
    return prompts




def parse_single_slide_response(response: str) -> Optional[Dict[str, Any]]:
    """
    Parse LLM response for a single slide (HIERARCHICAL MODE)
    
    CRITICAL: This function enforces strict content limits based on image presence.
    - With image: max 3 bullets, max 400 chars
    - Without image: max 5 bullets, max 650 chars

    Args:
        response: Raw LLM response (should be JSON)

    Returns:
        Slide dict or None if parsing fails
    """
    try:
        # Handle markdown code blocks
        if "```json" in response:
            response = response.split("```json")[1].split("```")[0]
        elif "```" in response:
            response = response.split("```")[1].split("```")[0]

        data = json.loads(response.strip())

        # Extract slide from response
        if "slide" in data:
            slide = data["slide"]
        elif "slides" in data and len(data["slides"]) > 0:
            slide = data["slides"][0]
        else:
            slide = data

        # Validate and normalize
        slide.setdefault("title", "")
        slide.setdefault("content", "")
        slide.setdefault("content_type", "content")
        slide.setdefault("voiceover", "")
        slide.setdefault("image_prompt", "")
        slide.setdefault("image_index", None)

        # ✅ ENFORCE CHARACTER AND BULLET LIMITS ON CONTENT
        has_image = slide.get("image_index") is not None
        content = slide.get("content", "")
        
        if isinstance(content, list) and content:
            # Step 1: Remove single-word fragments
            content = filter_single_word_bullets(content)
            
            # Step 2: Enforce character limits and truncate if needed
            enforced_content = enforce_content_character_limit(content, has_image=has_image)
            
            # Step 3: Log the enforcement for debugging
            char_count = sum(len(str(item).strip()) for item in enforced_content if str(item).strip())
            bullet_count = len(enforced_content)
            max_chars = 400 if has_image else 650
            max_bullets = 3 if has_image else 5
            
            print(f"[SLIDE CONTENT ENFORCEMENT] Image: {has_image} | Bullets: {bullet_count}/{max_bullets} | Chars: {char_count}/{max_chars}")
            
            # Step 4: Final validation - if limits still exceeded, truncate more aggressively
            if has_image and bullet_count > 3:
                print(f"  ⚠️  VIOLATION: {bullet_count} bullets with image (max 3) - truncating to 3")
                enforced_content = enforced_content[:3]
            
            if has_image and char_count > 400:
                print(f"  ⚠️  VIOLATION: {char_count} chars with image (max 400) - re-enforcing limit")
                enforced_content = enforce_content_character_limit(enforced_content, has_image=True)
            
            if not has_image and bullet_count > 5:
                print(f"  ⚠️  VIOLATION: {bullet_count} bullets without image (max 5) - truncating to 5")
                enforced_content = enforced_content[:5]
            
            if not has_image and char_count > 650:
                print(f"  ⚠️  VIOLATION: {char_count} chars without image (max 650) - re-enforcing limit")
                enforced_content = enforce_content_character_limit(enforced_content, has_image=False)
            
            slide["content"] = enforced_content
            
        elif isinstance(content, str) and content:
            # For string content, truncate cleanly at sentence boundary
            max_chars = 400 if has_image else 650
            if len(content) > max_chars:
                truncated = content[:max_chars]
                # Find last sentence ending
                last_period = truncated.rfind('.')
                last_exclaim = truncated.rfind('!')
                last_question = truncated.rfind('?')
                last_sentence_end = max(last_period, last_exclaim, last_question)
                
                if last_sentence_end != -1:
                    slide["content"] = truncated[:last_sentence_end + 1]
                else:
                    last_space = truncated.rfind(' ')
                    if last_space != -1:
                        slide["content"] = truncated[:last_space] + "."
                    else:
                        slide["content"] = truncated if truncated.endswith(('.', '!', '?')) else truncated + "."
                
                print(f"[STRING CONTENT TRUNCATED] Image: {has_image} | Original: {len(content)} chars | Truncated: {len(slide['content'])} chars")

        return slide

    except json.JSONDecodeError as e:
        print(f"❌ Failed to parse slide response: {e}\nResponse: {response}")
        return None


def build_summary_generation_prompt(
    slide_title: str,
    slide_content: str
) -> str:
    """
    Build prompt to generate slide summary (for previous_slide_context)

    This is used to create a concise summary of a slide for inclusion
    in the next slide's context.

    Args:
        slide_title: Title of slide
        slide_content: Content of slide

    Returns:
        Prompt for summarization
    """
    prompt = f"""Summarize this slide in 1-2 sentences for context in the next slide.
 
Slide Title: {slide_title}
 
Slide Content:
{slide_content}
 
Return ONLY the 1-2 sentence summary, no additional text."""
    return prompt