"""Catálogo EAP canônico versionado (`app/data/eap_catalog.json`) — leitura e validação.

Sem banco e sem XLSX: é o artefato que a carga (`seed.py`) consome. Os nós em
`review_required` documentam o que a Árvore não permite representar de forma
inequívoca; eles nunca são carregados.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.domain.eap import EapLevel, validate_eap_node

CATALOG_PATH = Path(__file__).resolve().parents[2] / "data" / "eap_catalog.json"
RESOLUTIONS_PATH = CATALOG_PATH.with_name("eap_catalog_resolutions.json")
CATALOG_FORMAT_VERSION = 1
# Ilha: letras da própria Árvore ("B", "D"...). Nunca dígitos — um código
# numérico aqui poderia ser confundido com prefixo de projeto.
ISLAND_CODE_RE = re.compile(r"^[A-Z]{1,3}$")
NAME_MAX_LENGTH = 160
_LEVEL_ORDER = {EapLevel.ISLAND: 0, EapLevel.PROCESS: 1, EapLevel.AREA: 2}


class EapCatalogError(ValueError):
    pass


@dataclass(slots=True, frozen=True)
class CatalogNode:
    level: EapLevel
    code: str
    name: str
    parent_code: str | None
    source_rows: tuple[int, ...] = ()


@dataclass(slots=True, frozen=True)
class EapCatalog:
    nodes: tuple[CatalogNode, ...]
    review_required: tuple[dict[str, Any], ...] = ()
    source: dict[str, Any] = field(default_factory=dict)
    sha256: str | None = None

    def ordered_nodes(self) -> list[CatalogNode]:
        """Pais antes de filhos: ISLAND → PROCESS → AREA."""
        return sorted(self.nodes, key=lambda node: (_LEVEL_ORDER[node.level], node.code))

    @property
    def review_codes(self) -> set[str]:
        return {item["code"] for item in self.review_required if item.get("code")}


def parse_catalog(document: dict[str, Any], *, sha256: str | None = None) -> EapCatalog:
    if document.get("format_version") != CATALOG_FORMAT_VERSION:
        raise EapCatalogError(f"format_version inesperado: {document.get('format_version')!r}")
    try:
        nodes = tuple(
            CatalogNode(
                level=EapLevel(item["level"]),
                code=item["code"],
                name=item["name"],
                parent_code=item.get("parent_code"),
                source_rows=tuple(item.get("source_rows", ())),
            )
            for item in document["nodes"]
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise EapCatalogError(f"nó inválido no catálogo: {exc}") from exc
    return EapCatalog(
        nodes=nodes,
        review_required=tuple(document.get("review_required", ())),
        source=dict(document.get("source", {})),
        sha256=sha256,
    )


def load_catalog(path: Path = CATALOG_PATH) -> EapCatalog:
    raw = path.read_bytes()
    try:
        document = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise EapCatalogError(f"JSON inválido em {path}: {exc}") from exc
    return parse_catalog(document, sha256=hashlib.sha256(raw).hexdigest())


def validate_catalog(catalog: EapCatalog) -> list[str]:
    """Regras estruturais do catálogo inteiro. Lista vazia = válido."""
    errors: list[str] = []
    by_code: dict[str, CatalogNode] = {}
    for node in catalog.nodes:
        if node.code in by_code:
            errors.append(f"{node.code}: código duplicado")
        by_code[node.code] = node

    for node in catalog.nodes:
        label = f"{node.code} ({node.level.value})"
        if not node.name.strip() or node.name != node.name.strip():
            errors.append(f"{label}: nome vazio ou com espaços nas pontas")
        if len(node.name) > NAME_MAX_LENGTH:
            errors.append(f"{label}: nome com mais de {NAME_MAX_LENGTH} caracteres")
        if node.level is EapLevel.ISLAND and not ISLAND_CODE_RE.fullmatch(node.code):
            errors.append(f"{label}: código de ilha deve ser letra(s) da Árvore")
        parent = by_code.get(node.parent_code) if node.parent_code is not None else None
        if node.parent_code is not None and parent is None:
            errors.append(f"{label}: pai {node.parent_code} não existe no catálogo")
        else:
            # validate_eap_node cobre formato do código e ALLOWED_PARENT_LEVELS
            # (AREA só sob PROCESS; PROCESS na raiz ou sob ISLAND; ISLAND na raiz).
            errors += [
                f"{label}: {message}"
                for message in validate_eap_node(
                    code=node.code,
                    level=node.level,
                    parent_code=node.parent_code,
                    parent_level=parent.level if parent is not None else None,
                )
            ]
        if node.code in catalog.review_codes:
            errors.append(f"{label}: também listado em review_required")

    for node in catalog.nodes:
        seen: set[str] = set()
        current: CatalogNode | None = node
        while current is not None and current.parent_code is not None:
            if current.code in seen:
                errors.append(f"{node.code}: ciclo na hierarquia")
                break
            seen.add(current.code)
            current = by_code.get(current.parent_code)
    return errors


def build_catalog_document(
    *,
    nodes: list[dict[str, Any]],
    review_required: list[dict[str, Any]],
    source: dict[str, Any],
    summary: dict[str, Any],
) -> dict[str, Any]:
    return {
        "format_version": CATALOG_FORMAT_VERSION,
        "description": (
            "Catálogo EAP corporativo extraído da Árvore de Localização oficial. Códigos sem prefixo "
            "de projeto (o prefixo é ProjectContext.eap_prefix). Itens de review_required NÃO são "
            "carregados."
        ),
        "source": source,
        "summary": summary,
        "nodes": nodes,
        "review_required": review_required,
    }


def load_resolutions(path: Path = RESOLUTIONS_PATH) -> dict[str, Any]:
    """Decisões de domínio aprovadas (código -> EapResolution) usadas na extração."""
    from app.modules.eap_catalog.tree import EapResolution

    document = json.loads(path.read_text(encoding="utf-8"))
    if document.get("format_version") != 1:
        raise EapCatalogError(f"format_version inesperado em {path}")
    resolutions: dict[str, Any] = {}
    for item in document["resolutions"]:
        if item["code"] in resolutions:
            raise EapCatalogError(f"resolução duplicada para {item['code']}")
        resolutions[item["code"]] = EapResolution(
            code=item["code"],
            level=EapLevel(item["level"]),
            canonical_name=item["canonical_name"],
            parent_code=item.get("parent_code"),
            source_names=tuple(item["source_names"]),
            decision=item["decision"],
        )
    return resolutions


def load_tree_decisions(
    path: Path = RESOLUTIONS_PATH,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Todas as decisões aprovadas da extração: resoluções por código, correções
    de digitação por texto da célula ÁREA e cabeçalhos visuais a ignorar."""
    from app.modules.eap_catalog.tree import IgnoredHeader, SourceCorrection

    document = json.loads(path.read_text(encoding="utf-8"))
    corrections: dict[str, Any] = {}
    for item in document.get("source_corrections", []):
        if item["source_area"] in corrections:
            raise EapCatalogError(f"correção duplicada para {item['source_area']}")
        corrections[item["source_area"]] = SourceCorrection(
            source_area=item["source_area"],
            canonical_area=item["canonical_area"],
            expected_name=item["expected_name"],
            decision=item["decision"],
        )
    headers: dict[str, Any] = {}
    for item in document.get("ignored_headers", []):
        headers[item["text"]] = IgnoredHeader(text=item["text"], decision=item["decision"])
    return load_resolutions(path), corrections, headers
