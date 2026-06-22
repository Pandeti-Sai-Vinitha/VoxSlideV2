from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pathlib import Path
import asyncio
import json
import logging
from urllib.parse import unquote
from datetime import datetime
from config import parse_versioned_basename

router = APIRouter(prefix="/api/status", tags=["status"])
logger = logging.getLogger(__name__)


@router.get("/logs/{basename}")
def get_logs(basename: str):
    from urllib.parse import unquote
    basename = unquote(basename)

    BASE_DIR = Path(__file__).resolve().parent.parent
    logs_dir = BASE_DIR / "logs"

    log_file = logs_dir / f"{basename}.log"
    if not log_file.exists():
        base_name, _ = parse_versioned_basename(basename)
        fallback_file = logs_dir / f"{base_name}.log"
        if fallback_file.exists():
            log_file = fallback_file

    print("🔎 Reading logs from:", log_file)

    if not log_file.exists():
        return {"logs": [], "status": "waiting", "file_mtime": None}

    try:
        with open(log_file, "r", encoding="utf-8") as f:
            lines = f.readlines()

        # ✅ Get file modification time to help frontend detect fresh logs
        file_mtime = log_file.stat().st_mtime
        
        return {
            "logs": [line.strip() for line in lines if line.strip()],
            "file_mtime": file_mtime
        }

    except Exception as e:
        print("❌ LOG ERROR:", str(e))
        return {
            "logs": [],
            "error": str(e),
            "file_mtime": None
        }