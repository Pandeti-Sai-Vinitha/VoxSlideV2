"""
Persona Configuration for Content Generation

Defines different audience personas with customized prompt instructions
that affect how content is generated, explained, and presented.
"""

from typing import Dict, List, Optional

# Default persona if none selected
DEFAULT_PERSONA = "trainee"

# Persona definitions
PERSONAS = {
    "trainee": {
        "id": "trainee",
        "display_name": "Trainee / Maverick",
        "emoji": "🚀",
        "description": "Beginner level - needs detailed explanations, basic concepts",
        "icon": "GraduationCap",
        "default_slides": 8,
        "min_slides": 3,
        "max_slides": 20,
        "prompt_instructions": """
AUDIENCE CONTEXT: This presentation is for TRAINEES/BEGINNERS.

CONTENT GUIDELINES:
1. Explain all concepts from first principles
2. Define technical terms before using them
3. Use analogies and simple examples
4. Avoid jargon; if necessary, explain it clearly
5. Focus on "WHY" before "HOW"
6. Include step-by-step breakdowns
7. Use relatable real-world examples
8. Keep language simple and conversational
9. Provide context for every concept introduced
10. End each slide with a clear takeaway

TONE: Friendly, encouraging, supportive. Make the learner feel comfortable asking questions.
        """,
    },
    "technical": {
        "id": "technical",
        "display_name": "Technical Expert",
        "emoji": "⚙️",
        "description": "Technical depth - code samples, architecture, implementation details",
        "icon": "Code",
        "default_slides": 10,
        "min_slides": 5,
        "max_slides": 25,
        "prompt_instructions": """
AUDIENCE CONTEXT: This presentation is for TECHNICAL PROFESSIONALS/DEVELOPERS.

CONTENT GUIDELINES:
1. Include technical depth and implementation details
2. Mention architectures, frameworks, tools, and languages
3. Include code samples, APIs, or technical specifications where relevant
4. Discuss performance considerations, scalability
5. Cover edge cases and technical challenges
6. Reference best practices and design patterns
7. Include system diagrams or technical diagrams if relevant
8. Discuss trade-offs between different approaches
9. Mention version compatibility and dependencies
10. Provide resources for deeper learning

TONE: Direct, precise, technical. Assume solid foundational knowledge.
        """,
    },
    "analyst": {
        "id": "analyst",
        "display_name": "Business Analyst",
        "emoji": "📊",
        "description": "Data-driven - metrics, trends, business impact, ROI",
        "icon": "BarChart3",
        "default_slides": 9,
        "min_slides": 4,
        "max_slides": 22,
        "prompt_instructions": """
AUDIENCE CONTEXT: This presentation is for DATA/BUSINESS ANALYSTS.

CONTENT GUIDELINES:
1. Focus on metrics, KPIs, and measurable outcomes
2. Include trends, patterns, and statistical insights
3. Highlight business impact and ROI
4. Use data visualization concepts (what charts would work)
5. Discuss correlations and causation carefully
6. Include historical context and benchmarks
7. Focus on actionable insights from data
8. Mention data sources and reliability
9. Discuss limitations and biases in data
10. Provide recommendations based on analysis

TONE: Data-driven, objective, evidence-based. Focus on "what the numbers tell us."
        """,
    },
    "manager": {
        "id": "manager",
        "display_name": "Executive",
        "emoji": "👔",
        "description": "Executive summary - business value, strategy, decisions",
        "icon": "Briefcase",
        "default_slides": 6,
        "min_slides": 3,
        "max_slides": 15,
        "prompt_instructions": """
AUDIENCE CONTEXT: This presentation is for MANAGERS/EXECUTIVES.

CONTENT GUIDELINES:
1. Focus on business value and strategic impact
2. Highlight ROI, savings, revenue opportunities
3. Discuss risk mitigation and benefits
4. Keep content high-level (avoid deep technical details)
5. Include timeline and resource requirements
6. Address "so what?" and "what's next?"
7. Mention market implications and competitive advantage
8. Include clear decision points or recommendations
9. Discuss team impacts and organizational changes
10. Keep language business-oriented, not technical

TONE: Strategic, concise, business-focused. Respect their time; deliver key points quickly.
        """,
    },
    "product_manager": {
        "id": "product_manager",
        "display_name": "Product Manager",
        "emoji": "🎯",
        "description": "Feature focus - user needs, product strategy, competition",
        "icon": "Zap",
        "default_slides": 8,
        "min_slides": 4,
        "max_slides": 18,
        "prompt_instructions": """
AUDIENCE CONTEXT: This presentation is for PRODUCT MANAGERS.

CONTENT GUIDELINES:
1. Focus on user needs and user stories
2. Discuss product strategy and roadmap implications
3. Include competitive analysis where relevant
4. Highlight feature benefits and use cases
5. Discuss user experience considerations
6. Include product metrics and adoption rates
7. Address customer pain points
8. Discuss market opportunities and positioning
9. Include implementation feasibility discussion
10. Focus on "why this matters to users"

TONE: User-centric, strategic, market-aware. Balance business and user perspectives.
        """,
    },
    "sales": {
        "id": "sales",
        "display_name": "Sales / Marketing",
        "emoji": "💼",
        "description": "Customer-focused - value proposition, benefits, objection handling",
        "icon": "TrendingUp",
        "default_slides": 7,
        "min_slides": 3,
        "max_slides": 16,
        "prompt_instructions": """
AUDIENCE CONTEXT: This presentation is for SALES/MARKETING PROFESSIONALS.

CONTENT GUIDELINES:
1. Focus on customer pain points and solutions
2. Highlight value proposition and unique selling points
3. Include competitive advantages and differentiators
4. Discuss customer success stories or case studies
5. Address common objections preemptively
6. Include pricing/cost justification where relevant
7. Emphasize customer benefits, not features
8. Include call-to-action or next steps
9. Use language that resonates with customer needs
10. Include proof points (testimonials, metrics, awards)

TONE: Persuasive, customer-centric, action-oriented. Focus on outcomes and benefits.
        """,
    },
    "client": {
        "id": "client",
        "display_name": "Client / Stakeholder",
        "emoji": "🤝",
        "description": "Non-technical - clear communication, results, partnership",
        "icon": "Users",
        "default_slides": 6,
        "min_slides": 3,
        "max_slides": 14,
        "prompt_instructions": """
AUDIENCE CONTEXT: This presentation is for CLIENTS/EXTERNAL STAKEHOLDERS.

CONTENT GUIDELINES:
1. Avoid internal jargon and acronyms
2. Explain everything in business terms
3. Focus on outcomes and results
4. Discuss partnership value and mutual benefits
5. Include timeline and deliverables
6. Address stakeholder concerns and risks
7. Use clear, everyday language
8. Include success criteria and how you'll measure it
9. Show understanding of their business context
10. End with clear next steps and commitment

TONE: Professional, transparent, partnership-oriented. Build confidence and trust.
        """,
    },
}

# Domain-specific guidance that can be injected into prompts based on user selection
DOMAIN_PROMPTS = {
    "finance": "DOMAIN CONTEXT: Financial Services\n\nCONTENT GUIDELINES:\n1. Organize content into the main Financial Services segments: retail banking, corporate finance, wealth management, risk and compliance, treasury operations, and digital customer channels.\n2. Emphasize financial performance, ROI, operational efficiency, controls, and regulatory compliance across these segments.\n3. Use clear metrics, cost/benefit comparisons, risk mitigation, and business value for each part.\n4. Highlight how services connect across customer lifecycle, reporting, advisory, and risk management.\n\nTONE: Analytical, professional, business-focused, and value-driven.",
    "banking": "DOMAIN CONTEXT: Banking\n\nCONTENT GUIDELINES:\n1. Treat banking as a service ecosystem with separate parts: deposit operations, payments and transaction processing, lending and credit, compliance/KYC/AML, treasury and liquidity management, and customer experience channels.\n2. Call out the operational controls, trust, security, and reliability needed for each banking area.\n3. Use banking-specific examples for products, customer journeys, branch/digital channels, risk controls, and regulatory oversight.\n4. Focus on efficiency, resilience, customer trust, and strategic differentiation within banking operations.\n\nTONE: Structured, dependable, regulatory-aware, and customer-trust oriented.",
}


def get_available_personas() -> List[Dict]:
    """
    Get list of available personas for frontend selection.
    
    Returns:
        List of persona objects with id, name, emoji, description, default_slides, min_slides, max_slides
    """
    return [
        {
            "id": persona_id,
            "name": data["display_name"],
            "emoji": data["emoji"],
            "description": data["description"],
            "icon": data.get("icon", "User"),
            "default_slides": data.get("default_slides", 8),
            "min_slides": data.get("min_slides", 3),
            "max_slides": data.get("max_slides", 20),
        }
        for persona_id, data in PERSONAS.items()
    ]


def is_valid_persona(persona_id: str) -> bool:
    """Check if persona_id is valid."""
    return persona_id in PERSONAS


def get_persona_info(persona_id: str) -> Dict:
    """Get detailed info about a persona."""
    return PERSONAS.get(persona_id, PERSONAS["trainee"])


def get_persona_prompt_instructions(persona_id: str) -> str:
    """
    Get the prompt instructions for a specific persona.
    These should be injected into the LLM prompt to customize content generation.
    """
    persona = get_persona_info(persona_id)
    return persona.get("prompt_instructions", "").strip()


def build_persona_aware_prompt(base_prompt: str, persona_id: str, extra_instructions: Optional[str] = None, domain: Optional[str] = None) -> str:
    """
    Enhance a prompt with persona-specific instructions.
    
    Args:
        base_prompt: The original prompt
        persona_id: The selected persona ID
        extra_instructions: Additional rules or instructions supplied by the user
        
    Returns:
        Enhanced prompt with persona instructions injected
    """
    if not is_valid_persona(persona_id):
        persona_id = "trainee"
    
    persona_instructions = get_persona_prompt_instructions(persona_id)
    combined_instructions = persona_instructions

    # Inject domain-specific guidance if provided
    domain_instructions = ""
    if domain:
        # Normalize common frontend labels to internal keys
        domain_key = domain.strip().lower()
        DOMAIN_LABEL_MAP = {
            "financial services": "finance",
            "finance": "finance",
            "banking": "banking",
        }
        normalized = DOMAIN_LABEL_MAP.get(domain_key, domain_key)
        domain_instructions = DOMAIN_PROMPTS.get(normalized, f"DOMAIN CONTEXT: {domain}")
        if domain_instructions:
            combined_instructions = f"{combined_instructions}\n\n{domain_instructions}"

    # Append any explicit user-provided instructions
    if extra_instructions:
        cleaned_extra = extra_instructions.strip()
        if cleaned_extra:
            combined_instructions = f"{combined_instructions}\n\nUSER INSTRUCTIONS:\n{cleaned_extra}"
    
    enhanced_prompt = f"""{combined_instructions}

---

{base_prompt}"""
    
    return enhanced_prompt


def get_persona_slide_settings(persona_id: str) -> Dict[str, int]:
    """
    Get slide count settings for a specific persona.
    
    Args:
        persona_id: The selected persona ID
        
    Returns:
        Dict with default_slides, min_slides, max_slides
    """
    if not is_valid_persona(persona_id):
        persona_id = "trainee"
    
    persona = PERSONAS[persona_id]
    return {
        "default_slides": persona.get("default_slides", 8),
        "min_slides": persona.get("min_slides", 3),
        "max_slides": persona.get("max_slides", 20),
    }


def validate_slide_count(persona_id: str, slide_count: int) -> int:
    """
    Validate and clamp slide count within persona limits.
    
    Args:
        persona_id: The selected persona ID
        slide_count: Requested number of slides
        
    Returns:
        Validated slide count within min/max bounds
    """
    settings = get_persona_slide_settings(persona_id)
    return max(settings["min_slides"], min(slide_count, settings["max_slides"]))
