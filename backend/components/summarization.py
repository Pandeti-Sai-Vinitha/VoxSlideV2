"""
Multi-Level Summarization Pipeline

Implements:
- MAP PHASE: Summarize individual chunks
- REDUCE PHASE: Combine chunk summaries into section summaries  
- GLOBAL PHASE: Create document-level summary (<1500 tokens)

All summaries cached for downstream use.
"""

from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field, asdict
import json
import logging

logger = logging.getLogger(__name__)


@dataclass
class ChunkSummary:
    """Summary of a single chunk"""
    chunk_id: str
    section_id: str
    section_title: str
    summary: str
    key_points: List[str] = field(default_factory=list)
    important_facts: List[str] = field(default_factory=list)
    topics: List[str] = field(default_factory=list)
    presentation_worthy_content: List[str] = field(default_factory=list)
    tokens: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dict"""
        return asdict(self)

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> 'ChunkSummary':
        """Deserialize from dict"""
        return ChunkSummary(**data)


@dataclass
class SectionSummary:
    """Summary of a document section (combines chunk summaries)"""
    section_id: str
    section_title: str
    summary: str
    major_themes: List[str] = field(default_factory=list)
    important_insights: List[str] = field(default_factory=list)
    narrative_flow: str = ""
    recommended_structure: List[str] = field(default_factory=list)  # Recommended slide points
    chunk_summaries: List[str] = field(default_factory=list)  # chunk_ids used
    tokens: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dict"""
        return asdict(self)

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> 'SectionSummary':
        """Deserialize from dict"""
        return SectionSummary(**data)


@dataclass
class GlobalDocumentSummary:
    """Compressed understanding of entire document"""
    document_purpose: str
    overall_narrative: str
    important_themes: List[str] = field(default_factory=list)
    learning_sequence: List[str] = field(default_factory=list)
    recommended_slide_count: int = 10
    content_type: str = ""  # e.g., "technical", "business", "educational"
    key_sections: List[str] = field(default_factory=list)  # section_ids in order
    tokens: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dict"""
        return asdict(self)

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> 'GlobalDocumentSummary':
        """Deserialize from dict"""
        return GlobalDocumentSummary(**data)


class SummarizationPipeline:
    """
    Multi-level summarization pipeline
    
    Flow:
    1. MAP: Chunk -> ChunkSummary (via LLM, one chunk at a time)
    2. REDUCE: ChunkSummaries -> SectionSummary
    3. GLOBAL: All sections -> GlobalDocumentSummary
    """

    def __init__(self, llm_service: Optional[Any] = None):
        """
        Initialize pipeline
        
        Args:
            llm_service: LLM service for summarization (injected)
        """
        self.llm_service = llm_service

    # ============================================================================
    # MAP PHASE: Individual Chunk Summarization
    # ============================================================================

    def summarize_chunk(self, chunk: 'ChunkObject') -> ChunkSummary:
        """
        Summarize individual chunk using LLM
        
        This is called for EACH chunk individually.
        
        Prompt asks LLM for:
        - summary: 2-3 sentence summary of key points
        - key_points: List of 3-5 most important points
        - important_facts: Specific facts, numbers, dates
        - topics: List of topics covered
        - presentation_worthy_content: Content that should appear on slides
        
        Args:
            chunk: ChunkObject to summarize
            
        Returns:
            ChunkSummary
        """
        logger.info(f"[MAP PHASE] Summarizing chunk {chunk.chunk_id} (section: {chunk.section_title})...")
        logger.debug(f"  Chunk size: {chunk.tokens} tokens")
        
        if not self.llm_service:
            # Fallback: simple text extraction
            logger.warning("No LLM service provided - using simple summarization")
            return self._simple_chunk_summary(chunk)

        # Build prompt for chunk summarization
        logger.info(f"  Building summarization prompt...")
        prompt = self._build_chunk_summary_prompt(chunk)

        try:
            # Call LLM
            logger.info(f"  Calling LLM for chunk summary...")
            response = self.llm_service.call_azure_llm(prompt)
            logger.info(f"  LLM response received")
            
            summary_data = self._parse_llm_response(response)
            logger.debug(f"  Parsed response: {len(summary_data.get('key_points', []))} key points")

            return ChunkSummary(
                chunk_id=chunk.chunk_id,
                section_id=chunk.section_id,
                section_title=chunk.section_title,
                summary=summary_data.get("summary", ""),
                key_points=summary_data.get("key_points", []),
                important_facts=summary_data.get("important_facts", []),
                topics=summary_data.get("topics", []),
                presentation_worthy_content=summary_data.get("presentation_worthy_content", []),
                tokens=chunk.tokens,
            )
        except Exception as e:
            logger.error(f"Error summarizing chunk {chunk.chunk_id}: {e}")
            return self._simple_chunk_summary(chunk)

    def _build_chunk_summary_prompt(self, chunk: 'ChunkObject') -> str:
        """Build prompt for chunk summarization"""
        prompt = f"""You are a document summarization expert. Summarize the following content chunk for a presentation.

CONTENT:
{chunk.text}

Provide response in JSON format:
{{
    "summary": "2-3 sentence summary of main points",
    "key_points": ["point1", "point2", "point3"],
    "important_facts": ["fact1", "fact2"],
    "topics": ["topic1", "topic2"],
    "presentation_worthy_content": ["content1", "content2"]
}}

Focus on:
- What would be most interesting to an audience?
- Key takeaways and learning points
- Specific data, numbers, or statistics
- Insights that would make good slide content

Return ONLY valid JSON, no additional text."""
        return prompt

    def _simple_chunk_summary(self, chunk: 'ChunkObject') -> ChunkSummary:
        """Fallback simple summarization (extract first sentences and key entities)"""
        # Take first 3 sentences as summary
        sentences = chunk.text.split('.')[:3]
        summary = '. '.join(sentences).strip()[:200]

        # Extract entities (words in CAPS or quoted text)
        topics = []
        for word in chunk.text.split():
            if word.isupper() and len(word) > 3:
                topics.append(word)

        return ChunkSummary(
            chunk_id=chunk.chunk_id,
            section_id=chunk.section_id,
            section_title=chunk.section_title,
            summary=summary,
            key_points=[],
            important_facts=[],
            topics=list(set(topics))[:5],
            presentation_worthy_content=[],
            tokens=chunk.tokens,
        )

    # ============================================================================
    # REDUCE PHASE: Section Summarization
    # ============================================================================

    def summarize_section(
        self,
        section_title: str,
        chunk_summaries: List[ChunkSummary]
    ) -> SectionSummary:
        """
        Combine chunk summaries into section summary
        
        Takes all chunk summaries from a section and creates unified summary.
        
        Args:
            section_title: Title of section
            chunk_summaries: List of ChunkSummary objects
            
        Returns:
            SectionSummary
        """
        logger.info(f"[REDUCE PHASE] Summarizing section: '{section_title}'")
        logger.info(f"  Combining {len(chunk_summaries)} chunk summaries...")
        
        if not chunk_summaries:
            logger.warning(f"  No chunks found for section '{section_title}'")
            return SectionSummary(
                section_id="unknown",
                section_title=section_title,
                summary="",
            )

        if not self.llm_service:
            logger.warning(f"  No LLM service - using simple section summarization")
            return self._simple_section_summary(section_title, chunk_summaries)

        # Build prompt combining all chunk summaries
        logger.info(f"  Building section summary prompt...")
        prompt = self._build_section_summary_prompt(section_title, chunk_summaries)

        try:
            logger.info(f"  Calling LLM for section summary...")
            response = self.llm_service.call_azure_llm(prompt)
            logger.info(f"  LLM response received")
            
            summary_data = self._parse_llm_response(response)
            logger.debug(f"  Themes: {summary_data.get('major_themes', [])}")

            return SectionSummary(
                section_id=chunk_summaries[0].section_id,
                section_title=section_title,
                summary=summary_data.get("summary", ""),
                major_themes=summary_data.get("major_themes", []),
                important_insights=summary_data.get("important_insights", []),
                narrative_flow=summary_data.get("narrative_flow", ""),
                recommended_structure=summary_data.get("recommended_structure", []),
                chunk_summaries=[c.chunk_id for c in chunk_summaries],
                tokens=sum(c.tokens for c in chunk_summaries),
            )
        except Exception as e:
            logger.error(f"Error summarizing section {section_title}: {e}")
            return self._simple_section_summary(section_title, chunk_summaries)

    def _build_section_summary_prompt(
        self,
        section_title: str,
        chunk_summaries: List[ChunkSummary]
    ) -> str:
        """Build prompt for section summarization"""
        chunk_summaries_text = "\n\n".join([
            f"Chunk {i+1}:\n{s.summary}\nKey Points: {', '.join(s.key_points)}"
            for i, s in enumerate(chunk_summaries)
        ])

        prompt = f"""You are a document strategist. Combine these chunk summaries into a cohesive section summary.

SECTION: {section_title}

CHUNK SUMMARIES:
{chunk_summaries_text}

Provide response in JSON format:
{{
    "summary": "Comprehensive summary of entire section",
    "major_themes": ["theme1", "theme2"],
    "important_insights": ["insight1", "insight2"],
    "narrative_flow": "How ideas flow through this section",
    "recommended_structure": ["slide point 1", "slide point 2"]
}}

Focus on:
- Overall narrative arc of this section
- Key themes that appear across chunks
- How to structure this content for slides

Return ONLY valid JSON."""
        return prompt

    def _simple_section_summary(
        self,
        section_title: str,
        chunk_summaries: List[ChunkSummary]
    ) -> SectionSummary:
        """Fallback section summarization"""
        combined_summary = " ".join([c.summary for c in chunk_summaries])[:300]
        all_points = []
        for c in chunk_summaries:
            all_points.extend(c.key_points)

        return SectionSummary(
            section_id=chunk_summaries[0].section_id,
            section_title=section_title,
            summary=combined_summary,
            major_themes=list(set(all_points))[:5],
            chunk_summaries=[c.chunk_id for c in chunk_summaries],
            tokens=sum(c.tokens for c in chunk_summaries),
        )

    # ============================================================================
    # GLOBAL PHASE: Document-Level Summary
    # ============================================================================

    def summarize_document(
        self,
        section_summaries: List[SectionSummary]
    ) -> GlobalDocumentSummary:
        """
        Create compressed global summary of entire document
        
        Target: <1500 tokens
        
        Args:
            section_summaries: List of all section summaries
            
        Returns:
            GlobalDocumentSummary
        """
        logger.info(f"[GLOBAL PHASE] Creating document-level summary")
        logger.info(f"  Synthesizing {len(section_summaries)} section summaries...")
        
        if not section_summaries:
            logger.warning("No section summaries provided")
            return GlobalDocumentSummary(
                document_purpose="",
                overall_narrative="",
            )

        if not self.llm_service:
            logger.warning("No LLM service - using simple global summarization")
            return self._simple_global_summary(section_summaries)

        prompt = self._build_global_summary_prompt(section_summaries)

        try:
            logger.info(f"  Calling LLM for global summary...")
            response = self.llm_service.call_azure_llm(prompt)
            logger.info(f"  LLM response received")
            
            summary_data = self._parse_llm_response(response)
            logger.debug(f"  Document purpose: {summary_data.get('document_purpose', 'N/A')[:60]}...")
            logger.debug(f"  Recommended slides: {summary_data.get('recommended_slide_count', 'N/A')}")

            return GlobalDocumentSummary(
                document_purpose=summary_data.get("document_purpose", ""),
                overall_narrative=summary_data.get("overall_narrative", ""),
                important_themes=summary_data.get("important_themes", []),
                learning_sequence=summary_data.get("learning_sequence", []),
                recommended_slide_count=summary_data.get("recommended_slide_count", 10),
                content_type=summary_data.get("content_type", ""),
                key_sections=[s.section_id for s in section_summaries],
                tokens=sum(s.tokens for s in section_summaries),
            )
        except Exception as e:
            logger.error(f"Error summarizing document: {e}")
            return self._simple_global_summary(section_summaries)

    def _build_global_summary_prompt(
        self,
        section_summaries: List[SectionSummary]
    ) -> str:
        """Build prompt for global document summarization"""
        sections_text = "\n\n".join([
            f"Section: {s.section_title}\n{s.summary}\nThemes: {', '.join(s.major_themes)}"
            for s in section_summaries
        ])

        prompt = f"""You are a document strategist. Create a compressed global summary of this document.

SECTION SUMMARIES:
{sections_text}

Provide response in JSON format (MUST be under 1500 tokens):
{{
    "document_purpose": "Why was this document created? What is its goal?",
    "overall_narrative": "The narrative arc or main story",
    "important_themes": ["theme1", "theme2"],
    "learning_sequence": ["First learn X", "Then Y", "Finally Z"],
    "recommended_slide_count": 10,
    "content_type": "technical|business|educational"
}}

Focus on:
- What's the big picture?
- What should someone know after reading?
- How to structure content for maximum impact
- Keep response VERY concise

Return ONLY valid JSON."""
        return prompt

    def _simple_global_summary(
        self,
        section_summaries: List[SectionSummary]
    ) -> GlobalDocumentSummary:
        """Fallback global summarization"""
        narrative = " → ".join([s.section_title for s in section_summaries])
        all_themes = []
        for s in section_summaries:
            all_themes.extend(s.major_themes)

        return GlobalDocumentSummary(
            document_purpose="Multi-section document",
            overall_narrative=narrative,
            important_themes=list(set(all_themes))[:5],
            learning_sequence=[s.section_title for s in section_summaries],
            recommended_slide_count=max(5, len(section_summaries) * 2),
            key_sections=[s.section_id for s in section_summaries],
            tokens=sum(s.tokens for s in section_summaries),
        )

    # ============================================================================
    # HELPER METHODS
    # ============================================================================

    def _parse_llm_response(self, response: str) -> Dict[str, Any]:
        """Parse JSON response from LLM"""
        try:
            # Handle markdown code blocks
            if "```json" in response:
                response = response.split("```json")[1].split("```")[0]
            elif "```" in response:
                response = response.split("```")[1].split("```")[0]

            return json.loads(response.strip())
        except json.JSONDecodeError:
            logger.error(f"Failed to parse LLM response: {response}")
            return {}
