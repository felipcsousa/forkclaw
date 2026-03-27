from fastapi.testclient import TestClient


def test_get_approval_not_found(test_client: TestClient) -> None:
    response = test_client.get("/approvals/missing-id")
    assert response.status_code == 404
    assert response.json()["detail"] == "Approval not found."


def test_approve_not_found(test_client: TestClient) -> None:
    response = test_client.post("/approvals/missing-id/approve")
    assert response.status_code == 404
    assert response.json()["detail"] == "Approval not found."


def test_deny_not_found(test_client: TestClient) -> None:
    response = test_client.post("/approvals/missing-id/deny")
    assert response.status_code == 404
    assert response.json()["detail"] == "Approval not found."
