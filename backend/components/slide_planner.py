"""
Slide Planner

Generates deterministic slide storyboard BEFORE slide generation.

Creates a plan for all slides with:
- Slide number, title, objective
- Required topics/content
- Source chunk IDs that should inform each slide

This plan acts as a blueprint for LLM slide generation.
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field, asdict
import json
import logging

logger = logging.getLogger(__name__)


@dataclass
class SlidePlanItem:
    """Plan for a single slide"""
    slide_number: int
    title: str
    objective: str  # What should this slide teach/convey?
    content_type: str  # "title" | "content" | "summary" | "transition"
    required_topics: List[str] = field(default_factory=list)  # Topics that must be covered
    source_chunk_ids: List[str] = field(default_factory=list)  # Which chunks to retrieve
    section_id: Optional[str] = None
    notes: str = ""  # Internal notes for LLM

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dict"""
        return asdict(self)

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> 'SlidePlanItem':
        """Deserialize from dict"""
        return SlidePlanItem(**data)


class SlidePlanner:
    """
    Generate slide storyboard from document structure and summaries
    
    Strategy:
    1. Analyze document structure (sections, themes)
    2. Determine slide count and flow
    3. Plan content for each slide
    4. Assign source chunks to each slide
    """

    def __init__(self, llm_service: Optional[Any] = None):
        """
        Initialize planner
        
        Args:
            llm_service: LLM service for slide planning (optional)
        """
        self.llm_service = llm_service

    def plan_slides(
        self,
        global_summary: 'GlobalDocumentSummary',
        section_summaries: List['SectionSummary'],
        chunks: List['ChunkObject'],
        num_target_slides: int = 8,
    ) -> List[SlidePlanItem]:
        """
        Generate complete slide plan for document
        
        Args:
            global_summary: GlobalDocumentSummary
            section_summaries: List of section summaries
            chunks: List of all chunks
            num_target_slides: Target number of slides to generate (default: 8)
            
        Returns:
            List of SlidePlanItem in presentation order
        """
        if self.llm_service:
            return self._plan_with_llm(global_summary, section_summaries, chunks, num_target_slides)
        else:
            return self._plan_without_llm(global_summary, section_summaries, chunks, num_target_slides)

    def _plan_with_llm(
        self,
        global_summary: 'GlobalDocumentSummary',
        section_summaries: List['SectionSummary'],
        chunks: List['ChunkObject'],
        num_target_slides: int = 8,
    ) -> List[SlidePlanItem]:
        """Plan slides using LLM"""
        prompt = self._build_planning_prompt(global_summary, section_summaries, num_target_slides)

        try:
            response = self.llm_service.call_azure_llm(prompt)
            plan_data = self._parse_llm_response(response)

            slides = []
            for i, slide_data in enumerate(plan_data.get("slides", []), 1):
                if i > num_target_slides:
                    break  # Enforce max limit
                
                # Map slide to relevant chunks
                source_chunks = self._find_relevant_chunks(
                    slide_data.get("required_topics", []),
                    chunks
                )

                slide = SlidePlanItem(
                    slide_number=i,
                    title=slide_data.get("title", f"Slide {i}"),
                    objective=slide_data.get("objective", ""),
                    content_type=slide_data.get("content_type", "content"),
                    required_topics=slide_data.get("required_topics", []),
                    source_chunk_ids=source_chunks,
                    notes=slide_data.get("notes", ""),
                )
                slides.append(slide)

            # ✅ ENFORCE EXACT SLIDE COUNT: Pad with filler slides if needed
            while len(slides) < num_target_slides:
                slide_num = len(slides) + 1
                slides.append(SlidePlanItem(
                    slide_number=slide_num,
                    title=f"Key Point {slide_num - 1}",
                    objective=f"Cover additional content point {slide_num - 1}",
                    content_type="content",
                    required_topics=global_summary.important_themes[:2] if global_summary.important_themes else [],
                    source_chunk_ids=[c.chunk_id for c in chunks[:2]] if chunks else [],
                ))

            return slides[:num_target_slides]  # Ensure exactly num_target_slides

        except Exception as e:
            logger.error(f"Error planning slides with LLM: {e}")
            return self._plan_without_llm(global_summary, section_summaries, chunks, num_target_slides)

    def _build_planning_prompt(
        self,
        global_summary: 'GlobalDocumentSummary',
        section_summaries: List['SectionSummary'],
        num_target_slides: int = 8
    ) -> str:
        """Build prompt for slide planning"""
        sections_text = "\n".join([
            f"- {s.section_title}: {s.summary}"
            for s in section_summaries
        ])

        prompt = f"""You are an expert presentation designer. Create a slide storyboard for this document.

DOCUMENT PURPOSE: {global_summary.document_purpose}

NARRATIVE: {global_summary.overall_narrative}

TARGET NUMBER OF SLIDES: {num_target_slides}

SECTIONS:
{sections_text}

Create a structured presentation plan with EXACTLY {num_target_slides} slides. Provide response in JSON:
{{
    "slides": [
        {{
            "title": "Slide Title",
            "objective": "What should viewers understand?",
            "content_type": "title|content|summary|transition",
            "required_topics": ["topic1", "topic2"],
            "notes": "Hints for LLM slide generation"
        }}
    ]
}}

CRITICAL REQUIREMENTS:
- MUST generate EXACTLY {num_target_slides} slides (not more, not less)
- Start with title slide
- End with conclusion slide
- Include 1-2 transition/summary slides between sections
- Each slide should cover 1-2 main topics
- Arrange in logical learning sequence

Return ONLY valid JSON with exactly {num_target_slides} slides."""
        return prompt

    def _plan_without_llm(
        self,
        global_summary: 'GlobalDocumentSummary',
        section_summaries: List['SectionSummary'],
        chunks: List['ChunkObject'],
        num_target_slides: int = 8,
    ) -> List[SlidePlanItem]:
        """Generate slide plan without LLM (heuristic-based)"""
        slides = []
        slide_num = 1

        # Title slide
        slides.append(SlidePlanItem(
            slide_number=slide_num,
            title="Title Slide",
            objective="Introduce document topic and main theme",
            content_type="title",
            required_topics=[],
            source_chunk_ids=[],
            notes=f"Purpose: {global_summary.document_purpose}",
        ))
        slide_num += 1

        # Content slides - one per major section
        for section_summary in section_summaries:
            if slide_num >= num_target_slides:  # Reserve space for conclusion
                break
                
            # Get chunks for this section
            section_chunks = [
                c.chunk_id for c in chunks
                if c.section_id == section_summary.section_id
            ]

            for i, topic in enumerate(section_summary.recommended_structure[:3]):
                if slide_num >= num_target_slides:  # Reserve space for conclusion
                    break

                slides.append(SlidePlanItem(
                    slide_number=slide_num,
                    title=section_summary.section_title,
                    objective=topic,
                    content_type="content",
                    required_topics=section_summary.major_themes[:2],
                    source_chunk_ids=section_chunks[:2],
                    section_id=section_summary.section_id,
                ))
                slide_num += 1

            if slide_num >= num_target_slides:  # Reserve space for conclusion
                break

        # Summary slide (if space available)
        if slide_num < num_target_slides:
            slides.append(SlidePlanItem(
                slide_number=slide_num,
                title="Summary & Key Takeaways",
                objective="Reinforce main learning points",
                content_type="summary",
                required_topics=global_summary.important_themes,
                source_chunk_ids=[],
            ))
            slide_num += 1

        # ✅ PAD WITH CONTENT SLIDES TO REACH EXACT TARGET COUNT
        while slide_num < num_target_slides:
            slides.append(SlidePlanItem(
                slide_number=slide_num,
                title=f"Key Points - Part {slide_num - 1}",
                objective=f"Continue covering important topics from the document",
                content_type="content",
                required_topics=global_summary.important_themes[:2] if global_summary.important_themes else [],
                source_chunk_ids=[c.chunk_id for c in chunks[slide_num % len(chunks):(slide_num % len(chunks)) + 2]] if chunks else [],
            ))
            slide_num += 1

        # Conclusion slide (if we still have the exact count)
        if len(slides) < num_target_slides:
            slides.append(SlidePlanItem(
                slide_number=len(slides) + 1,
                title="Conclusion",
                objective="Closing remarks and key takeaways",
                content_type="summary",
                required_topics=[],
                source_chunk_ids=[],
            ))

        # ✅ ENFORCE EXACT SLIDE COUNT
        return slides[:num_target_slides]

    def _find_relevant_chunks(
        self,
        topics: List[str],
        chunks: List['ChunkObject'],
        top_k: int = 3
    ) -> List[str]:
        """
        Find chunks most relevant to given topics
        
        Simple heuristic: match topic keywords in chunk text
        TODO: Use embeddings/FAISS for better matching
        
        Args:
            topics: Topics to match
            chunks: All chunks
            top_k: Number of chunks to return
            
        Returns:
            List of chunk_ids
        """
        if not topics:
            return []

        topic_str = " ".join(topics).lower()
        chunk_scores = []

        for chunk in chunks:
            # Count topic keyword matches
            score = 0
            chunk_text = chunk.text.lower()
            for topic in topics:
                score += chunk_text.count(topic.lower())

            chunk_scores.append((chunk.chunk_id, score))

        # Sort by score and return top k
        chunk_scores.sort(key=lambda x: x[1], reverse=True)
        return [chunk_id for chunk_id, score in chunk_scores[:top_k] if score > 0]

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
            logger.error(f"Failed to parse slide plan response: {response}")
            return {"slides": []}

    def validate_plan(self, slides: List[SlidePlanItem]) -> Dict[str, Any]:
        """
        Validate slide plan quality
        
        Returns:
            {
                "valid": bool,
                "stats": {...},
                "warnings": [...]
            }
        """
        warnings = []

        if len(slides) < 3:
            warnings.append("Less than 3 slides - presentation may be too short")

        if len(slides) > 50:
            warnings.append("More than 50 slides - presentation may be too long")

        # Check for missing objectives
        for slide in slides:
            if not slide.objective:
                warnings.append(f"Slide {slide.slide_number} missing objective")

        # Check for orphaned slides (no source chunks and not a title/summary)
        for slide in slides:
            if (not slide.source_chunk_ids and
                slide.content_type not in ["title", "summary", "transition"]):
                warnings.append(f"Slide {slide.slide_number} has no source chunks")

        return {
            "valid": len(warnings) == 0,
            "stats": {
                "total_slides": len(slides),
                "content_slides": sum(1 for s in slides if s.content_type == "content"),
                "summary_slides": sum(1 for s in slides if s.content_type == "summary"),
                "title_slides": sum(1 for s in slides if s.content_type == "title"),
            },
            "warnings": warnings
        }
