import os
import re
from pathlib import Path
from fastapi import APIRouter, HTTPException, UploadFile, File
from fastapi.responses import JSONResponse
from config import get_pdf_workspace, get_latest_project_version, parse_versioned_basename

router = APIRouter(prefix="/api/preview", tags=["preview"])

def natural_key(filename: str):
    """
    Extract numbers for natural sorting:
    'Slide10.JPG' -> ['Slide', 10, '.JPG']
    """
    return [
        int(text) if text.isdigit() else text.lower()
        for text in re.split(r"(\d+)", filename)
    ]

@router.get("/slides/{basename}")
def list_slide_images(basename: str):
    latest = get_latest_project_version(basename)
    if latest:
        basename = latest

    paths = get_pdf_workspace(basename)
    slides_dir = paths["slides_images_folder"]

    if not slides_dir.exists():
        raise HTTPException(404, "slides_images folder not found")

    images = [
        p.name
        for p in slides_dir.iterdir()
        if p.suffix.lower() in (".jpg", ".jpeg", ".png")
    ]

    # ✅ NATURAL SORT HERE
    images.sort(key=natural_key)

    slide_urls = [
        f"/{(slides_dir / img).as_posix()}"
        for img in images
    ]

    return JSONResponse(
        content={
            "slides": slide_urls,
            "slides_count": len(slide_urls)
        },
        headers={"Cache-Control": "no-store"},
    )


@router.get("/extracted/{basename}")
def list_extracted_images(basename: str):
    """
    List images extracted from the original document (extracted_images_docx/<basename>).
    """
    # Try multiple candidate folders to handle versioned/unversioned basenames.
    candidates = [basename]
    base_name, version_dir = parse_versioned_basename(basename)
    if version_dir:
        candidates.extend([
            os.path.join(base_name, version_dir),
            base_name
        ])

    extracted_dir = None
    actual_folder_name = None
    for cand in candidates:
        p = Path("extracted_images_docx") / cand
        if p.exists():
            extracted_dir = p
            actual_folder_name = cand
            break

    if extracted_dir is None:
        raise HTTPException(404, "extracted_images_docx folder not found")

    images = [
        p.name
        for p in extracted_dir.iterdir()
        if p.suffix.lower() in (".jpg", ".jpeg", ".png")
    ]

    images.sort(key=natural_key)

    # Return URLs pointing to the actual folder where images exist
    actual_folder_url = actual_folder_name.replace(os.sep, "/")
    image_urls = [f"/extracted_images_docx/{actual_folder_url}/{img}" for img in images]

    return JSONResponse(
        content={
            "slides": image_urls,
            "slides_count": len(image_urls),
        },
        headers={"Cache-Control": "no-store"},
    )


@router.post("/extracted/{basename}/upload")
async def upload_extracted_image(basename: str, file: UploadFile = File(...)):
    """
    Upload an image to `extracted_images_docx/<basename>/`.
    Returns the saved filename and URL.
    """
    # Try multiple candidate folders to handle versioned/unversioned basenames.
    candidates = [basename]
    base_name, version_dir = parse_versioned_basename(basename)
    if version_dir:
        candidates.extend([
            os.path.join(base_name, version_dir),
            base_name
        ])

    extracted_dir = None
    actual_folder_name = None
    for cand in candidates:
        p = Path("extracted_images_docx") / cand
        if p.exists():
            extracted_dir = p
            actual_folder_name = cand
            break

    # If no existing folder found, create under the versioned project folder if applicable.
    if extracted_dir is None:
        actual_folder_name = os.path.join(base_name, version_dir) if version_dir else basename
        extracted_dir = Path("extracted_images_docx") / actual_folder_name
        extracted_dir.mkdir(parents=True, exist_ok=True)

    # Ensure unique filename
    dest = extracted_dir / file.filename
    if dest.exists():
        stem = dest.stem
        suffix = dest.suffix
        i = 1
        while True:
            candidate = extracted_dir / f"{stem}_{i}{suffix}"
            if not candidate.exists():
                dest = candidate
                break
            i += 1

    try:
        with dest.open("wb") as f:
            content = await file.read()
            f.write(content)
    finally:
        await file.close()

    actual_folder_url = actual_folder_name.replace(os.sep, "/")
    url = f"/extracted_images_docx/{actual_folder_url}/{dest.name}"
    return {"status": "success", "file": url, "filename": dest.name}

@router.get("/audio/{basename}")
def list_slide_audio(basename: str):
    paths = get_pdf_workspace(basename)
    audio_dir = paths["audio_folder"]

    if not audio_dir.exists():
        return {"audio": {}}

    audio_map = {}
    for p in audio_dir.iterdir():
        if p.suffix.lower() == ".mp3":
            # extract slide number safely
            match = re.search(r"(\d+)", p.stem)
            if match:
                audio_map[match.group(1)] = f"/{p.as_posix()}"

    return {"audio": audio_map}