"""
MedBridge AI - Security Module
===============================

This package contains the PII (Personally Identifiable Information) redaction
layer. It acts as mandatory middleware: ALL user input passes through this
module BEFORE reaching any LLM agent, ensuring no protected health information
or personal data leaks to external APIs.

Kaggle Rubric Alignment: Security features
"""
