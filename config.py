"""
MedBridge AI - Central Configuration
"""

import os
import sys
from dotenv import load_dotenv

load_dotenv()

# Gemini API Configuration
GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
MODEL_NAME: str = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

# MCP Server Configuration
MCP_SERVER_SCRIPT: str = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "mcp_server",
    "server.py",
)

PYTHON_EXECUTABLE: str = sys.executable

def validate_api_key() -> bool:
    """Check that the Gemini API key is configured."""
    return bool(GEMINI_API_KEY)
