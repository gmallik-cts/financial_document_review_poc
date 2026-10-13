from app.rules import validate_case
from app.schemas import WorkflowType

def test_onboarding_missing_documents_flags_review():
    f = validate_case(WorkflowType.ACCOUNT_ONBOARDING, [{"document_type":"ACCOUNT_APPLICATION","text":"Name: Sample"}])
    codes = {x.code for x in f}
    assert "MISSING_DOCUMENT_TYPE" in codes
    assert "REQUIRED_FIELD_MISSING" in codes

def test_transfer_missing_authorization_flags_review():
    docs = [
        {"document_type":"TRANSFER_AUTHORIZATION","text":"Account Holder: Sample\\nDelivering Account: 1234\\nReceiving Account: 5678"},
        {"document_type":"DELIVERING_ACCOUNT_STATEMENT","text":"Account Holder: Sample\\nDelivering Account: 1234\\nReceiving Account: 5678"},
    ]
    assert any(x.code == "TRANSFER_AUTHORIZATION_UNCONFIRMED" for x in validate_case(WorkflowType.ACCOUNT_TRANSFER, docs))

def test_onboarding_accepts_literal_escaped_newlines():
    docs = [
        {"document_type":"ACCOUNT_APPLICATION", "text":"Name: Jordan Example\\nDOB: 01/02/1980\\nSignature: Present"},
        {"document_type":"IDENTITY_DOCUMENT", "text":"Name: Jordan Example\\nDOB: 01/02/1980"},
    ]

    findings = validate_case(WorkflowType.ACCOUNT_ONBOARDING, docs)

    assert not any(f.code in {"CROSS_DOCUMENT_MISMATCH", "REQUIRED_FIELD_MISSING", "SIGNATURE_STATUS_UNCONFIRMED"} for f in findings)
