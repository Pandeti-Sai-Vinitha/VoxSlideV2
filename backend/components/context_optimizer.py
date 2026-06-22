"""
Context Window Optimizer

Manages context to avoid token limit overflows:
- Token counting (via tiktoken)
- Context compression strategies
- Priority-based truncation
- Duplicate removal
"""

from typing import Dict, Any, List, Optional
import logging

logger = logging.getLogger(__name__)


def count_tokens(text: str) -> int:
    """
    Count tokens using tiktoken (or approximation)
    
    Args:
        text: Text to count
        
    Returns:
        Approximate token count
    """
    try:
        import tiktoken
        encoding = tiktoken.encoding_for_model("gpt-4")
        return len(encoding.encode(text))
    except (ImportError, KeyError):
        # Fallback: rough estimate (1 token ≈ 0.75 words)
        words = len(text.split())
        return int(words / 0.75)


class ContextOptimizer:
    """
    Optimize context to fit within token limits
    
    Strategies (in order of application):
    1. Remove duplicates
    2. Compress text
    3. Truncate low-priority content
    4. Drop entire sections if needed
    """

    def __init__(self, model_name: str = "gpt-4", max_tokens: int = 8000):
        """
        Initialize optimizer
        
        Args:
            model_name: LLM model (affects context window)
            max_tokens: Target maximum tokens for context
        """
        self.model_name = model_name
        self.max_tokens = max_tokens
        self.context_window = self._get_context_window(model_name)

        logger.info(
            f"Context optimizer: {model_name} "
            f"(window: {self.context_window}, target: {max_tokens})"
        )

    def _get_context_window(self, model_name: str) -> int:
        """Get context window size for model"""
        windows = {
            "gpt-4-turbo": 128000,
            "gpt-4": 8192,
            "gpt-3.5-turbo": 4096,
            "gpt-4-32k": 32768,
        }
        return windows.get(model_name, 8192)

    def optimize_context(self, context: 'RetrievedContext', buffer: int = 1000) -> 'RetrievedContext':
        """
        Optimize context to fit within token limits
        
        Applies strategies:
        1. Remove duplicates from summaries
        2. Compress verbose summaries
        3. Truncate lowest-priority content
        
        Args:
            context: RetrievedContext from RAG builder
            buffer: Token buffer for LLM output (subtract from max)
            
        Returns:
            Optimized context
        """
        max_context_tokens = self.max_tokens - buffer

        logger.info(
            f"Optimizing context for slide {context.slide_number} "
            f"(current: {context.total_tokens}, target: {max_context_tokens})"
        )

        # Step 1: Remove duplicates
        context = self._remove_duplicates(context)

        # Step 2: Compress if needed
        if context.total_tokens > max_context_tokens:
            context = self._compress_context(context, max_context_tokens)

        # Step 3: Truncate if still over
        if context.total_tokens > max_context_tokens:
            context = self._truncate_by_priority(context, max_context_tokens)

        logger.info(f"Optimized context: {context.total_tokens} tokens")
        return context

    def _remove_duplicates(self, context: 'RetrievedContext') -> 'RetrievedContext':
        """Remove duplicate chunks (same content from different sections)"""
        if not context.relevant_chunk_summaries:
            return context

        # Check for duplicates by comparing summaries
        seen_summaries = set()
        unique_chunks = []

        for chunk in context.relevant_chunk_summaries:
            # Use summary text as key (first 100 chars)
            summary_key = chunk.summary[:100].strip().lower()

            if summary_key not in seen_summaries:
                unique_chunks.append(chunk)
                seen_summaries.add(summary_key)
            else:
                logger.debug(f"Removed duplicate chunk {chunk.chunk_id}")

        original_count = len(context.relevant_chunk_summaries)
        context.relevant_chunk_summaries = unique_chunks

        if len(unique_chunks) < original_count:
            logger.info(f"Removed {original_count - len(unique_chunks)} duplicate chunks")

        return context

    def _compress_context(
        self,
        context: 'RetrievedContext',
        target_tokens: int
    ) -> 'RetrievedContext':
        """
        Compress context by shortening summaries
        
        Strategy: Keep key points, truncate verbose sections
        """
        # Shorten chunk summaries to bullet points only
        for chunk in context.relevant_chunk_summaries:
            if not chunk.key_points:
                continue

            # Create compressed summary from key points
            compressed = "• " + "\n• ".join(chunk.key_points[:3])
            original_tokens = count_tokens(chunk.summary)
            compressed_tokens = count_tokens(compressed)

            if compressed_tokens < original_tokens:
                chunk.summary = compressed
                logger.debug(
                    f"Compressed {chunk.chunk_id}: {original_tokens} → {compressed_tokens} tokens"
                )

        return context

    def _truncate_by_priority(
        self,
        context: 'RetrievedContext',
        target_tokens: int
    ) -> 'RetrievedContext':
        """
        Truncate context by dropping low-priority items
        
        Priority (keep first):
        1. Previous slide (continuity)
        2. Global summary (navigation)
        3. Chunk summaries (content) - drop highest tokens first
        4. Section summary (less critical)
        """
        current = context

        # Priority 1: Keep previous slide + global + objective
        reserved_tokens = 0
        if current.previous_slide_summary:
            reserved_tokens += count_tokens(current.previous_slide_summary)
        if current.global_summary:
            reserved_tokens += count_tokens(current.global_summary.overall_narrative)

        remaining_budget = target_tokens - reserved_tokens

        # Priority 2: Keep chunk summaries up to budget
        # Sort by size (drop largest first to save space efficiently)
        scored_chunks = []
        for chunk in current.relevant_chunk_summaries:
            token_count = count_tokens(chunk.summary)
            scored_chunks.append((chunk, token_count))

        # Sort by tokens (ascending) - keep smaller chunks to maximize count
        scored_chunks.sort(key=lambda x: x[1])

        kept_chunks = []
        chunk_tokens = 0

        for chunk, tokens in scored_chunks:
            if chunk_tokens + tokens <= remaining_budget:
                kept_chunks.append(chunk)
                chunk_tokens += tokens
            else:
                logger.info(
                    f"Dropped chunk {chunk.chunk_id} "
                    f"({tokens} tokens, budget exceeded: {chunk_tokens + tokens} > {remaining_budget})"
                )

        original_count = len(current.relevant_chunk_summaries)
        current.relevant_chunk_summaries = kept_chunks

        logger.info(
            f"Truncated from {original_count} to {len(kept_chunks)} chunks "
            f"({chunk_tokens + reserved_tokens} tokens)"
        )

        return current

    def validate_token_usage(self, context: 'RetrievedContext') -> Dict[str, Any]:
        """
        Validate context token usage
        
        Returns:
            {
                "total_tokens": int,
                "utilization": float (0-1),
                "within_limit": bool,
                "breakdown": {
                    "chunks": int,
                    "section": int,
                    "global": int,
                    "previous": int,
                }
            }
        """
        breakdown = {
            "chunks": 0,
            "section": 0,
            "global": 0,
            "previous": 0,
        }

        # Count chunk tokens
        for chunk in context.relevant_chunk_summaries:
            breakdown["chunks"] += count_tokens(chunk.summary)

        # Count section tokens
        if context.relevant_section_summary:
            breakdown["section"] += count_tokens(context.relevant_section_summary.summary)

        # Count global tokens
        if context.global_summary:
            breakdown["global"] += count_tokens(context.global_summary.overall_narrative)

        # Count previous slide tokens
        if context.previous_slide_summary:
            breakdown["previous"] += count_tokens(context.previous_slide_summary)

        total = sum(breakdown.values())
        utilization = total / self.max_tokens if self.max_tokens > 0 else 0

        return {
            "total_tokens": total,
            "utilization": min(utilization, 1.0),
            "within_limit": total <= self.max_tokens,
            "breakdown": breakdown,
            "remaining_budget": max(0, self.max_tokens - total),
        }

    def estimate_slide_response_size(self, slide_objective: str) -> int:
        """
        Estimate LLM response size for a slide
        
        Args:
            slide_objective: Slide objective text
            
        Returns:
            Estimated tokens for slide generation response
        """
        # Rough estimate: slide response ~500-1000 tokens
        # Title: ~50 tokens
        # Content (bullets): ~300-500 tokens
        # Voiceover script: ~200-400 tokens

        if "summary" in slide_objective.lower() or "conclusion" in slide_objective.lower():
            return 800  # Summary slides might be longer

        return 600  # Default estimate

    def get_recommended_max_tokens(self) -> int:
        """Get recommended max context tokens"""
        # Target: reserve 20% of context window for output + buffer
        reserved_for_output = int(self.context_window * 0.2)
        return self.context_window - reserved_for_output
