"""Leitura do catálogo consolidado de EAP e disciplinas (fonte OFICIAL).

Planilha local, somente leitura, com duas abas:

- "EAP Consolidada": Código EAP | Nível (PROCESSO/ÁREA) | Nome consolidado |
  ... | Ilha de Processo | Cód. Ilha | ...
- "Disciplinas": Disciplina | Sigla

Os cabeçalhos são localizados pelo nome (nunca pela posição). O nome oficial é
sempre "Nome consolidado". A ilha vem de "Ilha de Processo"/"Cód. Ilha" da linha
do PROCESS; PROCESS sem ilha informada fica na raiz (nenhuma ilha é inventada).
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.domain.eap import AREA_CODE_RE, PROCESS_CODE_RE, EapLevel
from app.modules.monday_import.normalization import canonical_header, clean_text
from app.modules.monday_import.xlsx import XlsxReadError, XlsxSheet, read_sheet

EAP_SHEET = "EAP Consolidada"
DISCIPLINE_SHEET = "Disciplinas"

_EAP_COLUMNS = {
    "code": "Código EAP",
    "level": "Nível",
    "name": "Nome consolidado",
    "island_name": "Ilha de Processo (Apoio)",
    "island_code": "Cód. Ilha",
}
_DISCIPLINE_COLUMNS = {"name": "Disciplina", "code": "Sigla"}
_LEVELS = {"PROCESSO": EapLevel.PROCESS, "AREA": EapLevel.AREA, "ÁREA": EapLevel.AREA}
_ISLAND_CODE_RE = re.compile(r"^[A-Z]{1,3}$")
_SIGLA_RE = re.compile(r"^[A-Z]{2,6}$")


class ConsolidatedCatalogError(ValueError):
    pass


@dataclass(slots=True, frozen=True)
class ConsolidatedDiscipline:
    code: str
    name: str
    row: int


@dataclass(slots=True)
class ConsolidatedCatalog:
    source_file: str
    sha256: str
    nodes: list[dict[str, Any]] = field(default_factory=list)
    disciplines: list[ConsolidatedDiscipline] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def eap_names(self) -> dict[str, str]:
        return {node["code"]: node["name"] for node in self.nodes if node["level"] != EapLevel.ISLAND.value}


def _columns(sheet: XlsxSheet, wanted: dict[str, str]) -> tuple[int, dict[str, int]]:
    targets = {canonical_header(header): key for key, header in wanted.items()}
    for row in sheet.rows:
        found = {
            targets[canonical_header(cell.value)]: column
            for column, cell in row.cells.items()
            if canonical_header(cell.value) in targets
        }
        if len(found) == len(wanted):
            return row.number, found
    missing = ", ".join(wanted.values())
    raise ConsolidatedCatalogError(f"aba '{sheet.name}': cabeçalhos obrigatórios ausentes ({missing})")


def load_consolidated_catalog(path: str | Path) -> ConsolidatedCatalog:
    source = Path(path)
    raw = source.read_bytes()
    catalog = ConsolidatedCatalog(source_file=source.name, sha256=hashlib.sha256(raw).hexdigest())
    try:
        eap_sheet = read_sheet(raw, EAP_SHEET)
        discipline_sheet = read_sheet(raw, DISCIPLINE_SHEET)
    except XlsxReadError as exc:
        raise ConsolidatedCatalogError(str(exc)) from exc

    _read_eap(eap_sheet, catalog)
    _read_disciplines(discipline_sheet, catalog)
    return catalog


def _read_eap(sheet: XlsxSheet, catalog: ConsolidatedCatalog) -> None:
    header_row, cols = _columns(sheet, _EAP_COLUMNS)
    islands: dict[str, dict[str, Any]] = {}
    processes: dict[str, dict[str, Any]] = {}
    areas: list[dict[str, Any]] = []
    seen: set[str] = set()

    for row in sheet.rows:
        if row.number <= header_row:
            continue
        code = clean_text(row.value(cols["code"]))
        if code is None:
            continue
        level_text = (clean_text(row.value(cols["level"])) or "").upper()
        level = _LEVELS.get(level_text)
        name = clean_text(row.value(cols["name"]))
        where = f"linha {row.number} ({code})"
        if level is None:
            catalog.errors.append(f"{where}: nível desconhecido '{level_text}'")
            continue
        if name is None:
            catalog.errors.append(f"{where}: sem nome consolidado")
            continue
        if code in seen:
            catalog.errors.append(f"{where}: código duplicado")
            continue
        seen.add(code)

        if level is EapLevel.PROCESS:
            if not PROCESS_CODE_RE.fullmatch(code):
                catalog.errors.append(f"{where}: código de PROCESS inválido")
                continue
            island_code = clean_text(row.value(cols["island_code"]))
            island_name = clean_text(row.value(cols["island_name"]))
            parent_code: str | None = None
            if island_code and island_name:
                if not _ISLAND_CODE_RE.fullmatch(island_code):
                    catalog.errors.append(f"{where}: código de ilha inválido '{island_code}'")
                    continue
                known = islands.get(island_code)
                if known is not None and known["name"] != island_name:
                    catalog.errors.append(f"{where}: ilha {island_code} com nomes divergentes")
                    continue
                islands.setdefault(
                    island_code,
                    {
                        "level": EapLevel.ISLAND.value,
                        "code": island_code,
                        "name": island_name,
                        "parent_code": None,
                        "source_rows": [],
                    },
                )["source_rows"].append(row.number)
                parent_code = island_code
            processes[code] = {
                "level": level.value,
                "code": code,
                "name": name,
                "parent_code": parent_code,
                "source_rows": [row.number],
            }
        else:
            if not AREA_CODE_RE.fullmatch(code):
                catalog.errors.append(f"{where}: código de ÁREA inválido")
                continue
            areas.append(
                {
                    "level": level.value,
                    "code": code,
                    "name": name,
                    "parent_code": code.split(".", 1)[0],
                    "source_rows": [row.number],
                }
            )

    for area in areas:
        if area["parent_code"] not in processes:
            catalog.errors.append(f"{area['code']}: PROCESS pai {area['parent_code']} ausente no consolidado")
    catalog.nodes = [*islands.values(), *processes.values(), *areas]


def _read_disciplines(sheet: XlsxSheet, catalog: ConsolidatedCatalog) -> None:
    header_row, cols = _columns(sheet, _DISCIPLINE_COLUMNS)
    names: set[str] = set()
    codes: set[str] = set()
    for row in sheet.rows:
        if row.number <= header_row:
            continue
        name = clean_text(row.value(cols["name"]))
        code = clean_text(row.value(cols["code"]))
        if name is None and code is None:
            continue
        where = f"Disciplinas linha {row.number}"
        if name is None or code is None or not _SIGLA_RE.fullmatch(code):
            catalog.errors.append(f"{where}: disciplina/sigla incompleta ou inválida")
            continue
        if name.casefold() in names or code in codes:
            catalog.errors.append(f"{where}: disciplina ou sigla duplicada")
            continue
        names.add(name.casefold())
        codes.add(code)
        catalog.disciplines.append(ConsolidatedDiscipline(code=code, name=name, row=row.number))
