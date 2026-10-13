from . import store
from .ai_adapter import AIReviewAdapter
from .privacy import mask_pii
from .rules import validate_case
from .schemas import CaseStatus, CaseResult, Recommendation, WorkflowType

ai_adapter = AIReviewAdapter()

async def process_case(case_id: str):
    row = store.get_case(case_id)
    if not row: return
    store.update_case(case_id, CaseStatus.PROCESSING.value)
    request = store.decode_json(row["request_json"])
    docs = request["documents"]
    workflow = WorkflowType(request["workflow_type"])

    masked_docs = []
    for doc in docs:
        masked = mask_pii(doc["text"])
        masked_docs.append({**doc, "text": masked.masked_text})

    # The model adapter receives masked text only. In this POC it is a no-op stub.
    findings = validate_case(workflow, docs)
    findings.extend(await ai_adapter.analyze(workflow, [d["text"] for d in masked_docs]))
    # Fail safe: uncertain, missing or conflicting evidence goes to a reviewer.
    recommendation = Recommendation.REQUIRES_REVIEW if any(f.requires_human_review for f in findings) else Recommendation.APPROVED
    result = CaseResult(case_id=case_id, status=CaseStatus.REVIEW_READY,
        recommendation=recommendation,
        reason_codes=sorted({f.code for f in findings if f.severity != "INFO"}),
        findings=findings, masked_for_ai=True, ai_provider_called=False).model_dump(mode="json")
    store.update_case(case_id, CaseStatus.REVIEW_READY.value, result=result)
