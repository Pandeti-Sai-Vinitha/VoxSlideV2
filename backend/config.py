"""
Application configuration and folder structure management.
"""
import os
import re
from pathlib import Path
from datetime import datetime

# Base directories
BASE_DIR = Path(__file__).parent.resolve()
UPLOADS_DIR = BASE_DIR / "uploads"
OUTPUTS_DIR = BASE_DIR / "outputs"
LOGS_DIR = BASE_DIR / "logs"
CACHE_DIR = BASE_DIR / "cache"
EXTRACTED_IMAGES_DIR = BASE_DIR / "extracted_images_docx"
PROJECTS_DIR = BASE_DIR / "projects"

VERSIONED_BASENAME_PATTERN = re.compile(r'^(.+)_v(\d+)$')

# Ensure base directories exist
UPLOADS_DIR.mkdir(exist_ok=True)
OUTPUTS_DIR.mkdir(exist_ok=True)
LOGS_DIR.mkdir(exist_ok=True)
CACHE_DIR.mkdir(exist_ok=True)
EXTRACTED_IMAGES_DIR.mkdir(exist_ok=True)
PROJECTS_DIR.mkdir(exist_ok=True)


def parse_versioned_basename(pdf_basename: str) -> tuple[str, str | None]:
    """
    Parse a versioned basename like "Project_v2".

    Returns:
        (base_name, version_dir) where version_dir is something like "v2".
        If not versioned, returns (pdf_basename, None).
    """
    match = VERSIONED_BASENAME_PATTERN.match(pdf_basename)
    if match:
        return match.group(1), f"v{match.group(2)}"
    return pdf_basename, None


def get_latest_project_version(pdf_basename: str) -> str | None:
    """
    If a non-versioned basename has generated outputs in `projects/{basename}/vN/`,
    return the highest versioned basename string.

    Example: "Proposal" -> "Proposal_v3" if projects/Proposal/v3 exists.
    """
    base_name, version_dir = parse_versioned_basename(pdf_basename)
    if version_dir:
        return pdf_basename

    project_root = Path("projects") / base_name
    if not project_root.exists() or not project_root.is_dir():
        return None

    latest_version = 0
    for child in project_root.iterdir():
        if child.is_dir() and child.name.startswith("v"):
            suffix = child.name[1:]
            if suffix.isdigit():
                latest_version = max(latest_version, int(suffix))

    if latest_version == 0:
        return None

    return f"{base_name}_v{latest_version}"


def get_pdf_workspace(pdf_basename: str) -> dict:
    """
    Get folder structure for a specific PDF.
    
    Args:
        pdf_basename: PDF name without extension (e.g., 'Sample')
    
    Returns:
        dict: Paths for all required folders
    """
    base_name, version_dir = parse_versioned_basename(pdf_basename)
    if version_dir:
        return get_versioned_pdf_workspace(pdf_basename, version_dir)

    # Create unique folder for this PDF
    pdf_folder = OUTPUTS_DIR / pdf_basename
    
    paths = {
        "pdf_folder": pdf_folder,
        "audio_folder": pdf_folder / "audio",
        "slides_images_folder": pdf_folder / "slides_images",
        "ppt_file": pdf_folder / f"{pdf_basename}.pptx",
        "video_file": pdf_folder / f"{pdf_basename}.mp4",
        "slides_json": pdf_folder / "slides.json",
        "log_file": LOGS_DIR / f"{pdf_basename}.log",
        "cache_file": CACHE_DIR / f"{pdf_basename}_llm.json",
    }
    
    # Create all directories
    for key, path in paths.items():
        if key not in ["ppt_file", "video_file", "slides_json", "log_file", "cache_file"]:
            Path(path).mkdir(parents=True, exist_ok=True)
    
    return paths


def get_versioned_pdf_workspace(pdf_basename: str, version_dir: str = None) -> dict:
    """
    Get folder structure for a versioned PDF.
    
    Args:
        pdf_basename: PDF name in format "basename_v1", "basename_v2", etc.
        version_dir: Version directory like "v1", "v2", etc. If None, parses from basename.
    
    Returns:
        dict: Paths for all required folders in versioned structure (projects/basename/v1/)
    """
    if not version_dir:
        base_name, version_dir = parse_versioned_basename(pdf_basename)
        if not version_dir:
            return get_pdf_workspace(pdf_basename)

    # Parse basename like "Project_v2" -> base_name = "Project"
    match = VERSIONED_BASENAME_PATTERN.match(pdf_basename)
    if match:
        base_name = match.group(1)
    else:
        base_name = pdf_basename
    
    # Create versioned folder: projects/base_name/v2/
    pdf_folder = Path("projects") / base_name / version_dir
    
    paths = {
        "pdf_folder": pdf_folder,
        "audio_folder": pdf_folder / "audio",
        "slides_images_folder": pdf_folder / "slides_images",
        "ppt_file": pdf_folder / f"{pdf_basename}.pptx",
        "video_file": pdf_folder / f"{pdf_basename}.mp4",
        "slides_json": pdf_folder / "slides.json",
        "log_file": LOGS_DIR / f"{pdf_basename}.log",
        "cache_file": CACHE_DIR / f"{pdf_basename}_llm.json",
    }
    
    # Create all directories
    for key, path in paths.items():
        if key not in ["ppt_file", "video_file", "slides_json", "log_file", "cache_file"]:
            Path(path).mkdir(parents=True, exist_ok=True)
    

    return paths

def get_next_versioned_basename(pdf_basename: str) -> str:
    """Return the next versioned basename for a document.

    If the incoming basename is already versioned, it is returned unchanged.
    Otherwise this returns the next available version under projects/{base_name}/.
    Example: "Proposal" -> "Proposal_v1" or "Proposal_v2" if v1 already exists.
    """
    base_name, version_dir = parse_versioned_basename(pdf_basename)
    if version_dir:
        return pdf_basename

    project_folder = Path("projects") / base_name
    max_version = 0
    if project_folder.exists():
        for item in project_folder.iterdir():
            if item.is_dir() and item.name.startswith("v"):
                try:
                    version_num = int(item.name[1:])
                    max_version = max(max_version, version_num)
                except ValueError:
                    continue

    return f"{base_name}_v{max_version + 1}"