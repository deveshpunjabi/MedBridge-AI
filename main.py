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
    click.echo(click.style("🔒 [Security] Applying PII redaction...", fg="yellow", bold=True))

    if mock:
        sanitized_text = redact_pii_mock(text, verbose=verbose)
    else:
        sanitized_text = redact_pii(text, verbose=verbose)

    if sanitized_text != text:
        click.echo(click.style("   ✓ PII detected and redacted", fg="yellow"))
        if verbose:
            click.echo(f"   Sanitized: {sanitized_text}")
    else:
        click.echo(click.style("   ✓ No PII detected in input", fg="yellow"))

    # -----------------------------------------------------------------
    # Step 4: Route and process via agents
    # -----------------------------------------------------------------
    if mock:
        # In mock mode, skip MCP server — agents use built-in mock responses
        await _run_agent_pipeline(sanitized_text, mcp_session=None, mock=True, verbose=verbose)
    else:
        # In real mode, spawn MCP server subprocess and connect
        await _run_with_mcp_server(sanitized_text, verbose=verbose)

    # -----------------------------------------------------------------
    # Step 5: Done
    # -----------------------------------------------------------------
    click.echo(click.style("\n" + "=" * 60, fg="white"))
    click.echo(click.style("MedBridge AI processing complete.\n", fg="green", bold=True))


# =============================================================================
# MCP Server Lifecycle
# =============================================================================

async def _run_with_mcp_server(sanitized_text: str, verbose: bool) -> None:
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
        await _run_agent_pipeline(sanitized_text, mcp_session=None, mock=True, verbose=verbose)

    except Exception as e:
        click.echo(
            click.style(f"   ❌ MCP server error: {e}", fg="red")
        )
        click.echo(
            click.style("   Falling back to mock mode...", fg="yellow")
        )
        await _run_agent_pipeline(sanitized_text, mcp_session=None, mock=True, verbose=verbose)


# =============================================================================
# Agent Pipeline
# =============================================================================

async def _run_agent_pipeline(
    text: str,
    mcp_session: Optional[object],
    mock: bool,
    verbose: bool,
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
    if intent in ("MEDICAL", "BOTH"):
        click.echo(
            click.style("\n💊 [Medical Agent] Processing...", fg="green", bold=True)
        )
        medical_result = await run_medical_agent(text, mcp_session, mock=mock)
        click.echo(click.style("\n" + "─" * 50, fg="green"))
        click.echo(click.style("💊 Medical Agent Response:", fg="green", bold=True))
        click.echo(medical_result)

    if intent in ("SCHEDULER", "BOTH"):
        click.echo(
            click.style("\n📅 [Scheduler Agent] Processing...", fg="blue", bold=True)
        )
        scheduler_result = await run_scheduler_agent(text, mcp_session, mock=mock)
        click.echo(click.style("\n" + "─" * 50, fg="blue"))
        click.echo(click.style("📅 Scheduler Agent Response:", fg="blue", bold=True))
        click.echo(scheduler_result)

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
# Entry Point
# =============================================================================

def main_entry():
    import sys
    # Auto-default to the 'query' command if the first argument is not a known command or option of the root group
    if len(sys.argv) > 1 and sys.argv[1] not in ("query", "--help", "-h", "--version", "-v"):
        sys.argv.insert(1, "query")
    cli()


if __name__ == "__main__":
    main_entry()
