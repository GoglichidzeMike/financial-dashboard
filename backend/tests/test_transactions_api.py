from collections.abc import AsyncGenerator

from fastapi.testclient import TestClient

from app.db import get_db
from app.main import app


async def _fake_db() -> AsyncGenerator[None, None]:
    yield None


def test_transactions_query_validation() -> None:
    app.dependency_overrides[get_db] = _fake_db
    client = TestClient(app)

    response = client.get("/transactions?limit=0")

    assert response.status_code == 422
    app.dependency_overrides.clear()
