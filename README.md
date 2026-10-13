# Financial Account Document Review POC

Runnable local starter for customer **Account Onboarding** and **Account Transfer** document review.

> Synthetic data only. This is not production-ready financial software and does not represent LPL Financial's internal procedures.

## Included
- FastAPI asynchronous case submission (`202 Accepted`), status polling and result retrieval
- `ACCOUNT_ONBOARDING` and `ACCOUNT_TRANSFER` workflows
- Basic PII masking before the AI adapter boundary
- Deterministic checks, evidence-backed findings, and reviewer final-decision capture
- AI adapter stub (does not call an external model)
- SQLite for local POC, tests, Dockerfile and AWS migration guidance
- Authenticated local PDF upload and selectable-text extraction; scanned PDFs are clearly marked for a future OCR step

## Run locally (Python 3.11+)
```bash
python -m venv .venv
# Windows: .venv\\Scripts\\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```
Open http://127.0.0.1:8000/docs.

## Extract text from a PDF

Upload one synthetic, text-based PDF before submitting it as text in a case.
The endpoint does not write the upload to disk. It requires the same demo
identity headers as the case endpoints, accepts only `application/pdf`, checks
the PDF signature, and limits documents to 10 MiB and 50 pages.

```bash
curl -X POST http://127.0.0.1:8000/v1/documents/extract \
  -H "X-Client-Id: demo-app" -H "X-Tenant-Id: demo-tenant" \
  -F "file=@synthetic-statement.pdf;type=application/pdf"
```

The response returns `text_extracted` and the selectable text for a text PDF.
For a scanned/image-only PDF, add the multipart form field `enable_ocr` with
the value `true`. The POC will rasterize each page and pass it to local
Tesseract OCR, returning `ocr_extracted`. OCR output can contain recognition
errors and must be reviewed before it is used for a decision. Without this
explicit flag, scanned PDFs return `ocr_required`.

Install the Python dependencies and the local Tesseract engine before enabling
OCR. On Windows, install Tesseract, ensure `tesseract.exe` is on `PATH`, then
restart the terminal running Uvicorn. The endpoint returns a clear `422` error
when the engine is unavailable. OCR is bounded to 50 pages, 10 MiB uploads,
10 million pixels per page, and 15 seconds per page for this local POC.

## Create a review case directly from PDFs

`POST /v1/cases/from-documents` accepts a document set, extracts each PDF in
memory, then queues the existing review workflow. Submit one `files` field and
one `document_types` field for each document, in matching order. Also submit
`external_reference`, `workflow_type`, optional `enable_ocr`, the usual demo
identity headers, and `Idempotency-Key`. The original PDFs are not stored;
only their extracted text is placed in the local case record.

For an account transfer, use `TRANSFER_AUTHORIZATION` and
`DELIVERING_ACCOUNT_STATEMENT` document types. The response is the same `202`
case response as `POST /v1/cases`; poll its `status_url` and then its
`result_url` to see the cross-document checks.

## Example onboarding case
```bash
curl -X POST http://127.0.0.1:8000/v1/cases \\
  -H "Content-Type: application/json" -H "X-Client-Id: demo-app" -H "X-Tenant-Id: demo-tenant" \\
  -H "Idempotency-Key: demo-001" \\
  -d '{"external_reference":"demo-001","workflow_type":"ACCOUNT_ONBOARDING","documents":[{"document_type":"ACCOUNT_APPLICATION","text":"Name: Jordan Example\\nDOB: 01/02/1980\\nEmail: jordan@example.test\\nAccount Number: 123456789\\nSignature: Present"},{"document_type":"IDENTITY_DOCUMENT","text":"Name: Jordan Example\\nDOB: 01/02/1980\\nID Number: 999-12-3456"}]}'
```
Use `GET /v1/cases` with the same `X-Client-Id` and `X-Tenant-Id` headers to list that identity's cases (newest first). Use the returned `case_id` with `GET /v1/cases/{case_id}` and then `GET /v1/cases/{case_id}/result`.

## Example transfer document fields
Use `workflow_type: "ACCOUNT_TRANSFER"` and document types `TRANSFER_AUTHORIZATION` and `DELIVERING_ACCOUNT_STATEMENT`. Synthetic text can include `Account Holder: Jordan Example`, `Delivering Account: 1234`, `Receiving Account: 5678`, and `Authorization: Present`.

## Important production gaps
1. `X-Client-Id` and `X-Tenant-Id` are demo headers, not authentication. Replace with verified OAuth2/OIDC or approved workload identity.
2. The in-memory PDF endpoint is intentionally local-POC scope. Before real files, add private object storage, malware scanning, encryption, retention/deletion controls, and a security review.
3. Regex masking is illustrative and can miss PII. Add OCR-span-aware detection, image redaction if images go to a model, a fail-closed masking gate, and leakage tests.
4. AI is a stub and no model is called. Integrate Bedrock or another approved provider only after privacy, legal, region and data-handling approval.
5. SQLite and in-process background tasks are local-demo-only. Use PostgreSQL/Aurora plus SQS/Step Functions and ECS/Lambda for deployed workloads.
6. Decision authorization is demo-only. Derive reviewer identity from verified claims, implement role-based authorization and immutable audit.
7. Add retention/deletion, rate limits, quotas, secure logging, monitoring, backups, load tests and security review.

See `docs/architecture.md` and `docs/poc-test-plan.md`.
