# --- artifact metadata ---
# owner_agent: {{OWNER_AGENT}}
# upstream:    {{UPSTREAM}}
# downstream:  {{DOWNSTREAM}}
# created_at:  {{CREATED_AT}}
# template:    task-scaffolder/endpoint
# ---
from fastapi import FastAPI
from fastapi.testclient import TestClient

from .skeleton import router

app = FastAPI()
app.include_router(router)
client = TestClient(app)


def test_list_returns_501_until_implemented() -> None:
    response = client.get("/{{NAME}}/")
    assert response.status_code == 501


def test_create_returns_501_until_implemented() -> None:
    response = client.post("/{{NAME}}/", json={})
    assert response.status_code == 501
