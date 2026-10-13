import pytest
from fastapi import HTTPException

from app import store
from app.main import app, list_cases


def test_list_cases_returns_only_callers_cases_newest_first(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "DB_PATH", tmp_path / "cases.db")
    store.init_db()
    store.insert_case({
        "case_id": "case_old", "tenant_id": "tenant-a", "client_id": "client-a",
        "external_reference": "old-reference", "workflow_type": "ACCOUNT_ONBOARDING",
        "status": "RECEIVED", "request_json": {},
        "created_at": "2026-01-01T00:00:00+00:00", "updated_at": "2026-01-01T00:00:00+00:00",
    })
    store.insert_case({
        "case_id": "case_new", "tenant_id": "tenant-a", "client_id": "client-a",
        "external_reference": "new-reference", "workflow_type": "ACCOUNT_TRANSFER",
        "status": "REVIEW_READY", "request_json": {},
        "created_at": "2026-01-02T00:00:00+00:00", "updated_at": "2026-01-02T00:00:00+00:00",
    })
    store.insert_case({
        "case_id": "case_other", "tenant_id": "tenant-b", "client_id": "client-a",
        "external_reference": "hidden-reference", "workflow_type": "ACCOUNT_ONBOARDING",
        "status": "RECEIVED", "request_json": {},
        "created_at": "2026-01-03T00:00:00+00:00", "updated_at": "2026-01-03T00:00:00+00:00",
    })

    response = list_cases("client-a", "tenant-a")

    assert [case["case_id"] for case in response["cases"]] == ["case_new", "case_old"]
    assert "request_json" not in response["cases"][0]
    assert any(route.path == "/v1/cases" and "GET" in route.methods for route in app.routes)


def test_list_cases_requires_identity():
    with pytest.raises(HTTPException) as error:
        list_cases(None, None)

    assert error.value.status_code == 401
    assert error.value.detail["code"] == "DEMO_IDENTITY_REQUIRED"
