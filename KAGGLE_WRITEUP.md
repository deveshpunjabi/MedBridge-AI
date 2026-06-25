# MedBridge AI: A Secure, Multi-Agent Health Concierge 🏥

**Submission Category:** Agents for Good  
**Kaggle Competition:** [AI Agents: Intensive Vibe Coding Capstone Project](https://www.kaggle.com/competitions/vibecoding-agents-capstone-project/)  
**GitHub Repository:** [deveshpunjabi/MedBridge-AI](https://github.com/deveshpunjabi/MedBridge-AI)

---

## 🎯 Project Overview

**MedBridge AI** is a locally-deployable, security-first multi-agent system designed to act as a personal health concierge. It takes messy, natural language medical queries (e.g., doctor notes, prescription updates, or symptom questions) and safely processes them through a multi-agent pipeline to:
1. **Redact PII/PHI locally** using spaCy NLP before any text is sent to an external API.
2. **Classify user intent** using a Gemini-powered Router Agent with a strict schema JSON output.
3. **Validate drug-drug interactions** via a Medical Specialist Agent querying the live OpenFDA API through standard Model Context Protocol (MCP) tools.
4. **Ground public health queries** with native Google Search integration for up-to-date outbreak information.
5. **Schedule medication reminders** via a Scheduler Specialist Agent that interfaces with a calendar tool over MCP.

All of this is wrapped in a highly polished, production-grade console script `med-ai` supporting live model modes, a persistent interactive terminal console, a fully functional offline `--mock` mode, and a gorgeous glassmorphic local Web GUI (`med-ai gui`).

---

## 🏗️ Architecture & Data Flow

```
                      User Input (CLI / Web GUI)
                                 │
                                 ▼
                     ┌──────────────────────┐
                     │  Local PII Redactor  │  spaCy NER — masks PERSON, GPE, ORG
                     └──────────┬───────────┘
                                │ (Sanitized Text)
                                ▼
                     ┌──────────────────────┐
                     │     Router Agent     │  Gemini 2.0 — Structured Output Enum
                     └──────────┬───────────┘
                                │
                 ┌──────────────┼──────────────┐
                 ▼              ▼              ▼
            (MEDICAL)         (BOTH)      (SCHEDULER)
                 │              │              │
                 │              ├──────────────┘
                 ▼              ▼
        ┌────────────────┐ ┌────────────────┐
        │ Medical Agent  │ │Scheduler Agent │
        │ • OpenFDA MCP  │ │ • Calendar MCP │
        │ • Google Search│ │   Tool         │
        │   Grounding    │ │                │
        └────────┬───────┘ └────────┬───────┘
                 │                  │
                 └────────┬─────────┘
                          ▼ (JSON-RPC stdio transport)
        ┌───────────────────────────────────┐
        │        Local MCP Server           │  FastMCP Subprocess
        │  • get_drug_interactions          │  → OpenFDA Adverse Events API
        │  • create_calendar_event          │  → Calendar Mock
        └───────────────────────────────────┘
```

---

## 🏆 Rubric Alignment & Core Features

| Rubric Criterion | MedBridge AI Implementation | File Reference |
| :--- | :--- | :--- |
| **ADK / Agent Pattern** | Multi-agent router-specialist architecture where a Router Agent classifies intent and sequences execution of specialized agents. | [router_agent.py](file:///D:/Hackathon/5%20days%20Ai%20agents%20-%20kaggle/medbridge-ai/agents/router_agent.py) |
| **MCP Server** | A real, compliant Model Context Protocol server built with `FastMCP` that runs as a separate subprocess and communicates over stdio. | [server.py](file:///D:/Hackathon/5%20days%20Ai%20agents%20-%20kaggle/medbridge-ai/mcp_server/server.py) |
| **Security** | Local, spaCy NER-based redaction of Personally Identifiable Information (PII) before LLM queries, whitelisting to protect medical terms, and `.env` secret containment. | [pii_redactor.py](file:///D:/Hackathon/5%20days%20Ai%20agents%20-%20kaggle/medbridge-ai/security/pii_redactor.py) |
| **Grounding** | Medical Agent uses native Gemini SDK Google Search grounding to answer general public health and disease outbreak questions with web citations. | [medical_agent.py](file:///D:/Hackathon/5%20days%20Ai%20agents%20-%20kaggle/medbridge-ai/agents/medical_agent.py) |
| **CLI Deployability** | Standard-compliant `med-ai` executable registered via `setup.py` that supports query strings, file parsing, interactive console mode, and offline mock degradation. | [main.py](file:///D:/Hackathon/5%20days%20Ai%20agents%20-%20kaggle/medbridge-ai/main.py) |
| **Code Quality** | Full type hinting, modular directory structure, docstrings following PEP 257, and standard error fallback paths. | Entire codebase |

---

## 🔑 Key Technical Design Decisions

1. **PII Redaction BEFORE LLM Calls:** Many systems attempt to redact output or rely on the LLM to ignore PII. For HIPAA compliance and privacy, MedBridge AI redacts text *before* it leaves the local machine.
2. **Reverse Loop Replacements:** During spaCy entity replacement, indices shift dynamically. The redactor loops through detected entities in *reverse* order (`reversed(doc.ents)`) to keep character offsets stable.
3. **Strict Schema Intent Routing:** The Router Agent uses Gemini's JSON mode with a schema constraint enum `["MEDICAL", "SCHEDULER", "BOTH", "UNKNOWN"]`. This guarantees the output matches Python's routing logic exactly.
4. **Medication Whitelisting:** spaCy's small general model (`en_core_web_sm`) occasionally misclassifies medications like *Aspirin* or *Lisinopril* as people (`PERSON`). We built a custom medical whitelist to prevent over-redacting vital drug names.
5. **Case-Sensitive Mock Redaction Regex**: To prevent common lowercase verbs like *"taking"* from triggering entity redaction on capitalized drug names, the mock redactor matches patient identification prefixes case-insensitively using character classes, while ensuring the name matching group itself remains case-sensitive.
6. **Sequential Execution for `BOTH`:** If a query contains both medical and calendar intents, the system executes the Medical Agent *first* to verify drug safety, then proceeds to the Scheduler Agent. This safety-first sequence ensures scheduling is informed by medical checks.
7. **Built-in Local Web GUI:** Runs a lightweight web server directly out of Python's built-in `http.server` module, eliminating complex dependencies while rendering a state-of-the-art glassmorphic dashboard showcasing real-time redaction.

---

## 🚀 Getting Started & Execution

### 1. Installation
Ensure Python dependencies and spaCy language models are installed:
```bash
pip install -e .
python -m spacy download en_core_web_sm
```

### 2. Configuration
Copy the environment variables template and configure your API key:
```bash
cp .env.example .env
# Set GEMINI_API_KEY=your_gemini_api_key_here
```

### 3. Run Commands

* **Launch Web GUI**:
  ```bash
  med-ai gui
  ```

* **Launch Interactive Terminal Console**:
  ```bash
  med-ai
  ```

* **Mock Run (Offline-safe)**:
  ```bash
  med-ai --mock "I am taking Aspirin and Warfarin. Remind me to check with Dr. Jones next Monday at 10am."
  ```

* **Live Mode (Requires API Key)**:
  ```bash
  med-ai "Are there any interactions between Aspirin and Warfarin?"
  ```

* **Google Search Grounding (Live Mode)**:
  ```bash
  med-ai "What is the latest CDC update on seasonal flu outbreaks?"
  ```
