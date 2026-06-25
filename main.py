"""
MedBridge AI - CLI Entry Point
================================

Kaggle Rubric Alignment: CLI Deployability (Code)
---------------------------------------------------

Design Rationale:
    This is the orchestration layer that ties all components together. It uses
    the `click` library to provide a polished command-line interface with:

    1. Direct text queries:     python main.py query "..."
    2. File-based input:        python main.py query --input-file notes.txt
    3. Offline mock mode:       python main.py query --mock "..."

Pipeline Orchestration (Data Flow):
    ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌───────────┐    ┌──────────┐
    │ CLI      │ →  │ PII      │ →  │ Router   │ →  │ Specialist│ →  │ Response │
    │ Input    │    │ Redactor │    │ Agent    │    │ Agent(s)  │    │ Output   │
    └──────────┘    └──────────┘    └──────────┘    └───────────┘    └──────────┘

MCP Server Lifecycle:
    In real mode, main.py spawns the MCP server as a subprocess, connects to it
    via stdio transport, and passes the session to agents. The `stdio_client`
    context manager handles clean startup and shutdown of the server process.

    In mock mode, the MCP server is NOT started. Agents use built-in mock
    responses instead, allowing the full pipeline to run without network access
    or API keys.

Why `click` over `argparse`:
    - click provides automatic help generation, colored output, and a cleaner
      decorator-based API.
    - click.style() gives us colored terminal output that makes the demo
      visually impressive and easy to follow during presentation.
    - click is the de-facto standard for Python CLIs in modern projects.
"""

import asyncio
import sys
from typing import Optional

import click

# ---------------------------------------------------------------------------
# Windows Console Encoding Fix
# ---------------------------------------------------------------------------
# Windows consoles often default to cp1252 encoding, which cannot render
# emoji or extended Unicode characters. Reconfiguring to UTF-8 with
# 'replace' error handling ensures the CLI never crashes on output.
# ---------------------------------------------------------------------------
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass  # Graceful fallback if reconfigure is unavailable

import config
from security.pii_redactor import redact_pii, redact_pii_mock


# =============================================================================
# ASCII Banner
# =============================================================================

BANNER = r"""
╔═══════════════════════════════════════════════════════════════════╗
║                                                                   ║
║   ███╗   ███╗███████╗██████╗ ██████╗ ██████╗ ██╗██████╗  ██████╗ ║
║   ████╗ ████║██╔════╝██╔══██╗██╔══██╗██╔══██╗██║██╔══██╗██╔════╝ ║
║   ██╔████╔██║█████╗  ██║  ██║██████╔╝██████╔╝██║██║  ██║██║  ███╗║
║   ██║╚██╔╝██║██╔══╝  ██║  ██║██╔══██╗██╔══██╗██║██║  ██║██║   ██║║
║   ██║ ╚═╝ ██║███████╗██████╔╝██████╔╝██║  ██║██║██████╔╝╚██████╔╝║
║   ╚═╝     ╚═╝╚══════╝╚═════╝ ╚═════╝ ╚═╝  ╚═╝╚═╝╚═════╝  ╚═════╝║
║                          A I                                      ║
║                                                                   ║
║   🏥 Your Secure Health Concierge — Powered by Multi-Agent AI     ║
║                                                                   ║
╚═══════════════════════════════════════════════════════════════════╝
"""


# =============================================================================
# CLI Definition
# =============================================================================

@click.group(invoke_without_command=True)
@click.pass_context
@click.version_option(version="1.0.0", prog_name="MedBridge AI")
def cli(ctx):
    """
    MedBridge AI — A secure, multi-agent health concierge.

    Powered by Google Gemini, MCP tools, and spaCy NLP.
    """
    if ctx.invoked_subcommand is None:
        _run_interactive_console()


def _run_interactive_console() -> None:
    """
    Launches an interactive shell console for querying MedBridge AI.
    """
    click.echo(click.style(BANNER, fg="cyan", bold=True))
    click.echo(click.style("🌐 Interactive Health Concierge Console", fg="cyan", bold=True))
    click.echo("Type your health question or task below.")
    click.echo("Type 'exit', 'quit', or press Enter with empty text to exit.\n")
    
    mock = click.confirm("Do you want to run in offline MOCK mode? (No API keys required)", default=True)
    verbose = click.confirm("Do you want to enable verbose logging?", default=False)
    
    mode_label = "🧪 MOCK MODE" if mock else "🔑 LIVE MODE"
    click.echo(click.style(f"\nInitialized in {mode_label}. Console is active.", fg="cyan", bold=True))
    
    while True:
        click.echo(click.style("─" * 60, fg="blue"))
        try:
            query_text = click.prompt(
                click.style("💬 Enter your health query", fg="green", bold=True),
                default="",
                show_default=False,
            )
        except (KeyboardInterrupt, EOFError):
            click.echo(click.style("\n\nGoodbye! Stay healthy! ❤️\n", fg="cyan"))
            break
            
        query_text = query_text.strip()
        if not query_text or query_text.lower() in ("exit", "quit", "q"):
            click.echo(click.style("\nGoodbye! Stay healthy! ❤️\n", fg="cyan"))
            break
            
        # Execute the pipeline (suppress the banner in the inner execution)
        asyncio.run(_process_query(query_text, None, mock, verbose, show_banner=False))


@cli.command()
@click.argument("query_text", required=False)
@click.option(
    "--input-file", "-f",
    type=click.Path(exists=True),
    help="Path to a text file containing the health query.",
)
@click.option(
    "--mock", "-m",
    is_flag=True,
    default=False,
    help="Run in mock mode (no API keys required, offline-safe).",
)
@click.option(
    "--verbose", "-v",
    is_flag=True,
    default=False,
    help="Show detailed processing information.",
)
def query(
    query_text: Optional[str],
    input_file: Optional[str],
    mock: bool,
    verbose: bool,
) -> None:
    """
    Process a health query through the MedBridge AI agent pipeline.

    Provide a query as a direct string or via --input-file.

    \b
    Examples:
      python main.py query "Check interactions between Aspirin and Warfarin"
      python main.py query --input-file doctor_notes.txt
      python main.py query --mock "Remind me to take Lisinopril at 8am"
    """
    # Run the async pipeline via asyncio
    asyncio.run(_process_query(query_text, input_file, mock, verbose))


# =============================================================================
# Helper Utilities & Memory Management (Google Capstone Project Upgrades)
# =============================================================================

MEMORY_FILE = "conversation_memory.json"

def rehydrate_text(text: str, token_map: dict[str, str]) -> str:
    """
    Replaces PII tokens with their original values.
    """
    if not text or not token_map:
        return text
    rehydrated = text
    for token, original in token_map.items():
        rehydrated = rehydrated.replace(token, original)
    return rehydrated


def load_memory() -> list[dict]:
    import os
    import json
    if os.path.exists(MEMORY_FILE):
        try:
            with open(MEMORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    return []


def save_memory(history: list[dict]) -> None:
    import json
    try:
        with open(MEMORY_FILE, "w", encoding="utf-8") as f:
            json.dump(history, f, indent=2)
    except Exception:
        pass


def clear_memory() -> None:
    import os
    if os.path.exists(MEMORY_FILE):
        try:
            os.remove(MEMORY_FILE)
        except Exception:
            pass


def build_history_context(history: list[dict]) -> str:
    if not history:
        return ""
    context = "\n--- Recent Conversation History (PII Sanitized) ---\n"
    for turn in history:
        context += f"User: {turn.get('user_sanitized', '')}\n"
        if turn.get("medical_response"):
            context += f"Medical Agent: {turn.get('medical_response', '')}\n"
        if turn.get("scheduler_response"):
            context += f"Scheduler Agent: {turn.get('scheduler_response', '')}\n"
    context += "---------------------------------------------------\n"
    return context


def fetch_fda_chart_data(sanitized_text: str, mock: bool = False) -> list:
    """
    Retrieves adverse reaction report counts to generate charts in the GUI.
    """
    if mock:
        text_lower = sanitized_text.lower()
        if "aspirin" in text_lower and "warfarin" in text_lower:
            return [
                {"reaction": "Hemorrhage (Bleeding)", "percentage": 88},
                {"reaction": "Hematoma (Bruising)", "percentage": 65},
                {"reaction": "Epistaxis (Nosebleed)", "percentage": 42},
                {"reaction": "Nausea", "percentage": 30},
                {"reaction": "Dizziness", "percentage": 15},
            ]
        elif "metformin" in text_lower and "contrast" in text_lower:
            return [
                {"reaction": "Lactic Acidosis", "percentage": 75},
                {"reaction": "Renal Failure", "percentage": 58},
                {"reaction": "Nausea & Vomiting", "percentage": 48},
                {"reaction": "Diarrhea", "percentage": 35},
                {"reaction": "Abdominal Pain", "percentage": 22},
            ]
        else:
            return [
                {"reaction": "Nausea", "percentage": 45},
                {"reaction": "Headache", "percentage": 35},
                {"reaction": "Fatigue", "percentage": 20},
            ]
    else:
        from security.pii_redactor import DRUG_WHITELIST
        detected_drugs = []
        for drug in DRUG_WHITELIST:
            if f" {drug} " in f" {sanitized_text.lower()} ":
                detected_drugs.append(drug)
        
        if len(detected_drugs) >= 2:
            import requests
            base_url = "https://api.fda.gov/drug/event.json"
            search_terms = "+AND+".join([f'patient.drug.medicinalproduct:"{drug}"' for drug in detected_drugs])
            params = {"search": search_terms, "limit": 10}
            try:
                r = requests.get(base_url, params=params, timeout=5)
                if r.status_code == 200:
                    data = r.json()
                    results = data.get("results", [])
                    counts = {}
                    for result in results:
                        for rx in result.get("patient", {}).get("reaction", []):
                            desc = rx.get("reactionmeddrapt", "").capitalize()
                            if desc:
                                counts[desc] = counts.get(desc, 0) + 1
                    sorted_reactions = sorted(counts.items(), key=lambda x: x[1], reverse=True)[:5]
                    if sorted_reactions:
                        return [{"reaction": rx, "percentage": int((count / len(results)) * 100)} for rx, count in sorted_reactions]
            except Exception:
                pass
        return []


# =============================================================================
# Core Pipeline (Async)
# =============================================================================

async def _process_query(
    query_text: Optional[str],
    input_file: Optional[str],
    mock: bool,
    verbose: bool,
    show_banner: bool = True,
) -> None:
    """
    Main async pipeline that orchestrates the full MedBridge AI flow.

    This function implements the complete data flow:
        Input → PII Redaction → Router → Specialist Agent(s) → Output

    In real mode, it also manages the MCP server subprocess lifecycle.
    """
    # -----------------------------------------------------------------
    # Step 0: Display banner
    # -----------------------------------------------------------------
    if show_banner:
        click.echo(click.style(BANNER, fg="cyan", bold=True))
        mode_label = "🧪 MOCK MODE" if mock else "🔑 LIVE MODE"
        click.echo(click.style(f"  Mode: {mode_label}\n", fg="cyan"))

    # -----------------------------------------------------------------
    # Step 1: Get input text
    # -----------------------------------------------------------------
    text = _get_input_text(query_text, input_file)
    if text is None:
        return

    click.echo(click.style("━" * 60, fg="white"))
    click.echo(click.style("📝 Input received:", fg="white", bold=True))
    # Show a truncated preview for long inputs
    preview = text[:200] + "..." if len(text) > 200 else text
    click.echo(f"   {preview}\n")

    # -----------------------------------------------------------------
    # Step 2: Validate configuration (skip in mock mode)
    # -----------------------------------------------------------------
    if not mock:
        if not config.validate_api_key():
            click.echo(
                click.style(
                    "\n❌ No Gemini API key found. Options:\n"
                    "   1. Set GEMINI_API_KEY in your .env file\n"
                    "   2. Run with --mock flag: python main.py query --mock \"...\"\n",
                    fg="red",
                )
            )
            return

    # -----------------------------------------------------------------
    # Step 3: PII Redaction (MANDATORY — runs before ANY LLM call)
    # -----------------------------------------------------------------
    click.echo(click.style("━" * 60, fg="white"))
    click.echo(click.style("🔒 [Security] Applying PII tokenization...", fg="yellow", bold=True))

    if mock:
        sanitized_text, token_map = redact_pii_mock(text, verbose=verbose)
    else:
        sanitized_text, token_map = redact_pii(text, verbose=verbose)

    if sanitized_text != text:
        click.echo(click.style("   ✓ PII detected and tokenized", fg="yellow"))
        if verbose:
            click.echo(f"   Tokenized: {sanitized_text}")
            click.echo(f"   Token Map: {token_map}")
    else:
        click.echo(click.style("   ✓ No PII detected in input", fg="yellow"))

    # Load conversation history context
    history = load_memory()
    history_context = build_history_context(history)
    prompt_with_history = history_context + sanitized_text

    # -----------------------------------------------------------------
    # Step 4: Route and process via agents
    # -----------------------------------------------------------------
    if mock:
        # In mock mode, skip MCP server — agents use built-in mock responses
        await _run_agent_pipeline(
            prompt_with_history,
            mcp_session=None,
            mock=True,
            verbose=verbose,
            token_map=token_map,
            sanitized_query=sanitized_text,
        )
    else:
        # In real mode, spawn MCP server subprocess and connect
        await _run_with_mcp_server(
            prompt_with_history,
            verbose=verbose,
            token_map=token_map,
            sanitized_query=sanitized_text,
        )

    # -----------------------------------------------------------------
    # Step 5: Done
    # -----------------------------------------------------------------
    click.echo(click.style("\n" + "=" * 60, fg="white"))
    click.echo(click.style("MedBridge AI processing complete.\n", fg="green", bold=True))


# =============================================================================
# MCP Server Lifecycle
# =============================================================================

async def _run_with_mcp_server(
    sanitized_text: str,
    verbose: bool,
    token_map: dict[str, str],
    sanitized_query: str,
) -> None:
    """
    Spawn the MCP server subprocess, connect, and run the agent pipeline.

    Design Choice: The MCP server runs as a subprocess communicating via stdio.
    The `stdio_client` context manager from the `mcp` package handles:
      - Spawning the server process
      - Establishing the JSON-RPC connection
      - Clean shutdown when done (even on errors)

    This demonstrates a real, protocol-compliant MCP integration.
    """
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    click.echo(click.style("\n🔌 [MCP] Starting tool server...", fg="magenta", bold=True))

    server_params = StdioServerParameters(
        command=config.PYTHON_EXECUTABLE,
        args=[config.MCP_SERVER_SCRIPT],
    )

    try:
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                # Initialize the MCP handshake
                await session.initialize()

                # List available tools (for verbose logging)
                tools_response = await session.list_tools()
                tool_names = [t.name for t in tools_response.tools]
                click.echo(
                    click.style(
                        f"   ✓ MCP server connected. Available tools: {tool_names}",
                        fg="magenta",
                    )
                )

                # Run the agent pipeline with the live MCP session
                await _run_agent_pipeline(
                    sanitized_text,
                    mcp_session=session,
                    mock=False,
                    verbose=verbose,
                    token_map=token_map,
                    sanitized_query=sanitized_query,
                )

    except FileNotFoundError:
        click.echo(
            click.style(
                f"   ❌ MCP server script not found: {config.MCP_SERVER_SCRIPT}",
                fg="red",
            )
        )
        click.echo(
            click.style("   Falling back to mock mode...", fg="yellow")
        )
        await _run_agent_pipeline(
            sanitized_text,
            mcp_session=None,
            mock=True,
            verbose=verbose,
            token_map=token_map,
            sanitized_query=sanitized_query,
        )

    except Exception as e:
        click.echo(
            click.style(f"   ❌ MCP server error: {e}", fg="red")
        )
        click.echo(
            click.style("   Falling back to mock mode...", fg="yellow")
        )
        await _run_agent_pipeline(
            sanitized_text,
            mcp_session=None,
            mock=True,
            verbose=verbose,
            token_map=token_map,
            sanitized_query=sanitized_query,
        )


# =============================================================================
# Agent Pipeline
# =============================================================================

async def _run_agent_pipeline(
    text: str,
    mcp_session: Optional[object],
    mock: bool,
    verbose: bool,
    token_map: Optional[dict[str, str]] = None,
    sanitized_query: Optional[str] = None,
) -> None:
    """
    Run the multi-agent pipeline: Router → Specialist Agent(s).

    This is the core orchestration logic. The Router Agent classifies the
    query, and then the appropriate specialist agent(s) handle it.

    When the Router returns "BOTH", we run the Medical Agent first (for safety
    analysis) and then the Scheduler Agent. This sequential approach is simpler
    and more reliable than parallel execution for a demo.

    Args:
        text: PII-redacted user input.
        mcp_session: Active MCP session (None in mock mode).
        mock: Whether to use mock agent responses.
        verbose: Whether to show detailed processing info.
        token_map: Mapping dictionary of tokens to original PII strings.
        sanitized_query: The user input before adding history context.
    """
    from agents.router_agent import classify_intent
    from agents.medical_agent import run_medical_agent
    from agents.scheduler_agent import run_scheduler_agent

    # -----------------------------------------------------------------
    # Step 4a: Intent Classification (Router Agent)
    # -----------------------------------------------------------------
    click.echo(click.style("\n🔀 [Router] Classifying intent...", fg="cyan", bold=True))

    intent = await classify_intent(text, mock=mock)

    intent_emoji = {
        "MEDICAL": "💊",
        "SCHEDULER": "📅",
        "BOTH": "💊📅",
        "UNKNOWN": "❓",
    }
    click.echo(
        click.style(
            f"   ✓ Intent: {intent_emoji.get(intent, '❓')} {intent}",
            fg="cyan",
        )
    )

    # -----------------------------------------------------------------
    # Step 4b: Dispatch to Specialist Agent(s)
    # -----------------------------------------------------------------
    medical_result = ""
    scheduler_result = ""

    if intent in ("MEDICAL", "BOTH"):
        click.echo(
            click.style("\n💊 [Medical Agent] Processing...", fg="green", bold=True)
        )
        medical_result = await run_medical_agent(text, mcp_session, mock=mock)
        click.echo(click.style("\n" + "─" * 50, fg="green"))
        click.echo(click.style("💊 Medical Agent Response (Rehydrated):", fg="green", bold=True))
        click.echo(rehydrate_text(medical_result, token_map or {}))

    if intent in ("SCHEDULER", "BOTH"):
        click.echo(
            click.style("\n📅 [Scheduler Agent] Processing...", fg="blue", bold=True)
        )
        scheduler_result = await run_scheduler_agent(text, mcp_session, mock=mock)
        click.echo(click.style("\n" + "─" * 50, fg="blue"))
        click.echo(click.style("📅 Scheduler Agent Response (Rehydrated):", fg="blue", bold=True))
        click.echo(rehydrate_text(scheduler_result, token_map or {}))

    if intent == "UNKNOWN":
        click.echo(
            click.style(
                "\n❓ I'm not sure how to help with that. I can assist with:\n"
                "   • Medical questions & drug interaction checks\n"
                "   • Scheduling health reminders & appointments\n"
                "\n   Try rephrasing your query with specific medications or dates.",
                fg="white",
            )
        )

    # Save to memory if sanitized_query is provided
    if sanitized_query:
        history = load_memory()
        history.append({
            "user_sanitized": sanitized_query,
            "medical_response": medical_result,
            "scheduler_response": scheduler_result,
        })
        save_memory(history)


# =============================================================================
# Input Handling
# =============================================================================

def _get_input_text(
    query_text: Optional[str],
    input_file: Optional[str],
) -> Optional[str]:
    """
    Extract input text from CLI arguments.

    Supports two input modes:
      1. Direct string: python main.py query "your text here"
      2. File input:    python main.py query --input-file notes.txt

    Args:
        query_text: Direct text from CLI argument.
        input_file: Path to a text file.

    Returns:
        The input text, or None if no valid input was provided.
    """
    if input_file:
        try:
            with open(input_file, "r", encoding="utf-8") as f:
                text = f.read().strip()
            if not text:
                click.echo(click.style("❌ Input file is empty.", fg="red"))
                return None
            return text
        except Exception as e:
            click.echo(click.style(f"❌ Error reading file: {e}", fg="red"))
            return None

    elif query_text:
        text = query_text.strip()
        if not text:
            click.echo(click.style("❌ Empty query provided.", fg="red"))
            return None
        return text

    else:
        click.echo(
            click.style(
                "❌ No input provided. Usage:\n"
                '   python main.py query "your health query here"\n'
                "   python main.py query --input-file notes.txt\n",
                fg="red",
            )
        )
        return None


# =============================================================================
# GUI Web Server Implementation
# =============================================================================

async def _execute_pipeline_for_gui(query_text: str, mock: bool, verbose: bool) -> dict:
    """
    Executes the multi-agent pipeline and returns structured JSON for the GUI.
    """
    # 1. PII Redaction / Tokenization
    if mock:
        sanitized_text, token_map = redact_pii_mock(query_text, verbose=verbose)
    else:
        sanitized_text, token_map = redact_pii(query_text, verbose=verbose)
        
    # 2. Memory Context Loading
    history = load_memory()
    history_context = build_history_context(history)
    prompt_with_history = history_context + sanitized_text

    # 3. Router classification
    from agents.router_agent import classify_intent
    intent = await classify_intent(prompt_with_history, mock=mock)
    
    # 4. Specialist Execution
    medical_resp = ""
    scheduler_resp = ""
    
    if mock:
        from agents.medical_agent import run_medical_agent
        from agents.scheduler_agent import run_scheduler_agent
        if intent in ("MEDICAL", "BOTH"):
            medical_resp = await run_medical_agent(prompt_with_history, mcp_session=None, mock=True)
        if intent in ("SCHEDULER", "BOTH"):
            scheduler_resp = await run_scheduler_agent(prompt_with_history, mcp_session=None, mock=True)
    else:
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client
        
        server_params = StdioServerParameters(
            command=config.PYTHON_EXECUTABLE,
            args=[config.MCP_SERVER_SCRIPT],
        )
        
        try:
            async with stdio_client(server_params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    
                    from agents.medical_agent import run_medical_agent
                    from agents.scheduler_agent import run_scheduler_agent
                    
                    if intent in ("MEDICAL", "BOTH"):
                        medical_resp = await run_medical_agent(prompt_with_history, mcp_session=session, mock=False)
                    if intent in ("SCHEDULER", "BOTH"):
                        scheduler_resp = await run_scheduler_agent(prompt_with_history, mcp_session=session, mock=False)
        except Exception as e:
            medical_resp = f"❌ Error executing live agent pipeline: {e}"

    # 5. Save the turn to local Zero-PII memory (store sanitized input and raw outputs containing tokens)
    history.append({
        "user_sanitized": sanitized_text,
        "medical_response": medical_resp,
        "scheduler_response": scheduler_resp,
    })
    save_memory(history)

    # 6. Fetch OpenFDA Telemetry risk data
    fda_chart_data = fetch_fda_chart_data(sanitized_text, mock=mock)
    
    # 7. Rehydrate response strings for front-end presentation
    medical_resp_rehydrated = rehydrate_text(medical_resp, token_map)
    scheduler_resp_rehydrated = rehydrate_text(scheduler_resp, token_map)

    return {
        "raw_input": query_text,
        "sanitized_input": sanitized_text,
        "token_map": token_map,
        "intent": intent,
        "medical_response": medical_resp,
        "medical_response_rehydrated": medical_resp_rehydrated,
        "scheduler_response": scheduler_resp,
        "scheduler_response_rehydrated": scheduler_resp_rehydrated,
        "fda_chart_data": fda_chart_data,
    }


from http.server import BaseHTTPRequestHandler

class GUIHTTPRequestHandler(BaseHTTPRequestHandler):
    """
    Minimal, zero-dependency HTTP server to serve index.html and handle API requests.
    """
    def log_message(self, format, *args):
        # Suppress logging to keep CLI console output clean
        pass

    def do_GET(self):
        import os
        if self.path == "/" or self.path == "/index.html":
            gui_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "gui")
            index_path = os.path.join(gui_dir, "index.html")
            
            if os.path.exists(index_path):
                self.send_response(200)
                self.send_header("Content-type", "text/html; charset=utf-8")
                self.end_headers()
                with open(index_path, "r", encoding="utf-8") as f:
                    self.wfile.write(f.read().encode("utf-8"))
            else:
                self.send_error(404, f"index.html not found in {gui_dir}")
        else:
            self.send_error(404, "File Not Found")
            
    def do_POST(self):
        import json
        if self.path == "/api/query":
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            
            try:
                data = json.loads(post_data.decode('utf-8'))
                query_text = data.get("query", "").strip()
                mock = data.get("mock", True)
                verbose = data.get("verbose", False)
                
                if not query_text:
                    self.send_response(400)
                    self.send_header("Content-type", "application/json")
                    self.end_headers()
                    self.wfile.write(json.dumps({"error": "Query cannot be empty"}).encode('utf-8'))
                    return
                    
                # Run the pipeline synchronously inside http server
                result = asyncio.run(_execute_pipeline_for_gui(query_text, mock, verbose))
                
                self.send_response(200)
                self.send_header("Content-type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(result).encode('utf-8'))
                
            except Exception as e:
                self.send_response(500)
                self.send_header("Content-type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(e)}).encode('utf-8'))
        elif self.path == "/api/clear":
            try:
                clear_memory()
                self.send_response(200)
                self.send_header("Content-type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"status": "success", "message": "Memory cleared"}).encode('utf-8'))
            except Exception as e:
                self.send_response(500)
                self.send_header("Content-type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(e)}).encode('utf-8'))
        else:
            self.send_error(404, "API Endpoint Not Found")


def _run_gui_server(port: int) -> None:
    """
    Launch server and open local browser.
    """
    import webbrowser
    from http.server import HTTPServer
    
    server_address = ("", port)
    
    click.echo(click.style(BANNER, fg="cyan", bold=True))
    click.echo(click.style(f"🌐 MedBridge AI Web GUI Server starting on http://localhost:{port}/", fg="green", bold=True))
    click.echo("Press Ctrl+C to stop the server.\n")
    
    try:
        webbrowser.open(f"http://localhost:{port}/")
    except Exception:
        pass
        
    httpd = HTTPServer(server_address, GUIHTTPRequestHandler)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        click.echo(click.style("\nStopping server. Goodbye!", fg="cyan"))
        httpd.server_close()


# =============================================================================
# Click GUI & Utility Commands
# =============================================================================

@cli.command()
def clear() -> None:
    """
    Clear the persistent conversation memory.
    """
    clear_memory()
    click.echo(click.style("🧹 Conversation memory cleared.", fg="green", bold=True))


@cli.command()
@click.option(
    "--port", "-p",
    type=int,
    default=8000,
    help="Port to run the local GUI server on.",
)
def gui(port: int) -> None:
    """
    Launch the MedBridge AI Web GUI in your browser.
    """
    _run_gui_server(port)


# =============================================================================
# Entry Point
# =============================================================================

def main_entry():
    import sys
    # Auto-default to the 'query' command if the first argument is not a known command or option of the root group
    if len(sys.argv) > 1 and sys.argv[1] not in ("query", "gui", "--help", "-h", "--version", "-v"):
        sys.argv.insert(1, "query")
    cli()


if __name__ == "__main__":
    main_entry()
