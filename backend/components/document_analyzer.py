"""
Document Structure Analyzer

Detects document hierarchy (headings, sections, subsections) and builds
a structured representation preserving formatting metadata.

Handles both:
- Structured documents (with clear heading hierarchy)
- Unstructured documents (flat text with formatting cues)
"""

import re
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class HeadingLevel(Enum):
    """Heading hierarchy levels"""
    H1 = 1  # Chapter/Major section
    H2 = 2  # Section
    H3 = 3  # Subsection
    H4 = 4  # Minor heading
    BODY = 5  # Regular text


@dataclass
class DocumentBlock:
    """Atomic block of document content with formatting metadata"""
    text: str
    page: int
    font_size: Optional[float] = None
    is_bold: bool = False
    is_italic: bool = False
    section_id: str = "root"
    section_title: str = "Untitled"
    heading_level: Optional[HeadingLevel] = None
    position: int = 0  # Position within document
    is_table: bool = False
    is_list: bool = False
    is_caption: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            "text": self.text,
            "page": self.page,
            "font_size": self.font_size,
            "is_bold": self.is_bold,
            "is_italic": self.is_italic,
            "section_id": self.section_id,
            "section_title": self.section_title,
            "heading_level": self.heading_level.name if self.heading_level else None,
            "position": self.position,
            "is_table": self.is_table,
            "is_list": self.is_list,
            "is_caption": self.is_caption,
        }


@dataclass
class DocumentSection:
    """Hierarchical section of document"""
    section_id: str
    title: str
    heading_level: HeadingLevel
    parent_id: Optional[str] = None
    blocks: List[DocumentBlock] = None
    children: List['DocumentSection'] = None
    page_range: Tuple[int, int] = None  # (start_page, end_page)

    def __post_init__(self):
        if self.blocks is None:
            self.blocks = []
        if self.children is None:
            self.children = []

    def add_block(self, block: DocumentBlock):
        """Add a block to this section"""
        block.section_id = self.section_id
        block.section_title = self.title
        self.blocks.append(block)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "section_id": self.section_id,
            "title": self.title,
            "heading_level": self.heading_level.name,
            "parent_id": self.parent_id,
            "page_range": self.page_range,
            "block_count": len(self.blocks),
            "children": [child.to_dict() for child in self.children],
        }

    def get_flat_sections(self) -> List['DocumentSection']:
        """Get all sections in flat list (DFS), including self"""
        sections = [self]
        for child in self.children:
            sections.extend(child.get_flat_sections())
        return sections


class DocumentAnalyzer:
    """Analyze document structure and build hierarchy"""

    def __init__(self, font_size_threshold: Dict[str, float] = None):
        """
        Initialize analyzer

        Args:
            font_size_threshold: Font size ranges for heading detection
                Default: {
                    'h1': 20,  # >= 20pt
                    'h2': 16,  # >= 16pt
                    'h3': 14,  # >= 14pt
                    'body': 10  # < 14pt
                }
        """
        self.font_size_threshold = font_size_threshold or {
            'h1': 20,
            'h2': 16,
            'h3': 14,
            'body': 10,
        }
        self.section_counter = 0
        self.root_section: Optional[DocumentSection] = None
        self.section_stack: List[DocumentSection] = []
        self.body_font_size = 12  # Will be detected from actual documents

    def analyze(self, blocks: List[DocumentBlock]) -> Tuple[List[DocumentBlock], DocumentSection]:
        """
        Analyze blocks and build document hierarchy

        Args:
            blocks: List of document blocks with formatting metadata

        Returns:
            (blocks with section assignments, root section hierarchy)
        """
        if not blocks:
            return [], self._create_root_section()

        # FIRST PASS: Detect body font size and heading size patterns
        self._detect_body_font_size(blocks)

        self.root_section = self._create_root_section()
        self.section_stack = [self.root_section]

        for i, block in enumerate(blocks):
            block.position = i
            heading_level = self._detect_heading_level(block)

            if heading_level and heading_level != HeadingLevel.BODY:
                # This is a heading - create new section
                self._handle_heading(block, heading_level, blocks)
            else:
                # Regular content - add to current section
                current_section = self.section_stack[-1]
                current_section.add_block(block)

        # Update page ranges
        self._update_page_ranges(self.root_section)

        return blocks, self.root_section

    def _detect_body_font_size(self, blocks: List[DocumentBlock]) -> None:
        """
        Detect the body/paragraph font size by finding the most common font size
        in non-bold text blocks (ignoring headings, captions, etc.)
        """
        font_sizes = {}
        
        for block in blocks:
            # Skip special blocks
            if block.is_bold or block.is_caption or block.is_table or block.is_list:
                continue
            
            # Only count reasonable font sizes (9-14pt is typical body text)
            if block.font_size and 9 <= block.font_size <= 14:
                fs = round(block.font_size, 1)
                font_sizes[fs] = font_sizes.get(fs, 0) + 1
        
        # The most common font size = body text
        if font_sizes:
            self.body_font_size = max(font_sizes.items(), key=lambda x: x[1])[0]
        else:
            self.body_font_size = 12  # Default fallback

    def _create_root_section(self) -> DocumentSection:
        """Create root section"""
        return DocumentSection(
            section_id="root",
            title="Document",
            heading_level=HeadingLevel.H1,
            parent_id=None,
        )

    def _detect_heading_level(self, block: DocumentBlock) -> Optional[HeadingLevel]:
        """
        Detect if block is a heading and its level

        Uses heuristics in order of priority:
        1. Explicit heading_level from HTML/Word styles (1-6)
        2. Font size relative to detected body font size
        3. Boldness + length + font size
        4. Numbering patterns
        5. Text length and capitalization
        """
        # Skip obviously non-heading content
        if block.is_table or block.is_list or block.is_caption:
            return HeadingLevel.BODY

        # Check if block has explicit heading level from HTML/Word
        if block.heading_level is not None:
            # heading_level is an integer (1-6) from HTML h1-h6 tags or Word styles
            if isinstance(block.heading_level, int):
                level_map = {
                    1: HeadingLevel.H1,
                    2: HeadingLevel.H2,
                    3: HeadingLevel.H3,
                    4: HeadingLevel.H4,
                    5: HeadingLevel.H4,  # h5 and h6 map to H4
                    6: HeadingLevel.H4,
                }
                return level_map.get(block.heading_level, HeadingLevel.BODY)

        text = block.text.strip()
        if not text or len(text) > 200:  # Headings typically short
            return HeadingLevel.BODY

        # PRIMARY: Font size heuristic (relative to body font size)
        # This is the most reliable indicator for most documents
        if block.font_size:
            size_diff = block.font_size - self.body_font_size
            
            # If font is significantly larger than body, it's likely a heading
            if size_diff >= 8:  # +8pt or more = H1
                return HeadingLevel.H1
            elif size_diff >= 4:  # +4pt to +7pt = H2
                return HeadingLevel.H2
            elif size_diff >= 2:  # +2pt to +3pt = H3
                # But also require bold or short text for H3
                if block.is_bold or len(text) < 80:
                    return HeadingLevel.H3
            elif size_diff >= 1 and block.is_bold and len(text) < 100:  # +1pt, bold, short = H4
                return HeadingLevel.H4

        # SECONDARY: Boldness + length heuristic (more aggressive)
        if block.is_bold and len(text) < 150:
            # Bold + short text usually indicates a heading
            if len(text) < 80 and len(text.split()) < 15:
                # Shorter bold text is likely h2
                return HeadingLevel.H2
            # Bold text slightly larger than body → H3
            elif block.font_size and block.font_size > self.body_font_size:
                return HeadingLevel.H3

        # TERTIARY: Pattern matching for numbered headings
        if self._matches_heading_pattern(text):
            if re.match(r'^(Chapter|Part|Section)\s+\d+', text, re.IGNORECASE):
                return HeadingLevel.H1
            elif re.match(r'^\d+\.\s+', text):
                return HeadingLevel.H2
            elif re.match(r'^\d+\.\d+\s+', text):
                return HeadingLevel.H3
            elif re.match(r'^\d+\.\d+\.\d+\s+', text):
                return HeadingLevel.H4

        return HeadingLevel.BODY

    def _matches_heading_pattern(self, text: str) -> bool:
        """Check if text matches common heading patterns"""
        patterns = [
            r'^(Chapter|Part|Section|Introduction|Conclusion|Summary|Appendix)',
            r'^\d+\.',
            r'^(Abstract|Overview|Background)',
        ]
        return any(re.match(pattern, text, re.IGNORECASE) for pattern in patterns)

    def _handle_heading(
        self,
        block: DocumentBlock,
        heading_level: HeadingLevel,
        all_blocks: List[DocumentBlock]
    ):
        """Handle heading block - create new section"""
        section_id = f"sec_{self.section_counter}"
        self.section_counter += 1

        # Pop stack to appropriate level
        while len(self.section_stack) > heading_level.value:
            self.section_stack.pop()

        # Create new section
        parent_id = self.section_stack[-1].section_id if self.section_stack else "root"
        new_section = DocumentSection(
            section_id=section_id,
            title=block.text.strip(),
            heading_level=heading_level,
            parent_id=parent_id,
            page_range=(block.page, block.page),
        )

        # Add to parent
        if self.section_stack:
            self.section_stack[-1].children.append(new_section)

        # Push to stack
        self.section_stack.append(new_section)
        block.heading_level = heading_level
        new_section.add_block(block)

    def _update_page_ranges(self, section: DocumentSection):
        """Recursively update page ranges for all sections"""
        if section.blocks:
            pages = [b.page for b in section.blocks]
            section.page_range = (min(pages), max(pages))

        for child in section.children:
            self._update_page_ranges(child)

            # Update parent range to include children
            if child.page_range:
                if section.page_range:
                    section.page_range = (
                        min(section.page_range[0], child.page_range[0]),
                        max(section.page_range[1], child.page_range[1]),
                    )
                else:
                    section.page_range = child.page_range

    def get_flat_sections(self, section: DocumentSection = None) -> List[DocumentSection]:
        """Get all sections in flat list (DFS)"""
        if section is None:
            section = self.root_section

        sections = []
        if section != self.root_section:  # Don't include root
            sections.append(section)

        for child in section.children:
            sections.extend(self.get_flat_sections(child))

        return sections

    def print_hierarchy(self, section: DocumentSection = None, indent: int = 0):
        """Print document hierarchy for debugging"""
        if section is None:
            section = self.root_section

        if section != self.root_section:
            prefix = "  " * indent + "├─ "
            block_count = len(section.blocks)
            page_range = f"p{section.page_range[0]}-{section.page_range[1]}" if section.page_range else "?"
            logger.info(f"{prefix}[{section.heading_level.name}] {section.title} ({block_count} blocks, {page_range})")

        for child in section.children:
            self.print_hierarchy(child, indent + 1)
