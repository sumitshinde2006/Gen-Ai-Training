from app.main import app
from fastapi.testclient import TestClient

client = TestClient(app)


def test_search_returns_existing_variety():
    response = client.get("/search", params={"q": "Bhima Dark Red"})

    assert response.status_code == 200
    body = response.json()
    assert body["total_results"] > 0
    assert body["results"][0]["variety_name"] == "Bhima Dark Red"


def test_search_returns_empty_list_for_no_match():
    response = client.get("/search", params={"q": "qzxwvuplmokn"})

    assert response.status_code == 200
    assert response.json()["total_results"] == 0
    assert response.json()["results"] == []

