# MedBridge AI: Manual Testing & Verification Guide 🏥

This guide details how to verify every component of the MedBridge AI system locally.

---

## 🛠️ Step 1: Verification Prerequisites
Ensure dependencies, package console scripts, and the NLP model are installed:
```bash
# Windows
python -m venv venv
.\venv\Scripts\activate

# Install package globally in editable mode
pip install -e .
python -m spacy download en_core_web_sm
```

---

## 🔒 Step 2: Test PII Tokenizer & Whitelist
Run the standalone self-test for the Named Entity Recognition (NER) middleware:
```bash
python security/pii_redactor.py
```

### Expected Output
The system should detect and tokenize personal details (PERSON, GPE, ORG) returning both the tokenized text and the mapping dictionary, while preserving medication names (on the drug whitelist) and dates:
* `Dr. Smith` &rarr; `Dr. [PERSON_0]` (with `[PERSON_0]` mapped to `Smith` in output dictionary)
* `New York` &rarr; `[GPE_0]`
* `Lisinopril` &rarr; `Lisinopril` (Preserved drug name!)
* `January 15` &rarr; `January 15` (Preserved date!)

---

## 🔀 Step 3: Run Interactive Modes

### 1. Launch the Interactive Web GUI Dashboard
Start the zero-dependency local HTTP server. It will automatically launch your system's default web browser:
```bash
med-ai gui
```
* **Verify Tokenization & Rehydration Loop**:
  1. Toggle **Mock Mode** on (top-right switch).
  2. Input: `"I am Alice. Check drug interactions between Aspirin and Warfarin. Call Dr. Bob next Monday."` and click **Send**.
  3. Look at the right panel **Secure Pipeline Inspector**:
     - Raw input vs sanitized input is shown.
     - **Local Token Mappings Table** shows `[PERSON_0] -> Bob` and `[PERSON_1] -> Alice`.
     - **Specialist Agent Outputs** shows both the raw response containing placeholders, and the **Re-hydrated User View** showing actual names.
     - The chat bubble itself shows the fully rehydrated text.

* **Verify OpenFDA adverse event charts**:
  1. Query: `"Check drug interactions between Aspirin and Warfarin"` (Mock or Live).
  2. Observe the **OpenFDA Adverse Events Telemetry** card appearing in the inspector panel.
  3. Verify color codes (Red for High-Frequency >=70% reactions like Hemorrhage, Amber for Moderate >=40% reactions, Green for Safe/Low-Frequency reactions).

* **Verify Zero-PII Persistent Memory**:
  1. Input a query: `"I am Alice. I am taking Aspirin."`
  2. Input a follow-up query: `"Check interaction with Warfarin."` (without repeating your name).
  3. Check the CLI console output or the local directory for `conversation_memory.json`. Ensure it records only sanitized tokens (`[PERSON_0]`) with no raw name text.
  4. Click the **Clear Memory** button in the top right of the GUI. Confirm the alert. Check `conversation_memory.json` to verify it was removed.

### 2. Launch the Interactive Terminal Console
Run `med-ai` with no parameters to launch the CLI console shell loop:
```bash
med-ai
```
* Follow the prompts to configure Mock Mode and Verbose Logging.
* Enter health queries repeatedly, and verify memory logs by executing follow-ups.
* Type `exit` to quit.

---

## 🛠️ Step 4: Run Direct Queries in Mock Mode (Offline-Safe)
Verify the CLI, Router, and Specialist Agents using built-in mock handlers. No API keys are required.

### Test A: Both Medical and Scheduling Intents
```bash
med-ai --mock "Dr. Smith prescribed Lisinopril. Remind me to take it at 8am tomorrow."
```
* **Expected Behavior**:
  1. Tokenizes `Dr. Smith` to `Dr. [PERSON_0]`.
  2. Router classifies as `BOTH`.
  3. Runs the Medical Agent *first* for safety evaluation.
  4. Runs the Scheduler Agent *second* to confirm the calendar entry.
  5. Outputs the rehydrated response (restoring `Dr. Smith` in output text).

---

## 🔌 Step 5: Test Live Mode (Requires Gemini API Key)
Once you add your `GEMINI_API_KEY` to the `.env` file, verify live API integrations and Model Context Protocol (MCP) tool execution.

### Test A: Real MCP Drug Check & Telemetry
```bash
med-ai "Are there any interactions between Aspirin and Warfarin?"
```
* **Expected Behavior**:
  1. The CLI spawns the MCP server subprocess (`mcp_server/server.py`).
  2. The Medical Agent calls the `get_drug_interactions` tool.
  3. The tool queries OpenFDA and returns real adverse reaction statistics.
  4. If run via Web GUI, custom color-coded progress bars display report percentages.

### Test B: Real Google Search Grounding (Queries Live Web)
```bash
med-ai "What is the latest CDC update on the seasonal influenza outbreak?"
```
* **Expected Behavior**:
  1. Router classifies as `MEDICAL`.
  2. The Medical Agent queries Gemini with Google Search enabled.
  3. Returns a cited response summarizing current outbreak data.
