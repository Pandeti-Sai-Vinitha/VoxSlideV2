import json
import os
from pathlib import Path
from llm.azure_llm import evaluate_with_azure_llm

def map_layouts_to_slides(slides: list, template_name: str) -> list:
    """
    Given a list of slides and a template name, query the LLM to map 
    each slide to the most appropriate layout_index from the template's JSON definition.
    Adds a 'layoutslide' key to each slide dictionary.
    """
    if not template_name:
        return slides
        
    template_base = os.path.splitext(template_name)[0]
    
    # Locate the template JSON
    template_json_path = Path("backend/sample_ppt") / f"{template_base}.json"
    if not template_json_path.exists():
        template_json_path = Path("sample_ppt") / f"{template_base}.json"
        
    if not template_json_path.exists():
        print(f"⚠️ Template JSON not found for {template_name}. Skipping dynamic layout mapping.")
        return slides
        
    try:
        with open(template_json_path, "r", encoding="utf-8") as f:
            template_layout_info = f.read()
    except Exception as e:
        print(f"⚠️ Failed to read template JSON: {e}")
        return slides

    # Prepare slides data for the LLM (strip out unnecessary heavy fields like voiceover)
    simplified_slides = []
    for i, s in enumerate(slides):
        simplified_slides.append({
            "slide_number": i + 1,
            "title": s.get("title", ""),
            "content_type": s.get("content_type", ""),
            "image_index": s.get("image_index"),
            "bullets_count": len(s.get("content", [])) if isinstance(s.get("content"), list) else 1
        })
        
    prompt = f"""You are a PowerPoint layout mapping expert.
I have a presentation with {len(slides)} slides. I need to map each slide to the most appropriate layout from my chosen PowerPoint template.

AVAILABLE SLIDE LAYOUTS FOR TEMPLATE '{template_name}':
{template_layout_info}

SLIDES TO MAP:
{json.dumps(simplified_slides, indent=2)}

MAPPING RULES:
1. For each slide, select the best layout index from the available layouts.
2. If the slide has `content_type` == "title", pick a title layout (usually index 0).
3. If the slide has `image_index` assigned (not null), YOU MUST pick an image/picture layout (a layout that contains a "PICTURE" or "OBJECT" placeholder).
4. If the slide has `content_type` == "double-row" or "two_column", pick a layout with two content placeholders.
5. If it is standard "single-row" or "content", pick a standard Title + Content layout.

You must return a valid JSON object mapping each slide number (as a string) to the chosen layout index (as an integer).

Return ONLY valid JSON in this exact format, with no markdown, code blocks, or extra text:
{{
  "1": 0,
  "2": 5,
  "3": 3
}}
"""
    try:
        response = evaluate_with_azure_llm(prompt)
        
        # Parse response
        if "```json" in response:
            response = response.split("```json")[1].split("```")[0]
        elif "```" in response:
            response = response.split("```")[1].split("```")[0]
            
        mapping = json.loads(response.strip())
        
        # Apply mapping back to original slides
        for i, s in enumerate(slides):
            slide_key = str(i + 1)
            if slide_key in mapping:
                s["layoutslide"] = mapping[slide_key]
                print(f"  ✓ Mapped Slide {slide_key} to layout {mapping[slide_key]}")
            else:
                s["layoutslide"] = None
                print(f"  ⚠️ Slide {slide_key} missing from LLM mapping")
                
        return slides
        
    except Exception as e:
        print(f"❌ Failed to map layouts dynamically: {e}")
        return slides
