from typing import Dict, List, Tuple
import click

try:
    import spacy
    nlp = spacy.load("en_core_web_sm")
except OSError:
    raise OSError(
        "\n❌ spaCy model 'en_core_web_sm' not found.\n"
        "   Install it with: python -m spacy download en_core_web_sm\n"
    )

ENTITY_REDACTION_MAP: Dict[str, str] = {
    "PERSON": "[REDACTED_PERSON]",
    "GPE": "[REDACTED_LOCATION]",
    "ORG": "[REDACTED_ORG]",
}

PRESERVED_ENTITIES: List[str] = ["DATE", "TIME", "CARDINAL", "ORDINAL"]

# Whitelist common medications to skip during redaction
DRUG_WHITELIST: set = {
    "aspirin", "warfarin", "lisinopril", "metformin", "ibuprofen",
    "acetaminophen", "tylenol", "advil", "amoxicillin", "atorvastatin",
    "metoprolol", "omeprazole", "losartan", "amlodipine", "simvastatin",
    "hydrochlorothiazide", "gabapentin", "sertraline", "prednisone",
    "levothyroxine", "albuterol", "furosemide", "tramadol", "clopidogrel",
    "pantoprazole", "montelukast", "escitalopram", "rosuvastatin",
    "duloxetine", "venlafaxine", "insulin", "ozempic", "wegovy",
    "penicillin", "ciprofloxacin", "azithromycin", "doxycycline", "potassium",
}

def redact_pii(text: str, verbose: bool = False) -> tuple[str, dict[str, str]]:
    """Redact PII/PHI from input text using spaCy NER."""
    doc = nlp(text)
    redacted_text = text
    token_map = {}
    entities_found: List[Tuple[str, str, str]] = []
    counts = {"PERSON": 0, "GPE": 0, "ORG": 0}

    # Iterate in reverse order to preserve offsets during replacement
    for ent in reversed(doc.ents):
        if ent.text.lower() in DRUG_WHITELIST:
            continue

        if ent.label_ in ENTITY_REDACTION_MAP:
            label = ent.label_
            index = counts.get(label, 0)
            counts[label] = index + 1
            
            token = f"[{label}_{index}]"
            token_map[token] = ent.text
            
            redacted_text = (
                redacted_text[:ent.start_char]
                + token
                + redacted_text[ent.end_char:]
            )
            entities_found.append((ent.text, ent.label_, token))

    if verbose and entities_found:
        click.echo(click.style("   PII entities tokenized:", fg="yellow"))
        for original, label, token in reversed(entities_found):
            click.echo(
                click.style(f"     - {label}: ", fg="yellow")
                + f"'{original}' -> {token}"
            )

    return redacted_text, token_map

def redact_pii_mock(text: str, verbose: bool = False) -> tuple[str, dict[str, str]]:
    """Lightweight mock PII tokenization for offline testing/CI."""
    import re

    redacted = text
    token_map = {}
    counts = {"PERSON": 0}

    def repl_dr(match):
        prefix = match.group(1)
        name = match.group(0).replace(prefix, "").strip()
        token = f"[PERSON_{counts['PERSON']}]"
        counts["PERSON"] += 1
        token_map[token] = name
        return f"{prefix} {token}"

    redacted = re.sub(
        r"\b(Dr\.|Mr\.|Mrs\.|Ms\.)\s+[A-Z][a-z]+",
        repl_dr,
        redacted,
    )

    def repl_name(match):
        name = match.group(1)
        token = f"[PERSON_{counts['PERSON']}]"
        counts["PERSON"] += 1
        token_map[token] = name
        return match.group(0).replace(name, token)

    redacted = re.sub(
        r"\b(?:[Ii]\s+[Aa]m|[Mm]y\s+[Nn]ame\s+[Ii]s|[Pp]atient)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)",
        repl_name,
        redacted,
    )

    if verbose:
        click.echo(click.style("   [Mock PII tokenization applied]", fg="yellow"))

    return redacted, token_map

if __name__ == "__main__":
    import sys
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    test_inputs = [
        "Dr. Smith in New York prescribed Lisinopril and Metformin.",
        "Patient John Doe from Chicago needs a follow-up on January 15.",
        "Remind me to take Aspirin at 8am tomorrow.",
        "The CDC in Atlanta reports a flu outbreak.",
    ]

    click.echo(click.style("\n=== PII Redactor Self-Test ===\n", bold=True))
    for text in test_inputs:
        click.echo(f"  Input:  {text}")
        result, mapping = redact_pii(text, verbose=True)
        click.echo(f"  Output: {result}")
        click.echo(f"  Map:    {mapping}\n")
