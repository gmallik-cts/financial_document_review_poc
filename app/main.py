from contextlib import asynccontextmanager
from datetime import datetime, timezone
from uuid import uuid4
from fastapi import FastAPI, BackgroundTasks, File, Form, Header, HTTPException, Request, UploadFile, status
from fastapi.responses import JSONResponse
from . import store
from .pdf_extraction import PdfExtractionError, extract_text_from_pdf
from .schemas import CreateCaseRequest, DecisionRequest, CaseStatus
from .worker import process_case

@asynccontextmanager
async def lifespan(app: FastAPI):
    store.init_db()
    yield

app = FastAPI(title="Financial Document Review POC", version="0.1.0",
    description="Synthetic-data POC for account onboarding and account transfer review.", lifespan=lifespan)

MAX_UPLOAD_BYTES = 10 * 1024 * 1024
PDF_SIGNATURE = b"%PDF-"

@app.middleware("http")
async def correlation_id(request: Request, call_next):
    request_id = request.headers.get("X-Correlation-ID") or str(uuid4())
    response = await call_next(request)
    response.headers["X-Correlation-ID"] = request_id
    return response

def identity(client_id, tenant_id):
    # DEMO ONLY: replace with verified token claims.
    if not client_id or not tenant_id:
        raise HTTPException(status_code=401, detail={"code":"DEMO_IDENTITY_REQUIRED"})
    return client_id, tenant_id

def authorized_case(case_id, client_id, tenant_id):
    client, tenant = identity(client_id, tenant_id)
    row = store.get_case(case_id)
    if not row or row["tenant_id"] != tenant or row["client_id"] != client:
        raise HTTPException(status_code=404, detail={"code":"CASE_NOT_FOUND"})
    return row

def queue_case(payload: CreateCaseRequest, background_tasks: BackgroundTasks, client: str, tenant: str):
    """Persist a validated case and retain the existing asynchronous review flow."""
    case_id = "case_" + uuid4().hex[:16]
    now = datetime.now(timezone.utc).isoformat()
    req = payload.model_dump(mode="json")
    row = {"case_id":case_id,"tenant_id":tenant,"client_id":client,
        "external_reference":payload.external_reference,"workflow_type":payload.workflow_type.value,
        "status":CaseStatus.RECEIVED.value,"request_json":req,"created_at":now,"updated_at":now}
    store.insert_case(row)
    background_tasks.add_task(process_case, case_id)
    return JSONResponse(status_code=202, content={"case_id":case_id,"status":CaseStatus.RECEIVED.value,
        "status_url":f"/v1/cases/{case_id}","result_url":f"/v1/cases/{case_id}/result"})

@app.get("/health")
def health():
    return {"status":"ok","mode":"local-poc"}

async def read_limited_upload(upload: UploadFile) -> bytes:
    """Reject large uploads while reading rather than persisting them to disk."""
    chunks: list[bytes] = []
    size = 0
    while chunk := await upload.read(64 * 1024):
        size += len(chunk)
        if size > MAX_UPLOAD_BYTES:
            raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                                detail={"code":"PDF_TOO_LARGE", "message":"PDF exceeds the 10 MiB POC limit."})
        chunks.append(chunk)
    return b"".join(chunks)

@app.post("/v1/documents/extract")
async def extract_document(file: UploadFile = File(...),
    enable_ocr: bool = Form(default=False),
    x_client_id: str | None = Header(default=None), x_tenant_id: str | None = Header(default=None)):
    """Extract selectable PDF text for a verified demo tenant/client identity.

    The upload remains in memory only. The caller can use returned text in the
    existing ``POST /v1/cases`` document payload.
    """
    identity(x_client_id, x_tenant_id)
    try:
        if file.content_type not in {"application/pdf", "application/x-pdf"}:
            raise HTTPException(status_code=415, detail={"code":"PDF_CONTENT_TYPE_REQUIRED"})
        pdf_bytes = await read_limited_upload(file)
        if not pdf_bytes.startswith(PDF_SIGNATURE):
            raise HTTPException(status_code=415, detail={"code":"PDF_SIGNATURE_REQUIRED"})
        try:
            result = extract_text_from_pdf(pdf_bytes, enable_ocr=enable_ocr)
        except PdfExtractionError as exc:
            raise HTTPException(status_code=422, detail={"code":"PDF_NOT_PROCESSABLE", "message":str(exc)}) from exc
        return {"filename":file.filename or "document.pdf", "status":result.status,
                "page_count":result.page_count, "text":result.text, "message":result.message}
    finally:
        await file.close()

@app.post("/v1/cases/from-documents", status_code=202)
async def create_case_from_documents(
    background_tasks: BackgroundTasks,
    external_reference: str = Form(...),
    workflow_type: str = Form(...),
    document_types: list[str] = Form(...),
    files: list[UploadFile] = File(...),
    enable_ocr: bool = Form(default=False),
    x_client_id: str | None = Header(default=None),
    x_tenant_id: str | None = Header(default=None),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    """Extract a document set in memory, then queue the normal case review.

    ``document_types`` and ``files`` are paired by their submitted order. Raw
    PDFs are not stored; only extracted text enters the existing case flow.
    """
    client, tenant = identity(x_client_id, x_tenant_id)
    if not idempotency_key:
        raise HTTPException(status_code=400, detail={"code":"IDEMPOTENCY_KEY_REQUIRED"})
    if not 1 <= len(files) <= 10 or len(files) != len(document_types):
        raise HTTPException(status_code=422, detail={
            "code":"DOCUMENT_METADATA_MISMATCH",
            "message":"Submit 1-10 files and one document_types value for each file, in the same order.",
        })

    documents = []
    try:
        for document_type, file in zip(document_types, files, strict=True):
            if file.content_type not in {"application/pdf", "application/x-pdf"}:
                raise HTTPException(status_code=415, detail={"code":"PDF_CONTENT_TYPE_REQUIRED"})
            pdf_bytes = await read_limited_upload(file)
            if not pdf_bytes.startswith(PDF_SIGNATURE):
                raise HTTPException(status_code=415, detail={"code":"PDF_SIGNATURE_REQUIRED"})
            try:
                result = extract_text_from_pdf(pdf_bytes, enable_ocr=enable_ocr)
            except PdfExtractionError as exc:
                raise HTTPException(status_code=422, detail={"code":"PDF_NOT_PROCESSABLE", "message":str(exc)}) from exc
            if result.status == "ocr_required":
                raise HTTPException(status_code=422, detail={
                    "code":"DOCUMENT_OCR_REQUIRED",
                    "message":"At least one document is image-only. Resubmit with enable_ocr=true after configuring Tesseract.",
                })
            documents.append({"document_type": document_type, "text": result.text})
    finally:
        for file in files:
            await file.close()

    try:
        payload = CreateCaseRequest(
            external_reference=external_reference, workflow_type=workflow_type, documents=documents
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail={"code":"INVALID_CASE_DOCUMENTS", "message":str(exc)}) from exc
    return queue_case(payload, background_tasks, client, tenant)

@app.post("/v1/cases", status_code=202)
async def create_case(payload: CreateCaseRequest, background_tasks: BackgroundTasks,
    x_client_id: str | None = Header(default=None), x_tenant_id: str | None = Header(default=None),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key")):
    client, tenant = identity(x_client_id, x_tenant_id)
    if not idempotency_key:
        raise HTTPException(status_code=400, detail={"code":"IDEMPOTENCY_KEY_REQUIRED"})
    # POC limitation: key is accepted but not yet backed by a deduplication table.
    return queue_case(payload, background_tasks, client, tenant)

@app.get("/v1/cases")
def list_cases(x_client_id: str | None = Header(default=None), x_tenant_id: str | None = Header(default=None)):
    client, tenant = identity(x_client_id, x_tenant_id)
    rows = store.list_cases(tenant, client)
    return {"cases": [
        {
            "case_id": row["case_id"],
            "external_reference": row["external_reference"],
            "workflow_type": row["workflow_type"],
            "status": row["status"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }
        for row in rows
    ]}

@app.get("/v1/cases/{case_id}")
def case_status(case_id: str, x_client_id: str | None = Header(default=None), x_tenant_id: str | None = Header(default=None)):
    row = authorized_case(case_id, x_client_id, x_tenant_id)
    return {"case_id":row["case_id"],"status":row["status"],"created_at":row["created_at"],"updated_at":row["updated_at"]}

@app.get("/v1/cases/{case_id}/result")
def case_result(case_id: str, x_client_id: str | None = Header(default=None), x_tenant_id: str | None = Header(default=None)):
    row = authorized_case(case_id, x_client_id, x_tenant_id)
    result = store.decode_json(row["result_json"])
    if result is None:
        raise HTTPException(status_code=409, detail={"code":"RESULT_NOT_READY","status":row["status"]})
    return result

@app.post("/v1/cases/{case_id}/decision")
def decision(case_id: str, payload: DecisionRequest,
    x_client_id: str | None = Header(default=None), x_tenant_id: str | None = Header(default=None)):
    row = authorized_case(case_id, x_client_id, x_tenant_id)
    if row["status"] not in {CaseStatus.REVIEW_READY.value, CaseStatus.REQUIRES_REVIEW.value}:
        raise HTTPException(status_code=409, detail={"code":"CASE_NOT_READY_FOR_DECISION"})
    result = payload.model_dump(mode="json")
    result["decision_id"] = "decision_" + uuid4().hex[:12]
    result["decided_at"] = datetime.now(timezone.utc).isoformat()
    # DEMO ONLY: production reviewer_id must come from verified identity claims.
    store.update_case(case_id, CaseStatus.DECIDED.value, decision=result)
    return {"case_id":case_id,"status":CaseStatus.DECIDED.value,"decision":result}
