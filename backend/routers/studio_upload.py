from fastapi import APIRouter, UploadFile, File, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import os
import logging
import json
from pathlib import Path

# Import extraction and analysis functions
from components.extractor import extract_structured_blocks_from_pdf, extract_structured_blocks_from_docx, parse_versioned_basename
from components.document_analyzer import DocumentAnalyzer, DocumentBlock as AnalyzerBlock
from config import PROJECTS_DIR, EXTRACTED_IMAGES_DIR, OUTPUTS_DIR, UPLOADS_DIR

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/studio", tags=["studio-upload"])

# Project folder for extracted content
PROJECTS_FOLDER = PROJECTS_DIR
PROJECTS_FOLDER.mkdir(exist_ok=True)

# ─── Models ───────────────────────────────────────────────────────────────────

class DocBlock(BaseModel):
    id: str
    type: str  # 'h1', 'h2', 'paragraph', 'image'
    content: Optional[str] = ""
    imageUrl: Optional[str] = None


class ExtractedContent(BaseModel):
    blocks: List[DocBlock]
    images: List[str]
    filename: str
    filesize: int
    extraction_status: str


# ─── Routes ───────────────────────────────────────────────────────────────────

@router.post("/upload", response_model=ExtractedContent)
async def upload_and_extract(file: UploadFile = File(...)):

    allowed_extensions = {'.pdf', '.docx', '.doc'}
    file_extension = os.path.splitext(file.filename)[1].lower()

    if file_extension not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail="Invalid file type. Only PDF and DOCX files are supported."
        )

    import tempfile
    temp_file_path = str(Path(tempfile.gettempdir()) / file.filename)

    try:
        contents = await file.read()
        file_size = len(contents)

        with open(temp_file_path, "wb") as f:
            f.write(contents)

        base_filename = os.path.splitext(file.filename)[0]
        base_name, version_dir = parse_versioned_basename(base_filename)
        
        # ✅ Create extracted images folder in correct versioned location
        extracted_images_folder = EXTRACTED_IMAGES_DIR / base_name
        if version_dir:
            extracted_images_folder = extracted_images_folder / version_dir
        extracted_images_folder.mkdir(exist_ok=True, parents=True)

        # ✅ Extract blocks + images
        if file_extension == '.pdf':
            extracted_blocks, image_paths = extract_structured_blocks_from_pdf(
                temp_file_path,
                images_folder=str(extracted_images_folder)
            )
        else:
            extracted_blocks, image_paths = extract_structured_blocks_from_docx(
                temp_file_path,
                images_folder=str(extracted_images_folder)
            )

        logger.info(f"✅ Extracted {len(image_paths)} images")

        # ✅ Normalize image paths for frontend URLs
        backend_root = Path(__file__).resolve().parent.parent  # Go up to backend/ from routers/
        image_paths = [str(Path(p).resolve().relative_to(backend_root).as_posix()) for p in image_paths]

        # Analyzer
        analyzer = DocumentAnalyzer()
        analyzed_blocks, hierarchy = analyzer.analyze(extracted_blocks)

        doc_blocks = _convert_to_simple_blocks(analyzed_blocks)

        # ✅ Inject images into correct positions
        doc_blocks = _merge_blocks_with_images(doc_blocks, image_paths)

        if not doc_blocks:
            raise HTTPException(
                status_code=400,
                detail="Could not extract any meaningful content from the document."
            )

        hierarchical_blocks = _create_hierarchical_structure(doc_blocks)

        # ✅ Create project folder in versioned location
        project_folder = PROJECTS_FOLDER / base_name
        if version_dir:
            project_folder = project_folder / version_dir
        project_folder.mkdir(exist_ok=True, parents=True)

        output_filename = "stage1.json"
        output_path = project_folder / output_filename

        # ✅ SAVE IMAGES ALSO
        extracted_content = {
            "filename": file.filename,
            "filesize": file_size,
            "extraction_status": "success",
            "blocks": hierarchical_blocks,
            "images": image_paths   # ✅ NEW
        }

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(extracted_content, f, indent=2, ensure_ascii=False)

        logger.info(f"✅ Saved extracted content to {output_path}")

        # ✅ RETURN IMAGES ALSO
        return ExtractedContent(
            blocks=doc_blocks,
            images=image_paths,
            filename=file.filename,
            filesize=file_size,
            extraction_status="success"
        )


    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error processing file: {str(e)}"
        )

    finally:
        if os.path.exists(temp_file_path):
            try:
                os.remove(temp_file_path)
            except:
                pass

@router.post("/parse-text", response_model=List[DocBlock])
async def parse_text_content(content: dict):
    """
    Parse plain text content into structured blocks
    
    Request body:
        {
            "text": "Your content here..."
        }
    
    Returns:
        List of DocBlock objects
    """
    try:
        text = content.get("text", "").strip()
        
        if not text:
            raise HTTPException(status_code=400, detail="No text content provided")
        
        # Create blocks from text
        doc_blocks = _parse_text_to_blocks(text)
        
        return doc_blocks
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error parsing content: {str(e)}"
        )

@router.post("/update-blocks")
async def update_document_blocks(blocks: List[DocBlock]):
    """
    Update and validate document blocks
    
    Request body:
        [
            {
                "id": "b1",
                "type": "h1",
                "content": "Updated content"
            }
        ]
    
    Returns:
        Updated blocks with validation
    """
    try:
        if not blocks:
            raise HTTPException(status_code=400, detail="No blocks provided")
        
        # Validate block structure
        for block in blocks:
            if block.type not in ["h1", "h2", "paragraph"]:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid block type: {block.type}. Must be h1, h2, or paragraph."
                )
            if not block.content.strip():
                raise HTTPException(
                    status_code=400,
                    detail="Block content cannot be empty"
                )
        
        # Return validated blocks
        return {
            "status": "success",
            "blocks": blocks,
            "block_count": len(blocks)
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error updating blocks: {str(e)}"
        )

# ─── Helper Functions ─────────────────────────────────────────────────────────

def _create_hierarchical_structure(blocks: List[DocBlock]) -> List[Dict[str, Any]]:
    """
    Create hierarchical JSON structure where headings contain their body content
    
    Example:
        Input: [h1 "Title", paragraph "Body 1", h2 "Subtitle", paragraph "Body 2"]
        Output:
        [
            {
                "id": "b0",
                "type": "h1",
                "content": "Title",
                "children": [
                    {"id": "b1", "type": "paragraph", "content": "Body 1"},
                    {
                        "id": "b2",
                        "type": "h2",
                        "content": "Subtitle",
                        "children": [
                            {"id": "b3", "type": "paragraph", "content": "Body 2"}
                        ]
                    }
                ]
            }
        ]
    """
    result = []
    stack = []  # Stack to track heading hierarchy: [(heading_level, block, children_list)]
    
    for block in blocks:
        block_dict = {
            "id": block.id,
            "type": block.type,
            "content": block.content
        }
        
        if block.type == "paragraph":
            # Add paragraph to current context
            if stack:
                # Add to the last heading's children
                if "children" not in stack[-1][2]:
                    stack[-1][2]["children"] = []
                stack[-1][2]["children"].append(block_dict)
            else:
                # No heading context, add to root
                result.append(block_dict)
        else:
            # This is a heading (h1 or h2)
            heading_level = 1 if block.type == "h1" else 2
            block_dict["children"] = []
            
            # Pop stack until we find appropriate parent
            while stack and stack[-1][0] >= heading_level:
                stack.pop()
            
            if stack:
                # Add as child of current heading
                if "children" not in stack[-1][2]:
                    stack[-1][2]["children"] = []
                stack[-1][2]["children"].append(block_dict)
            else:
                # Add to root
                result.append(block_dict)
            
            # Push to stack
            stack.append((heading_level, block, block_dict))
    
    return result

def _convert_to_simple_blocks(analyzer_blocks: List[AnalyzerBlock]) -> List[DocBlock]:
    """
    Convert DocumentAnalyzer blocks to simple DocBlock format for frontend
    
    Maps heading levels to h1/h2, and everything else to paragraph.
    Since the analyzer now uses intelligent font-size detection, this is mostly
    a direct mapping with minimal additional heuristics.
    """
    import re
    
    simple_blocks = []
    
    for block in analyzer_blocks:
        if not block.text.strip():
            continue
            
        block_type = "paragraph"
        text = block.text.strip()
        
        # Primary: Use explicit heading level from analyzer
        if block.heading_level:
            # Handle both Enum and string representations
            if hasattr(block.heading_level, 'name'):
                # It's an Enum
                heading_name = block.heading_level.name
            else:
                # It's a string
                heading_name = str(block.heading_level)
            
            # Map heading levels: H1 → h1, H2/H3/H4 → h2, else → paragraph
            if heading_name in ["H1", "1"]:
                block_type = "h1"
            elif heading_name in ["H2", "H3", "H4", "2", "3", "4"]:
                block_type = "h2"
        
        # Fallback: If no heading detected but text matches common patterns
        if block_type == "paragraph":
            # Pattern 1: All caps short text → h1
            if text.isupper() and len(text) < 80 and len(text.split()) >= 1:
                block_type = "h1"
            # Pattern 2: Numbered chapter/section patterns → h1
            elif re.match(r'^(Chapter|Part|Section|Introduction|Conclusion|Summary)\s+\d+', text, re.IGNORECASE):
                block_type = "h1"
            elif re.match(r'^(US\s+)?[A-Z][a-z]+\s+[A-Z][a-z]+:', text):
                # Pattern like "US Fund Taxation:" → h1
                block_type = "h1"
            # Pattern 3: Bold + colon pattern (like "Flow-Through Tax Treatment.") → h2
            elif (block.is_bold and len(text) < 100 and 
                  (text.endswith(':') or text.endswith('.'))):
                block_type = "h2"
            # Pattern 4: Title case with high cap ratio → h2
            elif len(text) < 100 and len(text.split()) >= 2:
                word_count = len(text.split())
                cap_words = sum(1 for word in text.split() if word and word[0].isupper())
                if word_count > 0 and cap_words / word_count > 0.65:
                    block_type = "h2"
        
        simple_blocks.append(DocBlock(
            id=f"b{len(simple_blocks)}",
            type=block_type,
            content=text
        ))
    
    return simple_blocks

def _parse_text_to_blocks(text: str) -> List[DocBlock]:
    """
    Parse plain text into blocks by detecting headings and paragraphs
    
    Heading detection heuristics:
    - ALL CAPS short lines → h1
    - Numbered patterns (1., 1.1, Chapter 1:) → h1
    - Title case short lines with majority capitalized words → h2
    """
    import re
    
    lines = text.split('\n')
    blocks = []
    block_index = 0
    current_paragraph = ""
    
    for line in lines:
        line = line.strip()
        
        # Skip empty lines but preserve paragraph boundaries
        if not line:
            if current_paragraph.strip():
                blocks.append(DocBlock(
                    id=f"b{block_index}",
                    type="paragraph",
                    content=current_paragraph.strip()
                ))
                block_index += 1
                current_paragraph = ""
            continue
        
        # Detect heading patterns
        heading_type = None
        line_length = len(line)
        word_count = len(line.split())
        
        # Pattern 1: ALL CAPS short lines (typical h1 pattern)
        if line_length < 80 and line.isupper() and word_count >= 1:
            heading_type = "h1"
        
        # Pattern 2: Numbered/Chapter patterns (h1)
        elif re.match(r'^(Chapter|Part|Section|Introduction|Conclusion|Summary|Appendix)\s+\d+', line, re.IGNORECASE):
            heading_type = "h1"
        elif re.match(r'^(\d+\.|Week\s+\d+:|Lesson\s+\d+:|Unit\s+\d+:)', line):
            heading_type = "h1"
        
        # Pattern 3: Title case short lines - mostly capitalized words (h2)
        elif line_length < 100 and word_count >= 2:
            # Count words that start with capital letter
            title_words = sum(1 for word in line.split() if word and word[0].isupper())
            title_ratio = title_words / word_count
            
            # If most words are capitalized, it's likely a heading
            if title_ratio > 0.6:
                heading_type = "h2"
        
        # Pattern 4: Numbered subheadings (h2)
        if not heading_type and re.match(r'^\d+\.\d*\s+', line) and line_length < 100:
            heading_type = "h2"
        
        if heading_type:
            # Save current paragraph if exists
            if current_paragraph.strip():
                blocks.append(DocBlock(
                    id=f"b{block_index}",
                    type="paragraph",
                    content=current_paragraph.strip()
                ))
                block_index += 1
                current_paragraph = ""
            
            # Add heading
            blocks.append(DocBlock(
                id=f"b{block_index}",
                type=heading_type,
                content=line
            ))
            block_index += 1
        else:
            # Accumulate paragraph lines
            if current_paragraph:
                current_paragraph += " " + line
            else:
                current_paragraph = line
    
    # Add final paragraph if exists
    if current_paragraph.strip():
        blocks.append(DocBlock(
            id=f"b{block_index}",
            type="paragraph",
            content=current_paragraph.strip()
        ))
    
    return blocks

def _merge_blocks_with_images(blocks: List[DocBlock], image_paths: List[str]) -> List[DocBlock]:
    """
    Merge images into text blocks in approximate document order
    """

    if not image_paths:
        return blocks

    merged = []
    total_blocks = len(blocks)
    total_images = len(image_paths)

    # Calculate spacing
    step = max(1, total_blocks // (total_images + 1))

    img_index = 0

    for i, block in enumerate(blocks):
        merged.append(block)

        # Insert image at intervals
        if img_index < total_images and (i + 1) % step == 0:
            merged.append(DocBlock(
                id=f"img_{img_index}",
                type="image",
                content="",
                imageUrl=image_paths[img_index]
            ))
            img_index += 1

    # Append remaining images (if any)
    while img_index < total_images:
        merged.append(DocBlock(
            id=f"img_{img_index}",
            type="image",
            content="",
            imageUrl=image_paths[img_index]
        ))
        img_index += 1

    return merged
@router.get("/content/{basename}")
async def get_extracted_content(basename: str):
    from config import parse_versioned_basename
    import tempfile
    from components.extractor import extract_structured_blocks_from_pdf, extract_structured_blocks_from_docx

    # Try staged extraction content from the studio projects folder first.
    # This is where extracted content is saved during document upload/extraction.
    base_name, version_dir = parse_versioned_basename(basename)
    candidate_paths = []

    if version_dir:
        # If basename has version like "Taxation (1)_v1", try that specific version first
        candidate_paths.append(PROJECTS_FOLDER / base_name / version_dir / "stage1.json")
    else:
        # If basename has no version like "Taxation (1)", try:
        # 1. The base folder (for new uploads)
        candidate_paths.append(PROJECTS_FOLDER / basename / "stage1.json")
        
        # 2. All versioned subfolders in reverse order (latest first)
        # This handles reconfigure on older versions
        project_base = PROJECTS_FOLDER / basename
        if project_base.exists():
            version_folders = sorted(
                [d for d in project_base.iterdir() if d.is_dir() and d.name.startswith('v')],
                key=lambda d: int(d.name[1:]) if d.name[1:].isdigit() else 0,
                reverse=True
            )
            for version_folder in version_folders:
                candidate_paths.append(version_folder / "stage1.json")

    # Fallback to outputs folder for older or alternate workflows.
    candidate_paths.append(OUTPUTS_DIR / basename / "stage1.json")

    file_path = None
    for candidate in candidate_paths:
        if candidate.exists():
            file_path = candidate
            break

    # If no stage1.json found, try to auto-extract from the original file in uploads
    if not file_path:
        original_pdf = UPLOADS_DIR / f"{base_name}.pdf"
        original_docx = UPLOADS_DIR / f"{base_name}.docx"
        
        if original_pdf.exists():
            original_file = original_pdf
        elif original_docx.exists():
            original_file = original_docx
        else:
            raise HTTPException(
                status_code=404,
                detail=f"Extracted content and original file not found for: {basename}"
            )

        # Auto-extract from original file
        try:
            logger.info(f"🔄 Auto-extracting content from {original_file}")
            
            extracted_images_folder = EXTRACTED_IMAGES_DIR / base_name
            if version_dir:
                extracted_images_folder = extracted_images_folder / version_dir
            extracted_images_folder.mkdir(exist_ok=True, parents=True)

            if original_file.suffix.lower() == '.pdf':
                extracted_blocks, image_paths = extract_structured_blocks_from_pdf(
                    str(original_file),
                    images_folder=str(extracted_images_folder)
                )
            else:
                extracted_blocks, image_paths = extract_structured_blocks_from_docx(
                    str(original_file),
                    images_folder=str(extracted_images_folder)
                )

            # Normalize image paths
            backend_root = Path(__file__).resolve().parent.parent
            image_paths = [str(Path(p).resolve().relative_to(backend_root).as_posix()) for p in image_paths]

            # Analyze blocks
            analyzer = DocumentAnalyzer()
            analyzed_blocks, hierarchy = analyzer.analyze(extracted_blocks)

            doc_blocks = _convert_to_simple_blocks(analyzed_blocks)
            doc_blocks = _merge_blocks_with_images(doc_blocks, image_paths)

            hierarchical_blocks = _create_hierarchical_structure(doc_blocks)

            # Save to cache for future use
            project_folder = PROJECTS_FOLDER / base_name
            if version_dir:
                project_folder = project_folder / version_dir
            project_folder.mkdir(exist_ok=True, parents=True)

            cache_path = project_folder / "stage1.json"
            cache_data = {
                "filename": original_file.name,
                "extraction_status": "auto-extracted",
                "blocks": hierarchical_blocks,
                "images": image_paths
            }
            
            with open(cache_path, "w", encoding="utf-8") as f:
                json.dump(cache_data, f, indent=2, ensure_ascii=False)
            
            logger.info(f"✅ Auto-extracted and cached content at {cache_path}")

            return {
                "blocks": doc_blocks,
                "images": image_paths
            }

        except Exception as e:
            logger.error(f"❌ Failed to auto-extract: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to extract content from original file: {str(e)}"
            )

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        return {
            "blocks": data.get("blocks", []),
            "images": data.get("images", [])
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to load content: {str(e)}"
        )