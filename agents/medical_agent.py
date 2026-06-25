"""
MedBridge AI - Medical Agent

Handles medical queries by checking drug interactions via MCP or
utilizing Google Search grounding for public health requests.
"""

import json
from typing import Optional
import click
from config import GEMINI_API_KEY, MODEL_NAME

MEDICAL_SYSTEM_PROMPT: str = """You are a safe, responsible medical information assistant for MedBridge AI.

Capabilities:
1. **Drug Interaction Checking**: Use `get_drug_interactions` tool when user mentions two or more medications.
2. **Public Health Information**: For outbreaks, epidemics, or public health data, search Google for cited updates.

Safety Rules:
- NEVER diagnose conditions or prescribe treatments.
- ALWAYS end response with: "⚕️ Please consult a healthcare professional for personalized medical advice."
- Acknowledge FDA report limitations (reports show co-occurrences, not definitive interactions).
"""

def _get_tool_declarations():
    from google.genai import types
    return types.Tool(
        function_declarations=[
            types.FunctionDeclaration(
                name="get_drug_interactions",
                description="Check for known drug interactions by querying the OpenFDA database.",
                parameters=types.Schema(
                    type="OBJECT",
                    properties={
                        "drug_list": types.Schema(
                            type="ARRAY",
                            items=types.Schema(type="STRING"),
                            description="List of drug names to check.",
                        ),
                    },
                    required=["drug_list"],
                ),
            ),
        ]
    )

def _get_grounding_tool():
    from google.genai import types
    from google.genai.types import GoogleSearch
    return types.Tool(google_search=GoogleSearch())

async def run_medical_agent(
    text: str,
    mcp_session: Optional[object] = None,
    mock: bool = False,
) -> str:
    """Execute the Medical Agent pipeline."""
    if mock:
        return _mock_medical_response(text)

    try:
        import time
        from google import genai
        from google.genai import types
        from rate_limiter import wait_for_rate_limit

        client = genai.Client(api_key=GEMINI_API_KEY)

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
                                    f"   ⚠️ Medical Agent got rate-limited. Retrying in {sleep_time}s...",
                                    fg="yellow",
                                )
                            )
                            time.sleep(sleep_time)
                            continue
                    raise e

        # Partition tools dynamically to avoid combining custom declarations and search grounding
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

        # Step 1: Initial generation call
        response = _generate_with_retry(
            contents=text,
            config_params=types.GenerateContentConfig(
                system_instruction=MEDICAL_SYSTEM_PROMPT,
                tools=tools,
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
                        f"   🔧 Medical Agent calling tool: {fc.name}({dict(fc.args)})",
                        fg="green",
                    )
                )

                tool_result = await _dispatch_to_mcp(mcp_session, fc.name, dict(fc.args))
                click.echo(click.style("   ✅ Tool result received from MCP server", fg="green"))

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
                            system_instruction=MEDICAL_SYSTEM_PROMPT,
                        ),
                    )
                except Exception:
                    click.echo(click.style("   ⚠️ Rehydration failed. Formatting tool result directly.", fg="yellow"))
                    return _format_tool_result_fallback(fc.name, dict(fc.args), tool_result)

        return response.text if response.text else "Unable to generate medical response. ⚕️ Please consult a professional."

    except Exception as e:
        click.echo(click.style(f"   ❌ Medical Agent error: {e}", fg="red"))
        return f"⚠️ Medical Agent error: {str(e)}\n⚕️ Please consult a healthcare professional."

def _format_tool_result_fallback(tool_name: str, args: dict, tool_result: str) -> str:
    """Format MCP tool results into a human-readable response upon quota exhaustion."""
    if tool_name == "get_drug_interactions":
        drugs = args.get("drug_list", [])
        drug_names = ", ".join(d.title() for d in drugs) if drugs else "the requested drugs"
        return (
            f"💊 **Drug Interaction Report** (Direct from OpenFDA)\n\n"
            f"**Medications checked:** {drug_names}\n\n"
            f"**OpenFDA Results:**\n{tool_result}\n\n"
            f"**Important Notes:**\n"
            f"• This data comes from FDA adverse event reports\n"
            f"• It shows reported co-occurrences, not definitive interactions\n"
            f"• Always discuss medication combinations with your doctor\n\n"
            f"⚕️ Please consult a healthcare professional for personalized medical advice."
        )
    return f"📋 **Tool Result** ({tool_name})\n\n{tool_result}\n\n⚕️ Please consult a healthcare professional."

async def _dispatch_to_mcp(mcp_session: object, tool_name: str, arguments: dict) -> str:
    try:
        result = await mcp_session.call_tool(tool_name, arguments=arguments)
        if result.content:
            return result.content[0].text
        return "Tool returned no content."
    except Exception as e:
        click.echo(click.style(f"   ⚠️ MCP tool call failed: {e}", fg="red"))
        return f"Unable to check drug interactions ({str(e)}). Please consult a pharmacist."

def _mock_medical_response(text: str) -> str:
    text_lower = text.lower()
    common_drugs = ["aspirin", "warfarin", "lisinopril", "metformin", "ibuprofen"]
    mentioned_drugs = [drug for drug in common_drugs if drug in text_lower]

    if len(mentioned_drugs) >= 2:
        return (
            f"💊 **Drug Interaction Check** (Mock Mode)\n\n"
            f"Medications analyzed: {', '.join(d.title() for d in mentioned_drugs)}\n\n"
            f"⚠️ **Potential Interaction Found:**\n"
            f"The combination of {mentioned_drugs[0].title()} and {mentioned_drugs[1].title()} "
            f"has been associated with adverse event reports in the FDA database.\n\n"
            f"⚕️ Please consult a healthcare professional for personalized medical advice."
        )
    elif any(kw in text_lower for kw in ["outbreak", "epidemic", "flu"]):
        return (
            f"🌍 **Public Health Update** (Mock Mode)\n\n"
            f"• Seasonal flu activity is reported at moderate levels.\n"
            f"• The CDC recommends annual vaccinations for everyone over 6 months.\n\n"
            f"⚕️ Please consult a healthcare professional for personalized medical advice."
        )
    return (
        f"💊 **Medical Information** (Mock Mode)\n\n"
        f"• Take medications exactly as prescribed.\n"
        f"• Keep an up-to-date medication list.\n\n"
        f"⚕️ Please consult a healthcare professional for personalized medical advice."
    )
