import json
from langchain.tools import tool


@tool
def load_slides(file_path: str) -> list:
    """Load slides from JSON file"""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("slides", [])
    except Exception as e:
        return [{"error": str(e)}]