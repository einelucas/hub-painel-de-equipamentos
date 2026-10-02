"""Reconciliação READ-ONLY Monday × catálogo EAP (sem banco)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.domain.eap import EapLevel
from app.modules.eap_catalog.catalog import CatalogNode, EapCatalog, load_catalog
from app.modules.eap_reconciliation.monday import build_reconciliation
from app.modules.eap_reconciliation.reconcile import CatalogIndex, MatchStatus, reconcile_value
from app.modules.eap_reconciliation.report import render_markdown
from tests.unit.monday_xlsx_fixture import build_xlsx

S = MatchStatus
REPO = Path(__file__).resolve().parents[3]
EXPORTS = REPO / "references" / "monday_exports"
C2_CANONICAL = [EXPORTS / "Equipamentos_LEM_C2_ fase-0.xlsx", EXPORTS / "Equipamentos_LEM_C2_1789930920.xlsx"]
C2_ARTIFACT = REPO / "backend" / "app" / "data" / "reconciliation" / "lem_c2_eap_reconciliation.json"


def _node(level: EapLevel, code: str, name: str, parent: str | None) -> CatalogNode:
    return CatalogNode(level, code, name, parent)


@pytest.fixture(scope="module")
def index() -> CatalogIndex:
    island, process, area = EapLevel.ISLAND, EapLevel.PROCESS, EapLevel.AREA
    catalog = EapCatalog(
        nodes=(
            _node(island, "D", "Utilidades", None),
            _node(process, "01", "Geração de vapor [SE-02]", "D"),
            _node(area, "01.A", "Caldeira", "01"),
            _node(process, "04", "Geração de energia [SE-01]", "D"),
            _node(area, "04.A", "Casa de força", "04"),
            _node(process, "20", "Fábrica de óleo", None),
            _node(area, "20.C", "Armazenamento de óleo", "20"),
            _node(area, "20.E", "Expedição de óleo", "20"),
            _node(process, "26", "Laboratórios", None),
            _node(area, "26.A", "Laboratório", "26"),
            _node(process, "27", "Etanol", None),
            _node(area, "27.A", "Laboratório", "27"),
        ),
        review_required=(
            {"code": None, "level": "ISLAND", "names_found": ["GERAL"], "reason": "ISLAND_CODE_MISSING"},
            {
                "code": "00.A",
                "level": "AREA",
                "names_found": ["Pipe Rack"],
                "reason": "PARENT_REVIEW_REQUIRED",
            },
            {
                "code": "15.B",
                "level": "AREA",
                "names_found": ["Balanças rodoviária", "Balanças rodoviária - executivo civil"],
                "reason": "DUPLICATE_CODE_DIFFERENT_NAMES",
                "alternatives": ["linha 75", "linha 76"],
            },
        ),
    )
    return CatalogIndex(catalog)


def test_code_and_name_match_separates_observed_prefix(index) -> None:
    result = reconcile_value("2101.A Caldeira", index)
    assert (result.status, result.observed_prefix, result.parsed_code, result.matched_code) == (
        S.MATCH_CODE_AND_NAME,
        "21",
        "01.A",
        "01.A",
    )
    assert result.matched_name == "Caldeira"


@pytest.mark.parametrize(("raw", "prefix"), [("2101.A", "21"), ("01.A", None), ("2304.A", "23")])
def test_code_without_name_is_match_code(index, raw: str, prefix: str | None) -> None:
    result = reconcile_value(raw, index)
    assert result.status is S.MATCH_CODE
    assert result.observed_prefix == prefix
    assert result.parsed_code in {"01.A", "04.A"}


def test_official_code_without_prefix_with_name(index) -> None:
    result = reconcile_value("04.A - Casa de Força", index)
    assert (result.status, result.observed_prefix, result.matched_code) == (
        S.MATCH_CODE_AND_NAME,
        None,
        "04.A",
    )


@pytest.mark.parametrize("raw", ["Caldeira", "caldeira", "  CALDEIRA  ", "Caldeira"])
def test_unique_name_resolves_with_case_and_space_differences(index, raw: str) -> None:
    result = reconcile_value(raw, index)
    assert (result.status, result.matched_code, result.observed_prefix) == (S.MATCH_UNIQUE_NAME, "01.A", None)


def test_unique_name_ignores_accents(index) -> None:
    assert reconcile_value("Casa de Forca", index).matched_code == "04.A"


@pytest.mark.parametrize("raw", ["2104.A Caldeira", "20.C Expedição de Óleo"])
def test_code_takes_precedence_and_conflicting_name_needs_review(index, raw: str) -> None:
    result = reconcile_value(raw, index)
    assert result.status is S.REVIEW_NAME_MISMATCH
    assert result.parsed_code in {"04.A", "20.C"}


@pytest.mark.parametrize("raw", ["2100.A Pipe Rack", "15.B", "Pipe Rack", "pipe rack"])
def test_review_required_codes_and_names_are_never_matched(index, raw: str) -> None:
    result = reconcile_value(raw, index)
    assert result.status is S.REVIEW_EAP_CATALOG
    assert result.matched_code is None


def test_review_by_code_keeps_catalog_alternatives(index) -> None:
    result = reconcile_value("2115.B Balanças rodoviária", index)
    assert result.status is S.REVIEW_EAP_CATALOG
    assert result.candidates == [{"alternatives": ["linha 75", "linha 76"]}]


def test_multiple_distinct_eaps_are_all_reported(index) -> None:
    result = reconcile_value("2101.A Caldeira / 2104.A Casa de Força", index)
    assert result.status is S.REVIEW_MULTIPLE_EAP
    assert [item["code"] for item in result.candidates] == ["01.A", "04.A"]
    assert result.matched_code is None


def test_unknown_structured_code(index) -> None:
    result = reconcile_value("2199.Z Algo", index)
    assert (result.status, result.parsed_code, result.observed_prefix) == (
        S.UNRESOLVED_UNKNOWN_CODE,
        "99.Z",
        "21",
    )


@pytest.mark.parametrize("raw", ["Diversos", "Pré-Obra", "Rede Provisória", "Drenagem", "", None])
def test_generic_or_unknown_names_are_unresolved(index, raw: str | None) -> None:
    assert reconcile_value(raw, index).status is S.UNRESOLVED_GENERIC_VALUE


def test_island_name_is_not_eligible(index) -> None:
    result = reconcile_value("Geral", index)
    assert result.status is S.UNRESOLVED_GENERIC_VALUE
    assert "ILHA" in result.reason


def test_no_fuzzy_or_partial_name_match(index) -> None:
    for raw in ("Caldeira de Biomassa", "Caldeiras", "Casa de força 2"):
        assert reconcile_value(raw, index).status is S.UNRESOLVED_GENERIC_VALUE


def test_ambiguous_name_is_never_auto_matched(index) -> None:
    result = reconcile_value("Laboratório", index)
    assert result.status is S.UNRESOLVED_AMBIGUOUS_NAME
    assert sorted(item["code"] for item in result.candidates) == ["26.A", "27.A"]
    assert result.matched_code is None


def test_equipment_name_is_never_used_to_infer_eap(tmp_path) -> None:
    header = ["Name", "Subelementos", "A.Status", "0.Área"]
    workbook = build_xlsx(
        [
            ["Equipamentos - LEM C2"],
            ["Fase 0 - Nova Demanda"],
            header,
            ["Caldeira de Biomassa", None, "0.Nova demanda", "Diversos"],
            ["Motores", None, "0.Nova demanda", "Caldeira"],
        ]
    )
    source = tmp_path / "board.xlsx"
    source.write_bytes(workbook)
    report = build_reconciliation(project="TESTE", paths=[source], catalog=load_catalog())
    by_name = {record["equipmentName"]: record for record in report["records"]}
    assert by_name["Caldeira de Biomassa"]["status"] == "UNRESOLVED_GENERIC_VALUE"
    assert by_name["Motores"]["matchedEapCode"] == "01.A"


@pytest.mark.skipif(not C2_CANONICAL[0].is_file(), reason="exports Monday C2 ausentes")
def test_versioned_c2_artifact_is_reproducible_from_exports() -> None:
    rebuilt = build_reconciliation(project="LEM C2", paths=C2_CANONICAL, catalog=load_catalog())
    stored = json.loads(C2_ARTIFACT.read_text(encoding="utf-8"))
    for key in ("metrics", "observed_prefixes", "candidate_project_eap_codes", "multiple_eap_equipments"):
        assert stored[key] == rebuilt[key], key
    assert [(r["externalId"], r["status"], r["matchedEapCode"]) for r in stored["records"]] == [
        (r["externalId"], r["status"], r["matchedEapCode"]) for r in rebuilt["records"]
    ]
    assert rebuilt["metrics"]["total_equipment"] == 41
    assert "Reconciliação EAP — LEM C2" in render_markdown(rebuilt)
