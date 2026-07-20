"""Document request schemas."""
from __future__ import annotations

from pydantic import BaseModel, Field


class CreateDocumentRequest(BaseModel):
    width: int = Field(default=1000, ge=100, le=4000)
    height: int = Field(default=1000, ge=100, le=4000)
    unit: str = Field(default="px", pattern=r"^(px|in|mm|cm)$")
    background: str = Field(default="#FFFFFF", pattern=r"^#[0-9A-Fa-f]{6}$")
    name: str = ""


class DeleteDocumentRequest(BaseModel):
    ids: list[str] = Field(min_length=1)
    confirm: bool = False


class CloneDocumentRequest(BaseModel):
    source_document_id: str | None = None
    name: str | None = Field(default=None, max_length=128)
    set_active: bool = True
