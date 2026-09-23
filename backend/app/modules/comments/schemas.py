"""Etapa 7E — comentários do equipamento. Sem anexos; texto puro."""

from __future__ import annotations

from datetime import datetime

from pydantic import Field, model_validator

from app.modules.equipments.schemas import UserRefOut
from app.shared.schema import CamelModel


class CommentCreateIn(CamelModel):
    text: str = Field(min_length=1, max_length=4000)

    @model_validator(mode="after")
    def clean(self) -> CommentCreateIn:
        if not self.text.strip():
            raise ValueError("Comentário não pode ficar em branco")
        return self


class CommentUpdateIn(CamelModel):
    text: str = Field(min_length=1, max_length=4000)

    @model_validator(mode="after")
    def clean(self) -> CommentUpdateIn:
        if not self.text.strip():
            raise ValueError("Comentário não pode ficar em branco")
        return self


class CommentOut(CamelModel):
    id: str
    equipment_id: str
    text: str
    author: UserRefOut | None = None
    created_at: datetime
    updated_at: datetime


class CommentListOut(CamelModel):
    items: list[CommentOut]
