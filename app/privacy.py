import re
from dataclasses import dataclass

@dataclass
class MaskResult:
    masked_text: str
    categories_found: list[str]

# Illustrative recognizers only; not production-complete.
PATTERNS = [
    ("EMAIL", re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I)),
    ("US_SSN", re.compile(r"\b\d{3}-\d{2}-\d{4}\b")),
    ("PHONE", re.compile(r"(?<!\w)(?:\+?1[-.\s]?)?(?:\(?\d{3}\)?[-.\s]?)\d{3}[-.\s]?\d{4}(?!\w)")),
    ("DOB", re.compile(r"\b(?:DOB|Date of Birth)\s*:\s*\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b", re.I)),
    ("ACCOUNT_NUMBER", re.compile(r"\b(?:Account Number|Account No\.?|Acct)\s*:\s*[A-Z0-9-]{4,}\b", re.I)),
]

def mask_pii(text: str) -> MaskResult:
    masked, found = text, []
    for category, pattern in PATTERNS:
        if pattern.search(masked):
            found.append(category)
            replacement = {
                "EMAIL": "[EMAIL]", "US_SSN": "[US_SSN]", "PHONE": "[PHONE]",
                "DOB": "DOB: [DATE_OF_BIRTH]", "ACCOUNT_NUMBER": "Account Number: [ACCOUNT_NUMBER]"
            }[category]
            masked = pattern.sub(replacement, masked)
    return MaskResult(masked, found)
