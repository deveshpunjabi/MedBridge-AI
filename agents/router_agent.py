"""
MedBridge AI - Router Agent (Intent Classifier)
=================================================

Kaggle Rubric Alignment: ADK / Agent Pattern (Code)
-----------------------------------------------------

Design Rationale:
    The Router Agent is the FIRST agent in the pipeline. It receives sanitized
    user input (post-PII-redaction) and classifies the intent into one of four
    categories: MEDICAL, SCHEDULER, BOTH, or UNKNOWN.

Why a dedicated Router Agent (not hardcoded rules):
    1. **LLM-powered classification** — The router uses Gemini to understand
       natural language intent, not brittle keyword matching. "I need to refill
       my heart pills next Tuesday" contains BOTH medical and scheduling intent,
       which keyword rules would struggle with.
    2. **Structured output** — We use Gemini's JSON response mode with a
       constrained schema to guarantee the output is a valid enum value.
       This eliminates the need for fragile text parsing.
    3. **Separation of concerns** — The router ONLY classifies. It does not
       answer questions, call tools, or generate medical advice. This follows
       the Single Responsibility Principle and makes the system easier to audit.

Why structured output over free-text parsing:
    Free-text classification (e.g., parsing "I think this is medical") is
    brittle and can fail silently. JSON mode with an enum schema guarantees
    the LLM returns exactly one of our valid categories, making the routing
    decision deterministic and testable.

Routing Logic:
    - MEDICAL   → Query contains drug names, symptoms, health conditions,
                   or public health questions.
    - SCHEDULER → Query contains dates, times, "remind me", or scheduling intent.
    - BOTH      → Query contains both medical content AND scheduling intent.
    - UNKNOWN   → Query is unclear, off-topic, or cannot be classified.
"""

import json
from typing import Optional

import click

from config import GEMINI_API_KEY, MODEL_NAME

# =============================================================================
# System Prompt
# =============================================================================

ROUTER_SYSTEM_PROMPT: str = """You are a healthcare intent routing agent for MedBridge AI.

Your ONLY job is to classify the user's input into exactly ONE of these categories:

- MEDICAL: The input mentions medications, drugs, symptoms, diseases, health conditions,
  drug interactions, side effects, or public health topics (outbreaks, epidemics, CDC).
  
- SCHEDULER: The input mentions dates, times, appointments, reminders, "remind me",
  "schedule", "book", or any calendar-related action.
  
- BOTH: The input contains BOTH medical content AND scheduling/reminder intent.
  Example: "Remind me to take Lisinopril at 8am" (drug name + scheduling).
  
- UNKNOWN: The input is unclear, unrelated to health or scheduling, or you cannot
  confidently classify it.

Rules:
1. Respond ONLY with the classification. No explanations.
2. When in doubt between MEDICAL and BOTH, prefer BOTH (safer — ensures both agents run).
3. Greetings or casual chat should be classified as UNKNOWN.
"""


# =============================================================================
# Intent Classification (Real Mode)
# =============================================================================

async def classify_intent(text: str, mock: bool = False) -> str:
    """
    Classify the user's input into a routing category.

    This function is the entry point of the multi-agent pipeline. After PII
    redaction, main.py calls this to determine which specialist agent(s)
    should handle the query.

    Args:
        text: Sanitized user input (PII already redacted).
        mock: If True, uses keyword matching instead of LLM.

    Returns:
        One of: "MEDICAL", "SCHEDULER", "BOTH", "UNKNOWN"
    """
    if mock:
        return _classify_intent_mock(text)

    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=GEMINI_API_KEY)

        # Use JSON mode with a constrained schema to guarantee valid output.
        # The response_schema ensures Gemini can ONLY return one of our
        # four valid intent categories.
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=text,
            config=types.GenerateContentConfig(
                system_instruction=ROUTER_SYSTEM_PROMPT,
                response_mime_type="application/json",
                response_schema={
                    "type": "OBJECT",
                    "properties": {
                        "intent": {
                            "type": "STRING",
                            "enum": ["MEDICAL", "SCHEDULER", "BOTH", "UNKNOWN"],
                        }
                    },
                    "required": ["intent"],
                },
            ),
        )

        # Parse the structured JSON response
        result = json.loads(response.text)
        intent = result.get("intent", "UNKNOWN")

        # Defensive validation — should never trigger with schema constraints,
        # but we validate anyway (defense in depth).
        valid_intents = {"MEDICAL", "SCHEDULER", "BOTH", "UNKNOWN"}
        if intent not in valid_intents:
            click.echo(
                click.style(
                    f"   ⚠️ Router returned unexpected intent '{intent}', defaulting to MEDICAL",
                    fg="yellow",
                )
            )
            intent = "MEDICAL"  # Safe default — medical queries get more careful handling

        return intent

    except Exception as e:
        click.echo(
            click.style(f"   ⚠️ Router Agent error: {e}", fg="red")
        )
        click.echo(
            click.style("   Defaulting to MEDICAL for safety.", fg="yellow")
        )
        return "MEDICAL"


# =============================================================================
# Mock Classification (for --mock mode)
# =============================================================================

def _classify_intent_mock(text: str) -> str:
    """
    Keyword-based intent classification for offline testing.

    This mock implementation allows the full pipeline to run without a
    Gemini API key. It uses simple keyword matching, which is sufficient
    to demonstrate the routing flow during a demo.

    Args:
        text: User input text.

    Returns:
        Classified intent string.
    """
    text_lower = text.lower()

    # Check for medical keywords
    medical_keywords = [
        "drug", "medication", "medicine", "prescription", "symptom",
        "interaction", "side effect", "aspirin", "warfarin", "lisinopril",
        "metformin", "ibuprofen", "dose", "diagnosis", "condition",
        "outbreak", "epidemic", "flu", "covid", "cdc", "health",
    ]
    has_medical = any(kw in text_lower for kw in medical_keywords)

    # Check for scheduling keywords
    scheduler_keywords = [
        "remind", "schedule", "appointment", "calendar", "book",
        "tomorrow", "next week", "at ", "am", "pm", "o'clock",
        "monday", "tuesday", "wednesday", "thursday", "friday",
        "saturday", "sunday",
    ]
    has_scheduler = any(kw in text_lower for kw in scheduler_keywords)

    if has_medical and has_scheduler:
        return "BOTH"
    elif has_medical:
        return "MEDICAL"
    elif has_scheduler:
        return "SCHEDULER"
    else:
        return "UNKNOWN"
