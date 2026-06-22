# schemas.py
from typing import List, Optional
from pydantic import BaseModel


class DocumentOut(BaseModel):
    id: str
    name: str
    fileType: str
    status: str
    size: str
    createdDate: Optional[str]
    updatedDate: Optional[str]
    slides_count: Optional[int] = None
    generated_at: Optional[str] = None
    basename: Optional[str] = None
    latest_basename: Optional[str] = None
    output_type: Optional[str] = None
    duration: Optional[float] = None
    allowedActions: List[str]
    template: Optional[str] = None
    persona: Optional[str] = None
    voice: Optional[str] = None

    class Config:
        from_attributes = True


class VersionMetadata(BaseModel):
    version: int
    basename: str
    document_id: str
    status: str
    created_date: str
    slides_count: Optional[int] = None
    template: Optional[str] = None
    persona: Optional[str] = None
    voice: Optional[str] = None


class AllVersionsResponse(BaseModel):
    base_name: str
    versions: List[VersionMetadata]
    total_versions: int


class DocumentsListResponse(BaseModel):
    items: List[DocumentOut]
    page: int
    pageSize: int
    total: int


class StatsResponse(BaseModel):
    total: int
    processing: int
    completed: int