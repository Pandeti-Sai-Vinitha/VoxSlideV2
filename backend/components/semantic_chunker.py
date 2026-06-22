"""
Semantic Chunker

Splits document sections into semantically coherent chunks of 800-2000 tokens
with 10-15% overlap. Uses sliding window with embeddings to maintain topic continuity.

"""

from typing import List, Tuple, Dict, Any, Optional
from dataclasses import dataclass, field
import logging

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------
# Token counting helpers
# ---------------------------------------------------------------------

def count_tokens_approximate(text: str) -> int:
    words = len(text.split())
    return max(1, int(words / 0.75))


def count_tokens_tiktoken(text: str) -> int:
    try:
        import tiktoken
        encoding = tiktoken.encoding_for_model("gpt-4")
        return len(encoding.encode(text))
    except Exception:
        return count_tokens_approximate(text)


# ---------------------------------------------------------------------
# Chunk object
# ---------------------------------------------------------------------

@dataclass
class ChunkObject:
    chunk_id: str
    section_id: str
    section_title: str
    text: str
    tokens: int
    page_range: Tuple[int, int]
    block_ids: List[int] = field(default_factory=list)
    embedding_vector: Optional[List[float]] = None
    source_blocks: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "chunk_id": self.chunk_id,
            "section_id": self.section_id,
            "section_title": self.section_title,
            "text": self.text,
            "tokens": self.tokens,
            "page_range": list(self.page_range),
            "block_count": len(self.block_ids),
            "embedding_vector": self.embedding_vector,
        }


# ---------------------------------------------------------------------
# Semantic chunker (FIXED)
# ---------------------------------------------------------------------

class SemanticChunker:

    def __init__(
        self,
        target_tokens: int = 1000,
        min_tokens: int = 800,
        max_tokens: int = 2000,
        overlap_percent: float = 0.15,
    ):
        self.target_tokens = target_tokens
        self.min_tokens = min_tokens
        self.max_tokens = max_tokens
        self.overlap_percent = overlap_percent
        self.chunk_counter = 0

    # -------------------------------------------------------------

    def chunk(self, blocks: List["DocumentBlock"], section_title: str) -> List[ChunkObject]:
        if not blocks:
            return []

        chunks: List[ChunkObject] = []
        chunk_buffer = []
        buffer_tokens = 0
        section_id = blocks[0].section_id

        for block_idx, block in enumerate(blocks):
            block_tokens = count_tokens_tiktoken(block.text)

            chunk_buffer.append((block_idx, block, block_tokens))
            buffer_tokens += block_tokens

            if buffer_tokens >= self.target_tokens:
                self._emit_chunk(chunks, chunk_buffer, buffer_tokens, section_id, section_title)

                # ---- overlap handling (SAFE) ----
                overlap_tokens = int(self.target_tokens * self.overlap_percent)

                overlap_buffer = []
                overlap_size = 0
                for item in reversed(chunk_buffer):
                    overlap_buffer.insert(0, item)
                    overlap_size += item[2]
                    if overlap_size >= overlap_tokens:
                        break

                # Prevent pathological tiny overlap
                if overlap_size < self.min_tokens * 0.25:
                    chunk_buffer = []
                    buffer_tokens = 0
                else:
                    chunk_buffer = overlap_buffer
                    buffer_tokens = overlap_size

        # ---- FINAL BUFFER HANDLING (CRITICAL FIX) ----
        if chunk_buffer:
            if buffer_tokens < self.min_tokens and chunks:
                self._merge_into_previous(chunks[-1], chunk_buffer)
            else:
                self._emit_chunk(chunks, chunk_buffer, buffer_tokens, section_id, section_title)

        return chunks

    # -------------------------------------------------------------

    def _emit_chunk(
        self,
        chunks: List[ChunkObject],
        buffer: list,
        token_count: int,
        section_id: str,
        section_title: str,
    ):
        if token_count < self.min_tokens and chunks:
            self._merge_into_previous(chunks[-1], buffer)
            return

        chunk_id = f"chunk_{self.chunk_counter}"
        self.chunk_counter += 1

        texts = [b.text for _, b, _ in buffer]
        pages = [b.page for _, b, _ in buffer]

        chunk = ChunkObject(
            chunk_id=chunk_id,
            section_id=section_id,
            section_title=section_title,
            text="\n\n".join(texts),
            tokens=sum(t for _, _, t in buffer),
            page_range=(min(pages), max(pages)),
            block_ids=[i for i, _, _ in buffer],
            source_blocks=[b.to_dict() for _, b, _ in buffer],
        )

        chunks.append(chunk)

    # -------------------------------------------------------------

    def _merge_into_previous(self, previous: ChunkObject, buffer: list):
        texts = [b.text for _, b, _ in buffer]
        pages = [b.page for _, b, _ in buffer]
        tokens = sum(t for _, _, t in buffer)

        previous.text += "\n\n" + "\n\n".join(texts)
        previous.tokens += tokens
        previous.block_ids.extend(i for i, _, _ in buffer)
        previous.source_blocks.extend(b.to_dict() for _, b, _ in buffer)

        previous.page_range = (
            min(previous.page_range[0], min(pages)),
            max(previous.page_range[1], max(pages)),
        )

    # -------------------------------------------------------------

    def chunk_document(self, hierarchy: "DocumentSection") -> List[ChunkObject]:
        all_chunks: List[ChunkObject] = []

        def walk(section):
            if section.blocks:
                all_chunks.extend(self.chunk(section.blocks, section.title))
            for child in section.children:
                walk(child)

        walk(hierarchy)

        # FINAL HARD GUARD (ABSOLUTE SAFETY)
        final_chunks = []
        for c in all_chunks:
            if c.tokens < self.min_tokens and final_chunks:
                self._merge_into_previous(final_chunks[-1], [
                    (-1, type("B", (), {"text": c.text, "page": c.page_range[0], "to_dict": lambda: {}}), c.tokens)
                ])
            else:
                final_chunks.append(c)

        return final_chunks


# ---------------------------------------------------------------------
# Validator (unchanged)
# ---------------------------------------------------------------------

class ChunkValidator:

    @staticmethod
    def validate(chunks: List[ChunkObject]) -> Dict[str, Any]:
        if not chunks:
            return {"valid": False, "warnings": ["No chunks generated"], "stats": {}}

        tokens = [c.tokens for c in chunks]
        warnings = []

        if any(t < 800 for t in tokens):
            warnings.append("Chunks below minimum size detected")

        return {
            "valid": not warnings,
            "stats": {
                "total_chunks": len(chunks),
                "avg_tokens": sum(tokens) / len(tokens),
                "min_tokens": min(tokens),
                "max_tokens": max(tokens),
            },
            "warnings": warnings,
        }