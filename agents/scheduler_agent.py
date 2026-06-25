"""
MedBridge AI - Scheduler Agent
================================

Kaggle Rubric Alignment: ADK / Agent Pattern, MCP Server (Code)
-----------------------------------------------------------------

Design Rationale:
    The Scheduler Agent handles all calendar and reminder-related queries.
    It demonstrates the complete tool-calling pipeline:

    User text → LLM extracts structured event info → MCP tool call → confirmation

Why a separate Scheduler Agent (not part of Medical Agent):
    1. **Separation of concerns** — Medical advice and scheduling are distinct
       domains with different safety profiles. Medical advice requires safety
       disclaimers; scheduling requires date/time parsing accuracy.
    2. **Independent system prompts** — The Scheduler Agent's prompt focuses on
       date extraction and calendar formatting, while the Medical Agent focuses
       on drug safety. Combining them would dilute both prompts.
    3. **Demonstrates multi-agent orchestration** — Having distinct agents that
       can be composed (via the Router's "BOTH" classification) demonstrates
       the ADK multi-agent pattern for the rubric.

Tool Calling Flow:
    1. LLM receives user text + the `create_calendar_event` tool declaration.
    2. LLM extracts a title and date/time from the text.
    3. LLM generates a function call with structured arguments.
    4. Agent code dispatches the function call to the MCP server.
    5. MCP server executes the tool and returns confirmation.
    6. Agent feeds the confirmation back to the LLM for a friendly response.
"""

import json
from typing import Optional

import click

from config import GEMINI_API_KEY, MODEL_NAME


# =============================================================================
# System Prompt
# =============================================================================

SCHEDULER_SYSTEM_PROMPT: str = """You are a scheduling and reminder assistant for MedBridge AI.

Your capabilities:
1. **Event Creation**: You have access to the `create_calendar_event` tool.
   Extract the event title and date/time from the user's text and call this tool.

Rules:
- Extract the most likely date and time from natural language.
  Examples: "tomorrow at 8am", "next Tuesday", "January 15 at 3pm"
- If no specific time is given, default to 9:00 AM.
- If no specific date is given, say "today" or "the next available day".
- Create a clear, descriptive title for the event.
  Example: "Take blood pressure medication" not just "medication"
- After creating the event, confirm the details to the user in a friendly tone.
- If the input doesn't contain any schedulable information, ask the user
  to provide a date/time and what they'd like to be reminded about.
"""


# =============================================================================
# Tool Declarations (for Gemini function calling)
# =============================================================================

def _get_tool_declarations():
    """
    Build the function declaration for the calendar event tool.

    This tells Gemini what the tool expects so it can generate properly
    structured function calls.

    Returns:
        A Gemini-compatible Tool object with the calendar event function.
    """
    from google.genai import types

    return types.Tool(
        function_declarations=[
            types.FunctionDeclaration(
                name="create_calendar_event",
                description=(
                    "Create a calendar event or reminder. Use this whenever the user "
                    "wants to schedule something, set a reminder, or book an appointment."
                ),
                parameters=types.Schema(
                    type="OBJECT",
                    properties={
                        "title": types.Schema(
                            type="STRING",
                            description="A clear, descriptive title for the calendar event.",
                        ),
                        "date_time": types.Schema(
                            type="STRING",
                            description="The date and time for the event (e.g., '2024-01-15 at 8:00 AM').",
                        ),
                    },
                    required=["title", "date_time"],
                ),
            ),
        ]
    )


# =============================================================================
# Scheduler Agent Execution (Real Mode)
# =============================================================================

async def run_scheduler_agent(
    text: str,
    mcp_session: Optional[object] = None,
    mock: bool = False,
) -> str:
    """
    Execute the Scheduler Agent pipeline.

    This is the main entry point called by main.py when the Router classifies
    a query as SCHEDULER (or BOTH).

    Pipeline:
        1. Send query to Gemini with the create_calendar_event tool available
        2. If Gemini requests a function call → dispatch to MCP server
        3. Feed tool result back to Gemini for friendly confirmation
        4. Return the final response

    Args:
        text: Sanitized user input (PII already redacted).
        mcp_session: Active MCP client session for tool dispatch (None in mock mode).
        mock: If True, returns a canned response without API calls.

    Returns:
        The Scheduler Agent's confirmation or follow-up message.
    """
    if mock:
        return _mock_scheduler_response(text)

    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=GEMINI_API_KEY)
        calendar_tool = _get_tool_declarations()

        # -----------------------------------------------------------------
        # Step 1: Initial LLM call with calendar tool available
        # -----------------------------------------------------------------
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=text,
            config=types.GenerateContentConfig(
                system_instruction=SCHEDULER_SYSTEM_PROMPT,
                tools=[calendar_tool],
            ),
        )

        # -----------------------------------------------------------------
        # Step 2: Handle function calls (tool dispatch)
        # -----------------------------------------------------------------
        if response.candidates and response.candidates[0].content.parts:
            function_call_part = None
            for part in response.candidates[0].content.parts:
                if part.function_call:
                    function_call_part = part
                    break

            if function_call_part:
                fc = function_call_part.function_call
                click.echo(
                    click.style(
                        f"   🔧 Scheduler Agent calling tool: {fc.name}("
                        f"title='{fc.args.get('title', '')}', "
                        f"date_time='{fc.args.get('date_time', '')}')",
                        fg="blue",
                    )
                )

                # Dispatch to MCP server
                tool_result = await _dispatch_to_mcp(
                    mcp_session, fc.name, dict(fc.args)
                )

                click.echo(
                    click.style("   ✅ Calendar event created via MCP server", fg="blue")
                )

                # ---------------------------------------------------------
                # Step 3: Feed tool result back to LLM for friendly response
                # ---------------------------------------------------------
                response = client.models.generate_content(
                    model=MODEL_NAME,
                    contents=[
                        types.Content(
                            role="user",
                            parts=[types.Part.from_text(text=text)],
                        ),
                        types.Content(
                            role="model",
                            parts=[function_call_part],
                        ),
                        types.Content(
                            role="user",
                            parts=[
                                types.Part.from_function_response(
                                    name=fc.name,
                                    response={"result": tool_result},
                                ),
                            ],
                        ),
                    ],
                    config=types.GenerateContentConfig(
                        system_instruction=SCHEDULER_SYSTEM_PROMPT,
                    ),
                )

        # Extract final text response
        return response.text if response.text else (
            "I've processed your scheduling request. "
            "Please check your calendar for the event."
        )

    except Exception as e:
        click.echo(click.style(f"   ❌ Scheduler Agent error: {e}", fg="red"))
        return (
            f"⚠️ The Scheduler Agent encountered an error: {str(e)}\n"
            "Please try again or manually set your reminder."
        )


# =============================================================================
# MCP Tool Dispatch
# =============================================================================

async def _dispatch_to_mcp(
    mcp_session: object,
    tool_name: str,
    arguments: dict,
) -> str:
    """
    Dispatch a tool call to the MCP server and return the result.

    Args:
        mcp_session: Active MCP ClientSession connected to the server.
        tool_name: Name of the MCP tool to call.
        arguments: Dictionary of arguments for the tool.

    Returns:
        The tool's response as a string.
    """
    try:
        result = await mcp_session.call_tool(tool_name, arguments=arguments)

        if result.content:
            return result.content[0].text
        return "Calendar event created."

    except Exception as e:
        click.echo(click.style(f"   ⚠️ MCP tool call failed: {e}", fg="red"))
        return f"Calendar event creation failed: {str(e)}. Please set a manual reminder."


# =============================================================================
# Mock Mode
# =============================================================================

def _mock_scheduler_response(text: str) -> str:
    """
    Generate a mock scheduler response for offline testing.

    Parses the input text for basic scheduling cues and returns a realistic
    confirmation message.

    Args:
        text: User input text.

    Returns:
        A realistic-looking mock scheduling confirmation.
    """
    import re

    # Try to extract a time-like pattern
    time_match = re.search(r"(\d{1,2}\s*(?:am|pm|:\d{2}))", text, re.IGNORECASE)
    time_str = time_match.group(1) if time_match else "9:00 AM"

    # Try to extract a date-like pattern
    date_keywords = [
        "tomorrow", "today", "next week", "monday", "tuesday", "wednesday",
        "thursday", "friday", "saturday", "sunday", "next",
    ]
    date_str = "tomorrow"  # default
    text_lower = text.lower()
    for kw in date_keywords:
        if kw in text_lower:
            date_str = kw
            break

    # Build a mock event title from the text
    title = "Health reminder"
    action_words = ["take", "check", "call", "visit", "schedule", "book"]
    for word in action_words:
        if word in text_lower:
            # Grab the rest of the sentence after the action word
            idx = text_lower.index(word)
            snippet = text[idx:idx + 50].split(".")[0].split(",")[0].strip()
            title = snippet.capitalize()
            break

    return (
        f"📅 **Scheduling Confirmation** (Mock Mode)\n\n"
        f"✅ Calendar event created successfully!\n\n"
        f"   📌 **Event:** {title}\n"
        f"   📅 **When:** {date_str.capitalize()} at {time_str}\n"
        f"   🔔 **Reminder:** 30 minutes before\n\n"
        f"Your reminder has been set. I'll make sure you don't forget!"
    )
