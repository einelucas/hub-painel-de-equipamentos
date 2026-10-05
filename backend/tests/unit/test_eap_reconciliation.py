"""Reconciliação READ-ONLY Monday × catálogo EAP (sem banco).

Somente dados sintéticos: catálogo, decisões e exports fictícios (a EAP real é privada).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.domain.eap import EapLevel
from app.modules.eap_catalog.catalog import CatalogNode, EapCatalog, load_catalog
from app.modules.eap_reconciliation.monday import build_reconciliation
from app.modules.eap_reconciliation.reconcile import (
    SAFE_STATUSES,
    ApprovedAlias,
    CatalogIndex,
    EapAliasError,
    MatchStatus,
    ReconciliationDecisions,
    load_decisions,
    reconcile_value,
)
from app.modules.eap_reconciliation.report import render_markdown
from tests.eap_fixture import ALIASES_PATH, CATALOG_PATH, FIXTURE_DIR
from tests.unit.monday_xlsx_fixture import build_xlsx

S = MatchStatus
SYNTHETIC_ARTIFACT = FIXTURE_DIR / "reconciliation_sintetica.json"
BOARD = "Equipamentos - Obra Sintética"
HEADER = ["Name", "Subelementos", "A.Status", "0.Área"]


def _node(level: EapLevel, code: str, name: str, parent: str | None) -> CatalogNode:
    return CatalogNode(level, code, name, parent)


@pytest.fixture(scope="module")
def index() -> CatalogIndex:
    island, process, area = EapLevel.ISLAND, EapLevel.PROCESS, EapLevel.AREA
    catalog = EapCatalog(
        nodes=(
            _node(island, "D", "Ilha Sintética D", None),
            _node(process, "01", "Processo Sintético A [SX-02]", "D"),
            _node(area, "01.A", "Área Sintética Alfa", "01"),
            _node(process, "04", "Processo Sintético B [SX-01]", "D"),
            _node(area, "04.A", "Galpão Sintético", "04"),
            _node(process, "20", "Processo Sintético G", None),
            _node(area, "20.C", "Depósito Sintético", "20"),
            _node(area, "20.E", "Expedição Sintética", "20"),
            _node(process, "26", "Processo Sintético E", None),
            _node(area, "26.A", "Sala Sintética Comum", "26"),
            _node(process, "27", "Processo Sintético F", None),
            _node(area, "27.A", "Sala Sintética Comum", "27"),
        ),
        review_required=(
            {"code": None, "level": "ISLAND", "names_found": ["GERAL"], "reason": "ISLAND_CODE_MISSING"},
            {
                "code": "00.A",
                "level": "AREA",
                "names_found": ["Estrutura Sintética"],
                "reason": "PARENT_REVIEW_REQUIRED",
            },
            {
                "code": "15.B",
                "level": "AREA",
                "names_found": ["Área Sintética Delta", "Área Sintética Delta - executivo"],
                "reason": "DUPLICATE_CODE_DIFFERENT_NAMES",
                "alternatives": ["linha 75", "linha 76"],
            },
        ),
    )
    return CatalogIndex(catalog)


def test_code_and_name_match_separates_observed_prefix(index) -> None:
    result = reconcile_value("2101.A Área Sintética Alfa", index)
    assert (result.status, result.observed_prefix, result.parsed_code, result.matched_code) == (
        S.MATCH_CODE_AND_NAME,
        "21",
        "01.A",
        "01.A",
    )
    assert result.matched_name == "Área Sintética Alfa"


@pytest.mark.parametrize(("raw", "prefix"), [("2101.A", "21"), ("01.A", None), ("2304.A", "23")])
def test_code_without_name_is_match_code(index, raw: str, prefix: str | None) -> None:
    result = reconcile_value(raw, index)
    assert result.status is S.MATCH_CODE
    assert result.observed_prefix == prefix
    assert result.parsed_code in {"01.A", "04.A"}


def test_official_code_without_prefix_with_name(index) -> None:
    result = reconcile_value("04.A - Galpão Sintético", index)
    assert (result.status, result.observed_prefix, result.matched_code) == (
        S.MATCH_CODE_AND_NAME,
        None,
        "04.A",
    )


@pytest.mark.parametrize(
    "raw", ["Área Sintética Alfa", "área sintética alfa", "  ÁREA SINTÉTICA ALFA  ", "Área Sintética Alfa"]
)
def test_unique_name_resolves_with_case_and_space_differences(index, raw: str) -> None:
    result = reconcile_value(raw, index)
    assert (result.status, result.matched_code, result.observed_prefix) == (S.MATCH_UNIQUE_NAME, "01.A", None)


def test_unique_name_ignores_accents(index) -> None:
    assert reconcile_value("Galpao Sintetico", index).matched_code == "04.A"


@pytest.mark.parametrize("raw", ["2104.A Área Sintética Alfa", "20.C Expedição Sintética"])
def test_code_takes_precedence_and_conflicting_name_needs_review(index, raw: str) -> None:
    result = reconcile_value(raw, index)
    assert result.status is S.REVIEW_NAME_MISMATCH
    assert result.parsed_code in {"04.A", "20.C"}


@pytest.mark.parametrize(
    "raw", ["2100.A Estrutura Sintética", "15.B", "Estrutura Sintética", "estrutura sintética"]
)
def test_review_required_codes_and_names_are_never_matched(index, raw: str) -> None:
    result = reconcile_value(raw, index)
    assert result.status is S.REVIEW_EAP_CATALOG
    assert result.matched_code is None


def test_review_by_code_keeps_catalog_alternatives(index) -> None:
    result = reconcile_value("2115.B Área Sintética Delta", index)
    assert result.status is S.REVIEW_EAP_CATALOG
    assert result.candidates == [{"alternatives": ["linha 75", "linha 76"]}]


def test_multiple_distinct_eaps_are_all_reported(index) -> None:
    result = reconcile_value("2101.A Área Sintética Alfa / 2104.A Galpão Sintético", index)
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


@pytest.mark.parametrize("raw", ["Diversos", "Pré-Obra", "Rede Provisória", "Rede Sintética", "", None])
def test_generic_or_unknown_names_are_unresolved(index, raw: str | None) -> None:
    assert reconcile_value(raw, index).status is S.UNRESOLVED_GENERIC_VALUE


def test_island_name_is_not_eligible(index) -> None:
    result = reconcile_value("Geral", index)
    assert result.status is S.UNRESOLVED_GENERIC_VALUE
    assert "ILHA" in result.reason


def test_no_fuzzy_or_partial_name_match(index) -> None:
    for raw in ("Área Sintética Alfa Extra", "Área Sintética Alfas", "Galpão Sintético 2"):
        assert reconcile_value(raw, index).status is S.UNRESOLVED_GENERIC_VALUE


def test_ambiguous_name_is_never_auto_matched(index) -> None:
    result = reconcile_value("Sala Sintética Comum", index)
    assert result.status is S.UNRESOLVED_AMBIGUOUS_NAME
    assert sorted(item["code"] for item in result.candidates) == ["26.A", "27.A"]
    assert result.matched_code is None


def test_equipment_name_is_never_used_to_infer_eap(tmp_path) -> None:
    workbook = build_xlsx(
        [
            [BOARD],
            ["Fase 0 - Nova Demanda"],
            HEADER,
            ["Área Sintética Alfa - Equipamento A", None, "0.Nova demanda", "Diversos"],
            ["Equipamento Sintético B", None, "0.Nova demanda", "Área Sintética Alfa"],
        ]
    )
    source = tmp_path / "board.xlsx"
    source.write_bytes(workbook)
    report = build_reconciliation(project="TESTE", paths=[source], catalog=load_catalog(CATALOG_PATH))
    by_name = {record["equipmentName"]: record for record in report["records"]}
    assert by_name["Área Sintética Alfa - Equipamento A"]["status"] == "UNRESOLVED_GENERIC_VALUE"
    assert by_name["Equipamento Sintético B"]["matchedEapCode"] == "01.A"


def _synthetic_exports(directory: Path) -> list[Path]:
    """Dois snapshots sintéticos do mesmo board; o segundo repete um equipamento."""
    first = build_xlsx(
        [
            [BOARD],
            ["Fase 0 - Nova Demanda"],
            HEADER,
            ["Equipamento Sintético A", None, "0.Nova demanda", "2101.A Área Sintética Alfa"],
            ["Equipamento Sintético B", None, "0.Nova demanda", "Estrutura Sintética"],
            ["Equipamento Sintético C", None, "0.Nova demanda", "Rede Sintética"],
            ["Equipamento Sintético D", None, "0.Nova demanda", "Geral"],
            ["Equipamento Sintético E", None, "0.Nova demanda", "2104.A"],
            ["Equipamento Sintético F", None, "0.Nova demanda", "Sala Sintética Comum"],
        ]
    )
    second = build_xlsx(
        [
            [BOARD],
            ["Fase 4 - Negociação"],
            HEADER,
            ["Equipamento Sintético A", None, "4.Negociação", "2101.A Área Sintética Alfa"],
            ["Equipamento Sintético G", None, "4.Negociação", "2104.A Galpão Sintético"],
        ]
    )
    paths = [directory / "snapshot-1.xlsx", directory / "snapshot-2.xlsx"]
    for path, content in zip(paths, (first, second), strict=True):
        path.write_bytes(content)
    return paths


def _rebuild_synthetic_artifact(directory: Path) -> dict:
    return build_reconciliation(
        project="OBRA SINTÉTICA",
        paths=_synthetic_exports(directory),
        catalog=load_catalog(CATALOG_PATH),
        decisions=load_decisions(ALIASES_PATH),
    )


ARTIFACT_KEYS = ("metrics", "observed_prefixes", "candidate_project_eap_codes", "multiple_eap_equipments")


def test_versioned_synthetic_artifact_is_reproducible_from_exports(tmp_path) -> None:
    rebuilt = _rebuild_synthetic_artifact(tmp_path)
    stored = json.loads(SYNTHETIC_ARTIFACT.read_text(encoding="utf-8"))
    for key in ARTIFACT_KEYS:
        assert stored[key] == rebuilt[key], key
    assert [(r["externalId"], r["status"], r["matchedEapCode"]) for r in stored["records"]] == [
        (r["externalId"], r["status"], r["matchedEapCode"]) for r in rebuilt["records"]
    ]
    metrics = rebuilt["metrics"]
    assert (metrics["total_equipment"], metrics["auto_match_safe_total"]) == (7, 5)
    assert metrics["unresolved_generic"] == 1
    assert metrics["unresolved_ambiguous_name"] == 1
    assert sum(value for key, value in metrics.items() if key.startswith("review_")) == 0
    assert rebuilt["candidate_project_eap_codes"] == ["00.A", "00.C", "01.A", "04.A"]
    by_value = {record["rawEapValue"]: record for record in rebuilt["records"]}
    assert (by_value["Estrutura Sintética"]["status"], by_value["Estrutura Sintética"]["matchedEapCode"]) == (
        "MATCH_UNIQUE_NAME",
        "00.A",
    )
    assert (by_value["Rede Sintética"]["status"], by_value["Rede Sintética"]["matchedEapCode"]) == (
        "MATCH_APPROVED_ALIAS",
        "00.C",
    )
    assert (by_value["Geral"]["status"], by_value["Geral"]["matchedEapCode"]) == (
        "UNRESOLVED_GENERIC_VALUE",
        None,
    )
    assert "Reconciliação EAP — OBRA SINTÉTICA" in render_markdown(rebuilt)


_NETWORK_OFFICIAL = "Rede Sintética (trecho a, trecho b)"


@pytest.fixture(scope="module")
def general_index() -> CatalogIndex:
    """Bloco 00 sintético: PROCESS raiz 'Geral' + áreas, alias e valor não vinculável."""
    process, area = EapLevel.PROCESS, EapLevel.AREA
    catalog = EapCatalog(
        nodes=(
            _node(process, "00", "Geral", None),
            _node(area, "00.A", "Estrutura Sintética", "00"),
            _node(area, "00.C", _NETWORK_OFFICIAL, "00"),
        ),
        review_required=(
            {"code": None, "level": "ISLAND", "names_found": ["GERAL"], "reason": "ISLAND_CODE_MISSING"},
        ),
    )
    decisions = ReconciliationDecisions(
        aliases={"rede sintetica": ApprovedAlias("Rede Sintética", "00.C", "teste")},
        non_linkable={"geral": "genérico"},
    )
    return CatalogIndex(catalog, decisions)


def test_structure_resolves_to_00a_by_unique_name(general_index) -> None:
    result = reconcile_value("Estrutura Sintética", general_index)
    assert (result.status, result.matched_code) == (S.MATCH_UNIQUE_NAME, "00.A")


def test_network_resolves_by_explicit_approved_alias(general_index) -> None:
    result = reconcile_value("rede sintética", general_index)
    assert (result.status, result.matched_code, result.category) == (S.MATCH_APPROVED_ALIAS, "00.C", "MATCH")
    assert "Alias EAP aprovado" in result.reason


@pytest.mark.parametrize(
    "raw", ["Redes Sintéticas", "Rede Sintética pluvial", "Outra Rede Sintética", "Rede"]
)
def test_alias_is_exact_never_fuzzy(general_index, raw: str) -> None:
    assert reconcile_value(raw, general_index).status is S.UNRESOLVED_GENERIC_VALUE


def test_geral_stays_unresolved_even_with_process_00_named_geral(general_index) -> None:
    result = reconcile_value("Geral", general_index)
    assert (result.status, result.matched_code) == (S.UNRESOLVED_GENERIC_VALUE, None)


def test_code_00_area_still_resolves_by_code(general_index) -> None:
    assert reconcile_value("2100.A Estrutura Sintética", general_index).matched_code == "00.A"


def test_approved_alias_is_safe_and_review_unresolved_are_not() -> None:
    assert S.MATCH_APPROVED_ALIAS in SAFE_STATUSES
    assert not any(status.value.startswith(("REVIEW", "UNRESOLVED")) for status in SAFE_STATUSES)


def test_alias_cannot_shadow_official_name_or_point_to_ineligible_node() -> None:
    catalog = EapCatalog(
        nodes=(
            _node(EapLevel.PROCESS, "00", "Geral", None),
            _node(EapLevel.AREA, "00.A", "Estrutura Sintética", "00"),
        )
    )
    with pytest.raises(EapAliasError):
        CatalogIndex(
            catalog,
            ReconciliationDecisions(
                aliases={"estrutura sintetica": ApprovedAlias("Estrutura Sintética", "00.A", "x")}
            ),
        )
    with pytest.raises(EapAliasError):
        CatalogIndex(catalog, ReconciliationDecisions(aliases={"tubos": ApprovedAlias("Tubos", "99.Z", "x")}))


def test_decisions_file_format() -> None:
    decisions = load_decisions(ALIASES_PATH)
    assert {alias.alias: alias.eap_code for alias in decisions.aliases.values()} == {"Rede Sintética": "00.C"}
    assert set(decisions.non_linkable) == {"geral"}


def test_regenerating_report_preserves_manual_history_section(tmp_path) -> None:
    from app.modules.eap_reconciliation.cli import HISTORY_MARKER, main

    workbook = build_xlsx(
        [
            [BOARD],
            ["Fase 0 - Nova Demanda"],
            HEADER,
            ["Equipamento Sintético B", None, "0.Nova demanda", "Área Sintética Alfa"],
        ]
    )
    source = tmp_path / "board.xlsx"
    source.write_bytes(workbook)
    report = tmp_path / "relatorio.md"
    report.write_text(
        f"conteúdo antigo gerado\n\n{HISTORY_MARKER}\n## Histórico\n- decisão registrada\n", encoding="utf-8"
    )

    assert (
        main(
            [
                "analyze",
                "--project",
                "TESTE",
                "--export",
                str(source),
                "--catalog",
                str(CATALOG_PATH),
                "--aliases",
                str(ALIASES_PATH),
                "--markdown-out",
                str(report),
            ]
        )
        == 0
    )

    text = report.read_text(encoding="utf-8")
    assert "conteúdo antigo gerado" not in text
    assert text.startswith("# Reconciliação EAP — TESTE")
    assert text.count(HISTORY_MARKER) == 1
    assert text.rstrip().endswith("- decisão registrada")
