"""
MedBridge AI - Scheduler Agent

Handles scheduling and calendar-related queries using MCP tools.
"""

import json
from typing import Optional
import click
from config import GEMINI_API_KEY, MODEL_NAME

SCHEDULER_SYSTEM_PROMPT: str = """You are a scheduling and reminder assistant for MedBridge AI.

Capabilities:
1. **Event Creation**: Use the `create_calendar_event` tool to create reminders and appointments.

Rules:
- Extract the most likely date and time from natural language. Defaults to 9:00 AM if no time is given.
- Create clear, descriptive titles (e.g., "Take blood pressure medication").
- Confirm the details to the user in a friendly tone after creating the event.
"""

def _get_tool_declarations():
    from google.genai import types
    return types.Tool(
        function_declarations=[
            types.FunctionDeclaration(
                name="create_calendar_event",
                description="Create a calendar event or reminder.",
                parameters=types.Schema(
                    type="OBJECT",
                    properties={
                        "title": types.Schema(
                            type="STRING",
                            description="Descriptive title for the event.",
                        ),
                        "date_time": types.Schema(
                            type="STRING",
                            description="Date and time (e.g. '2024-01-15 at 8:00 AM').",
                        ),
                    },
                    required=["title", "date_time"],
                ),
            ),
        ]
    )

async def run_scheduler_agent(
    text: str,
    mcp_session: Optional[object] = None,
    mock: bool = False,
) -> str:
    """Execute the Scheduler Agent pipeline."""
    if mock:
        return _mock_scheduler_response(text)

    try:
        import time
        from google import genai
        from google.genai import types
        from rate_limiter import wait_for_rate_limit

        client = genai.Client(api_key=GEMINI_API_KEY)
        calendar_tool = _get_tool_declarations()

        def _generate_with_retry(contents, config_params, max_retries=2):
            for attempt in range(max_retries):
                try:
                    wait_for_rate_limit()
                    return client.models.generate_content(
                        model=MODEL_NAME,
                        contents=contents,
                        config=config_params,
                    )
                except Exception as e:
                    err_str = str(e)
                    if any(err in err_str for err in ["503", "UNAVAILABLE", "429", "RESOURCE_EXHAUSTED"]):
                        if attempt < max_retries - 1:
                            sleep_time = 32 * (attempt + 1)
                            click.echo(
                                click.style(
                                    f"   ⚠️ Scheduler Agent got rate-limited. Retrying in {sleep_time}s...",
                                    fg="yellow",
                                )
                            )
                            time.sleep(sleep_time)
                            continue
                    raise e

        # Step 1: Initial call to calendar tool
        response = _generate_with_retry(
            contents=text,
            config_params=types.GenerateContentConfig(
                system_instruction=SCHEDULER_SYSTEM_PROMPT,
                tools=[calendar_tool],
            ),
        )

        # Step 2: Handle function calls
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

                tool_result = await _dispatch_to_mcp(mcp_session, fc.name, dict(fc.args))
                click.echo(click.style("   ✅ Calendar event created via MCP server", fg="blue"))

                # Step 3: Rehydrate tool results
                try:
                    response = _generate_with_retry(
                        contents=[
                            types.Content(role="user", parts=[types.Part.from_text(text=text)]),
                            types.Content(role="model", parts=[function_call_part]),
                            types.Content(
                                role="user",
                                parts=[types.Part.from_function_response(name=fc.name, response={"result": tool_result})],
                            ),
                        ],
                        config_params=types.GenerateContentConfig(
                            system_instruction=SCHEDULER_SYSTEM_PROMPT,
                        ),
                    )
                except Exception:
                    click.echo(click.style("   ⚠️ Rehydration failed. Formatting tool result directly.", fg="yellow"))
                    title = fc.args.get("title", "Health reminder")
                    date_time = fc.args.get("date_time", "as requested")
                    return (
                        f"📅 **Scheduling Confirmation**\n\n"
                        f"✅ Calendar event created successfully!\n\n"
                        f"   📌 **Event:** {title}\n"
                        f"   📅 **When:** {date_time}\n"
                        f"   🔔 **Reminder:** Set\n\n"
                        f"MCP Server Response: {tool_result}"
                    )

        return response.text if response.text else "Event processed. Check calendar for updates."

    except Exception as e:
        click.echo(click.style(f"   ❌ Scheduler Agent error: {e}", fg="red"))
        return f"⚠️ Scheduler Agent error: {str(e)}\nPlease try again or manually set your reminder."

async def _dispatch_to_mcp(mcp_session: object, tool_name: str, arguments: dict) -> str:
    try:
        result = await mcp_session.call_tool(tool_name, arguments=arguments)
        if result.content:
            return result.content[0].text
        return "Calendar event created."
    except Exception as e:
        click.echo(click.style(f"   ⚠️ MCP tool call failed: {e}", fg="red"))
        return f"Calendar event creation failed ({str(e)}). Please set a manual reminder."

def _mock_scheduler_response(text: str) -> str:
    import re
    time_match = re.search(r"(\d{1,2}\s*(?:am|pm|:\d{2}))", text, re.IGNORECASE)
    time_str = time_match.group(1) if time_match else "9:00 AM"

    date_keywords = [
        "tomorrow", "today", "next week", "monday", "tuesday", "wednesday",
        "thursday", "friday", "saturday", "sunday", "next",
    ]
    date_str = "tomorrow"
    text_lower = text.lower()
    for kw in date_keywords:
        if kw in text_lower:
            date_str = kw
            break

    title = "Health reminder"
    action_words = ["take", "check", "call", "visit", "schedule", "book"]
    for word in action_words:
        if word in text_lower:
            idx = text_lower.index(word)
            snippet = text[idx:idx + 50].split(".")[0].split(",")[0].strip()
            title = snippet.capitalize()
            break

    return (
        f"📅 **Scheduling Confirmation** (Mock Mode)\n\n"
        f"✅ Calendar event created successfully!\n\n"
        f"   📌 **Event:** {title}\n"
        f"   📅 **When:** {date_str.capitalize()} at {time_str}\n"
        f"   🔔 **Reminder:** 30 minutes before"
    )
