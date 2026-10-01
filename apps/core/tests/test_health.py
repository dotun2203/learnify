import pytest


@pytest.mark.django_db
def test_health(api_client):
    res = api_client.get("/health/")
    assert res.status_code == 200
    assert res.data["database"] == "ok"
