import os
import shutil
import re
from fastapi import APIRouter, HTTPException, status, Depends
from sqlalchemy.orm import Session
from db import models
from db.database import get_db
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/delete", tags=["delete"])

VERSIONED_BASENAME_PATTERN = re.compile(r'^(.+)_v(\d+)$')

def extract_base_project_name(basename: str) -> str:
    """
    Extract the base project name by removing version suffix.
    
    Example:
        'Taxation_images_v1' -> 'Taxation_images'
        'Taxation_images' -> 'Taxation_images'
    """
    match = VERSIONED_BASENAME_PATTERN.match(basename)
    return match.group(1) if match else basename


def close_log_handlers(log_path: str) -> None:
    """
    Close all file handlers that are using the specified log file.
    This allows the file to be deleted without "file in use" errors.
    """
    abs_log_path = os.path.abspath(log_path)
    
    # Close handlers in all registered loggers
    for logger_name in list(logging.root.manager.loggerDict):
        try:
            log_obj = logging.getLogger(logger_name)
            for handler in list(getattr(log_obj, 'handlers', [])):
                try:
                    if hasattr(handler, 'baseFilename'):
                        if os.path.abspath(handler.baseFilename) == abs_log_path:
                            handler.close()
                            log_obj.removeHandler(handler)
                except Exception as e:
                    logger.debug(f"Failed to close handler: {e}")
        except Exception as e:
            logger.debug(f"Failed to process logger {logger_name}: {e}")
    
    # Also check root logger
    try:
        for handler in list(logging.root.handlers):
            if hasattr(handler, 'baseFilename'):
                if os.path.abspath(handler.baseFilename) == abs_log_path:
                    handler.close()
                    logging.root.removeHandler(handler)
    except Exception as e:
        logger.debug(f"Failed to close root logger handler: {e}")


def safe_delete_file(file_path: str, description: str) -> bool:
    """
    Safely delete a file with error handling and logging.
    
    Returns:
        True if deleted, False if not found or error
    """
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
            logger.info(f"✅ Deleted {description}: {file_path}")
            return True
        else:
            logger.debug(f"⚠️  {description} not found: {file_path}")
            return False
    except Exception as e:
        logger.warning(f"❌ Failed to delete {description}: {file_path} - {str(e)}")
        return False


def safe_delete_directory(dir_path: str, description: str) -> bool:
    """
    Safely delete a directory with error handling and logging.
    
    Returns:
        True if deleted, False if not found or error
    """
    try:
        if os.path.exists(dir_path):
            shutil.rmtree(dir_path)
            logger.info(f"✅ Deleted {description}: {dir_path}")
            return True
        else:
            logger.debug(f"⚠️  {description} not found: {dir_path}")
            return False
    except Exception as e:
        logger.warning(f"❌ Failed to delete {description}: {dir_path} - {str(e)}")
        return False


@router.delete("/{doc_id}", status_code=204)
def delete_document(doc_id: str, db: Session = Depends(get_db)):
    """
    Delete a document and ALL its project versions from the database.
    
    When deleting a document (e.g., Taxation_images_v1), also deletes:
    - All other versions of the same project (Taxation_images_v2, v3, etc.)
    - Database records for all versions
    - All associated files and folders
    
    Cleans up:
    - Database records for all versions
    - Uploaded files for all versions
    - Cache files
    - Generated outputs (PPT, video, audio, images, slides.json) for all versions
    - Extracted images (from DOCX) for all versions
    - Project versioned folders (projects/base_name/v1, v2, etc.)
    - Log files for all versions
    """
    doc = db.query(models.Document).filter(models.Document.id == doc_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    logger.info(f"Deleting document: {doc_id} ({doc.name})")
    
    # Extract base project name (remove _vX suffix if present)
    basename = doc.basename or os.path.splitext(doc.name)[0]
    base_project_name = extract_base_project_name(basename)
    
    logger.info(f"Base project name: {base_project_name}")
    logger.info(f"Document basename: {basename}")
    
    if not base_project_name:
        logger.error(f"Cannot determine base project name for document {doc_id}")
        raise HTTPException(status_code=400, detail="Invalid document name")
    
    try:
        # ✅ 1. Find all documents of this project (all versions)
        related_docs = db.query(models.Document).filter(
            models.Document.basename.like(f"{base_project_name}%")
        ).all()
        
        logger.info(f"Found {len(related_docs)} version(s) to delete for project: {base_project_name}")
        
        # ✅ 2. Delete all related documents from database
        for related_doc in related_docs:
            logger.info(f"  - Deleting DB record: {related_doc.basename or related_doc.name}")
            db.delete(related_doc)
        
        db.commit()
        logger.info(f"  ✓ Removed {len(related_docs)} record(s) from database")
        
        # ✅ 3. Delete all uploaded files and associated data for each basename
        for related_doc in related_docs:
            bn = related_doc.basename or os.path.splitext(related_doc.name)[0]
            logger.info(f"Cleaning up files for: {bn}")

            # Delete uploaded file(s) for this version
            if related_doc.name:
                uploads_path = os.path.join("uploads", related_doc.name)
                safe_delete_file(uploads_path, f"Uploaded file for {bn}")

            # Delete cache files for this version
            cache_files = [
                f"cache/{bn}_llm.json",
                f"cache/{bn}.json",
                f"cache/{bn}_llm_persona.json",
            ]
            for cache_file in cache_files:
                safe_delete_file(cache_file, f"Cache file ({bn})")

            # Delete outputs folder for this version
            outputs_path = os.path.join("outputs", bn)
            safe_delete_directory(outputs_path, f"Outputs folder ({bn})")

            # Delete log file for this version
            logs_path = os.path.join("logs", f"{bn}.log")
            close_log_handlers(logs_path)
            safe_delete_file(logs_path, f"Log file ({bn})")

        # Remove any remaining shared / project-level files by base project name
        for upload_file in Path("uploads").glob(f"{base_project_name}*"):
            safe_delete_file(str(upload_file), f"Uploaded file ({upload_file.name})")

        for cache_file in Path("cache").glob(f"{base_project_name}*"):
            safe_delete_file(str(cache_file), f"Cache file ({cache_file.name})")

        for log_file in Path("logs").glob(f"{base_project_name}*.log"):
            close_log_handlers(str(log_file))
            safe_delete_file(str(log_file), f"Log file ({log_file.name})")

        # Delete extracted images folder for the base project
        extracted_images_path = os.path.join("extracted_images_docx", base_project_name)
        safe_delete_directory(extracted_images_path, f"Extracted images folder ({base_project_name})")

        # ✅ 4. Delete entire project folder (projects/base_name/)
        projects_path = os.path.join("projects", base_project_name)
        safe_delete_directory(projects_path, f"Project folder ({base_project_name})")
        
        logger.info(f"✅ Successfully deleted all versions and files for project: {base_project_name}")
        
    except Exception as e:
        logger.error(f"❌ Error during deletion of document {doc_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to delete document: {str(e)}")

