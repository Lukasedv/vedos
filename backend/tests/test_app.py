"""Basic API tests for the Vedos backend."""

import pytest
from fastapi.testclient import TestClient

from vedos.app import app

client = TestClient(app)


def test_health():
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert "version" in data


def test_import_missing_file():
    resp = client.post("/api/import", json=["/nonexistent/file.cr2"])
    assert resp.status_code == 404


def test_process_returns_job_id():
    resp = client.post(
        "/api/process",
        json={"files": ["/tmp/test.cr2"], "film_type": "color_negative"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "job_id" in data
    assert data["status"] == "queued"


def test_process_status():
    resp = client.get("/api/process/fake-job-id/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["job_id"] == "fake-job-id"
    assert data["status"] == "unknown"


def test_ai_correct():
    resp = client.post("/api/ai-correct", json={"job_id": "fake-job-id"})
    # No image stored for this job → 404
    assert resp.status_code == 404


def test_preview():
    resp = client.get("/api/preview/fake-job-id")
    # No preview stored for this job → 404
    assert resp.status_code == 404
