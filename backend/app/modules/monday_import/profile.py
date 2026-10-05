"""ImportProfile: configuração DECLARATIVA de um layout de board Monday.

Um profile traduz a estrutura/semântica da ORIGEM (cabeçalhos, títulos de board
e grupo, rótulos de status, identidade) para os conceitos canônicos do Hub
(`mappings.EQUIPMENT_CONCEPTS` / `COMPONENT_CONCEPTS`). Ele é só dados: não há
código, expressão regular nem plugin vindo do arquivo. Normalização de tipos,
plan, apply e reconciliação são os mesmos para qualquer profile.

O profile NÃO resolve valores para entidades do Hub (usuário, área, disciplina,
Work Package): isso é papel do MappingFile (`mapping_file.py`). Também nunca
contém IDs de ProjectContext ou de catálogos.
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from hashlib import sha256
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.modules.monday_import.mappings import COMPONENT_CONCEPTS, EQUIPMENT_CONCEPTS
from app.modules.monday_import.normalization import canonical_header, canonical_text, clean_text

PROFILES_DIR = Path(__file__).resolve().parent / "profiles"
DEFAULT_PROFILE_PATH = PROFILES_DIR / "monday-equipamentos-legacy.json"
NOT_APPLICABLE: Literal["NOT_APPLICABLE"] = "NOT_APPLICABLE"
STATUS_CONCEPT = "current_stage"
# Mesma regra histórica do parser: um dígito 0-8 isolado ("3.Contrato", "Fase 3").
_STAGE_NUMBER_RE = re.compile(r"(?:^|\s)([0-8])(?:\.|\s|$)")


class ImportProfileError(ValueError):
    pass


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class BoardRules(_Strict):
    """Título do board: linha com uma única célula na coluna A."""

    title_prefixes: tuple[str, ...] = ()
    # True: board sem título reconhecido é incompatível (erro). False: só aviso.
    title_required: bool = False


class GroupRules(_Strict):
    """Títulos de grupo: linha com uma única célula na coluna A.

    O grupo é contexto estrutural. Só vira estágio quando o status da linha está
    vazio E `stage_fallback_from_group` é True; nunca sobrescreve status explícito.
    """

    stage_prefixes: tuple[str, ...] = ()  # "Fase" reconhece "Fase 3 - ..."
    other_titles: tuple[str, ...] = ()
    not_applicable_titles: tuple[str, ...] = ()
    stage_fallback_from_group: bool = False


class SectionRules(_Strict):
    """Cabeçalhos de um nível (Equipment ou Component)."""

    # conceito canônico -> cabeçalhos aceitos na origem
    aliases: dict[str, tuple[str, ...]]
    # conceitos que, juntos, identificam a linha de cabeçalho
    header_signature: tuple[str, ...] = ("name",)
    # só Component: primeira célula do cabeçalho de subitens ("Subitems")
    header_markers: tuple[str, ...] = ()
    required: tuple[str, ...] = ("name",)
    # colunas conhecidas e deliberadamente não usadas: ficam no raw, não são "unknown"
    ignored_headers: tuple[str, ...] = ()
    # conceito que carrega o ID estável do item na origem (None = sem ID)
    external_id_concept: str | None = None

    def alias_map(self) -> dict[str, str]:
        return {
            canonical_header(header): concept
            for concept, headers in self.aliases.items()
            for header in headers
        }

    def ignored_set(self) -> frozenset[str]:
        return frozenset(canonical_header(header) for header in self.ignored_headers)

    def _validate(self, level: str, allowed: frozenset[str]) -> None:
        seen: dict[str, str] = {}
        for concept, headers in self.aliases.items():
            if concept not in allowed:
                raise ImportProfileError(f"{level}: conceito canônico desconhecido '{concept}'")
            if not headers:
                raise ImportProfileError(f"{level}: conceito '{concept}' sem nenhum cabeçalho de origem")
            for header in headers:
                key = canonical_header(header)
                if not key:
                    raise ImportProfileError(f"{level}: cabeçalho em branco para '{concept}'")
                if key in seen and seen[key] != concept:
                    raise ImportProfileError(
                        f"{level}: cabeçalho '{header}' aponta para '{seen[key]}' e '{concept}'"
                    )
                seen[key] = concept
        if "name" not in self.aliases or "name" not in self.required:
            raise ImportProfileError(f"{level}: 'name' deve ter alias e ser obrigatório")
        for label, concepts in (("required", self.required), ("header_signature", self.header_signature)):
            missing = [concept for concept in concepts if concept not in self.aliases]
            if missing:
                raise ImportProfileError(f"{level}: {label} sem alias: {missing}")
        if self.external_id_concept is not None and self.external_id_concept not in self.aliases:
            raise ImportProfileError(f"{level}: external_id_concept '{self.external_id_concept}' sem alias")
        overlap = self.ignored_set() & set(seen)
        if overlap:
            raise ImportProfileError(
                f"{level}: cabeçalho ignorado e mapeado ao mesmo tempo: {sorted(overlap)}"
            )


class StatusRules(_Strict):
    """Tradução do status da origem (conceito `current_stage`) para estágio 0..8."""

    # rótulo exato (comparação sem acento/caixa) -> estágio ou NOT_APPLICABLE
    values: dict[str, int | Literal["NOT_APPLICABLE"]] = Field(default_factory=dict)
    # True: aceita o número do estágio no texto ("3.Contrato" -> 3)
    stage_number_in_text: bool = False


class ExpectedGroup(_Strict):
    equipments: int = Field(ge=0)
    components: int = Field(ge=0)


class ExpectedCounts(_Strict):
    equipments: int = Field(ge=0)
    components: int = Field(ge=0)
    groups: dict[str, ExpectedGroup] = Field(default_factory=dict)


class StageResolution(_Strict):
    stage: int | None
    not_applicable: bool
    recognized: bool


class ImportProfile(_Strict):
    profile_id: str = Field(pattern=r"^[a-z0-9][a-z0-9._-]{2,63}$")
    version: int = Field(ge=1)
    source_system: Literal["monday"]
    description: str = ""
    board: BoardRules = BoardRules()
    groups: GroupRules = GroupRules()
    equipment: SectionRules
    component: SectionRules
    status: StatusRules = StatusRules()
    expected_counts: ExpectedCounts | None = None

    @model_validator(mode="after")
    def _consistent(self) -> ImportProfile:
        self.equipment._validate("equipment", EQUIPMENT_CONCEPTS)
        self.component._validate("component", COMPONENT_CONCEPTS)
        if not self.component.header_markers:
            raise ImportProfileError("component: header_markers obrigatório (ex.: 'Subitems')")
        if self.equipment.header_markers:
            raise ImportProfileError("equipment: header_markers só se aplica a component")
        keys: set[str] = set()
        for label, stage in self.status.values.items():
            key = canonical_text(label)
            if not key:
                raise ImportProfileError("status: rótulo em branco")
            if key in keys:
                raise ImportProfileError(f"status: rótulo repetido '{label}'")
            keys.add(key)
            if isinstance(stage, int) and not 0 <= stage <= 8:
                raise ImportProfileError(f"status: estágio fora de 0..8 para '{label}'")
        if self.status.values and STATUS_CONCEPT not in self.equipment.aliases:
            raise ImportProfileError("status: há valores mapeados, mas 'current_stage' não tem alias")
        return self

    @property
    def sha256(self) -> str:
        canonical = json.dumps(self.model_dump(mode="json"), sort_keys=True, ensure_ascii=False)
        return sha256(canonical.encode("utf-8")).hexdigest()

    def identity(self) -> dict[str, Any]:
        return {"profileId": self.profile_id, "version": self.version, "sha256": self.sha256}

    # -- regras estruturais usadas pelo parser ----------------------------------------------

    def is_board_title(self, text: str | None) -> bool:
        canonical = canonical_text(text)
        return any(canonical.startswith(canonical_text(prefix)) for prefix in self.board.title_prefixes)

    def _stage_prefixed(self, canonical: str) -> int | None:
        for prefix in self.groups.stage_prefixes:
            head = canonical_text(prefix)
            if canonical.startswith(head):
                match = re.match(r"\s+([0-8])\b", canonical[len(head) :])
                if match:
                    return int(match.group(1))
        return None

    def is_group_title(self, text: str | None) -> bool:
        canonical = canonical_text(text)
        titles = (*self.groups.other_titles, *self.groups.not_applicable_titles)
        exact = {canonical_text(title) for title in titles}
        return canonical in exact or self._stage_prefixed(canonical) is not None

    def group_is_not_applicable(self, group: str | None) -> bool:
        return canonical_text(group) in {canonical_text(title) for title in self.groups.not_applicable_titles}

    def resolve_stage(self, raw: Any) -> StageResolution:
        text = clean_text(raw)
        if text is None:
            return StageResolution(stage=None, not_applicable=False, recognized=True)
        mapped = {canonical_text(label): stage for label, stage in self.status.values.items()}.get(
            canonical_text(text)
        )
        if mapped == NOT_APPLICABLE:
            return StageResolution(stage=None, not_applicable=True, recognized=True)
        if isinstance(mapped, int):
            return StageResolution(stage=mapped, not_applicable=False, recognized=True)
        if self.status.stage_number_in_text:
            match = _STAGE_NUMBER_RE.search(text)
            if match is not None:
                return StageResolution(stage=int(match.group(1)), not_applicable=False, recognized=True)
        return StageResolution(stage=None, not_applicable=False, recognized=False)


def load_profile(path: str | Path) -> ImportProfile:
    source = Path(path)
    try:
        document = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ImportProfileError(f"profile ilegível em {source}: {exc}") from exc
    try:
        return ImportProfile.model_validate(document)
    except ValueError as exc:
        raise ImportProfileError(f"profile inválido em {source}: {exc}") from exc


def runtime_profiles() -> list[ImportProfile]:
    """Profiles de runtime versionados com a aplicação (`profiles/*.json`).

    Fixtures de teste ficam fora deste diretório e nunca aparecem aqui.
    """
    return sorted(
        (load_profile(path) for path in PROFILES_DIR.glob("*.json")),
        key=lambda item: (item.profile_id, item.version),
    )


def load_runtime_profile(profile_id: str) -> ImportProfile:
    """Seleção por ID (nunca por caminho vindo do cliente)."""
    for profile in runtime_profiles():
        if profile.profile_id == profile_id:
            return profile
    raise ImportProfileError(f"profile de importação desconhecido: {profile_id}")


@lru_cache(maxsize=1)
def default_profile() -> ImportProfile:
    """Profile histórico versionado: comportamento padrão quando nenhum é informado."""
    return load_profile(DEFAULT_PROFILE_PATH)
