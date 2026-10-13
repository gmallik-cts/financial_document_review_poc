import fitz
import pytesseract
from fastapi.testclient import TestClient

from app.main import app
from app import pdf_extraction, store


def make_pdf(text: str | None) -> bytes:
    document = fitz.open()
    page = document.new_page()
    if text is not None:
        page.insert_text((72, 72), text)
    data = document.tobytes()
    document.close()
    return data


def upload(pdf: bytes, content_type: str = "application/pdf", enable_ocr: bool = False):
    with TestClient(app) as client:
        return client.post(
            "/v1/documents/extract",
            headers={"X-Client-Id": "demo-app", "X-Tenant-Id": "demo-tenant"},
            data={"enable_ocr": str(enable_ocr).lower()},
            files={"file": ("synthetic.pdf", pdf, content_type)},
        )


def test_extracts_text_from_synthetic_pdf():
    response = upload(make_pdf("Synthetic account statement: balance 125.00"))

    assert response.status_code == 200
    assert response.json()["status"] == "text_extracted"
    assert "balance 125.00" in response.json()["text"]


def test_reports_synthetic_image_only_pdf_as_requiring_ocr():
    response = upload(make_pdf(None))

    assert response.status_code == 200
    assert response.json()["status"] == "ocr_required"
    assert "OCR" in response.json()["message"]


def test_uses_opt_in_ocr_for_an_image_only_pdf(monkeypatch):
    monkeypatch.setattr(pdf_extraction.pytesseract, "image_to_string", lambda *args, **kwargs: "OCR Account Holder: Jordan Example")

    response = upload(make_pdf(None), enable_ocr=True)

    assert response.status_code == 200
    assert response.json()["status"] == "ocr_extracted"
    assert response.json()["text"] == "OCR Account Holder: Jordan Example"
    assert "review" in response.json()["message"]


def test_reports_when_the_local_ocr_engine_is_not_installed(monkeypatch):
    def missing_engine(*args, **kwargs):
        raise pytesseract.TesseractNotFoundError()

    monkeypatch.setattr(pdf_extraction.pytesseract, "image_to_string", missing_engine)

    response = upload(make_pdf(None), enable_ocr=True)

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "PDF_NOT_PROCESSABLE"
    assert "install Tesseract" in response.json()["detail"]["message"]


def test_rejects_invalid_signature_despite_pdf_content_type():
    response = upload(b"not a pdf")

    assert response.status_code == 415


def test_requires_demo_identity_headers():
    with TestClient(app) as client:
        response = client.post("/v1/documents/extract", files={"file": ("x.pdf", make_pdf("x"), "application/pdf")})

    assert response.status_code == 401


def test_creates_case_from_two_uploaded_text_pdfs(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "DB_PATH", tmp_path / "cases.db")
    with TestClient(app) as client:
        response = client.post(
            "/v1/cases/from-documents",
            headers={
                "X-Client-Id": "demo-app", "X-Tenant-Id": "demo-tenant", "Idempotency-Key": "upload-case-1",
            },
            data={
                "external_reference": "upload-case-1",
                "workflow_type": "ACCOUNT_TRANSFER",
                "document_types": ["TRANSFER_AUTHORIZATION", "DELIVERING_ACCOUNT_STATEMENT"],
            },
            files=[
                ("files", ("authorization.pdf", make_pdf("Account Holder: Jordan Example\nDelivering Account: 123\nReceiving Account: 456\nAuthorization: Present"), "application/pdf")),
                ("files", ("statement.pdf", make_pdf("Account Holder: Jordan Example\nDelivering Account: 123\nReceiving Account: 456"), "application/pdf")),
            ],
        )

    assert response.status_code == 202
    body = response.json()
    assert body["case_id"].startswith("case_")
    assert store.get_case(body["case_id"])["workflow_type"] == "ACCOUNT_TRANSFER"
