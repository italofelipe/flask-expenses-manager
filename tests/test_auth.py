def test_health_check(client):
    response = client.get("/auth/login")
    assert response.status_code in (400, 405)
