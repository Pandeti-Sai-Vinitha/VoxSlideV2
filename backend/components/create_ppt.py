import re
import os
from pathlib import Path
import shutil
import tempfile
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.enum.text import PP_ALIGN
from pptx.dml.color import RGBColor
 
 
# ==========================================
# COLOR PATTERNS FOR DIFFERENT TEMPLATES
# ==========================================
COLOR_PATTERNS = {
    "sample": {
        "title": RGBColor(0, 51, 102),      # Blue
        "content": RGBColor(0, 0, 0)        # Black
    },
    "sample1": {
        "title": RGBColor(0, 51, 102),      # Blue
        "content": RGBColor(0, 0, 0)        # Black
    },
    "sample2": {
        "title": RGBColor(128, 0, 0),   # custom color
        "content": RGBColor(40, 40, 40)
    },
    "sample4": {
        "title": RGBColor(255, 255, 255),   # custom color
        "content": RGBColor(255, 255, 255)
    }

}
 
# Default colors if template not found
DEFAULT_COLORS = {
    "title": RGBColor(0, 51, 102),
    "content": RGBColor(0, 0, 0)
}
 
def normalize_template_name(template_name: str):
    if not template_name:
        return None
    cleaned = str(template_name).strip().strip('"\'"')
    cleaned = Path(cleaned).stem
    return cleaned.lower()


def sanitize_template_name(template_name: str):
    if not template_name:
        return template_name
    return str(template_name).strip().strip('"\'"')


def get_colors_for_template(template_name):
    """
    Get color scheme for a specific template.
   
    Args:
        template_name: Name of the template (e.g., 'sample', 'sample3')
   
    Returns:
        Dictionary with 'title' and 'content' RGBColor values
    """
    if template_name and template_name in COLOR_PATTERNS:
        return COLOR_PATTERNS[template_name]
    return DEFAULT_COLORS
 
 
def clean_title(title: str) -> str:
    return re.sub(r'^Slide\s+\d+:\s*', '', title or "").strip()
 
 
def estimate_paragraph_height(text: str, font_size_pt: int) -> float:
    """
    Rough height estimation (in inches) for a paragraph.
    """
    lines = max(1, len(text) // 90 + 1)
    line_height = font_size_pt * 1.25 / 72  # pt -> inches
    return lines * line_height
 
 
def split_content_to_fit(content, max_height_in, font_size_pt):
    """
    Splits content (bullets or text) into chunks that fit inside height.
    """
    chunks = []
    current = []
    current_height = 0.0
 
    for item in content:
        Para_height = estimate_paragraph_height(str(item), font_size_pt)
 
        if current_height + Para_height > max_height_in:
            chunks.append(current)
            current = [item]
            current_height = Para_height
        else:
            current.append(item)
            current_height += Para_height
 
    if current:
        chunks.append(current)
 
    return chunks
 
 
def enforce_content_character_limit(content, has_image=False):
    """
    Enforce character limits on slide content, truncating cleanly at sentence boundaries.
   
    Args:
        content: List of bullet points or content string
        has_image: Whether the slide has an image (350 char limit) or not (600 char limit)
   
    Returns:
        Content that respects character limits and ends at sentence boundaries
    """
    max_chars = 400 if has_image else 650
    max_bullets = 3 if has_image else 7
   
    if isinstance(content, list):
        total_chars = 0
        result = []
       
        # First, filter single-word bullets (already done by filter_single_word_bullets before this call)
        # Then, enforce character limit
        for item in content:
            item_str = str(item).strip()
            if not item_str:
                continue
            item_chars = len(item_str)
           
            if total_chars + item_chars <= max_chars:
                result.append(item_str)
                total_chars += item_chars
            elif total_chars < max_chars:
                # Item doesn't fit - truncate at sentence boundary
                remaining = max_chars - total_chars
                if remaining > 10:  # Only truncate if we have enough room
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
                break # Stop adding items once limit is reached or next item doesn't fit
            else:
                break # Already at limit
       
        # Enforce maximum number of bullets (truncate extra bullets)
        if len(result) > max_bullets:
            return result[:max_bullets]
           
        return result
       
    elif isinstance(content, str):
        # For string content, truncate cleanly
        if len(content) > max_chars:
            truncated = content[:max_chars]
            # Find last sentence ending
            last_period = truncated.rfind('.')
            last_exclaim = truncated.rfind('!')
            last_question = truncated.rfind('?')
            last_sentence_end = max(last_period, last_exclaim, last_question)
           
            if last_sentence_end != -1:
                return truncated[:last_sentence_end + 1]
            else:
                last_space = truncated.rfind(' ')
                if last_space != -1:
                    return truncated[:last_space] + "."
                return truncated if truncated.endswith(('.', '!', '?')) else truncated + "."
        return content
 
 
def filter_single_word_bullets(content):
    """
    Remove single-word bullet points from slide content.
    """
    if not isinstance(content, list):
        return content
 
    filtered = []
    for item in content:
        item_str = str(item).strip()
        if not item_str:
            continue
        if len(item_str.split()) <= 1:
            continue
        filtered.append(item_str)
    return filtered
 
 
# ----------------------------
# Main function
# ----------------------------
 
def _get_best_blank_layout(prs):
    """
    Find the best blank layout from the template that preserves master slide styling.
    Most templates have multiple layouts - we want one that's blank but inherits the master.
    """
    # Try layouts in order of preference (typically blank layouts with master inheritance)
    for layout_idx in [6, 5, 7, 8, 1]:
        if layout_idx < len(prs.slide_layouts):
            return prs.slide_layouts[layout_idx]
    # Fallback to first available
    return prs.slide_layouts[0] if prs.slide_layouts else prs.slide_layouts[6]


def _find_layout_by_name(prs, keywords):
    """Return the first layout whose name contains all keywords."""
    lower_keywords = [k.lower() for k in keywords]
    for layout in prs.slide_layouts:
        layout_name = (layout.name or "").lower()
        if all(keyword in layout_name for keyword in lower_keywords):
            return layout
    return None


def _get_best_title_layout(prs):
    """Prefer a title-only layout from the template, fallback to blank."""
    return _find_layout_by_name(prs, ["title"]) or _get_best_blank_layout(prs)


def _get_best_content_layout(prs):
    """Prefer a title+content layout from the template, fallback to blank."""
    return (
        _find_layout_by_name(prs, ["title", "content"]) or
        _find_layout_by_name(prs, ["title", "body"]) or
        _find_layout_by_name(prs, ["title", "text"]) or
        _get_best_blank_layout(prs)
    )


def _find_placeholder_by_partial_name(shapes, names):
    for shape in shapes:
        if getattr(shape, "is_placeholder", False):
            name = (shape.name or "").lower()
            if any(part in name for part in names):
                return shape
    return None


def split_bullets_into_columns(bullets):
    """
    Split bullets into two roughly equal columns for text-only slides.
    """
    if not bullets:
        return [], []

    bullets = [str(b).strip() for b in bullets if str(b).strip()]
    if len(bullets) <= 3:
        return bullets, []

    mid = (len(bullets) + 1) // 2
    return bullets[:mid], bullets[mid:]


def create_ppt(slides, audio_folder, output_ppt="output_slides.pptx", template_path=None, template_name=None, images_folder=None):
    # Allow selecting a template by full path (`template_path`) or by name
    # (`template_name`) which will be resolved inside backend/sample_ppt.
    if template_name:
        template_name = sanitize_template_name(template_name)
        root = Path(__file__).parent.parent / "sample_ppt"
        candidate = root / template_name
        if candidate.exists():
            template_path = candidate
            print(f"✅ Using selected template: {template_path}")
        else:
            # Support selection by name without extension for .pptx and .potx
            found = None
            for ext in [".pptx", ".potx"]:
                candidate = root / f"{template_name}{ext}"
                if candidate.exists():
                    found = candidate
                    break
            if found:
                template_path = found
                print(f"✅ Using selected template: {template_path}")
            else:
                print(f"❌ Template NOT found: {template_name}")
                template_path = None
    else:
        print("⚠️ No template selected. Using blank presentation.")
        template_path = None
 
    # If a template path was resolved and exists, use it, otherwise start
    # with a blank Presentation to avoid errors.
    if template_path and Path(template_path).exists():
        try:
            prs = Presentation(str(template_path))
        except Exception as exc:
            if Path(template_path).suffix.lower() == ".potx":
                with tempfile.TemporaryDirectory() as temp_dir:
                    temp_pptx = Path(temp_dir) / f"{Path(template_path).stem}.pptx"
                    shutil.copy(str(template_path), str(temp_pptx))
                    prs = Presentation(str(temp_pptx))
            else:
                raise

        print(f"✅ Template loaded with {len(prs.slide_layouts)} layouts")
        # ✅ IMPORTANT: Keep template's master slides and only remove content slides
        # This preserves the template's styling, layouts, and design
        while len(prs.slides) > 0:
            # Remove only the content (not master slide relationships)
            rId = prs.slides._sldIdLst[0].rId
            prs.part.drop_rel(rId)
            del prs.slides._sldIdLst[0]
    else:
        prs = Presentation()
    
    # ✅ Determine which layout to use for new slides (should inherit template master design)
    blank_layout = _get_best_blank_layout(prs)
    title_layout = _get_best_title_layout(prs)
    content_layout = _get_best_content_layout(prs)
   
    # ✅ Collect available images if folder provided
    available_images = {}
    if images_folder and Path(images_folder).exists():
        for img_file in sorted(Path(images_folder).glob("*")):
            if img_file.is_file() and img_file.suffix.lower() in ['.png', '.jpg', '.jpeg', '.gif']:
                available_images[img_file.name] = str(img_file)
        print(f"✅ Loaded {len(available_images)} images from: {images_folder}")
        if available_images:
            print(f"   Images: {list(available_images.keys())}")
    else:
        if images_folder:
            print(f"⚠️  Images folder does not exist: {images_folder}")
        else:
            print(f"⚠️  No images folder provided")
 
    # ✅ Get color scheme based on template name
    
    normalized_template = normalize_template_name(template_name)
    if normalized_template in COLOR_PATTERNS:
        colors = get_colors_for_template(normalized_template)
    else:
        colors = DEFAULT_COLORS  # or skip styling completely


    print(f"🎨 Template for colors: {normalized_template}")

 
    for idx, slide_data in enumerate(slides, start=1):
 
        title_text = clean_title(slide_data.get("title", f"Slide {idx}"))
        content = slide_data.get("content", [])
        ctype = slide_data.get("content_type", "bullets")
        voiceover = slide_data.get("voiceover", "")
 
        # Determine font colors based on template
        title_color = colors["title"]
        content_color = colors["content"]
 
        # Normalize content
        if isinstance(content, str):
            content = [content]
 
        # Remove any single-word bullet points
        content = filter_single_word_bullets(content)
 
        # Check if this is a title-only slide (cover slide)
        # First slide is ALWAYS title-only (centered)
        is_title_only = (idx == 1) or (not content or all(not str(item).strip() for item in content))
 
        if is_title_only:
            # ----------------------------
            # TITLE-ONLY SLIDE (CENTERED)
            # ----------------------------
            slide = prs.slides.add_slide(title_layout or blank_layout)
            title_shape = slide.shapes.title if slide.shapes.title else None

            if title_shape:
                tf = title_shape.text_frame
                tf.clear()
                tf.word_wrap = True
                p = tf.paragraphs[0]
                p.text = title_text
                p.font.size = Pt(54)
                p.font.bold = True
                p.font.name = "Arial"
                p.font.color.rgb = title_color
                if p.runs:
                    p.runs[0].font.color.rgb = title_color
                p.alignment = PP_ALIGN.CENTER
            else:
                slide_height = prs.slide_height
                slide_width = prs.slide_width
 
                title_box = slide.shapes.add_textbox(
                    Inches(0.8),
                    (slide_height - Inches(2)) / 2,  # Vertical center
                    slide_width - Inches(1.6),
                    Inches(2)
                )
 
                tf = title_box.text_frame
                tf.word_wrap = True
                tf.auto_size = True
                p = tf.paragraphs[0]
                p.text = title_text
                p.font.size = Pt(54)
                p.font.bold = True
                p.font.name = "Arial"
                p.font.color.rgb = title_color
                if p.runs:
                    p.runs[0].font.color.rgb = title_color
                p.alignment = PP_ALIGN.CENTER
 
            # ----------------------------
            # NOTES
            # ----------------------------
            slide.notes_slide.notes_text_frame.text = (
                f"{title_text}\n\n"
                f"{voiceover}"
            )
 
        else:
            # ----------------------------
            # REGULAR SLIDES WITH CONTENT
            # ----------------------------
            # Content zone measurements
            content_top = Inches(2.8)
            content_height = prs.slide_height - Inches(3.5)
 
            # ✅ Convert EMUs → inches safely
            max_height_in = content_height / 914400
 
            content_font_size = 22
 
            content_chunks = split_content_to_fit(
                content,
                max_height_in=max_height_in,
                font_size_pt=content_font_size
            )
 
            for slide_part_idx, chunk in enumerate(content_chunks):
 
                slide = prs.slides.add_slide(content_layout or blank_layout)
                title_shape = slide.shapes.title if slide.shapes.title else None

                # ----------------------------
                # TITLE BOX (AUTO SAFE)
                # ----------------------------
                if title_shape:
                    tf = title_shape.text_frame
                    tf.clear()
                    tf.word_wrap = True
                    p = tf.paragraphs[0]
                    p.text = title_text
                    p.font.size = Pt(36)
                    p.font.bold = True
                    p.font.name = "Arial"
                    p.font.color.rgb = title_color
                    p.alignment = PP_ALIGN.LEFT
                else:
                    title_box = slide.shapes.add_textbox(
                        Inches(0.8),
                        Inches(1.2),
                        prs.slide_width - Inches(1.6),
                        Inches(1.4)  # taller title box
                    )
 
                    tf = title_box.text_frame
                    tf.word_wrap = True
                    tf.auto_size = True
                    p = tf.paragraphs[0]
                    p.text = title_text
                    p.font.size = Pt(36)
                    p.font.bold = True
                    p.font.name = "Arial"
                    p.font.color.rgb = title_color
                    p.alignment = PP_ALIGN.LEFT
 
                # ----------------------------
                # CONTENT BOX
                # ----------------------------
                image_index = slide_data.get("image_index")
                has_image = (
                    image_index is not None
                    and isinstance(image_index, int)
                    and isinstance(available_images, dict)
                    and 0 <= image_index < len(list(available_images.keys()))
                )
               
                # Log image processing
                if image_index is not None:
                    available_count = len(list(available_images.keys())) if isinstance(available_images, dict) else 0
                    print(f"  Slide {idx}: image_index={image_index}, available_images={available_count}, has_image={has_image}")
                    if not has_image and available_count > 0:
                        if not isinstance(image_index, int):
                            print(f"    → image_index is not int (type: {type(image_index)})")
                        elif image_index < 0 or image_index >= available_count:
                            print(f"    → image_index out of range [0, {available_count-1}]")
 
                # ✅ ENFORCE CHARACTER LIMITS ON CONTENT
                enforced_chunk = enforce_content_character_limit(chunk, has_image=has_image)
 
                def add_bullet_list_to_frame(frame, bullets):
                    if isinstance(bullets, str):
                        bullets = [bullets]
                    elif bullets is None:
                        bullets = []
                    frame.clear()
                    frame.word_wrap = True
                    for i, bullet in enumerate(bullets):
                        para = frame.paragraphs[0] if i == 0 else frame.add_paragraph()
                        bullet_text = f"• {str(bullet)}"
                        para.text = bullet_text
                        para.font.size = Pt(content_font_size)
                        para.font.name = "Arial"
                        para.font.color.rgb = content_color
                        if para.runs:
                            para.runs[0].font.color.rgb = content_color
                        para.level = 0
 
                body_placeholder = _find_placeholder_by_partial_name(slide.shapes, ["content", "body", "text"])
                if body_placeholder is not None and not has_image:
                    tf = body_placeholder.text_frame
                    add_bullet_list_to_frame(tf, enforced_chunk)
                elif has_image:
                    text_width = prs.slide_width / 2 - Inches(1.0)
                    content_box = slide.shapes.add_textbox(
                        Inches(0.8),
                        content_top,
                        text_width,
                        content_height
                    )
                    tf = content_box.text_frame
                    add_bullet_list_to_frame(tf, enforced_chunk)
                else:
                    use_two_columns = (
                        len(slides) >= 4
                        and isinstance(enforced_chunk, list)
                        and len(enforced_chunk) > 3
                        and idx % 2 == 0
                    )
                    if use_two_columns:
                        left_bullets, right_bullets = split_bullets_into_columns(enforced_chunk)
                        left_box = slide.shapes.add_textbox(
                            Inches(0.8),
                            content_top,
                            prs.slide_width / 2 - Inches(1.1),
                            content_height
                        )
                        right_box = slide.shapes.add_textbox(
                            prs.slide_width / 2 + Inches(0.1),
                            content_top,
                            prs.slide_width / 2 - Inches(1.1),
                            content_height
                        )
                        add_bullet_list_to_frame(left_box.text_frame, left_bullets)
                        add_bullet_list_to_frame(right_box.text_frame, right_bullets)
                    else:
                        content_box = slide.shapes.add_textbox(
                            Inches(0.8),
                            content_top,
                            prs.slide_width - Inches(1.6),
                            content_height
                        )
                        tf = content_box.text_frame
                        add_bullet_list_to_frame(tf, enforced_chunk)
 
                # ✅ INSERT IMAGE IF AVAILABLE (only on first chunk/slide)
                if slide_part_idx == 0 and has_image:
                    image_filenames = list(available_images.keys())
                    image_filename = image_filenames[image_index]
                    image_path = available_images[image_filename]
                    try:
                        # Add image to the right side of the slide
                        img_width = prs.slide_width / 2 - Inches(1.0)
                        img_left = prs.slide_width / 2 + Inches(0.2)
                        img_top = content_top
                        slide.shapes.add_picture(
                            image_path,
                            img_left,
                            img_top,
                            width=img_width
                        )
                        print(f"  ✓ Slide {idx}: Added image #{image_index} ({image_filename})")
                    except Exception as e:
                        print(f"  ⚠️  Slide {idx}: Failed to add image #{image_index} - {e}")
                elif slide_part_idx == 0 and not has_image and image_index is not None:
                    # Log why image was not added
                    image_filenames = list(available_images.keys()) if available_images else []
                    print(f"  ⚠️  Slide {idx}: image_index={image_index}, but has_image=False (available: {len(image_filenames)} images)")
 
                # ----------------------------
                # NOTES
                # ----------------------------
                slide.notes_slide.notes_text_frame.text = (
                    f"{title_text}\n\n"
                    f"{voiceover}\n\n"
                    f"Audio: {os.path.join(audio_folder, f'slide_{idx}.mp3')}"
                )
 
    
    if os.path.exists(output_ppt):
        os.remove(output_ppt)

    prs.save(output_ppt)
    final_slide_count = len(prs.slides)
 
    print(f"✅ PPT created with {final_slide_count} slides")
    return final_slide_count