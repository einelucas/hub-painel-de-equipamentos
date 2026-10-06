"""Artefato JSON canônico do catálogo global de fornecedores."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

DEFAULT_DATA_DIR = Path(__file__).resolve().parents[2] / "data"
CATALOG_PATH = DEFAULT_DATA_DIR / "supplier_catalog.json"
CATALOG_FORMAT_VERSION = 1
CORPORATE_CODE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,19}$")


class SupplierCatalogError(ValueError):
    pass


@dataclass(slots=True, frozen=True)
class CatalogSupplier:
    corporate_code: str
    legal_name: str
    trade_name: str | None
    tax_id: str | None
    active: bool
    aliases: tuple[str, ...]
    source_row: int
    evidence: str | None = None
    equipment_count: int | None = None
    source_action: str | None = None


@dataclass(slots=True, frozen=True)
class SupplierCatalog:
    suppliers: tuple[CatalogSupplier, ...]
    source: dict[str, Any] = field(default_factory=dict)
    sha256: str | None = None

    def ordered_suppliers(self) -> list[CatalogSupplier]:
        return sorted(self.suppliers, key=lambda item: item.corporate_code)


def parse_catalog(document: dict[str, Any], *, sha256: str | None = None) -> SupplierCatalog:
    if document.get("format_version") != CATALOG_FORMAT_VERSION:
        raise SupplierCatalogError(f"format_version inesperado: {document.get('format_version')!r}")
    try:
        suppliers = tuple(
            CatalogSupplier(
                corporate_code=item["corporate_code"],
                legal_name=item["legal_name"],
                trade_name=item.get("trade_name"),
                tax_id=item.get("tax_id"),
                active=item["active"],
                aliases=tuple(item.get("aliases", ())),
                source_row=item["source_row"],
                evidence=item.get("evidence"),
                equipment_count=item.get("equipment_count"),
                source_action=item.get("source_action"),
            )
            for item in document["suppliers"]
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise SupplierCatalogError(f"fornecedor inválido no catálogo: {exc}") from exc
    return SupplierCatalog(suppliers, dict(document.get("source", {})), sha256)


def load_catalog(path: Path = CATALOG_PATH) -> SupplierCatalog:
    if not path.is_file():
        raise SupplierCatalogError(f"catálogo não encontrado: {path}")
    raw = path.read_bytes()
    try:
        document = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise SupplierCatalogError(f"JSON inválido em {path}: {exc}") from exc
    return parse_catalog(document, sha256=hashlib.sha256(raw).hexdigest())


def validate_catalog(catalog: SupplierCatalog) -> list[str]:
    errors: list[str] = []
    codes: set[str] = set()
    tax_ids: dict[str, str] = {}
    aliases: dict[str, str] = {}
    for item in catalog.suppliers:
        label = item.corporate_code or "(sem código)"
        if not isinstance(item.corporate_code, str) or not CORPORATE_CODE_RE.fullmatch(item.corporate_code):
            errors.append(f"{label}: corporate_code obrigatório/inválido")
        elif item.corporate_code in codes:
            errors.append(f"{label}: corporate_code duplicado")
        codes.add(item.corporate_code)
        if not isinstance(item.legal_name, str) or not item.legal_name.strip():
            errors.append(f"{label}: legal_name obrigatório")
        elif item.legal_name != item.legal_name.strip() or len(item.legal_name) > 200:
            errors.append(f"{label}: legal_name inválido")
        if item.trade_name is not None and (not item.trade_name.strip() or len(item.trade_name) > 200):
            errors.append(f"{label}: trade_name inválido")
        if type(item.active) is not bool:
            errors.append(f"{label}: active deve ser boolean")
        if item.tax_id is not None:
            if not re.fullmatch(r"\d{14}", item.tax_id):
                errors.append(f"{label}: tax_id deve conter 14 dígitos normalizados")
            holder = tax_ids.setdefault(item.tax_id, item.corporate_code)
            if holder != item.corporate_code:
                errors.append(f"{label}: tax_id {item.tax_id} também pertence ao código {holder}")
        for alias in item.aliases:
            if not isinstance(alias, str) or not alias.strip() or alias != alias.strip() or len(alias) > 200:
                errors.append(f"{label}: alias vazio ou inválido")
                continue
            holder = aliases.setdefault(alias, item.corporate_code)
            if holder != item.corporate_code:
                errors.append(f"{label}: alias {alias!r} também pertence ao código {holder}")
    return errors


def build_catalog_document(workbook: Any) -> dict[str, Any]:
    suppliers = sorted(workbook.suppliers, key=lambda item: item.corporate_code)
    return {
        "format_version": CATALOG_FORMAT_VERSION,
        "description": "Catálogo global de fornecedores oficiais aprovado para carga no Hub.",
        "source": {
            "file": workbook.source_file,
            "sha256": workbook.source_sha256,
            "sheet": workbook.sheet,
        },
        "summary": {
            "suppliers": len(suppliers),
            "active": sum(item.active for item in suppliers),
            "inactive": sum(not item.active for item in suppliers),
            "aliases": sum(len(item.aliases) for item in suppliers),
        },
        "suppliers": [
            {
                "corporate_code": item.corporate_code,
                "legal_name": item.legal_name,
                "trade_name": item.trade_name,
                "tax_id": item.tax_id,
                "active": item.active,
                "aliases": list(item.aliases),
                "source_row": item.source_row,
                "evidence": item.evidence,
                "equipment_count": item.equipment_count,
                "source_action": item.action,
            }
            for item in suppliers
        ],
    }
