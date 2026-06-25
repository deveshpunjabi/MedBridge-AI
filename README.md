# MedBridge AI 🏥

> **A Secure, Multi-Agent Health Concierge — Powered by Google Gemini, MCP, and spaCy NLP**

**Kaggle AI Agents Intensive Course — Capstone Project**  
**Track:** Agents for Good

---

## 🎯 What is MedBridge AI?

MedBridge AI is a locally-deployable multi-agent system that acts as a health concierge. Users input messy medical text (doctor's notes, medication questions, scheduling requests), and the system:

1. **Redacts PII** — Names, locations, and organizations are masked before any LLM call
2. **Routes intelligently** — A Router Agent classifies intent using Gemini's structured output
3. **Checks drug interactions** — A Medical Agent queries the OpenFDA API via MCP tools
4. **Grounds public health info** — Uses Google Search grounding for live outbreak data
5. **Schedules reminders** — A Scheduler Agent creates calendar events via MCP tools

All of this runs through a clean CLI interface built with `click`.

---

## 🏗️ Architecture

```
User Input (CLI)
       │
       ▼
┌──────────────┐
│ PII Redactor │  spaCy NER — masks PERSON, GPE, ORG
└──────┬───────┘
       │
       ▼
┌──────────────┐
│ Router Agent │  Gemini structured output → MEDICAL / SCHEDULER / BOTH / UNKNOWN
└──────┬───────┘
       │
       ├─────────────────┐
       ▼                 ▼
┌──────────────┐  ┌───────────────┐
│ Medical Agent│  │Scheduler Agent│
│ • Drug check │  │ • Calendar    │
│ • Google     │  │   events      │
│   Search     │  │               │
│   grounding  │  │               │
└──────┬───────┘  └───────┬───────┘
       │                  │
       └────────┬─────────┘
                ▼
┌──────────────────────┐
│ MCP Server (stdio)   │  FastMCP — real MCP protocol over subprocess
│ • get_drug_interactions  → OpenFDA API
│ • create_calendar_event  → Mock Calendar
└──────────────────────┘
```

---

## 🚀 Quick Start

### 1. Clone & Install

```bash
cd medbridge-ai
pip install -r requirements.txt
python -m spacy download en_core_web_sm
```

### 2. Configure API Key

```bash
cp .env.example .env
# Edit .env and add your Gemini API key:
# GEMINI_API_KEY=your_key_here
```

Get a free API key at: https://aistudio.google.com/apikey

### 3. Run

```bash
# With API key (real mode)
python main.py query "Check interactions between Aspirin and Warfarin"

# Without API key (mock mode)
python main.py query --mock "Dr. Smith prescribed Lisinopril and Metformin. Remind me to take them at 8am."

# From a file
python main.py query --input-file doctor_notes.txt

# Verbose output
python main.py query --mock -v "Check drug interactions for Ibuprofen and Aspirin"
```

---

## 📁 Project Structure

```
medbridge-ai/
├── main.py                  # CLI entry point (click) — orchestrates the pipeline
├── config.py                # API keys, model config, MCP server path
├── requirements.txt         # All dependencies
├── .env.example             # Template for API key (security best practice)
├── README.md                # This file
│
├── security/
│   ├── __init__.py
│   └── pii_redactor.py      # spaCy NER-based PII masking middleware
│
├── mcp_server/
│   ├── __init__.py
│   └── server.py            # Real MCP server (FastMCP, stdio transport)
│
└── agents/
    ├── __init__.py
    ├── router_agent.py       # Intent classifier (structured output)
    ├── medical_agent.py      # Drug interactions + Google Search grounding
    └── scheduler_agent.py    # Calendar event creation
```

---

## 🔑 Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| **Real MCP server over stdio** | Demonstrates actual protocol compliance, not just function imports. The server runs as a subprocess — decoupled and portable. |
| **spaCy NER for PII** (not regex) | Statistical NER understands linguistic context. "Paris" as a city vs. person name. More accurate than pattern matching. |
| **Router uses structured output** | JSON mode with enum schema guarantees valid classification. No brittle text parsing. |
| **DATE entities NOT redacted** | Dates are essential for the Scheduler Agent. Deliberate security vs. functionality trade-off. |
| **Sequential BOTH handling** | Medical Agent runs first (safety analysis), then Scheduler. Simpler and more reliable than parallel execution. |
| **Native Google Search grounding** | Built into the Gemini SDK — cleaner than a custom web scraping tool. |
| **`--mock` flag for offline mode** | Demonstrates graceful degradation. Entire pipeline runs without API keys. |

---

## 🏆 Kaggle Rubric Coverage

| Criterion | Implementation | File(s) |
|-----------|---------------|---------|
| **ADK / Agent Pattern** | Router-Specialist multi-agent architecture | `agents/*.py` |
| **MCP Server** | Real FastMCP server over stdio with 2 tools | `mcp_server/server.py` |
| **Security** | spaCy PII redaction middleware + `.env` for secrets | `security/pii_redactor.py` |
| **Grounding** | Google Search via native Gemini SDK | `agents/medical_agent.py` |
| **CLI Deployability** | Click-based CLI with file/string input | `main.py` |
| **Code Quality** | Type hints, docstrings, modular architecture | All files |
| **Error Handling** | Try/except, graceful fallbacks, mock mode | All files |

---

## 🧪 Testing the PII Redactor

```bash
python security/pii_redactor.py
```

This runs a self-test that demonstrates PII detection and redaction.

---

## 📋 Example Queries

```bash
# Drug interaction check
python main.py query "I'm taking Aspirin and Warfarin. Are there any interactions?"

# Public health query (uses Google Search grounding)
python main.py query "What is the latest on the flu outbreak in the US?"

# Scheduling
python main.py query "Remind me to check my blood pressure tomorrow at 8am"

# Combined medical + scheduling
python main.py query "Dr. Smith prescribed Metformin and Lisinopril. Schedule a follow-up for next Tuesday at 2pm."
```

---

## ⚙️ Dependencies

- `google-genai` — Google Gemini AI SDK
- `spacy` — NLP for PII redaction
- `click` — CLI framework
- `mcp` — Model Context Protocol server/client
- `requests` — HTTP client for OpenFDA
- `python-dotenv` — Environment variable loading

---

## 📜 License

Built for the Kaggle AI Agents Intensive Course capstone.
