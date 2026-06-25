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

## 🔒 Step 2: Test PII Redactor (Local Security Gate)
Run the standalone self-test for the Named Entity Recognition (NER) middleware:
```bash
python security/pii_redactor.py
```

### Expected Output
The system should detect and redact personal details (PERSON, GPE, ORG) while preserving medication names (on the drug whitelist) and dates:
* `Dr. Smith` &rarr; `Dr. [REDACTED_PERSON]`
* `New York` &rarr; `[REDACTED_LOCATION]`
* `Lisinopril` &rarr; `Lisinopril` (Preserved drug name!)
* `January 15` &rarr; `January 15` (Preserved date!)

---

## 🔀 Step 3: Run Interactive Modes

### 1. Launch the Interactive Web GUI Dashboard
Start the zero-dependency local HTTP server. It will automatically launch your system's default web browser:
```bash
med-ai gui
```
* **Verify Web Operations**:
  1. Toggle **Mock Mode** on (top-right switch).
  2. Input: `"I am taking Aspirin and Warfarin. Remind me to check with Dr. Jones next Monday at 10am."` and click **Send**.
  3. Look at the right panel **Secure Pipeline Inspector**:
     - Raw input vs sanitized input is shown (verifying PII redaction happened first).
     - Intent is badge-labeled as `BOTH`.
     - Output cards for both Medical Agent and Scheduler Agent appear correctly.

### 2. Launch the Interactive Terminal Console
Run `med-ai` with no parameters to launch the CLI console shell loop:
```bash
med-ai
```
* Follow the prompts to configure Mock Mode and Verbose Logging.
* Enter health queries repeatedly, and type `exit` to quit.

---

## 🛠️ Step 4: Run Direct Queries in Mock Mode (Offline-Safe)
Verify the CLI, Router, and Specialist Agents using built-in mock handlers. No API keys are required.

### Test A: Medical Interaction Intent
```bash
med-ai --mock "Check drug interactions for Ibuprofen and Aspirin"
```
* **Expected Behavior**: 
  1. Router classifies as `MEDICAL`.
  2. Medical Agent returns a mock interaction report highlighting Ibuprofen and Aspirin.

### Test B: Scheduling Intent
```bash
med-ai --mock "Remind me to check my blood pressure tomorrow at 8am"
```
* **Expected Behavior**:
  1. Router classifies as `SCHEDULER`.
  2. Scheduler Agent extracts event details and confirms the calendar entry.

### Test C: Both Medical and Scheduling Intents
```bash
med-ai --mock "Dr. Smith prescribed Lisinopril. Remind me to take it at 8am tomorrow."
```
* **Expected Behavior**:
  1. Redacts `Dr. Smith` to `Dr. [REDACTED_PERSON]`.
  2. Router classifies as `BOTH`.
  3. Runs the Medical Agent *first* for safety evaluation.
  4. Runs the Scheduler Agent *second* to confirm the calendar entry.

---

## 🔌 Step 5: Test Live Mode (Requires Gemini API Key)
Once you add your `GEMINI_API_KEY` to the `.env` file, verify live API integrations and Model Context Protocol (MCP) tool execution.

### Test A: Real MCP Drug Check (Queries Live OpenFDA API)
```bash
med-ai "Are there any interactions between Aspirin and Warfarin?"
```
* **Expected Behavior**:
  1. The CLI spawns the MCP server subprocess (`mcp_server/server.py`).
  2. The Medical Agent calls the `get_drug_interactions` tool.
  3. The tool queries OpenFDA and returns real adverse reaction statistics.

### Test B: Real Google Search Grounding (Queries Live Web)
```bash
med-ai "What is the latest CDC update on the seasonal influenza outbreak?"
```
* **Expected Behavior**:
  1. Router classifies as `MEDICAL`.
  2. The Medical Agent queries Gemini with Google Search enabled.
  3. Returns a cited response summarizing current outbreak data.
