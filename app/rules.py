import re
from .schemas import Finding, WorkflowType

def normalize_document_text(text: str) -> str:
    """Accept newline characters and literal JSON-style newline sequences in POC text input."""
    text = (text.replace("\\r\\n", "\n")
                .replace("\\n", "\n")
                .replace("\\r", "\n"))
    return re.sub(r"\\\r?\n", "\n", text)

def field_values(texts: list[str], label: str) -> list[str]:
    pattern = re.compile(rf"(?im)^\s*{re.escape(label)}\s*:\s*(.+?)\s*$")
    return [m.group(1).strip() for text in texts
            for m in pattern.finditer(normalize_document_text(text))]

def validate_case(workflow: WorkflowType, documents: list[dict]) -> list[Finding]:
    findings = []
    texts = [d["text"] for d in documents]
    types = {d["document_type"].upper() for d in documents}
    if workflow == WorkflowType.ACCOUNT_ONBOARDING:
        missing = sorted({"ACCOUNT_APPLICATION", "IDENTITY_DOCUMENT"} - types)
        if missing:
            findings.append(Finding(code="MISSING_DOCUMENT_TYPE", severity="HIGH",
                summary=f"Expected document type(s) not supplied: {', '.join(missing)}.",
                evidence=[{"type":"DOCUMENT_SET","supplied_types":sorted(types)}], requires_human_review=True))
        for label in ("Name", "DOB"):
            vals = field_values(texts, label)
            if not vals:
                findings.append(Finding(code="REQUIRED_FIELD_MISSING", severity="HIGH", field=label.lower(),
                    summary=f"Could not locate required field '{label}'.",
                    evidence=[{"type":"EXTRACTION_CHECK","field":label}], requires_human_review=True))
            elif len({v.casefold() for v in vals}) > 1:
                findings.append(Finding(code="CROSS_DOCUMENT_MISMATCH", severity="HIGH", field=label.lower(),
                    summary=f"Values for '{label}' differ across supplied documents.",
                    evidence=[{"type":"FIELD_COMPARISON","field":label,"value_count":len(vals)}], requires_human_review=True))
        signatures = field_values(texts, "Signature")
        if not signatures or any(v.casefold() not in {"present","signed","yes"} for v in signatures):
            findings.append(Finding(code="SIGNATURE_STATUS_UNCONFIRMED", severity="MEDIUM", field="signature",
                summary="Signature status is missing or not confirmed in text; visual signature verification is not implemented.",
                evidence=[{"type":"DOCUMENT_TEXT_CHECK","field":"Signature"}], requires_human_review=True))
    else:
        missing = sorted({"TRANSFER_AUTHORIZATION", "DELIVERING_ACCOUNT_STATEMENT"} - types)
        if missing:
            findings.append(Finding(code="MISSING_DOCUMENT_TYPE", severity="HIGH",
                summary=f"Expected transfer document type(s) not supplied: {', '.join(missing)}.",
                evidence=[{"type":"DOCUMENT_SET","supplied_types":sorted(types)}], requires_human_review=True))
        for label in ("Account Holder", "Delivering Account", "Receiving Account"):
            vals = field_values(texts, label)
            if not vals:
                findings.append(Finding(code="TRANSFER_FIELD_MISSING", severity="HIGH", field=label.lower(),
                    summary=f"Could not locate transfer field '{label}'.",
                    evidence=[{"type":"EXTRACTION_CHECK","field":label}], requires_human_review=True))
            elif label == "Account Holder" and len({v.casefold() for v in vals}) > 1:
                findings.append(Finding(code="TRANSFER_HOLDER_MISMATCH", severity="HIGH", field="account_holder",
                    summary="Account holder values differ across transfer documents.",
                    evidence=[{"type":"FIELD_COMPARISON","field":label,"value_count":len(vals)}], requires_human_review=True))
        auth = field_values(texts, "Authorization")
        if not auth or any(v.casefold() not in {"present","authorized","yes","signed"} for v in auth):
            findings.append(Finding(code="TRANSFER_AUTHORIZATION_UNCONFIRMED", severity="HIGH", field="authorization",
                summary="Transfer authorization is not confirmed in text.",
                evidence=[{"type":"DOCUMENT_TEXT_CHECK","field":"Authorization"}], requires_human_review=True))
    return findings
