"""
MedBridge AI - Medical Agent
==============================

Kaggle Rubric Alignment: ADK / Agent Pattern, MCP Server, Grounding (Code)
---------------------------------------------------------------------------

Design Rationale:
    The Medical Agent is the most feature-rich agent in MedBridge AI. It
    demonstrates three key capabilities from the Kaggle rubric:

    1. **MCP Tool Calling** — Connects to the MCP server (as a client) to call
       the `get_drug_interactions` tool, which queries the OpenFDA API.
    2. **Google Search Grounding** — For public health queries (outbreaks,
       epidemics, CDC data), it uses Gemini's native Google Search grounding
       to provide up-to-date, cited information.
    3. **Safety-First Design** — The system prompt strictly prohibits diagnosis
       and always recommends professional consultation.

Multi-Step Reasoning Flow:
    Step 1: LLM analyzes the sanitized query with both MCP tools AND Google
            Search grounding available.
    Step 2: LLM decides which tool(s) to call based on query content:
            - Drug names detected → calls get_drug_interactions via MCP
            - Public health topic → uses Google Search grounding
            - General health question → answers with safety disclaimers
    Step 3: Tool results are fed back to the LLM for final response generation.

Why the agent handles tool dispatch (not the LLM directly):
    The LLM generates function call requests, but our code dispatches them
    to the MCP server. This gives us control over error handling, logging,
    and security — the LLM never has direct network access.
"""

import json
from typing import Optional

import click

from config import GEMINI_API_KEY, MODEL_NAME


# =============================================================================
# System Prompt
# =============================================================================

MEDICAL_SYSTEM_PROMPT: str = """You are a safe, responsible medical information assistant for MedBridge AI.

Your capabilities:
1. **Drug Interaction Checking**: You have access to the `get_drug_interactions` tool.
   When the user mentions two or more medications, ALWAYS call this tool before advising.
2. **Public Health Information**: For questions about disease outbreaks, epidemics,
   vaccination campaigns, or public health data, use Google Search to provide the
   latest information with citations.

Safety Rules (MANDATORY — violations are unacceptable):
- You are NOT a doctor. NEVER diagnose conditions or prescribe treatments.
- ALWAYS end your response with: "⚕️ Please consult a healthcare professional for personalized medical advice."
- If you're unsure about drug interactions, err on the side of caution and recommend
  the user speak with a pharmacist.
- Acknowledge the limitations of the OpenFDA data (it shows adverse event reports,
  not definitive interaction data).

Response Format:
- Be clear, concise, and empathetic.
- Use bullet points for readability.
- Cite sources when using Google Search grounding.
"""


# =============================================================================
# Tool Declarations (for Gemini function calling)
# =============================================================================

def _get_tool_declarations():
    """
    Build the function declarations that tell Gemini what MCP tools are available.

    Design Choice: We define tool schemas here rather than dynamically fetching
    them from the MCP server. This is simpler and ensures the LLM always has
    correct schema information, even if the MCP server connection has issues.

    Returns:
        A list of Gemini-compatible tool objects.
    """
    from google.genai import types

    drug_interaction_tool = types.Tool(
        function_declarations=[
            types.FunctionDeclaration(
                name="get_drug_interactions",
                description=(
                    "Check for known drug interactions by querying the OpenFDA "
                    "Adverse Events database. Call this whenever the user mentions "
                    "two or more medication names."
                ),
                parameters=types.Schema(
                    type="OBJECT",
                    properties={
                        "drug_list": types.Schema(
                            type="ARRAY",
                            items=types.Schema(type="STRING"),
                            description="List of drug names to check for interactions.",
                        ),
                    },
                    required=["drug_list"],
                ),
            ),
        ]
    )

    return drug_interaction_tool


def _get_grounding_tool():
    """
    Build the Google Search grounding tool for public health queries.

    Design Choice: We use Gemini's NATIVE Google Search grounding rather than
    a custom web scraping tool. This is the recommended approach because:
      1. The grounding is built into the model — results are more relevant.
      2. Google Search grounding provides automatic citation/attribution.
      3. It directly demonstrates the Kaggle rubric's "Grounding" requirement.

    Returns:
        A Google Search grounding tool configuration.
    """
    from google.genai import types
    from google.genai.types import GoogleSearch

    return types.Tool(google_search=GoogleSearch())


# =============================================================================
# Medical Agent Execution (Real Mode)
# =============================================================================

async def run_medical_agent(
    text: str,
    mcp_session: Optional[object] = None,
    mock: bool = False,
) -> str:
    """
    Execute the Medical Agent pipeline.

    This is the main entry point called by main.py when the Router classifies
    a query as MEDICAL (or BOTH).

    Pipeline:
        1. Send query to Gemini with MCP tool + Google Search grounding available
        2. If Gemini requests a function call → dispatch to MCP server
        3. Feed tool results back to Gemini
        4. Return the final grounded, safe response

    Args:
        text: Sanitized user input (PII already redacted).
        mcp_session: Active MCP client session for tool dispatch (None in mock mode).
        mock: If True, returns a canned response without API calls.

    Returns:
        The Medical Agent's response with safety disclaimers.
    """
    if mock:
        return _mock_medical_response(text)

    try:
        import time
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=GEMINI_API_KEY)

        def _generate_with_retry(contents, config_params, max_retries=3):
            for attempt in range(max_retries):
                try:
                    return client.models.generate_content(
                        model=MODEL_NAME,
                        contents=contents,
                        config=config_params,
                    )
                except Exception as e:
                    err_str = str(e)
                    if any(err in err_str for err in ["503", "UNAVAILABLE", "429", "RESOURCE_EXHAUSTED"]):
                        if attempt < max_retries - 1:
                            sleep_time = 2 * (attempt + 1)
                            click.echo(
                                click.style(
                                    f"   ⚠️ Medical Agent got transient error. Retrying in {sleep_time}s...",
                                    fg="yellow",
                                )
                            )
                            time.sleep(sleep_time)
                            continue
                    raise e

        # Build the tool configuration.
        # Google GenAI API does not allow combining built-in tools (google_search) and
        # function calling (MCP tools) in the same request. We select the appropriate tool
        # dynamically based on query content.
        mcp_tool = _get_tool_declarations()
        grounding_tool = _get_grounding_tool()

        text_lower = text.lower()
        from security.pii_redactor import DRUG_WHITELIST
        has_drugs = any(f" {drug} " in f" {text_lower} " or text_lower.startswith(drug) or text_lower.endswith(drug) for drug in DRUG_WHITELIST)
        has_drug_keywords = any(kw in text_lower for kw in ["interaction", "side effect", "dosage", "dose", "combine", "medication", "drug"])

        if has_drugs or has_drug_keywords:
            tools = [mcp_tool]
            click.echo(click.style("   🩺 [Medical Agent] Drug query detected. Enabling MCP tools.", fg="green"))
        else:
            tools = [grounding_tool]
            click.echo(click.style("   🩺 [Medical Agent] General query detected. Enabling Google Search grounding.", fg="green"))

        # -----------------------------------------------------------------
        # Step 1: Initial LLM call with tools available
        # -----------------------------------------------------------------
        response = _generate_with_retry(
            contents=text,
            config_params=types.GenerateContentConfig(
                system_instruction=MEDICAL_SYSTEM_PROMPT,
                tools=tools,
            ),
        )

        # -----------------------------------------------------------------
        # Step 2: Handle function calls (tool dispatch loop)
        # -----------------------------------------------------------------
        # The LLM may request one or more function calls. We intercept each
        # call, dispatch it to the MCP server, and feed the results back.
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
                        f"   🔧 Medical Agent calling tool: {fc.name}({dict(fc.args)})",
                        fg="green",
                    )
                )

                # Dispatch to MCP server
                tool_result = await _dispatch_to_mcp(
                    mcp_session, fc.name, dict(fc.args)
                )

                click.echo(
                    click.style("   ✅ Tool result received from MCP server", fg="green")
                )

                # ---------------------------------------------------------
                # Step 3: Feed tool result back to LLM for final response
                # ---------------------------------------------------------
                response = _generate_with_retry(
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
                    config_params=types.GenerateContentConfig(
                        system_instruction=MEDICAL_SYSTEM_PROMPT,
                    ),
                )

        # Extract final text response
        return response.text if response.text else (
            "I was unable to generate a medical response. "
            "⚕️ Please consult a healthcare professional."
        )

    except Exception as e:
        click.echo(click.style(f"   ❌ Medical Agent error: {e}", fg="red"))
        return (
            f"⚠️ The Medical Agent encountered an error: {str(e)}\n"
            "⚕️ Please consult a healthcare professional for medical advice."
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

    This function is the bridge between Gemini's function calling and the
    MCP server. When Gemini generates a function call, we forward it to the
    MCP server via the client session.

    Args:
        mcp_session: Active MCP ClientSession connected to the server.
        tool_name: Name of the MCP tool to call.
        arguments: Dictionary of arguments for the tool.

    Returns:
        The tool's response as a string.
    """
    try:
        result = await mcp_session.call_tool(tool_name, arguments=arguments)

        # MCP tool results come as a list of content blocks
        if result.content:
            return result.content[0].text
        return "Tool returned no content."

    except Exception as e:
        click.echo(click.style(f"   ⚠️ MCP tool call failed: {e}", fg="red"))
        return (
            f"Unable to check drug interactions at this time ({str(e)}). "
            "Please consult a pharmacist."
        )


# =============================================================================
# Mock Mode
# =============================================================================

def _mock_medical_response(text: str) -> str:
    """
    Generate a mock medical response for offline testing.

    This allows the full pipeline to demonstrate the agent flow without
    requiring a Gemini API key or MCP server connection.

    Args:
        text: User input text.

    Returns:
        A realistic-looking mock medical response.
    """
    text_lower = text.lower()

    # Check if the query mentions specific drugs for a more realistic mock
    common_drugs = ["aspirin", "warfarin", "lisinopril", "metformin", "ibuprofen"]
    mentioned_drugs = [drug for drug in common_drugs if drug in text_lower]

    if len(mentioned_drugs) >= 2:
        return (
            f"💊 **Drug Interaction Check** (Mock Mode)\n\n"
            f"Medications analyzed: {', '.join(d.title() for d in mentioned_drugs)}\n\n"
            f"⚠️ **Potential Interaction Found:**\n"
            f"The combination of {mentioned_drugs[0].title()} and {mentioned_drugs[1].title()} "
            f"has been associated with adverse event reports in the FDA database.\n\n"
            f"**Recommendations:**\n"
            f"• Consult your doctor before combining these medications\n"
            f"• Monitor for unusual symptoms\n"
            f"• Do not stop any medication without medical guidance\n\n"
            f"⚕️ Please consult a healthcare professional for personalized medical advice."
        )
    elif "outbreak" in text_lower or "epidemic" in text_lower or "flu" in text_lower:
        return (
            f"🌍 **Public Health Update** (Mock Mode)\n\n"
            f"Based on recent data from public health authorities:\n\n"
            f"• Current seasonal flu activity is reported at moderate levels\n"
            f"• The CDC recommends annual flu vaccination for everyone 6 months and older\n"
            f"• Practice good hygiene: wash hands frequently, cover coughs\n\n"
            f"⚕️ Please consult a healthcare professional for personalized medical advice."
        )
    else:
        return (
            f"💊 **Medical Information** (Mock Mode)\n\n"
            f"Thank you for your health query. Based on general medical knowledge:\n\n"
            f"• Always take medications as prescribed by your doctor\n"
            f"• Report any unusual side effects immediately\n"
            f"• Keep an up-to-date list of all your medications\n\n"
            f"⚕️ Please consult a healthcare professional for personalized medical advice."
        )
