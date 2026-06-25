"""
Slides JSON Validator and Auto-Fixer
 
This module provides utilities to:
1. Validate slides.json after LLM generation
2. Automatically fix slides that violate content limits
3. Generate validation reports
4. Integrate with the slide generation pipeline
 
Usage in pipeline:
    from components.slides_json_validator import validate_and_fix_slides_json
   
    # After LLM generates slides.json
    report = validate_and_fix_slides_json(
        slides_json_path="path/to/slides.json",
        auto_fix=True,
        verbose=True
    )
"""
 
import json
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional
from components.validate_and_rebalance_slides import (
    count_characters,
    count_bullets,
    enforce_content_character_limit,
    validate_slide_content
)
 
 
class SlidesJSONValidator:
    """Validator for slides.json files with auto-fix capabilities."""
   
    def __init__(self, slides_json_path: str, verbose: bool = True):
        """
        Initialize validator.
       
        Args:
            slides_json_path: Path to slides.json file
            verbose: Whether to print detailed logs
        """
        self.path = Path(slides_json_path)
        self.verbose = verbose
        self.data = None
        self.slides = []
       
        if not self.path.exists():
            raise FileNotFoundError(f"slides.json not found: {slides_json_path}")
       
        self._load_slides()
   
    def _load_slides(self):
        """Load slides from JSON file."""
        with open(self.path, 'r', encoding='utf-8') as f:
            self.data = json.load(f)
        self.slides = self.data.get('slides', [])
       
        if self.verbose:
            print(f"✅ Loaded {len(self.slides)} slides from: {self.path}")
   
    def _save_slides(self):
        """Save modified slides back to JSON file."""
        with open(self.path, 'w', encoding='utf-8') as f:
            json.dump(self.data, f, indent=2, ensure_ascii=False)
       
        if self.verbose:
            print(f"✅ Saved updated slides.json: {self.path}")
   
    def validate_all(self) -> Dict[str, Any]:
        """
        Validate all slides in JSON.
       
        Returns:
            Report with validation results
        """
        report = {
            "total_slides": len(self.slides),
            "valid_slides": 0,
            "slides_with_violations": [],
            "summary": {
                "with_image": {"count": 0, "violations": 0},
                "without_image": {"count": 0, "violations": 0}
            }
        }
       
        if self.verbose:
            print("\n" + "="*80)
            print("VALIDATING SLIDES.JSON")
            print("="*80 + "\n")
       
        for idx, slide in enumerate(self.slides, 1):
            is_valid, issues = validate_slide_content(slide, idx)
           
            has_image = slide.get("image_index") is not None
            if has_image:
                report["summary"]["with_image"]["count"] += 1
            else:
                report["summary"]["without_image"]["count"] += 1
           
            if is_valid:
                report["valid_slides"] += 1
            else:
                report["summary"]["with_image" if has_image else "without_image"]["violations"] += 1
                report["slides_with_violations"].append({
                    "slide_number": idx,
                    "title": slide.get("title", ""),
                    "has_image": has_image,
                    "issues": issues
                })
       
        if self.verbose:
            self._print_validation_report(report)
       
        return report
   
    def auto_fix_all(self) -> Dict[str, Any]:
        """
        Automatically fix all slides with violations.
       
        Returns:
            Report with all fixes applied
        """
        report = {
            "total_slides": len(self.slides),
            "fixed_slides": 0,
            "slides_fixed": [],
            "all_valid": True
        }
       
        if self.verbose:
            print("\n" + "="*80)
            print("AUTO-FIXING SLIDES.JSON")
            print("="*80 + "\n")
       
        for idx, slide in enumerate(self.slides, 1):
            was_modified, fixes = self._auto_fix_slide(slide, idx)
           
            if was_modified:
                report["fixed_slides"] += 1
                report["slides_fixed"].append({
                    "slide_number": idx,
                    "title": slide.get("title", ""),
                    "fixes": fixes
                })
               
                if self.verbose:
                    print(f"🔧 Slide {idx}: FIXED")
                    print(f"   Title: {slide.get('title', 'No title')[:60]}")
                    for fix in fixes:
                        print(f"   ✓ {fix}")
                    print()
            else:
                # Verify it's now valid
                is_valid, issues = validate_slide_content(slide, idx)
                if not is_valid:
                    report["all_valid"] = False
                    if self.verbose:
                        print(f"⚠️  Slide {idx}: Still has issues after fix attempt")
                        for issue in issues:
                            print(f"   {issue}")
                        print()
       
        # Save fixed slides
        self._save_slides()
       
        if self.verbose:
            self._print_fix_report(report)
       
        return report
   
    def _auto_fix_slide(self, slide: Dict[str, Any], slide_number: int) -> Tuple[bool, List[str]]:
        """
        Auto-fix a single slide's content.
       
        Returns:
            (was_modified, list_of_fixes)
        """
        fixes = []
        has_image = slide.get("image_index") is not None
        content = slide.get("content", [])
       
        # Skip title-only slides
        if slide.get("content_type") == "title" or not content:
            return False, fixes
       
        char_count = count_characters(content)
        bullet_count = count_bullets(content)
       
        max_chars = 400 if has_image else 650
        max_bullets = 3 if has_image else 5
       
        # Step 1: Truncate excess bullets
        if bullet_count > max_bullets:
            original_bullets = bullet_count
            slide["content"] = slide["content"][:max_bullets]
            fixes.append(f"Reduced bullets from {original_bullets} to {max_bullets}")
            char_count = count_characters(slide["content"])
            bullet_count = max_bullets
       
        # Step 2: Truncate excess characters
        if char_count > max_chars:
            original_chars = char_count
            enforced = enforce_content_character_limit(slide["content"], has_image=has_image)
            slide["content"] = enforced
            new_chars = count_characters(enforced)
            fixes.append(f"Reduced characters from {original_chars} to {new_chars} (max {max_chars})")
       
        return len(fixes) > 0, fixes
   
    def _print_validation_report(self, report: Dict[str, Any]):
        """Print detailed validation report."""
        print("="*80)
        print("VALIDATION SUMMARY")
        print("="*80)
        print(f"Total slides: {report['total_slides']}")
        print(f"Valid slides: {report['valid_slides']}")
        print(f"Slides with violations: {len(report['slides_with_violations'])}")
        print()
        print(f"Slides WITH images: {report['summary']['with_image']['count']} (violations: {report['summary']['with_image']['violations']})")
        print(f"Slides WITHOUT images: {report['summary']['without_image']['count']} (violations: {report['summary']['without_image']['violations']})")
        print()
       
        if report['slides_with_violations']:
            print("VIOLATIONS FOUND:")
            print("-" * 80)
            for violation_slide in report['slides_with_violations']:
                print(f"Slide {violation_slide['slide_number']}: {violation_slide['title']}")
                for issue in violation_slide['issues']:
                    print(f"  {issue}")
                print()
       
        print("="*80 + "\n")
   
    def _print_fix_report(self, report: Dict[str, Any]):
        """Print detailed fix report."""
        print("="*80)
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
       
        print("="*80 + "\n")
 
 
def validate_and_fix_slides_json(
    slides_json_path: str,
    auto_fix: bool = True,
    verbose: bool = True
) -> Dict[str, Any]:
    """
    Validate slides.json and optionally auto-fix violations.
   
    This is the main entry point for the pipeline.
   
    Args:
        slides_json_path: Path to slides.json file
        auto_fix: Whether to auto-fix violations (default: True)
        verbose: Whether to print detailed logs (default: True)
   
    Returns:
        Report with validation/fix results
   
    Example:
        >>> report = validate_and_fix_slides_json("path/to/slides.json", auto_fix=True)
        >>> print(f"Fixed {report['fixed_slides']} slides")
    """
    validator = SlidesJSONValidator(slides_json_path, verbose=verbose)
   
    if auto_fix:
        return validator.auto_fix_all()
    else:
        return validator.validate_all()
 
 
if __name__ == "__main__":
    import sys
   
    if len(sys.argv) < 2:
        print("Usage: python slides_json_validator.py <slides.json_path> [--fix]")
        print("\nExamples:")
        print("  # Validate only (report violations)")
        print("  python slides_json_validator.py backend/projects/Taxation_images/v1/slides.json")
        print("\n  # Validate and auto-fix")
        print("  python slides_json_validator.py backend/projects/Taxation_images/v1/slides.json --fix")
        sys.exit(1)
   
    slides_json_path = sys.argv[1]
    auto_fix = "--fix" in sys.argv
   
    try:
        report = validate_and_fix_slides_json(slides_json_path, auto_fix=auto_fix, verbose=True)
    except FileNotFoundError as e:
        print(f"❌ {e}")
        sys.exit(1)