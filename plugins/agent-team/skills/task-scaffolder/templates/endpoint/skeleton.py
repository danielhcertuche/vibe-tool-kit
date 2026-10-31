# --- artifact metadata ---
# owner_agent: {{OWNER_AGENT}}
# upstream:    {{UPSTREAM}}
# downstream:  {{DOWNSTREAM}}
# created_at:  {{CREATED_AT}}
# template:    task-scaffolder/endpoint
# ---
from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

router = APIRouter(prefix="/{{NAME}}", tags=["{{NAME}}"])


class {{NAME}}Request(BaseModel):
    pass


class {{NAME}}Response(BaseModel):
    pass


@router.get("/", response_model=list[{{NAME}}Response])
async def list_{{NAME}}() -> list[{{NAME}}Response]:
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED)


@router.post("/", response_model={{NAME}}Response, status_code=status.HTTP_201_CREATED)
async def create_{{NAME}}(body: {{NAME}}Request) -> {{NAME}}Response:
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED)
