from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_health():
    r = client.get("/health")
    assert r.status_code == 200

def test_empty_question():
    r = client.post("/ask", json={"question": ""})
    assert r.status_code == 400

def test_valid_question():
    r = client.post("/ask", json={"question": "Nghỉ phép năm được mấy ngày?"})
    assert r.status_code == 200
    assert "answer" in r.json()