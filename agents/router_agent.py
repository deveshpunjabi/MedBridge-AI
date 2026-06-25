"""
MedBridge AI - Router Agent (Intent Classifier)

Classifies sanitized user queries into routing categories:
MEDICAL, SCHEDULER, BOTH, or UNKNOWN.
"""

import json
from typing import Optional
import click
from config import GEMINI_API_KEY, MODEL_NAME

ROUTER_SYSTEM_PROMPT: str = """You are a healthcare intent routing agent for MedBridge AI.

Your ONLY job is to classify the user's input into exactly ONE of these categories:

- MEDICAL: The input mentions medications, drugs, symptoms, diseases, health conditions,
  drug interactions, side effects, or public health topics (outbreaks, epidemics, CDC).
  
- SCHEDULER: The input mentions dates, times, appointments, reminders, "remind me",
  "schedule", "book", or any calendar-related action.
  
- BOTH: The input contains BOTH medical content AND scheduling/reminder intent.
  
- UNKNOWN: The input is unclear, unrelated to health or scheduling, or you cannot
  confidently classify it.

Rules:
1. Respond ONLY with the classification. No explanations.
2. When in doubt between MEDICAL and BOTH, prefer BOTH.
3. Greetings or casual chat should be classified as UNKNOWN.
"""

async def classify_intent(text: str, mock: bool = False, raw_query: Optional[str] = None) -> str:
    """Classify the user's input into a routing category."""
    query_to_check = raw_query if raw_query else text
    if mock:
        return _classify_intent_mock(query_to_check)

    # Local keyword check to bypass API calls for simple queries
    local_intent = _classify_intent_mock(query_to_check)
    if local_intent != "UNKNOWN":
        click.echo(
            click.style(
                f"   ✓ Router classified locally: {local_intent}",
                fg="cyan",
            )
        )
        return local_intent

    click.echo(
        click.style(
            "   🤖 Query is ambiguous — using Gemini for classification...",
            fg="cyan",
        )
    )

    import time
    from google import genai
    from google.genai import types
    from rate_limiter import wait_for_rate_limit

    try:
        client = genai.Client(api_key=GEMINI_API_KEY)
    except Exception as e:
        click.echo(click.style(f"   ⚠️ Client initialization error: {e}", fg="red"))
        return "MEDICAL"

    max_retries = 3
    for attempt in range(max_retries):
        try:
            wait_for_rate_limit()

            response = client.models.generate_content(
                model=MODEL_NAME,
                contents=query_to_check,
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

            result = json.loads(response.text)
            intent = result.get("intent", "UNKNOWN")

            valid_intents = {"MEDICAL", "SCHEDULER", "BOTH", "UNKNOWN"}
            if intent not in valid_intents:
                intent = "MEDICAL"

            return intent

        except Exception as e:
            err_str = str(e)
            if any(err in err_str for err in ["503", "UNAVAILABLE", "429", "RESOURCE_EXHAUSTED"]):
                if attempt < max_retries - 1:
                    sleep_time = 32 * (attempt + 1)
                    click.echo(
                        click.style(
                            f"   ⚠️ Router Agent got rate-limited. Retrying in {sleep_time}s...",
                            fg="yellow",
                        )
                    )
                    time.sleep(sleep_time)
                    continue
                click.echo(
                    click.style(
                        "   ⚠️ Gemini quota exhausted. Falling back to local classification.",
                        fg="yellow",
                    )
                )
                return "MEDICAL"

            click.echo(click.style(f"   ⚠️ Router Agent error: {e}", fg="red"))
            return "MEDICAL"

def _classify_intent_mock(text: str) -> str:
    """Keyword-based intent classification for offline testing."""
    text_lower = text.lower()

    medical_keywords = [
        "drug", "medication", "medicine", "prescription", "symptom",
        "interaction", "side effect", "aspirin", "warfarin", "lisinopril",
        "metformin", "ibuprofen", "dose", "diagnosis", "condition",
        "outbreak", "epidemic", "flu", "covid", "cdc", "health",
    ]
    has_medical = any(kw in text_lower for kw in medical_keywords)

    scheduler_keywords = [
        "remind", "schedule", "appointment", "calendar", "book",
        "tomorrow", "next week", "o'clock",
        "monday", "tuesday", "wednesday", "thursday", "friday",
        "saturday", "sunday",
    ]
    
    import re
    has_scheduler = any(kw in text_lower for kw in scheduler_keywords)
    if not has_scheduler:
        has_scheduler = bool(re.search(r"\bat\s+\d{1,2}\s*(?:am|pm)", text_lower))
        if not has_scheduler:
            has_scheduler = bool(re.search(r"\d{1,2}:\d{2}", text_lower))

    if has_medical and has_scheduler:
        return "BOTH"
    elif has_medical:
        return "MEDICAL"
    elif has_scheduler:
        return "SCHEDULER"
    else:
        return "UNKNOWN"
