from typing import TypedDict, List, Dict, Any, Optional
from langgraph.graph import StateGraph, END
from openai import AzureOpenAI
from Agent.tools.slide_reader import load_slides
from llm.azure_llm_service import build_llm_config
import os
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)





# ==============================
# ✅ LLM - Azure OpenAI
# ==============================
llm_config = build_llm_config(temperature=0)
azure_client = AzureOpenAI(
    api_key=llm_config['api_key'],
    api_version=llm_config['api_version'],
    base_url=f"{llm_config['endpoint']}/openai/deployments/{llm_config['model']}"
)


# ==============================
# ✅ Quiz Generation
# ==============================
def generate_quiz(slides_data: List[Dict[str, Any]], quiz_type: str = 'test', num_questions: int = 5) -> Dict[str, Any]:
    """
    Generate quiz questions based on slide content using LLM.
    Only generates two types of questions:
    - 'mcq': Multiple choice questions with 4 options
    - 'true_false': True/False questions
    
    quiz_type:
      - 'test': Challenging questions testing deep understanding and application
      - 'assignment': Comprehensive questions covering all key concepts and broader knowledge
    """
    logger.info(f"📝 Generating {quiz_type} with {num_questions} questions...")

    # Build content from all slides
    all_content = "\n\n".join([
        f"Slide {i + 1}: {slide.get('title', 'Untitled')}\n"
        f"Content: {slide.get('content', '')}"
        for i, slide in enumerate(slides_data)
    ])

    if quiz_type == 'test':
        quiz_mode_instruction = """Create CHALLENGING questions that test:
1. Deep understanding of concepts
2. Application of knowledge to new scenarios
3. Analysis and critical thinking
4. Ability to distinguish between similar concepts
Make questions focused and strategic to identify true understanding."""
    else:  # assignment
        quiz_mode_instruction = """Create COMPREHENSIVE questions that cover:
1. Core definitions and key terms
2. Main concepts and their relationships
3. Practical applications
4. Broader implications and significance
5. Real-world examples and scenarios
Make questions diverse to assess broad knowledge across all topics."""

    system_prompt = f"""You are an expert quiz generator. Based on the provided presentation content, generate exactly {num_questions} questions.

QUIZ TYPE: {quiz_type.upper()}

QUESTION TYPES (mix both types):
1. MCQ (Multiple Choice Questions): 4 options with one correct answer
2. TRUE/FALSE: Yes/No style questions

{quiz_mode_instruction}

Requirements:
1. Mix MCQ and True/False questions approximately equally
2. For MCQ: must have exactly 4 options and one correct answer
3. For True/False: questions must be a statement with true or false as answer
4. Questions should NOT be trivial - require thinking
5. Return response as valid JSON ONLY (no extra text)
6. NO typed answer questions - only MCQ or True/False

Format your response as a JSON array ONLY:
[
  {{
    "id": 1,
    "type": "mcq",
    "question": "Question text here?",
    "options": ["Option A", "Option B", "Option C", "Option D"],
    "correctAnswer": "Option A"
  }},
  {{
    "id": 2,
    "type": "true_false",
    "question": "Is this statement true?",
    "correctAnswer": true
  }},
  ...
]

IMPORTANT: Return ONLY the JSON array, nothing else."""

    try:
        response = azure_client.chat.completions.create(
            model=llm_config['model'],
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Generate {num_questions} questions from this content:\n\n{all_content}"}
            ],
            temperature=0.7,
            max_tokens=2000
        )

        logger.info("✅ Quiz generated successfully")

        # Parse response as JSON
        import json
        response_text = response.choices[0].message.content

        # Extract JSON from response (handle cases where LLM adds extra text)
        import re
        json_match = re.search(r'\[.*\]', response_text, re.DOTALL)
        if json_match:
            questions = json.loads(json_match.group())
        else:
            questions = json.loads(response_text)

        return {
            "questions": questions,
            "quiz_type": quiz_type,
            "total_questions": len(questions)
        }

    except Exception as e:
        logger.error(f"❌ Error generating quiz: {str(e)}")
        # Return fallback quiz with mixed types
        questions = []
        for i in range(num_questions):
            if i % 2 == 0:
                # MCQ
                questions.append({
                    "id": i + 1,
                    "type": "mcq",
                    "question": f"Question {i + 1}: What is the main concept?",
                    "options": ["Option A", "Option B", "Option C", "Option D"],
                    "correctAnswer": "Option A"
                })
            else:
                # True/False
                questions.append({
                    "id": i + 1,
                    "type": "true_false",
                    "question": f"Is this a key concept from the content?",
                    "correctAnswer": True
                })
        
        return {
            "questions": questions,
            "quiz_type": quiz_type,
            "total_questions": len(questions)
        }