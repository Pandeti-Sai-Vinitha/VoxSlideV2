"""
Validate and rebalance slide content based on image presence.
 
This script:
1. Validates that slides with image_index have appropriately reduced content
2. Validates that slides without image_index can have more content
3. Flags slides that violate content limits
4. Suggests content redistribution or adjustments
"""
 
import json
from pathlib import Path
from typing import List, Dict, Any, Tuple
 
def count_characters(content: List[str] | str) -> int:
    """Count total characters in content."""
    if isinstance(content, list):
        return sum(len(str(item).strip()) for item in content if str(item).strip())
    elif isinstance(content, str):
        return len(content.strip())
    return 0
 
def count_bullets(content: List[str] | str) -> int:
    """Count number of bullet points."""
    if isinstance(content, list):
        return len([item for item in content if str(item).strip()])
    elif isinstance(content, str) and content.strip():
        return 1
    return 0
 
def enforce_content_character_limit(content, has_image=False):
    """
    Enforce character limits on slide content, truncating cleanly at sentence boundaries.
   
    Args:
        content: List of bullet points or content string
        has_image: Whether the slide has an image (400 char limit) or not (650 char limit)
   
    Returns:
        Content that respects character limits and ends at sentence boundaries
    """
    max_chars = 400 if has_image else 650
    max_bullets = 3 if has_image else 5
   
    if isinstance(content, list):
        total_chars = 0
        result = []
       
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
                break
            else:
                break
       
        # Enforce maximum number of bullets
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
 
def validate_slide_content(slide: Dict[str, Any], slide_number: int) -> Tuple[bool, List[str]]:
    """
    Validate a single slide's content based on image presence.
   
    Returns:
        (is_valid, list_of_issues)
    """
    issues = []
    has_image = slide.get("image_index") is not None
    content = slide.get("content", [])
   
    # Skip title-only slides
    if slide.get("content_type") == "title" or not content:
        return True, []
   
    char_count = count_characters(content)
    bullet_count = count_bullets(content)
   
    # Detailed logging
    image_label = "WITH" if has_image else "WITHOUT"
   
    if has_image:
        # Slides WITH images: max 400 chars, max 3 bullets
        if char_count > 400:
            issues.append(f"❌ Slide {slide_number} (WITH IMAGE): {char_count} chars (MAX: 400) - EXCEEDS by {char_count - 400}")
        if bullet_count > 3:
            issues.append(f"❌ Slide {slide_number} (WITH IMAGE): {bullet_count} bullets (MAX: 3) - EXCEEDS by {bullet_count - 3}")
       
        # Log validation result
        if not issues:
            print(f"✅ Slide {slide_number} (WITH IMAGE): {char_count} chars, {bullet_count} bullets - VALID")
    else:
        # Slides WITHOUT images: max 650 chars, max 5 bullets
        if char_count < 300:
            issues.append(f"⚠️  Slide {slide_number} (NO IMAGE): {char_count} chars (MIN recommended: 300) - NEEDS {300 - char_count} more chars")
        if char_count > 650:
            issues.append(f"❌ Slide {slide_number} (NO IMAGE): {char_count} chars (MAX: 650) - EXCEEDS by {char_count - 650}")
        if bullet_count < 3:
            issues.append(f"⚠️  Slide {slide_number} (NO IMAGE): {bullet_count} bullets (MIN recommended: 3)")
        if bullet_count > 5:
            issues.append(f"❌ Slide {slide_number} (NO IMAGE): {bullet_count} bullets (MAX: 5) - EXCEEDS by {bullet_count - 5}")
       
        # Log validation result
        if not issues:
            print(f"✅ Slide {slide_number} (NO IMAGE): {char_count} chars, {bullet_count} bullets - VALID")
   
    is_valid = len(issues) == 0
    return is_valid, issues
 
def analyze_slides_json(slides_json_path: str) -> Dict[str, Any]:
    """
    Analyze a slides.json file and report issues.
   
    Args:
        slides_json_path: Path to slides.json file
       
    Returns:
        Analysis report with issues and recommendations
    """
    with open(slides_json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
   
    slides = data.get('slides', [])
   
    report = {
        "total_slides": len(slides),
        "valid_slides": 0,
        "slides_with_issues": [],
        "stats": {
            "with_image": {"count": 0, "avg_chars": 0, "avg_bullets": 0},
            "without_image": {"count": 0, "avg_chars": 0, "avg_bullets": 0}
        }
    }
   
    with_image_chars = []
    with_image_bullets = []
    without_image_chars = []
    without_image_bullets = []
   
    print("\n" + "="*80)
    print("SLIDE CONTENT VALIDATION REPORT")
    print("="*80 + "\n")
   
    for idx, slide in enumerate(slides, 1):
        is_valid, issues = validate_slide_content(slide, idx)
       
        has_image = slide.get("image_index") is not None
        char_count = count_characters(slide.get("content", []))
        bullet_count = count_bullets(slide.get("content", []))
       
        # Track stats
        if has_image:
            report["stats"]["with_image"]["count"] += 1
            with_image_chars.append(char_count)
            with_image_bullets.append(bullet_count)
        else:
            report["stats"]["without_image"]["count"] += 1
            without_image_chars.append(char_count)
            without_image_bullets.append(bullet_count)
       
        if is_valid:
            report["valid_slides"] += 1
            status = "✅ PASS"
        else:
            report["slides_with_issues"].append({
                "slide_number": idx,
                "title": slide.get("title", ""),
                "has_image": has_image,
                "char_count": char_count,
                "bullet_count": bullet_count,
                "issues": issues
            })
            status = "❌ FAIL"
       
        image_label = "[WITH IMAGE]" if has_image else "[NO IMAGE]"
        limits_label = f"(limit: {400 if has_image else 650} chars, {3 if has_image else 7} bullets)"
        print(f"{status} Slide {idx:2d} {image_label}: {char_count:3d} chars, {bullet_count} bullets {limits_label}")
        print(f"         Title: {slide.get('title', 'No title')[:60]}")
       
        for issue in issues:
            print(f"         {issue}")
        print()
   
    # Calculate stats
    if with_image_chars:
        report["stats"]["with_image"]["avg_chars"] = sum(with_image_chars) / len(with_image_chars)
        report["stats"]["with_image"]["avg_bullets"] = sum(with_image_bullets) / len(with_image_bullets)
    if without_image_chars:
        report["stats"]["without_image"]["avg_chars"] = sum(without_image_chars) / len(without_image_chars)
        report["stats"]["without_image"]["avg_bullets"] = sum(without_image_bullets) / len(without_image_bullets)
   
    # Print summary
    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)
    print(f"Total slides: {report['total_slides']}")
    print(f"Valid slides: {report['valid_slides']}")
    print(f"Slides with issues: {len(report['slides_with_issues'])}")
    print()
    print(f"Slides WITH images: {report['stats']['with_image']['count']}")
    print(f"  Avg chars: {report['stats']['with_image']['avg_chars']:.0f} (limit: 400)")
    print(f"  Avg bullets: {report['stats']['with_image']['avg_bullets']:.1f} (limit: 3)")
    print()
    print(f"Slides WITHOUT images: {report['stats']['without_image']['count']}")
    print(f"  Avg chars: {report['stats']['without_image']['avg_chars']:.0f} (limit: 650)")
    print(f"  Avg bullets: {report['stats']['without_image']['avg_bullets']:.1f} (limit: 7)")
    print()
   
    if report['slides_with_issues']:
        print("ISSUES REQUIRING ATTENTION:")
        print("-" * 80)
        for issue_slide in report['slides_with_issues']:
            print(f"Slide {issue_slide['slide_number']}: {issue_slide['title']}")
            for issue in issue_slide['issues']:
                print(f"  {issue}")
            print()
   
    print("="*80 + "\n")
   
    return report
 
def validate_single_slide_real_time(slide: Dict[str, Any], slide_number: int) -> Tuple[bool, str]:
    """
    Real-time validation for a single slide during generation.
   
    This is used by the LLM generation pipeline to validate each slide
    immediately after it's generated, before it's saved.
   
    Args:
        slide: Slide dict from LLM
        slide_number: Slide number (1-indexed)
   
    Returns:
        (is_valid, validation_message)
    """
    has_image = slide.get("image_index") is not None
    content = slide.get("content", [])
   
    # Skip title-only slides
    if slide.get("content_type") == "title" or not content:
        return True, f"Slide {slide_number} (TITLE): Valid - no content enforcement needed"
   
    char_count = count_characters(content)
    bullet_count = count_bullets(content)
   
    violations = []
   
    if has_image:
        if char_count > 400:
            violations.append(f"WITH IMAGE but {char_count} chars (max 400)")
        if bullet_count > 3:
            violations.append(f"WITH IMAGE but {bullet_count} bullets (max 3)")
    else:
        if char_count > 650:
            violations.append(f"NO IMAGE but {char_count} chars (max 650)")
        if bullet_count > 5:
            violations.append(f"NO IMAGE but {bullet_count} bullets (max 5)")
   
    if violations:
        msg = f"❌ Slide {slide_number} VIOLATIONS: {' | '.join(violations)}"
        return False, msg
    else:
        image_label = "WITH IMAGE" if has_image else "NO IMAGE"
        msg = f"✅ Slide {slide_number} ({image_label}): {bullet_count} bullets, {char_count} chars - VALID"
        return True, msg
 
def auto_fix_slide_content(slide: Dict[str, Any], slide_number: int) -> Tuple[bool, List[str]]:
    """
    Automatically fix slide content to comply with limits.
   
    For slides WITH images: enforces max 3 bullets, max 400 chars
    For slides WITHOUT images: enforces max 5 bullets, max 650 chars
   
    Args:
        slide: Slide dict (modified in-place)
        slide_number: Slide number (1-indexed)
   
    Returns:
        (was_modified, list_of_fixes_applied)
    """
    fixes = []
    has_image = slide.get("image_index") is not None
    content = slide.get("content", [])
   
    # Skip title-only slides
    if slide.get("content_type") == "title" or not content:
        return False, fixes
   
    char_count = count_characters(content)
    bullet_count = count_bullets(content)
   
    if has_image:
        max_chars = 400
        max_bullets = 3
    else:
        max_chars = 650
        max_bullets = 5
   
    # Step 1: If too many bullets, truncate to max
    if bullet_count > max_bullets:
        original_bullets = bullet_count
        slide["content"] = slide["content"][:max_bullets]
        fixes.append(f"Reduced bullets from {original_bullets} to {max_bullets}")
        char_count = count_characters(slide["content"])
        bullet_count = max_bullets
   
    # Step 2: If too many characters, truncate at sentence boundary
    if char_count > max_chars:
        original_chars = char_count
        enforced = enforce_content_character_limit(slide["content"], has_image=has_image)
        slide["content"] = enforced
        new_chars = count_characters(enforced)
        fixes.append(f"Reduced characters from {original_chars} to {new_chars} (max {max_chars})")
   
    was_modified = len(fixes) > 0
    return was_modified, fixes
 
def auto_fix_slides_json(slides_json_path: str) -> Dict[str, Any]:
    """
    Automatically fix all slides in slides.json that violate content limits.
   
    Args:
        slides_json_path: Path to slides.json file
       
    Returns:
        Report with all fixes applied
    """
    with open(slides_json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
   
    slides = data.get('slides', [])
   
    report = {
        "total_slides": len(slides),
        "fixed_slides": 0,
        "slides_fixed": [],
        "all_valid": True
    }
   
    print("\n" + "="*80)
    print("AUTO-FIX SLIDES.JSON")
    print("="*80 + "\n")
   
    for idx, slide in enumerate(slides, 1):
        was_modified, fixes = auto_fix_slide_content(slide, idx)
       
        if was_modified:
            report["fixed_slides"] += 1
            report["slides_fixed"].append({
                "slide_number": idx,
                "title": slide.get("title", ""),
                "fixes": fixes
            })
           
            print(f"🔧 Slide {idx}: FIXED")
            print(f"   Title: {slide.get('title', 'No title')[:60]}")
            for fix in fixes:
                print(f"   ✓ {fix}")
            print()
        else:
            # Validate that it's now compliant
            is_valid, issues = validate_slide_content(slide, idx)
            if not is_valid:
                report["all_valid"] = False
                print(f"❌ Slide {idx}: STILL HAS ISSUES")
                for issue in issues:
                    print(f"   {issue}")
                print()
            else:
                has_image = slide.get("image_index") is not None
                char_count = count_characters(slide.get("content", []))
                bullet_count = count_bullets(slide.get("content", []))
                image_label = "WITH IMAGE" if has_image else "NO IMAGE"
                print(f"✅ Slide {idx} ({image_label}): {bullet_count} bullets, {char_count} chars - OK")
   
    # Save the fixed slides.json
    with open(slides_json_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
   
    # Print summary
    print("\n" + "="*80)
    print("AUTO-FIX SUMMARY")
    print("="*80)
    print(f"Total slides: {report['total_slides']}")
    print(f"Fixed slides: {report['fixed_slides']}")
    print(f"All slides compliant: {'✅ YES' if report['all_valid'] else '❌ NO'}")
    print()
   
    if report['slides_fixed']:
        print("SLIDES THAT WERE FIXED:")
        print("-" * 80)
        for fixed_slide in report['slides_fixed']:
            print(f"Slide {fixed_slide['slide_number']}: {fixed_slide['title']}")
            for fix in fixed_slide['fixes']:
                print(f"  • {fix}")
            print()
   
    print(f"✅ Updated slides.json: {slides_json_path}")
    print("="*80 + "\n")
   
    return report
 
if __name__ == "__main__":
 
    import sys
   
    if len(sys.argv) > 1:
        command = sys.argv[1].lower()
        slides_json_path = sys.argv[2] if len(sys.argv) > 2 else "backend/projects/Taxation_images/v1/slides.json"
    else:
        command = "analyze"
        slides_json_path = "backend/projects/Taxation_images/v1/slides.json"
   
    if not Path(slides_json_path).exists():
        print(f"❌ File not found: {slides_json_path}")
        sys.exit(1)
   
    if command == "fix":
        # Auto-fix mode: fix all violations
        report = auto_fix_slides_json(slides_json_path)
    elif command == "analyze":
        # Analysis mode: report issues without fixing
        report = analyze_slides_json(slides_json_path)
    else:
        print(f"❌ Unknown command: {command}")
        print("Usage: python validate_and_rebalance_slides.py [analyze|fix] [path/to/slides.json]")
        sys.exit(1)