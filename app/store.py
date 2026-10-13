import json, sqlite3
from pathlib import Path
DB_PATH = Path("poc.db")

def connect():
    c = sqlite3.connect(DB_PATH, check_same_thread=False)
    c.row_factory = sqlite3.Row
    return c

def init_db():
    with connect() as c:
        c.execute("CREATE TABLE IF NOT EXISTS cases (case_id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL, client_id TEXT NOT NULL, external_reference TEXT NOT NULL, workflow_type TEXT NOT NULL, status TEXT NOT NULL, request_json TEXT NOT NULL, result_json TEXT, decision_json TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_cases_tenant ON cases(tenant_id, created_at)")
        c.commit()

def insert_case(r):
    with connect() as c:
        c.execute("INSERT INTO cases VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            (r["case_id"],r["tenant_id"],r["client_id"],r["external_reference"],r["workflow_type"],r["status"],json.dumps(r["request_json"]),None,None,r["created_at"],r["updated_at"]))
        c.commit()

def update_case(case_id, status, result=None, decision=None):
    from datetime import datetime, timezone
    with connect() as c:
        row = c.execute("SELECT result_json, decision_json FROM cases WHERE case_id=?", (case_id,)).fetchone()
        if not row: return
        c.execute("UPDATE cases SET status=?, result_json=?, decision_json=?, updated_at=? WHERE case_id=?",
            (status, json.dumps(result) if result is not None else row["result_json"],
             json.dumps(decision) if decision is not None else row["decision_json"],
             datetime.now(timezone.utc).isoformat(), case_id))
        c.commit()

def get_case(case_id):
    with connect() as c:
        row = c.execute("SELECT * FROM cases WHERE case_id=?", (case_id,)).fetchone()
        return dict(row) if row else None

def list_cases(tenant_id, client_id):
    """Return case records visible to one tenant/client identity, newest first."""
    with connect() as c:
        rows = c.execute(
            "SELECT * FROM cases WHERE tenant_id=? AND client_id=? "
            "ORDER BY created_at DESC, case_id DESC",
            (tenant_id, client_id),
        ).fetchall()
        return [dict(row) for row in rows]

def decode_json(value):
    return json.loads(value) if value else None
