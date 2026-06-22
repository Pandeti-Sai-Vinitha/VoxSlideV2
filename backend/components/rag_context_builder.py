"""
RAG Context Builder

Builds retrieval-augmented generation (RAG) system using embeddings + FAISS.

For each slide:
- Retrieve only relevant chunk/section summaries
- Retrieve global document summary
- Retrieve previous slide summary (for continuity)
- Discard low-relevance content first

This keeps LLM context window small while maintaining coherence.
"""

from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field, asdict
import logging
import json

logger = logging.getLogger(__name__)


@dataclass
class RetrievedContext:
    """Context retrieved for a single slide"""
    slide_number: int
    slide_objective: str
    relevant_chunk_summaries: List['ChunkSummary'] = field(default_factory=list)
    relevant_section_summary: Optional['SectionSummary'] = None
    global_summary: Optional['GlobalDocumentSummary'] = None
    previous_slide_summary: Optional[str] = None
    total_tokens: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dict"""
        return {
            "slide_number": self.slide_number,
            "slide_objective": self.slide_objective,
            "chunk_summaries_count": len(self.relevant_chunk_summaries),
            "has_section_summary": self.relevant_section_summary is not None,
            "has_global_summary": self.global_summary is not None,
            "has_previous_slide": self.previous_slide_summary is not None,
            "total_tokens": self.total_tokens,
        }


class RAGContextBuilder:
    """
    Build context for each slide using retrieval-augmented generation
    
    Strategy:
    1. Create embeddings for all chunk/section summaries
    2. Build FAISS index for semantic search
    3. For each slide:
       - Retrieve relevant chunk summaries by embedding similarity
       - Add section summary (if exists)
       - Add global summary (always)
       - Add previous slide context (for flow)
       - Count tokens and drop lowest-priority content if needed
    """

    def __init__(self, embedding_model: Optional[str] = None):
        """
        Initialize RAG builder
        
        Args:
            embedding_model: Name of embedding model to use
                Options: "azure" (Azure OpenAI embeddings),
                         "sentence-transformers" (local),
                         None (will use mock embeddings for testing)
        """
        self.embedding_model = embedding_model or "mock"
        self.faiss_index: Optional[Any] = None
        self.chunk_id_to_summary: Dict[str, 'ChunkSummary'] = {}
        self.embeddings_cache: Dict[str, List[float]] = {}

    def build_index(
        self,
        chunk_summaries: List['ChunkSummary'],
        section_summaries: List['SectionSummary'],
    ):
        """
        Build FAISS index from summaries
        
        Args:
            chunk_summaries: All chunk summaries
            section_summaries: All section summaries
        """
        logger.info(f"Building FAISS index from {len(chunk_summaries)} chunk summaries")

        try:
            import faiss
            import numpy as np
        except ImportError:
            logger.warning("FAISS not installed - using mock retrieval")
            self.faiss_index = None
            self._build_mock_index(chunk_summaries, section_summaries)
            return

        # Get embeddings for all chunk summaries
        embeddings = []
        chunk_ids = []

        for chunk_summary in chunk_summaries:
            embedding = self._get_embedding(chunk_summary.summary)
            embeddings.append(embedding)
            chunk_ids.append(chunk_summary.chunk_id)
            self.chunk_id_to_summary[chunk_summary.chunk_id] = chunk_summary

        if not embeddings:
            logger.warning("No embeddings generated")
            return

        # Create FAISS index
        embedding_dim = len(embeddings[0])
        embeddings_array = np.array(embeddings, dtype=np.float32)

        # Use flat L2 index (exact search)
        self.faiss_index = faiss.IndexFlatL2(embedding_dim)
        self.faiss_index.add(embeddings_array)

        logger.info(f"FAISS index built: {self.faiss_index.ntotal} vectors, dimension {embedding_dim}")

    def _build_mock_index(
        self,
        chunk_summaries: List['ChunkSummary'],
        section_summaries: List['SectionSummary'],
    ):
        """Build mock index for testing (no FAISS dependency)"""
        for chunk_summary in chunk_summaries:
            self.chunk_id_to_summary[chunk_summary.chunk_id] = chunk_summary

    def retrieve_context(
        self,
        slide_objective: str,
        slide_number: int,
        section_id: Optional[str] = None,
        source_chunk_ids: Optional[List[str]] = None,
        global_summary: Optional['GlobalDocumentSummary'] = None,
        previous_slide_summary: Optional[str] = None,
        max_tokens: int = 3000,
        top_k: int = 3,
    ) -> RetrievedContext:
        """
        Retrieve context for a single slide
        
        Priority ranking:
        1. Chunks specified in slide plan (source_chunk_ids) - MUST include
        2. Chunks matching slide objective (semantic search) - HIGH
        3. Section summary (if available) - MEDIUM
        4. Global summary - ALWAYS include
        5. Previous slide summary - ALWAYS include
        
        Args:
            slide_objective: What the slide should convey
            slide_number: Slide number (for tracking)
            section_id: Section this slide belongs to
            source_chunk_ids: Specific chunks to include (from slide plan)
            global_summary: Document-level summary
            previous_slide_summary: Summary of previous slide
            max_tokens: Maximum tokens for context (drop content if exceeded)
            top_k: Number of semantic search results to retrieve
            
        Returns:
            RetrievedContext with selected summaries
        """
        context = RetrievedContext(
            slide_number=slide_number,
            slide_objective=slide_objective,
        )

        # 1. Add required chunks from slide plan
        required_summaries = []
        if source_chunk_ids:
            for chunk_id in source_chunk_ids:
                if chunk_id in self.chunk_id_to_summary:
                    required_summaries.append(self.chunk_id_to_summary[chunk_id])

        # 2. Retrieve semantically similar chunks
        semantic_summaries = self._semantic_search(
            slide_objective,
            top_k=top_k,
            exclude_ids=[s.chunk_id for s in required_summaries]
        )

        # Combine in priority order
        all_summaries = required_summaries + semantic_summaries
        context.relevant_chunk_summaries = all_summaries

        # 3. Add section summary if available
        if section_id and not section_id.startswith("root"):
            # TODO: Pass section summaries to this method and retrieve
            pass

        # 4. Add global summary (always)
        context.global_summary = global_summary

        # 5. Add previous slide context
        context.previous_slide_summary = previous_slide_summary

        # Count tokens and apply truncation if needed
        context.total_tokens = self._count_context_tokens(context)

        if context.total_tokens > max_tokens:
            context = self._truncate_context(context, max_tokens)

        logger.info(
            f"Slide {slide_number}: Retrieved {len(context.relevant_chunk_summaries)} "
            f"chunks, {context.total_tokens} tokens"
        )

        return context

    def _semantic_search(
        self,
        query: str,
        top_k: int = 3,
        exclude_ids: Optional[List[str]] = None,
    ) -> List['ChunkSummary']:
        """
        Semantic search for relevant chunks
        
        Args:
            query: Search query (e.g., slide objective)
            top_k: Number of results to return
            exclude_ids: Chunk IDs to exclude from results
            
        Returns:
            List of top-k relevant ChunkSummary objects
        """
        if not self.chunk_id_to_summary:
            return []

        exclude_ids = exclude_ids or []

        if self.faiss_index is None:
            # Mock search - keyword matching
            return self._mock_semantic_search(query, top_k, exclude_ids)

        try:
            import numpy as np
            # Get embedding for query
            query_embedding = self._get_embedding(query)
            query_embedding = np.array([query_embedding], dtype=np.float32)

            # Search FAISS index
            distances, indices = self.faiss_index.search(query_embedding, top_k * 2)

            # Collect results, filtering out excluded IDs
            results = []
            for idx in indices[0]:
                chunk_id = list(self.chunk_id_to_summary.keys())[idx]
                if chunk_id not in exclude_ids:
                    results.append(self.chunk_id_to_summary[chunk_id])
                if len(results) >= top_k:
                    break

            return results

        except Exception as e:
            logger.error(f"Error in semantic search: {e}")
            return self._mock_semantic_search(query, top_k, exclude_ids)

    def _mock_semantic_search(
        self,
        query: str,
        top_k: int,
        exclude_ids: List[str]
    ) -> List['ChunkSummary']:
        """
        Mock semantic search using keyword matching
        
        Falls back when FAISS not available or embeddings fail
        """
        query_words = set(query.lower().split())

        # Score chunks by keyword overlap
        scored = []
        for chunk_id, summary in self.chunk_id_to_summary.items():
            if chunk_id in exclude_ids:
                continue

            # Count matching keywords in summary
            summary_words = set(summary.summary.lower().split())
            overlap = len(query_words & summary_words)

            # Also check key_points and topics
            overlap += len([kp for kp in summary.key_points if any(w in kp.lower() for w in query_words)])
            overlap += len([t for t in summary.topics if any(w in t.lower() for w in query_words)])

            scored.append((chunk_id, overlap))

        # Sort by overlap and return top-k
        scored.sort(key=lambda x: x[1], reverse=True)
        return [
            self.chunk_id_to_summary[chunk_id]
            for chunk_id, score in scored[:top_k]
            if score > 0
        ]

    def _get_embedding(self, text: str) -> List[float]:
        """
        Get embedding vector for text
        
        Args:
            text: Text to embed
            
        Returns:
            Embedding vector
        """
        # Check cache
        if text in self.embeddings_cache:
            return self.embeddings_cache[text]

        if self.embedding_model == "azure":
            embedding = self._get_azure_embedding(text)
        elif self.embedding_model == "sentence-transformers":
            embedding = self._get_sentence_transformers_embedding(text)
        else:
            # Mock embedding - deterministic for testing
            embedding = self._get_mock_embedding(text)

        self.embeddings_cache[text] = embedding
        return embedding

    def _get_azure_embedding(self, text: str) -> List[float]:
        """Get embedding from Azure OpenAI"""
        try:
            # This would require Azure OpenAI embeddings API
            # For now, return mock
            logger.warning("Azure embeddings not configured - using mock")
            return self._get_mock_embedding(text)
        except Exception as e:
            logger.error(f"Error getting Azure embedding: {e}")
            return self._get_mock_embedding(text)

    def _get_sentence_transformers_embedding(self, text: str) -> List[float]:
        """Get embedding from sentence-transformers"""
        try:
            from sentence_transformers import SentenceTransformer
            model = SentenceTransformer('all-MiniLM-L6-v2')
            embedding = model.encode(text, convert_to_numpy=True)
            return embedding.tolist()
        except ImportError:
            logger.warning("sentence-transformers not installed - using mock")
            return self._get_mock_embedding(text)

    def _get_mock_embedding(self, text: str) -> List[float]:
        """Generate mock deterministic embedding for testing"""
        import hashlib
        # Use hash to generate deterministic but different embeddings
        hash_val = hashlib.md5(text.encode()).hexdigest()
        # Convert hex chars to floats
        embedding = [float(int(hash_val[i:i+2], 16)) / 256.0 for i in range(0, 32, 2)]
        return embedding

    def _count_context_tokens(self, context: RetrievedContext) -> int:
        """Estimate total tokens in context"""
        from .semantic_chunker import count_tokens_tiktoken

        tokens = 0

        # Chunk summaries
        for summary in context.relevant_chunk_summaries:
            tokens += count_tokens_tiktoken(summary.summary)

        # Section summary (if present)
        if context.relevant_section_summary:
            tokens += count_tokens_tiktoken(context.relevant_section_summary.summary)

        # Global summary (if present)
        if context.global_summary:
            tokens += count_tokens_tiktoken(context.global_summary.overall_narrative)

        # Previous slide
        if context.previous_slide_summary:
            tokens += count_tokens_tiktoken(context.previous_slide_summary)

        return tokens

    def _truncate_context(
        self,
        context: RetrievedContext,
        max_tokens: int
    ) -> RetrievedContext:
        """
        Truncate context to fit within token limit
        
        Priority (keep first, drop last):
        1. Previous slide (for continuity)
        2. Global summary (for navigation)
        3. Chunk summaries (content)
        4. Section summary (less critical)
        """
        from .semantic_chunker import count_tokens_tiktoken

        current_tokens = 0
        tokens_budget = max_tokens

        # Always keep: objective, previous slide, global summary
        kept_context = RetrievedContext(
            slide_number=context.slide_number,
            slide_objective=context.slide_objective,
            previous_slide_summary=context.previous_slide_summary,
            global_summary=context.global_summary,
        )

        # Count reserved tokens
        if context.previous_slide_summary:
            kept_context.total_tokens += count_tokens_tiktoken(context.previous_slide_summary)

        if context.global_summary:
            kept_context.total_tokens += count_tokens_tiktoken(context.global_summary.overall_narrative)

        # Add chunk summaries until budget exhausted
        for summary in context.relevant_chunk_summaries:
            summary_tokens = count_tokens_tiktoken(summary.summary)
            if kept_context.total_tokens + summary_tokens <= tokens_budget:
                kept_context.relevant_chunk_summaries.append(summary)
                kept_context.total_tokens += summary_tokens
            else:
                logger.warning(
                    f"Dropped chunk {summary.chunk_id} - exceeds token limit "
                    f"({kept_context.total_tokens + summary_tokens} > {tokens_budget})"
                )

        return kept_context
