from collections.abc import AsyncGenerator

from fastapi.testclient import TestClient

from app.db import get_db
from app.main import app
from app.services.upload_service import UploadAccepted, UploadStatus


async def _fake_db() -> AsyncGenerator[None, None]:
    yield None


def test_upload_rejects_non_xlsx() -> None:
    app.dependency_overrides[get_db] = _fake_db
    client = TestClient(app)

    response = client.post(
        "/upload",
        files={"file": ("statement.csv", b"a,b,c", "text/csv")},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Only .xlsx files are supported"
    app.dependency_overrides.clear()


def test_upload_returns_accepted(monkeypatch) -> None:
    async def _fake_create_upload_job(db, filename: str):
        return UploadAccepted(upload_id=1, filename=filename, status="processing")

    async def _fake_process_upload_job(upload_id: int, filename: str, file_bytes: bytes, generate_embeddings: bool):
        return None

    monkeypatch.setattr("app.routers.upload.create_upload_job", _fake_create_upload_job)
    monkeypatch.setattr("app.routers.upload.process_upload_job", _fake_process_upload_job)

    app.dependency_overrides[get_db] = _fake_db
    client = TestClient(app)

    response = client.post(
        "/upload",
        files={
            "file": (
                "statement.xlsx",
                b"dummy",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )

    assert response.status_code == 202
    payload = response.json()
    assert payload["upload_id"] == 1
    assert payload["status"] == "processing"
    app.dependency_overrides.clear()


def test_upload_status_returns_payload(monkeypatch) -> None:
    async def _fake_get_upload_status(db, upload_id: int):
        return UploadStatus(
            upload_id=upload_id,
            filename="statement.xlsx",
            status="done",
            processing_phase="done",
            progress_percent=100,
            rows_total=10,
            rows_processed=10,
            rows_skipped_non_transaction=2,
            rows_invalid=1,
            rows_duplicate=3,
            rows_inserted=4,
            llm_used_count=2,
            fallback_used_count=2,
            embeddings_generated=4,
            error_message=None,
        )

    monkeypatch.setattr("app.routers.upload.get_upload_status", _fake_get_upload_status)

    app.dependency_overrides[get_db] = _fake_db
    client = TestClient(app)

    response = client.get("/upload/42")

    assert response.status_code == 200
    payload = response.json()
    assert payload["upload_id"] == 42
    assert payload["status"] == "done"
    assert payload["embeddings_generated"] == 4
    app.dependency_overrides.clear()
