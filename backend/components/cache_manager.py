"""
Cache Manager

Caches intermediate results for reuse:
- Document hierarchies
- Chunks and chunk summaries
- Section and global summaries
- Embeddings and FAISS indices
- Slide plans

Enables fast re-processing if document is regenerated.
"""

import os
import json
import pickle
import logging
from typing import Dict, Any, Optional, List
from pathlib import Path
from dataclasses import asdict

logger = logging.getLogger(__name__)


class CacheManager:
    """
    Manage caching of hierarchical context pipeline artifacts
    
    Storage structure:
    {cache_root}/{document_id}/
    ├── hierarchy.json          (DocumentHierarchy)
    ├── chunks.json             (ChunkObject[])
    ├── summaries/
    │   ├── chunks.json         (ChunkSummary[])
    │   ├── sections.json       (SectionSummary{})
    │   └── global.json         (GlobalDocumentSummary)
    ├── slide_plan.json         (SlidePlanItem[])
    └── embeddings/
        ├── embeddings.pkl      (FAISS index)
        └── metadata.json       (chunk_id -> vector mapping)
    """

    def __init__(self, cache_root: str = "./cache"):
        """
        Initialize cache manager
        
        Args:
            cache_root: Root directory for caches
        """
        self.cache_root = Path(cache_root)
        self.cache_root.mkdir(parents=True, exist_ok=True)
        logger.info(f"Cache root: {self.cache_root}")

    def get_document_cache_path(self, document_id: str) -> Path:
        """Get cache directory for document"""
        path = self.cache_root / document_id
        path.mkdir(parents=True, exist_ok=True)
        return path

    # ============================================================================
    # HIERARCHY CACHING
    # ============================================================================

    def save_hierarchy(self, document_id: str, hierarchy: 'DocumentSection') -> bool:
        """
        Save document hierarchy to cache
        
        Args:
            document_id: Unique document identifier
            hierarchy: Root DocumentSection
            
        Returns:
            Success
        """
        try:
            cache_path = self.get_document_cache_path(document_id)
            hierarchy_file = cache_path / "hierarchy.json"

            # Serialize hierarchy
            hierarchy_data = self._serialize_hierarchy(hierarchy)

            with open(hierarchy_file, "w") as f:
                json.dump(hierarchy_data, f, indent=2)

            logger.info(f"Saved hierarchy for {document_id}")
            return True

        except Exception as e:
            logger.error(f"Error saving hierarchy: {e}")
            return False

    def load_hierarchy(self, document_id: str) -> Optional['DocumentSection']:
        """
        Load document hierarchy from cache
        
        Args:
            document_id: Unique document identifier
            
        Returns:
            DocumentSection or None if not cached
        """
        try:
            cache_path = self.get_document_cache_path(document_id)
            hierarchy_file = cache_path / "hierarchy.json"

            if not hierarchy_file.exists():
                return None

            with open(hierarchy_file, "r") as f:
                hierarchy_data = json.load(f)

            # Deserialize hierarchy
            hierarchy = self._deserialize_hierarchy(hierarchy_data)
            logger.info(f"Loaded hierarchy for {document_id}")
            return hierarchy

        except Exception as e:
            logger.error(f"Error loading hierarchy: {e}")
            return None

    # ============================================================================
    # CHUNKS CACHING
    # ============================================================================

    def save_chunks(self, document_id: str, chunks: List['ChunkObject']) -> bool:
        """Save chunks to cache"""
        try:
            cache_path = self.get_document_cache_path(document_id)
            chunks_file = cache_path / "chunks.json"

            chunks_data = [c.to_dict() for c in chunks]

            with open(chunks_file, "w") as f:
                json.dump(chunks_data, f, indent=2)

            logger.info(f"Saved {len(chunks)} chunks for {document_id}")
            return True

        except Exception as e:
            logger.error(f"Error saving chunks: {e}")
            return False

    def load_chunks(self, document_id: str) -> Optional[List['ChunkObject']]:
        """Load chunks from cache"""
        try:
            cache_path = self.get_document_cache_path(document_id)
            chunks_file = cache_path / "chunks.json"

            if not chunks_file.exists():
                return None

            with open(chunks_file, "r") as f:
                chunks_data = json.load(f)

            # Reconstruct ChunkObject - requires import
            from semantic_chunker import ChunkObject
            chunks = [ChunkObject(**data) for data in chunks_data]
            logger.info(f"Loaded {len(chunks)} chunks for {document_id}")
            return chunks

        except Exception as e:
            logger.error(f"Error loading chunks: {e}")
            return None

    # ============================================================================
    # SUMMARIES CACHING
    # ============================================================================

    def save_summaries(
        self,
        document_id: str,
        chunk_summaries: List['ChunkSummary'],
        section_summaries: List['SectionSummary'],
        global_summary: 'GlobalDocumentSummary'
    ) -> bool:
        """Save all summaries to cache"""
        try:
            cache_path = self.get_document_cache_path(document_id)
            summaries_dir = cache_path / "summaries"
            summaries_dir.mkdir(exist_ok=True)

            # Save chunk summaries
            chunk_data = [s.to_dict() for s in chunk_summaries]
            with open(summaries_dir / "chunks.json", "w") as f:
                json.dump(chunk_data, f, indent=2)

            # Save section summaries
            section_data = [s.to_dict() for s in section_summaries]
            with open(summaries_dir / "sections.json", "w") as f:
                json.dump(section_data, f, indent=2)

            # Save global summary
            global_data = global_summary.to_dict()
            with open(summaries_dir / "global.json", "w") as f:
                json.dump(global_data, f, indent=2)

            logger.info(
                f"Saved summaries for {document_id}: "
                f"{len(chunk_summaries)} chunks, {len(section_summaries)} sections"
            )
            return True

        except Exception as e:
            logger.error(f"Error saving summaries: {e}")
            return False

    def load_summaries(self, document_id: str) -> Optional[Dict[str, Any]]:
        """Load all summaries from cache"""
        try:
            cache_path = self.get_document_cache_path(document_id)
            summaries_dir = cache_path / "summaries"

            if not summaries_dir.exists():
                return None

            from summarization import ChunkSummary, SectionSummary, GlobalDocumentSummary

            # Load chunk summaries
            with open(summaries_dir / "chunks.json", "r") as f:
                chunk_data = json.load(f)
            chunk_summaries = [ChunkSummary.from_dict(data) for data in chunk_data]

            # Load section summaries
            with open(summaries_dir / "sections.json", "r") as f:
                section_data = json.load(f)
            section_summaries = [SectionSummary.from_dict(data) for data in section_data]

            # Load global summary
            with open(summaries_dir / "global.json", "r") as f:
                global_data = json.load(f)
            global_summary = GlobalDocumentSummary.from_dict(global_data)

            logger.info(
                f"Loaded summaries for {document_id}: "
                f"{len(chunk_summaries)} chunks, {len(section_summaries)} sections"
            )

            return {
                "chunk_summaries": chunk_summaries,
                "section_summaries": section_summaries,
                "global_summary": global_summary,
            }

        except Exception as e:
            logger.error(f"Error loading summaries: {e}")
            return None

    # ============================================================================
    # SLIDE PLAN CACHING
    # ============================================================================

    def save_slide_plan(self, document_id: str, slides: List['SlidePlanItem']) -> bool:
        """Save slide plan to cache"""
        try:
            cache_path = self.get_document_cache_path(document_id)
            plan_file = cache_path / "slide_plan.json"

            slides_data = [s.to_dict() for s in slides]

            with open(plan_file, "w") as f:
                json.dump(slides_data, f, indent=2)

            logger.info(f"Saved slide plan ({len(slides)} slides) for {document_id}")
            return True

        except Exception as e:
            logger.error(f"Error saving slide plan: {e}")
            return False

    def load_slide_plan(self, document_id: str) -> Optional[List['SlidePlanItem']]:
        """Load slide plan from cache"""
        try:
            cache_path = self.get_document_cache_path(document_id)
            plan_file = cache_path / "slide_plan.json"

            if not plan_file.exists():
                return None

            with open(plan_file, "r") as f:
                slides_data = json.load(f)

            from slide_planner import SlidePlanItem
            slides = [SlidePlanItem.from_dict(data) for data in slides_data]
            logger.info(f"Loaded slide plan ({len(slides)} slides) for {document_id}")
            return slides

        except Exception as e:
            logger.error(f"Error loading slide plan: {e}")
            return None

    # ============================================================================
    # EMBEDDINGS CACHING
    # ============================================================================

    def save_embeddings(
        self,
        document_id: str,
        faiss_index: Any,
        chunk_id_to_summary: Dict[str, 'ChunkSummary']
    ) -> bool:
        """Save FAISS index and embeddings metadata to cache"""
        try:
            cache_path = self.get_document_cache_path(document_id)
            embeddings_dir = cache_path / "embeddings"
            embeddings_dir.mkdir(exist_ok=True)

            # Save FAISS index if available
            if faiss_index:
                try:
                    import faiss
                    index_file = embeddings_dir / "index.faiss"
                    faiss.write_index(faiss_index, str(index_file))
                except ImportError:
                    logger.warning("FAISS not available - skipping index save")

            # Save metadata (chunk IDs)
            metadata = {
                "chunk_ids": list(chunk_id_to_summary.keys()),
                "chunk_count": len(chunk_id_to_summary),
            }
            with open(embeddings_dir / "metadata.json", "w") as f:
                json.dump(metadata, f, indent=2)

            logger.info(f"Saved embeddings for {document_id}")
            return True

        except Exception as e:
            logger.error(f"Error saving embeddings: {e}")
            return False

    def load_embeddings(self, document_id: str) -> Optional[Dict[str, Any]]:
        """Load FAISS index and embeddings metadata from cache"""
        try:
            cache_path = self.get_document_cache_path(document_id)
            embeddings_dir = cache_path / "embeddings"

            if not embeddings_dir.exists():
                return None

            faiss_index = None
            try:
                import faiss
                index_file = embeddings_dir / "index.faiss"
                if index_file.exists():
                    faiss_index = faiss.read_index(str(index_file))
            except ImportError:
                logger.warning("FAISS not available - skipping index load")

            # Load metadata
            with open(embeddings_dir / "metadata.json", "r") as f:
                metadata = json.load(f)

            logger.info(f"Loaded embeddings for {document_id}")
            return {
                "faiss_index": faiss_index,
                "metadata": metadata,
            }

        except Exception as e:
            logger.error(f"Error loading embeddings: {e}")
            return None

    # ============================================================================
    # CACHE MANAGEMENT
    # ============================================================================

    def is_cached(self, document_id: str) -> bool:
        """Check if document is fully cached"""
        cache_path = self.get_document_cache_path(document_id)

        required_files = [
            cache_path / "hierarchy.json",
            cache_path / "chunks.json",
            cache_path / "summaries" / "chunks.json",
            cache_path / "summaries" / "sections.json",
            cache_path / "summaries" / "global.json",
            cache_path / "slide_plan.json",
        ]

        return all(f.exists() for f in required_files)

    def clear_cache(self, document_id: str) -> bool:
        """Clear cache for a document"""
        try:
            import shutil
            cache_path = self.get_document_cache_path(document_id)
            if cache_path.exists():
                shutil.rmtree(cache_path)
                logger.info(f"Cleared cache for {document_id}")
            return True
        except Exception as e:
            logger.error(f"Error clearing cache: {e}")
            return False

    def get_cache_size(self, document_id: str) -> int:
        """Get cache size in bytes"""
        try:
            cache_path = self.get_document_cache_path(document_id)
            total = 0
            for file in cache_path.rglob("*"):
                if file.is_file():
                    total += file.stat().st_size
            return total
        except Exception as e:
            logger.error(f"Error getting cache size: {e}")
            return 0

    # ============================================================================
    # SERIALIZATION HELPERS
    # ============================================================================

    def _serialize_hierarchy(self, section: 'DocumentSection') -> Dict[str, Any]:
        """Recursively serialize DocumentSection hierarchy"""
        return {
            "section_id": section.section_id,
            "title": section.title,
            "heading_level": section.heading_level.name,
            "parent_id": section.parent_id,
            "page_range": section.page_range,
            "block_count": len(section.blocks),
            "children": [self._serialize_hierarchy(child) for child in section.children],
        }

    def _deserialize_hierarchy(self, data: Dict[str, Any]) -> 'DocumentSection':
        """Recursively deserialize hierarchy - returns structure info only"""
        # Returns simplified structure since we reconstruct from documents
        # Full reconstruction would require reprocessing
        return None
