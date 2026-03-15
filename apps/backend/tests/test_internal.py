from fastapi import status
from fastapi.testclient import TestClient


def test_internal_shutdown(test_client: TestClient) -> None:
    response = test_client.post("/internal/shutdown")
    assert response.status_code == status.HTTP_202_ACCEPTED
    assert response.json() == {"status": "accepted"}
