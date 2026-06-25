# MedBridge AI: A Secure, Multi-Agent Health Concierge 🏥

**Submission Category:** Agents for Good  
**Kaggle Competition:** [AI Agents: Intensive Vibe Coding Capstone Project](https://www.kaggle.com/competitions/vibecoding-agents-capstone-project/)  
**GitHub Repository:** [deveshpunjabi/MedBridge-AI](https://github.com/deveshpunjabi/MedBridge-AI)

---

## 🎯 Project Overview

**MedBridge AI** is a locally-deployable, security-first multi-agent system designed to act as a personal health concierge. It takes messy, natural language medical queries (e.g., doctor notes, prescription updates, or symptom questions) and safely processes them through a multi-agent pipeline to:
1. 🔒 **Tokenize PII/PHI locally** using spaCy NER preceding LLM transmission, mapping names and locations to dynamic index placeholders (e.g. `[PERSON_0]`).
2. 🔄 **Rehydrate output response strings** locally on the client interface to display real names post-execution, preventing unencrypted data flight to external models.
3. 🔀 **Classify user intent** using a Gemini-powered Router Agent with strict schema constraints to dispatch queries to specialized agent endpoints.
4. 🧠 **Track multi-turn conversation memory** securely, saving only tokenized turns to prevent local database privacy leaks.
5. 💊 **Validate drug interactions** via a Medical Specialist Agent calling a stdio-based FastMCP server querying the live OpenFDA API.
6. 📊 **Visualize adverse event risks** dynamically using progress bars and risk color-coding inside the local Web GUI dashboard.
7. 🌐 **Ground public health inquiries** using native Gemini Google Search grounding for real-time citations.

All of this is wrapped in a highly polished Click CLI `med-ai`, a persistent interactive shell loop, an offline-safe `--mock` mode, and a gorgeous glassmorphic local Web GUI (`med-ai gui`).

---

## 🏗️ Architecture & Data Flow

```
                      User Input (CLI / Web GUI)
                                 │
                                 ▼
                     ┌──────────────────────┐
                     │ Local PII Tokenizer  │  spaCy NER — maps entities to [PERSON_0] etc.
                     └──────────┬───────────┘
                                │ (Sanitized Query Text + History Context)
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
        └─────────────────┬─────────────────┘
                          │ (Sanitized Output)
                          ▼
                     ┌──────────────────────┐
                     │ Re-hydration Loop    │  Restores original names using local map
                     └──────────┬───────────┘
                                │
                                ▼
                     User Output Display & FDA Charts
```

---

## 🏆 Rubric Alignment & Core Features

| Rubric Criterion | MedBridge AI Implementation | File Reference |
| :--- | :--- | :--- |
| **ADK / Agent Pattern** | Multi-agent router-specialist architecture where a Router Agent classifies intent and sequences execution of specialized agents. | [router_agent.py](file:///D:/Hackathon/5%20days%20Ai%20agents%20-%20kaggle/medbridge-ai/agents/router_agent.py) |
| **MCP Server** | A standard-compliant Model Context Protocol server built with `FastMCP` that runs as a separate subprocess and communicates over stdio JSON-RPC. | [server.py](file:///D:/Hackathon/5%20days%20Ai%20agents%20-%20kaggle/medbridge-ai/mcp_server/server.py) |
| **Security** | Local, spaCy NER-based tokenization of PII before LLM queries, rehydration loop, drug whitelist, and `.env` secret containment. | [pii_redactor.py](file:///D:/Hackathon/5%20days%20Ai%20agents%20-%20kaggle/medbridge-ai/security/pii_redactor.py) |
| **Grounding** | Medical Agent uses native Gemini SDK Google Search grounding to answer general public health and disease outbreak questions with web citations. | [medical_agent.py](file:///D:/Hackathon/5%20days%20Ai%20agents%20-%20kaggle/medbridge-ai/agents/medical_agent.py) |
| **CLI Deployability** | Standard-compliant `med-ai` executable registered via `setup.py` that supports query strings, file parsing, interactive console mode, and offline mock degradation. | [main.py](file:///D:/Hackathon/5%20days%20Ai%20agents%20-%20kaggle/medbridge-ai/main.py) |
| **Code Quality** | Full type hinting, modular directory structure, docstrings following PEP 257, and standard error fallback paths. | Entire codebase |

---

## 🔑 Key Technical Design Decisions

1. **PII Tokenization & Rehydration Loop**: destructively redacting names confusingly breaks downstream context. Tokenization preserves entity relationships (e.g. `[PERSON_0]` vs `[PERSON_1]`) while letting local re-hydration present customized user output post-execution.
2. **Zero-PII Local History Memory**: Multi-turn conversation state is saved safely to `conversation_memory.json` by only storing the sanitized inputs (tokens) and raw agent responses. No PII resides in the persistent database.
3. **OpenFDA Chart Telemetry**: Rather than dumping massive JSON text logs in the browser, the Web GUI parses FDA response counts to build visual HTML risk bars, showing high/medium/low probability warnings in colors.
4. **Safety Sequencing**: If intent is classified as `BOTH`, the system calls the Medical Specialist Agent first to verify medication compatibility before triggering scheduling tools.
5. **Robust spaCy Whitelisting**: Simple NER tools mistake medications (like *Aspirin*) for `PERSON` entities. We built a custom medical whitelist filter to prevent over-redaction of medical terms.
6. **Case-Sensitive Mock NER Regex**: Character classes verify greeting names follow specific prefixes case-insensitively, while ensuring the name extraction group enforces case-sensitive capitalization (protecting lowercase verbs from redaction).

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

* **Clear Conversation History**:
  ```bash
  med-ai clear
  ```

* **Mock Run (Offline-safe)**:
  ```bash
  med-ai --mock "I am Alice. Check drug interactions between Aspirin and Warfarin. Call Dr. Bob next Monday."
  ```

* **Live Mode (Requires API Key)**:
  ```bash
  med-ai "Are there any interactions between Aspirin and Warfarin?"
  ```
