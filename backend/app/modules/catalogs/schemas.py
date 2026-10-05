from __future__ import annotations

from datetime import datetime

from pydantic import Field, model_validator

from app.domain.eap import AREA_CODE_RE, PROCESS_CODE_RE, EapLevel
from app.shared.schema import CamelModel


class UnitOut(CamelModel):
    id: str
    code: str
    name: str
    active: bool
    created_at: datetime
    updated_at: datetime


class ProjectContextOut(CamelModel):
    id: str
    unit_id: str
    code: str
    name: str
    active: bool


class AreaOut(CamelModel):
    id: str
    unit_id: str
    name: str
    active: bool


class DisciplineOut(CamelModel):
    id: str
    code: str
    name: str
    active: bool


class WorkPackageOut(CamelModel):
    id: str
    project_context_id: str
    code: str
    name: str
    active: bool


class CatalogListOut(CamelModel):
    items: list[UnitOut | ProjectContextOut | AreaOut | DisciplineOut | WorkPackageOut]


class UnitCreateIn(CamelModel):
    code: str = Field(min_length=1, max_length=40)
    name: str = Field(min_length=1, max_length=160)


class EapNodeOut(CamelModel):
    id: str
    code: str
    name: str
    level: EapLevel
    parent_id: str | None
    active: bool
    created_at: datetime
    updated_at: datetime


class EapNodeListOut(CamelModel):
    items: list[EapNodeOut]


class EapNodeCreateIn(CamelModel):
    """Só a parte corporativa do código ("01", "01.A") — nunca "2101.A".
    A coerência com o pai é validada no serviço, que conhece o nó pai."""

    code: str = Field(min_length=1, max_length=20)
    name: str = Field(min_length=1, max_length=160)
    level: EapLevel
    parent_id: str | None = None

    @model_validator(mode="after")
    def code_matches_level(self) -> EapNodeCreateIn:
        if self.code != self.code.strip() or " " in self.code:
            raise ValueError("Código da EAP não pode ter espaços")
        if self.level is EapLevel.PROCESS and not PROCESS_CODE_RE.fullmatch(self.code):
            raise ValueError("PROCESS usa 2 dígitos (ex.: 01), sem o prefixo da unidade")
        if self.level is EapLevel.AREA and not AREA_CODE_RE.fullmatch(self.code):
            raise ValueError("AREA usa o formato 01.A, sem o prefixo da unidade")
        if self.level is EapLevel.AREA and self.parent_id is None:
            raise ValueError("AREA exige um PROCESS pai")
        if self.level is EapLevel.ISLAND and self.parent_id is not None:
            raise ValueError("ISLAND é raiz e não tem pai")
        return self


class ProjectEapOut(CamelModel):
    id: str
    project_context_id: str
    eap_node: EapNodeOut
    active: bool
    created_at: datetime


class ProjectEapListOut(CamelModel):
    items: list[ProjectEapOut]


class ProjectContextCreateIn(CamelModel):
    # Uma obra precisa só de unidade, código e nome. Não há prefixo EAP: a EAP é
    # propriedade da localização do equipamento (`EapNode.code`), sem composição.
    code: str = Field(min_length=1, max_length=60)
    name: str = Field(min_length=1, max_length=160)


class AreaCreateIn(CamelModel):
    unit_id: str
    name: str = Field(min_length=1, max_length=160)


class DisciplineCreateIn(CamelModel):
    code: str = Field(min_length=1, max_length=40)
    name: str = Field(min_length=1, max_length=160)


class WorkPackageCreateIn(CamelModel):
    project_context_id: str
    code: str = Field(min_length=1, max_length=60)
    name: str = Field(min_length=1, max_length=160)


class CatalogUpdateIn(CamelModel):
    """Atualização comum dos catálogos. `code` só é aceito onde existe."""

    name: str | None = Field(default=None, min_length=1, max_length=200)
    code: str | None = Field(default=None, min_length=1, max_length=60)
    active: bool | None = None

    @model_validator(mode="after")
    def has_update(self) -> CatalogUpdateIn:
        if not self.model_fields_set:
            raise ValueError("Informe ao menos um campo para atualizar")
        return self


class ProjectContextUpdateIn(CatalogUpdateIn):
    """Atualização de contexto: os campos comuns (nome, código, situação).

    `eapPrefix` deixou de existir na API (P1.3.1); se um cliente antigo ainda o
    enviar, o campo é ignorado e a coluna legada não é alterada."""
