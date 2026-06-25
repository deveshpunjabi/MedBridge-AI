"""
MedBridge AI - Agents Module
==============================

This package contains the multi-agent system built with the Google Gemini SDK
(google-genai). The architecture follows a Router-Specialist pattern:

  Router Agent  →  classifies user intent (MEDICAL / SCHEDULER / BOTH / UNKNOWN)
  Medical Agent →  handles drug interactions (via MCP) and public health grounding
  Scheduler Agent → handles appointment/reminder scheduling (via MCP)

Design Rationale (Kaggle Rubric: ADK / Agent Pattern):
    The Router-Specialist pattern was chosen over a single monolithic agent
    because it demonstrates:
      1. Agent orchestration — a core ADK concept.
      2. Separation of concerns — each agent has a focused system prompt
         and toolset, reducing hallucination risk.
      3. Composability — new specialist agents can be added without modifying
         existing ones (Open/Closed Principle).
"""
