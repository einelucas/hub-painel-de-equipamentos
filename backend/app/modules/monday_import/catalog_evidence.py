"""Evidências para CRIAR catálogos na migração Monday → Hub.

Um catálogo novo (disciplina, Work Package, processo/área de EAP, fornecedor) só
é criado quando alguma fonte comprova os dados obrigatórios. As fontes, em ordem
de prioridade:

0. OFFICIAL_CATALOG — catálogo consolidado de EAP e disciplinas (fonte oficial).
   É AUTORITATIVO: quando cobre o código/nome, seu valor é usado e as demais
   fontes não são consultadas;
1. MONDAY — o próprio export selecionado;
2. LGE — Lista Geral de Equipamentos local (tabelas de apoio);
3. MANUAL_MAPPING — `catalogEvidence` no arquivo de mapping (fallback).

Nada aqui cria Equipment, escolhe entre valores divergentes ou aproxima nomes:
a comparação é determinística (caixa, acentos, espaços e pontuação trivial).
Quando duas fontes divergem, o resultado é `conflict` e o catálogo não é criado.

A LGE é auditada como fonte AUXILIAR: os pacotes PWP dela são estratégia de
aquisição provisória e NÃO equivalem ao Work Package do Hub; por isso a LGE não
fornece evidência de Work Package.
"""

from __future__ import annotations

import re
import unicodedata
import zipfile
from collections.abc import Iterable, Iterator, Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from xml.etree.ElementTree import iterparse

from app.domain.eap import (
    AREA_CODE_RE,
    PROCESS_CODE_RE,
    EapLocationKind,
    extract_eap_codes,
    parse_eap_reference,
)


class EvidenceSource(StrEnum):
    OFFICIAL_CATALOG = "OFFICIAL_CATALOG"
    MONDAY = "MONDAY"
    LGE = "LGE"
    MANUAL_MAPPING = "MANUAL_MAPPING"


_TRIVIAL_PUNCTUATION_RE = re.compile(r"[.,;:]+")
_TRUNCATED_RE = re.compile(r"(\.\.\.|…)\s*$")


def reliable_label(label: str | None) -> str | None:
    """Rótulo da origem utilizável como nome: não vazio e não truncado ("...")."""
    text = " ".join((label or "").split())
    if not text or _TRUNCATED_RE.search(text):
        return None
    return text


def evidence_key(value: str | None) -> str:
    """Forma de comparação: sem acentos, casefold, espaços e pontuação trivial
    normalizados. Determinística; não aproxima nomes diferentes."""
    if value is None:
        return ""
    decomposed = unicodedata.normalize("NFKD", str(value))
    text = "".join(c for c in decomposed if not unicodedata.combining(c)).casefold()
    text = _TRIVIAL_PUNCTUATION_RE.sub(" ", text)
    return " ".join(text.split())


@dataclass(slots=True, frozen=True)
class EvidenceValue:
    value: str
    source: EvidenceSource


@dataclass(slots=True, frozen=True)
class EvidenceLookup:
    """Resultado de uma consulta: valor comprovado, ou divergência entre fontes."""

    value: str | None = None
    source: EvidenceSource | None = None
    conflict: tuple[EvidenceValue, ...] = ()

    @property
    def found(self) -> bool:
        return self.value is not None


class _EvidenceTable:
    """Chave → valores por fonte. Uma fonte com dois valores distintos para a mesma
    chave é ambígua e não comprova nada."""

    def __init__(self) -> None:
        self._values: dict[str, dict[EvidenceSource, set[str]]] = {}
        self._display: dict[str, dict[str, str]] = {}

    def add(self, key: str, value: str, source: EvidenceSource) -> None:
        clean_value = " ".join(str(value).split())
        if not key or not clean_value:
            return
        self._values.setdefault(key, {}).setdefault(source, set()).add(evidence_key(clean_value))
        self._display.setdefault(key, {}).setdefault(evidence_key(clean_value), clean_value)

    def lookup(self, key: str, order: Iterable[EvidenceSource]) -> EvidenceLookup:
        by_source = self._values.get(key)
        if not by_source:
            return EvidenceLookup()
        display = self._display[key]
        official = by_source.get(EvidenceSource.OFFICIAL_CATALOG)
        if official:
            # Fonte oficial é autoritativa; ambiguidade nela continua sendo conflito.
            if len(official) > 1:
                return EvidenceLookup(
                    conflict=tuple(
                        EvidenceValue(display[v], EvidenceSource.OFFICIAL_CATALOG) for v in sorted(official)
                    )
                )
            return EvidenceLookup(value=display[next(iter(official))], source=EvidenceSource.OFFICIAL_CATALOG)
        chosen: EvidenceValue | None = None
        for source in order:
            values = by_source.get(source)
            if not values:
                continue
            if len(values) > 1:
                return EvidenceLookup(
                    conflict=tuple(EvidenceValue(display[v], source) for v in sorted(values))
                )
            candidate = EvidenceValue(display[next(iter(values))], source)
            if chosen is None:
                chosen = candidate
            elif evidence_key(candidate.value) != evidence_key(chosen.value):
                # Fontes divergentes: nunca escolher silenciosamente.
                return EvidenceLookup(conflict=(chosen, candidate))
        if chosen is None:
            return EvidenceLookup()
        return EvidenceLookup(value=chosen.value, source=chosen.source)


_DISCIPLINE_ORDER = (EvidenceSource.MONDAY, EvidenceSource.LGE, EvidenceSource.MANUAL_MAPPING)
_EAP_ORDER = (EvidenceSource.MONDAY, EvidenceSource.LGE, EvidenceSource.MANUAL_MAPPING)
_WP_ORDER = (EvidenceSource.MONDAY, EvidenceSource.MANUAL_MAPPING)


@dataclass(slots=True, frozen=True)
class SupplierEvidence:
    legal_name: str
    trade_name: str | None = None
    tax_id: str | None = None
    source: EvidenceSource = EvidenceSource.MANUAL_MAPPING


@dataclass(slots=True)
class CatalogEvidence:
    """Evidências agregadas de todas as fontes, consultadas pelo plan."""

    discipline_codes: _EvidenceTable = field(default_factory=_EvidenceTable)  # nome → sigla
    work_package_names: _EvidenceTable = field(default_factory=_EvidenceTable)  # código → nome
    eap_names: _EvidenceTable = field(default_factory=_EvidenceTable)  # código EAP → nome
    suppliers: dict[str, SupplierEvidence] = field(default_factory=dict)  # código corporativo → dados
    sources_loaded: set[EvidenceSource] = field(default_factory=set)

    # -- registro ---------------------------------------------------------------------

    def add_discipline(self, name: str, code: str, source: EvidenceSource) -> None:
        self.discipline_codes.add(evidence_key(name), code.strip(), source)
        self.sources_loaded.add(source)

    def add_work_package(self, code: str, name: str, source: EvidenceSource) -> None:
        self.work_package_names.add(evidence_key(code), name, source)
        self.sources_loaded.add(source)

    def add_eap_name(self, code: str, name: str, source: EvidenceSource) -> None:
        if PROCESS_CODE_RE.match(code) or AREA_CODE_RE.match(code):
            self.eap_names.add(code, name, source)
            self.sources_loaded.add(source)

    def add_supplier(self, corporate_code: str, evidence: SupplierEvidence) -> None:
        self.suppliers[corporate_code.strip()] = evidence
        self.sources_loaded.add(evidence.source)

    # -- consulta ---------------------------------------------------------------------

    def discipline_code(self, name: str | None) -> EvidenceLookup:
        return self.discipline_codes.lookup(evidence_key(name), _DISCIPLINE_ORDER)

    def work_package_name(self, code: str | None) -> EvidenceLookup:
        return self.work_package_names.lookup(evidence_key(code), _WP_ORDER)

    def eap_name(self, code: str) -> EvidenceLookup:
        return self.eap_names.lookup(code, _EAP_ORDER)

    def supplier(self, corporate_code: str | None) -> SupplierEvidence | None:
        return self.suppliers.get((corporate_code or "").strip())


# --- LGE (somente leitura, streaming) --------------------------------------------------

_NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
_REL_NS = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
_MAX_PART_BYTES = 32 * 1024 * 1024  # só as partes lidas; a aba de escopo (grande) nunca é aberta
_MAX_ENTRIES = 2_000
_CELL_RE = re.compile(r"([A-Z]+)\d*")
_SIGLA_RE = re.compile(r"^[A-Z]{2,6}$")

LGE_SUPPORT_SHEET = "Apoio"
_DISCIPLINE_HEADERS = ("DISCIPLINA", "SIGLA DISCIPLINA")
_EAP_HEADERS = ("CÓD. ÁREA (EAP)", "ÁREA / SETOR", "PROCESSO")


class LgeReadError(ValueError):
    pass


def _column(reference: str | None, previous: int) -> int:
    if not reference:
        return previous + 1
    letters = _CELL_RE.match(reference)
    if letters is None:
        return previous + 1
    number = 0
    for char in letters.group(1):
        number = number * 26 + ord(char) - 64
    return number


def _check_part(archive: zipfile.ZipFile, part: str) -> None:
    info = archive.getinfo(part)
    if info.file_size > _MAX_PART_BYTES:
        raise LgeReadError(f"parte {part} excede o limite de leitura")


def _sheet_part(archive: zipfile.ZipFile, sheet_name: str) -> str:
    rel_ids: dict[str, str] = {}
    for _, element in iterparse(archive.open("xl/workbook.xml")):
        if element.tag == _NS + "sheet":
            rel_ids[element.get("name") or ""] = element.get(_REL_NS + "id") or ""
    rel_id = rel_ids.get(sheet_name)
    if not rel_id:
        raise LgeReadError(f"aba '{sheet_name}' ausente na LGE")
    for _, element in iterparse(archive.open("xl/_rels/workbook.xml.rels")):
        if element.get("Id") == rel_id:
            target = (element.get("Target") or "").lstrip("/")
            return target if target.startswith("xl/") else f"xl/{target}"
    raise LgeReadError(f"aba '{sheet_name}' sem destino na LGE")


def _shared_strings(archive: zipfile.ZipFile) -> list[str]:
    if "xl/sharedStrings.xml" not in archive.namelist():
        return []
    _check_part(archive, "xl/sharedStrings.xml")
    strings: list[str] = []
    for _, element in iterparse(archive.open("xl/sharedStrings.xml")):
        if element.tag == _NS + "si":
            strings.append("".join(node.text or "" for node in element.iter(_NS + "t")))
            element.clear()
    return strings


def _rows(archive: zipfile.ZipFile, part: str, shared: list[str]) -> Iterator[dict[int, str]]:
    _check_part(archive, part)
    for _, element in iterparse(archive.open(part)):
        if element.tag != _NS + "row":
            continue
        values: dict[int, str] = {}
        column = 0
        for cell in element.findall(_NS + "c"):
            column = _column(cell.get("r"), column)
            kind = cell.get("t")
            if kind == "inlineStr":
                text = "".join(node.text or "" for node in cell.iter(_NS + "t"))
            else:
                raw = cell.find(_NS + "v")
                if raw is None or raw.text is None:
                    continue
                text = shared[int(raw.text)] if kind == "s" else raw.text
            text = " ".join(text.split())
            if text:
                values[column] = text
        element.clear()
        yield values


def _header_columns(row: Mapping[int, str], headers: tuple[str, ...]) -> list[int] | None:
    """Colunas dos cabeçalhos procurados, quando todos estão na linha (adjacentes)."""
    by_name = {evidence_key(value): column for column, value in row.items()}
    columns = [by_name.get(evidence_key(header)) for header in headers]
    if any(column is None for column in columns):
        return None
    found = [column for column in columns if column is not None]
    if found != list(range(found[0], found[0] + len(found))):
        return None
    return found


def load_lge_evidence(path: str | Path, evidence: CatalogEvidence | None = None) -> CatalogEvidence:
    """Lê da aba de apoio da LGE as tabelas DISCIPLINA→SIGLA e EAP (código,
    área, processo). Somente leitura; não lê a aba de escopo nem cria Equipment."""
    evidence = evidence or CatalogEvidence()
    try:
        archive = zipfile.ZipFile(path)
    except (OSError, zipfile.BadZipFile) as exc:
        raise LgeReadError(f"LGE ilegível: {exc}") from exc
    with archive:
        if len(archive.infolist()) > _MAX_ENTRIES:
            raise LgeReadError("LGE com entradas demais")
        shared = _shared_strings(archive)
        part = _sheet_part(archive, LGE_SUPPORT_SHEET)
        discipline_cols: list[int] | None = None
        discipline_open = False
        eap_cols: list[int] | None = None
        for row in _rows(archive, part, shared):
            if discipline_cols is None:
                discipline_cols = _header_columns(row, _DISCIPLINE_HEADERS)
                discipline_open = discipline_cols is not None
                if discipline_open:
                    eap_cols = eap_cols or _header_columns(row, _EAP_HEADERS)
                    continue
            if eap_cols is None:
                eap_cols = _header_columns(row, _EAP_HEADERS)
                if eap_cols is not None:
                    continue
            if discipline_open and discipline_cols is not None:
                name = row.get(discipline_cols[0])
                sigla = row.get(discipline_cols[1])
                if not name and not sigla:
                    discipline_open = False  # fim do bloco contíguo da tabela
                elif name and sigla and _SIGLA_RE.match(sigla):
                    evidence.add_discipline(name, sigla, EvidenceSource.LGE)
            if eap_cols is not None:
                code = row.get(eap_cols[0])
                area_name = row.get(eap_cols[1])
                process_name = row.get(eap_cols[2])
                if code and AREA_CODE_RE.match(code):
                    if area_name:
                        evidence.add_eap_name(code, area_name, EvidenceSource.LGE)
                    if process_name:
                        evidence.add_eap_name(code.split(".", 1)[0], process_name, EvidenceSource.LGE)
                elif code and PROCESS_CODE_RE.match(code) and process_name:
                    evidence.add_eap_name(code, process_name, EvidenceSource.LGE)
    return evidence


def add_official_catalog_evidence(
    evidence: CatalogEvidence,
    eap_names: Iterable[tuple[str, str]],
    disciplines: Iterable[tuple[str, str]],
) -> CatalogEvidence:
    """Catálogo oficial (consolidado): EAP (código, nome) e disciplinas (nome, sigla)."""
    for code, name in eap_names:
        evidence.add_eap_name(code, name, EvidenceSource.OFFICIAL_CATALOG)
    for name, code in disciplines:
        evidence.add_discipline(name, code, EvidenceSource.OFFICIAL_CATALOG)
    return evidence


def load_official_catalog_evidence(
    catalog_document: Mapping[str, object], evidence: CatalogEvidence | None = None
) -> CatalogEvidence:
    """Lê o `eap_catalog.json` gerado do catálogo consolidado (nós + disciplinas)."""
    evidence = evidence or CatalogEvidence()
    nodes = catalog_document.get("nodes")
    source = catalog_document.get("source")
    disciplines = source.get("disciplines") if isinstance(source, Mapping) else None
    eap_pairs = [
        (str(node["code"]), str(node["name"]))
        for node in (nodes if isinstance(nodes, list) else [])
        if isinstance(node, Mapping) and node.get("level") in {"PROCESS", "AREA"}
    ]
    discipline_pairs = [
        (str(item["name"]), str(item["code"]))
        for item in (disciplines if isinstance(disciplines, list) else [])
        if isinstance(item, Mapping) and item.get("name") and item.get("code")
    ]
    return add_official_catalog_evidence(evidence, eap_pairs, discipline_pairs)


def build_catalog_evidence(
    normalized_records: Iterable[Mapping[str, object]],
    *,
    manual: object | None = None,
    official_document: Mapping[str, object] | None = None,
    lge_path: str | Path | None = None,
) -> CatalogEvidence:
    """Agrega as fontes de evidência para um plan.

    - oficial: documento do catálogo consolidado (`eap_catalog.json`);
    - Monday: rótulos de localização ("23 - Nome", "23.C - Nome") e, se o layout
      tiver, a sigla da disciplina (`discipline_code`);
    - LGE: tabelas de apoio, quando o caminho local estiver configurado;
    - manual: `catalogEvidence` do mapping (`CatalogEvidenceIn`).
    """
    evidence = CatalogEvidence()
    if official_document is not None:
        load_official_catalog_evidence(official_document, evidence)

    for normalized in normalized_records:
        location = normalized.get("area_name")
        if isinstance(location, str):
            parsed = extract_eap_codes(location)
            if parsed.kind is EapLocationKind.SINGLE:
                reference = parse_eap_reference(location)
                label = reliable_label(reference.label if reference is not None else None)
                if label:
                    evidence.add_eap_name(parsed.codes[0], label, EvidenceSource.MONDAY)
        discipline = normalized.get("discipline_name")
        discipline_code = normalized.get("discipline_code")
        if isinstance(discipline, str) and isinstance(discipline_code, str) and discipline_code.strip():
            evidence.add_discipline(discipline, discipline_code, EvidenceSource.MONDAY)

    if lge_path:
        load_lge_evidence(lge_path, evidence)

    if manual is not None:
        _add_manual(evidence, manual)
    return evidence


def _add_manual(evidence: CatalogEvidence, manual: object) -> None:
    disciplines = getattr(manual, "disciplines", {}) or {}
    for source_value, item in disciplines.items():
        evidence.add_discipline(source_value, item.code, EvidenceSource.MANUAL_MAPPING)
    for code, item in (getattr(manual, "work_packages", {}) or {}).items():
        evidence.add_work_package(code, item.name, EvidenceSource.MANUAL_MAPPING)
    for code, item in (getattr(manual, "eap_processes", {}) or {}).items():
        evidence.add_eap_name(code.strip(), item.name, EvidenceSource.MANUAL_MAPPING)
    for code, item in (getattr(manual, "suppliers", {}) or {}).items():
        evidence.add_supplier(
            code,
            SupplierEvidence(
                legal_name=item.legal_name.strip(),
                trade_name=(item.trade_name or "").strip() or None,
                tax_id=(item.tax_id or "").strip() or None,
                source=EvidenceSource.MANUAL_MAPPING,
            ),
        )
