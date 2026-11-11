from pathlib import Path

from fastapi.testclient import TestClient

import app.main as main
from app.storage import BatchStore


def test_batch_history_and_edits_survive_reopening_storage(tmp_path, monkeypatch):
    directory = tmp_path / "batches"
    monkeypatch.setattr(main, "SESSIONS", BatchStore(directory))
    client = TestClient(main.app)
    sample = Path(__file__).resolve().parents[1] / "66075.pdf"
    with sample.open("rb") as pdf:
        uploaded = client.post("/api/upload", files={"files": (sample.name, pdf, "application/pdf")})
    assert uploaded.status_code == 200
    batch = uploaded.json()
    session = batch["session_id"]
    invoice = batch["invoices"][0]["id"]
    updated = client.put(f"/api/invoices/{session}/{invoice}", json={"warehouse_name": "Verified warehouse"})
    assert updated.status_code == 200

    monkeypatch.setattr(main, "SESSIONS", BatchStore(directory))
    history = client.get("/api/batches").json()["batches"]
    assert history[0]["session_id"] == session
    assert history[0]["filename"] == sample.name
    assert client.get(f"/api/invoices/{session}").json()["invoices"][0]["warehouse_name"] == "Verified warehouse"
    assert client.post(f"/api/generate/{session}").status_code == 200
