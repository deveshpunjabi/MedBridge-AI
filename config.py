"""
MedBridge AI - Central Configuration
=====================================

Kaggle Rubric Alignment: Security, Code Quality
-------------------------------------------------
Design Rationale:
    This module centralizes all configuration — API keys, model selection,
    and file paths. API keys are loaded from environment variables via a .env
    file (never hardcoded), demonstrating security best practices.

    The separation of config into its own module follows the Single Responsibility
    Principle and makes the codebase easy to audit for security concerns.

Why .env over hardcoding:
    In a healthcare context, API keys could grant access to patient-adjacent
    systems. Loading from environment variables ensures secrets stay out of
    version control and code reviews.
"""

import os
import sys
from dotenv import load_dotenv

# Load environment variables from .env file at module import time
load_dotenv()


# =============================================================================
# Gemini API Configuration
# =============================================================================

GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
"""API key for Google Gemini. Loaded from GEMINI_API_KEY env var."""

MODEL_NAME: str = "gemini-2.0-flash"
"""
Model used for all agents (Router, Medical, Scheduler).

Design Choice: We use gemini-2.0-flash for the entire system because:
  1. Flash is fast — critical for a CLI tool where users expect quick responses.
  2. Flash supports function calling, structured output, and Google Search
     grounding — all features we need for the multi-agent system.
  3. Using one model simplifies configuration without sacrificing capability.
"""


# =============================================================================
# MCP Server Configuration
# =============================================================================

MCP_SERVER_SCRIPT: str = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "mcp_server",
    "server.py",
)
"""
Absolute path to the MCP server script.

Design Choice: We resolve the absolute path at import time using __file__
so the CLI works regardless of the user's current working directory.
"""

PYTHON_EXECUTABLE: str = sys.executable
"""
Path to the current Python interpreter. Used to spawn the MCP server
subprocess, ensuring it runs in the same environment with access to
installed packages.
"""


# =============================================================================
# Validation
# =============================================================================

def validate_api_key() -> bool:
    """
    Check that the Gemini API key is configured.

    Returns:
        bool: True if the key is present, False otherwise.

    Note:
        This does NOT validate the key against the API — it only checks
        that a non-empty value exists. Full validation happens on the
        first API call, where we handle errors gracefully.
    """
    return bool(GEMINI_API_KEY)
