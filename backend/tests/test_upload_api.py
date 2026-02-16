from collections.abc import AsyncGenerator

from fastapi.testclient import TestClient

from app.db import get_db
from app.main import app
from app.services.upload_service import UploadSummary


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


def test_upload_returns_summary(monkeypatch) -> None:
    async def _fake_import_statement_file(db, filename: str, file_bytes: bytes):
        return UploadSummary(
            upload_id=1,
            filename=filename,
            status="done",
            rows_total=10,
            rows_skipped_non_transaction=2,
            rows_invalid=1,
            rows_duplicate=3,
            rows_inserted=4,
        )

    monkeypatch.setattr(
        "app.routers.upload.import_statement_file", _fake_import_statement_file
    )

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

    assert response.status_code == 200
    payload = response.json()
    assert payload["upload_id"] == 1
    assert payload["rows_inserted"] == 4
    assert payload["rows_duplicate"] == 3
    app.dependency_overrides.clear()
