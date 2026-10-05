"""Catálogo EAP: arquivo (fixture sintética), validador e extração da Árvore (sem banco).

Nenhum teste usa a EAP corporativa real (privada); os nomes são fictícios.
"""

from __future__ import annotations

import re

import pytest

from app.domain.eap import EapLevel, EapRuleError, assert_equipment_eap_level
from app.modules.eap_catalog.catalog import (
    CatalogNode,
    EapCatalog,
    load_catalog,
    validate_catalog,
)
from app.modules.eap_catalog.tree import (
    DUPLICATE_CODE,
    ISLAND_CODE_MISSING,
    MALFORMED_MARKER,
    PARENT_REVIEW_REQUIRED,
    POSITION_MISMATCH,
    EapResolution,
    EapResolutionError,
    IgnoredHeader,
    SourceCorrection,
    TreeRow,
    extract_tree,
)
from tests.eap_fixture import CATALOG_PATH, RESOLUTIONS_PATH

ISLAND, PROCESS, AREA = EapLevel.ISLAND, EapLevel.PROCESS, EapLevel.AREA


@pytest.fixture(scope="module")
def catalog() -> EapCatalog:
    return load_catalog(CATALOG_PATH)


def test_versioned_catalog_is_valid(catalog: EapCatalog) -> None:
    assert validate_catalog(catalog) == []


def test_versioned_catalog_codes_are_unique_and_without_project_prefix(catalog: EapCatalog) -> None:
    codes = [node.code for node in catalog.nodes]
    assert len(codes) == len(set(codes))
    for node in catalog.nodes:
        pattern = {ISLAND: r"[A-Z]{1,3}", PROCESS: r"\d{2}", AREA: r"\d{2}\.[A-Z0-9]+"}[node.level]
        assert re.fullmatch(pattern, node.code), node.code
        assert not node.code.startswith("X")


def test_versioned_catalog_hierarchy(catalog: EapCatalog) -> None:
    by_code = {node.code: node for node in catalog.nodes}
    for node in catalog.nodes:
        parent = by_code.get(node.parent_code) if node.parent_code else None
        if node.level is ISLAND:
            assert node.parent_code is None
        elif node.level is PROCESS:
            assert parent is None or parent.level is ISLAND
        else:
            assert parent is not None and parent.level is PROCESS
            assert node.code.startswith(f"{parent.code}.")


def test_versioned_catalog_matches_summary_and_keeps_review_out(catalog: EapCatalog) -> None:
    summary = {level: sum(1 for n in catalog.nodes if n.level is level) for level in EapLevel}
    assert summary == {ISLAND: 2, PROCESS: 8, AREA: 9}
    # P0.4.1: as pendências da Árvore foram resolvidas por decisões aprovadas.
    assert catalog.review_required == ()
    assert catalog.review_codes == set()
    assert catalog.source["file"].startswith("ARVORE-SINTETICA")


def _catalog(*nodes: tuple[EapLevel, str, str | None], review: tuple[str, ...] = ()) -> EapCatalog:
    return EapCatalog(
        nodes=tuple(CatalogNode(level, code, f"Nó {code}", parent) for level, code, parent in nodes),
        review_required=tuple({"code": code} for code in review),
    )


def test_validator_accepts_process_without_area_and_root_process() -> None:
    assert validate_catalog(_catalog((ISLAND, "B", None), (PROCESS, "08", "B"), (PROCESS, "10", None))) == []


@pytest.mark.parametrize(
    ("nodes", "review", "fragment"),
    [
        (((PROCESS, "01", None), (PROCESS, "01", None)), (), "duplicado"),
        (((AREA, "01.A", "01"),), (), "não existe"),
        (((ISLAND, "B", None), (AREA, "01.A", "B")), (), "AREA não pode ter pai do nível ISLAND"),
        (((ISLAND, "B", None), (ISLAND, "C", "B")), (), "ISLAND não pode ter pai"),
        (((PROCESS, "2301", None),), (), "PROCESS deve ter 2 dígitos"),
        (((PROCESS, "23", None), (AREA, "2301.A", "23")), (), "AREA deve seguir"),
        (((ISLAND, "23", None),), (), "código de ilha"),
        (((PROCESS, "01", None),), ("01",), "review_required"),
        (((PROCESS, "01", "02"), (PROCESS, "02", "01")), (), "ciclo"),
    ],
)
def test_validator_rejects_invalid_catalogs(nodes, review, fragment) -> None:
    errors = validate_catalog(_catalog(*nodes, review=review))
    assert any(fragment in error for error in errors), errors


def test_equipment_may_use_process_or_area_but_never_island() -> None:
    assert_equipment_eap_level(PROCESS)
    assert_equipment_eap_level(AREA)
    with pytest.raises(EapRuleError):
        assert_equipment_eap_level(ISLAND)


def _rows(*values: tuple[str, str | None]) -> list[TreeRow]:
    return [TreeRow(number, area, sector) for number, (area, sector) in enumerate(values, start=2)]


def test_extract_reads_islands_processes_areas_and_ignores_responsibility_rows() -> None:
    tree = extract_tree(
        _rows(
            ("XD Ilha Sintética D", None),
            ("X01", "Processo Sintético A  "),
            ("X01.A", "Área Sintética Alfa"),
            ("X01.A", "Área Sintética Alfa"),
            ("X16", "Processo Sintético P"),
            ("Materiais", None),
            ("Geral", "Controle sintético de listas"),
        )
    )
    assert [(n.level, n.code, n.name, n.parent_code) for n in tree.nodes] == [
        (ISLAND, "D", "Ilha Sintética D", None),
        (PROCESS, "01", "Processo Sintético A", "D"),
        (PROCESS, "16", "Processo Sintético P", "D"),
        (AREA, "01.A", "Área Sintética Alfa", "01"),
    ]
    assert tree.review_required == []
    assert tree.non_eap_rows == [7, 8]


def test_extract_sends_ambiguous_nodes_and_descendants_to_review() -> None:
    tree = extract_tree(
        _rows(
            ("X GERAL", None),
            ("X00", "Geral"),
            ("X00", "Layout Sintético"),
            ("X00.A", "Estrutura Sintética"),
            ("XB Ilha Sintética B", None),
            ("X02", "Processo Sintético Q"),
            ("X06", "Processo Sintético C"),
            ("X02.G", "Área Sintética Gama-Executivo"),
            ("XE Ilha Sintética E", None),
            ("X15", "Processo Sintético D"),
            ("X15.B", "Área Sintética Delta"),
            ("X15.B", "Área Sintética Delta - executivo"),
            ("XX21", "Processo Sintético Ar"),
            ("XX21.A", "Área Sintética Épsilon"),
        )
    )
    reasons = {(item.level, item.code): item.reason for item in tree.review_required}
    assert reasons == {
        (ISLAND, None): ISLAND_CODE_MISSING,
        (PROCESS, "00"): DUPLICATE_CODE,
        (PROCESS, "21"): MALFORMED_MARKER,
        (AREA, "00.A"): PARENT_REVIEW_REQUIRED,
        (AREA, "02.G"): POSITION_MISMATCH,
        (AREA, "15.B"): DUPLICATE_CODE,
        (AREA, "21.A"): MALFORMED_MARKER,
    }
    assert {n.code for n in tree.nodes} == {"B", "E", "02", "06", "15"}
    duplicated = next(item for item in tree.review_required if item.code == "00")
    assert duplicated.source_rows == [3, 4] and duplicated.names_found == ["Geral", "Layout Sintético"]


def test_general_areas_family_00_is_a_root_process_with_documented_resolution(catalog: EapCatalog) -> None:
    by_code = {node.code: node for node in catalog.nodes}
    general = by_code["00"]
    assert (general.level, general.name, general.parent_code) == (PROCESS, "Geral", None)
    children = sorted(node.code for node in catalog.nodes if node.parent_code == "00")
    assert children == ["00.A", "00.C"]
    assert all(by_code[code].level is AREA for code in children)
    assert by_code["00.C"].name.startswith("Rede Sintética (")
    assert not any(node.level is ISLAND and node.name.upper() == "GERAL" for node in catalog.nodes)
    for code in ("00", "00.A", "00.C"):
        assert_equipment_eap_level(by_code[code].level)


def test_resolutions_file_documents_source_names_for_00() -> None:
    from app.modules.eap_catalog.catalog import load_resolutions

    resolution = load_resolutions(RESOLUTIONS_PATH)["00"]
    assert resolution.canonical_name == "Geral" and resolution.parent_code is None
    assert resolution.source_names == ("Geral Sintético", "Layout Sintético", "Bloco Sintético")


def _general_block_rows() -> list[TreeRow]:
    return _rows(
        ("X GERAL", None),
        ("X00", "Geral Sintético"),
        ("X00", "Layout Sintético"),
        ("X00", "Bloco Sintético"),
        ("X00.A", "Estrutura Sintética"),
        ("XB Ilha Sintética B", None),
        ("X15", "Processo Sintético D"),
        ("X15.B", "Área Sintética Delta"),
        ("X15.B", "Área Sintética Delta - executivo"),
    )


def _resolution(source_names: tuple[str, ...]) -> dict[str, EapResolution]:
    return {"00": EapResolution("00", PROCESS, "Geral", None, source_names, "decisão de teste")}


def test_resolution_turns_duplicate_00_into_root_process_and_releases_children() -> None:
    names = ("Geral Sintético", "Layout Sintético", "Bloco Sintético")
    tree = extract_tree(_general_block_rows(), _resolution(names))
    nodes = {n.code: n for n in tree.nodes}
    assert (nodes["00"].name, nodes["00"].parent_code, nodes["00"].source_rows) == ("Geral", None, [3, 4, 5])
    assert nodes["00"].as_dict()["source_names"] == list(names)
    assert nodes["00.A"].parent_code == "00"
    # A resolução vale só para 00: 15.B (também duplicado) continua em revisão.
    assert {(r.code, r.reason) for r in tree.review_required} == {
        (None, ISLAND_CODE_MISSING),
        ("15.B", DUPLICATE_CODE),
    }


def test_resolution_refuses_to_apply_when_source_names_differ() -> None:
    with pytest.raises(EapResolutionError):
        extract_tree(_general_block_rows(), _resolution(("Geral Sintético", "Layout Sintético")))


def test_resolution_without_matching_code_is_rejected() -> None:
    rows = _rows(("XB Ilha Sintética B", None), ("X02", "Processo Sintético Q"))
    with pytest.raises(EapResolutionError):
        extract_tree(rows, _resolution(("Geral",)))


def test_approved_tree_corrections_in_versioned_catalog(catalog: EapCatalog) -> None:
    by_code = {node.code: node for node in catalog.nodes}
    assert (by_code["21"].level, by_code["21"].name) == (PROCESS, "Processo Sintético Ar")
    assert (by_code["21.A"].level, by_code["21.A"].parent_code) == (AREA, "21")
    assert (by_code["06.G"].level, by_code["06.G"].parent_code) == (AREA, "06")
    assert by_code["06.G"].name == "Área Sintética Gama-Executivo"
    assert "02.G" not in by_code
    assert [node.code for node in catalog.nodes].count("15.B") == 1
    assert by_code["15.B"].parent_code == "15"
    assert not any(node.level is ISLAND and node.name.upper() == "GERAL" for node in catalog.nodes)
    assert catalog.source["ignored_header_rows"] == [2]
    assert catalog.source["source_corrections_applied"] == ["X02.G", "XX21", "XX21.A"]


def test_tree_decisions_file_lists_each_approved_correction() -> None:
    from app.modules.eap_catalog.catalog import load_tree_decisions

    resolutions, corrections, headers = load_tree_decisions(RESOLUTIONS_PATH)
    assert set(resolutions) == {"00", "15.B"}
    assert {c.source_area: c.canonical_area for c in corrections.values()} == {
        "XX21": "X21",
        "XX21.A": "X21.A",
        "X02.G": "X06.G",
    }
    assert set(headers) == {"X GERAL"}


def _corrections() -> dict[str, SourceCorrection]:
    return {
        "XX21": SourceCorrection("XX21", "X21", "Processo Sintético Ar", "digitação"),
        "XX21.A": SourceCorrection("XX21.A", "X21.A", "Área Sintética Épsilon", "digitação"),
        "X02.G": SourceCorrection("X02.G", "X06.G", "Área Sintética Gama-Executivo", "digitação"),
    }


def _correction_rows() -> list[TreeRow]:
    return _rows(
        ("X GERAL", None),
        ("XB Ilha Sintética B", None),
        ("X02", "Processo Sintético Q"),
        ("X06", "Processo Sintético C"),
        ("X02.G", "Área Sintética Gama-Executivo"),
        ("XE Ilha Sintética E", None),
        ("X15", "Processo Sintético D"),
        ("X15.B", "Área Sintética Delta"),
        ("X15.B", "Área Sintética Delta - executivo"),
        ("XD Ilha Sintética D", None),
        ("XX21", "Processo Sintético Ar"),
        ("XX21.A", "Área Sintética Épsilon"),
    )


def test_source_corrections_header_and_duplicate_resolution_leave_no_review() -> None:
    tree = extract_tree(
        _correction_rows(),
        {
            "15.B": EapResolution(
                "15.B",
                AREA,
                "Área Sintética Delta",
                "15",
                ("Área Sintética Delta", "Área Sintética Delta - executivo"),
                "x",
            )
        },
        _corrections(),
        {"X GERAL": IgnoredHeader("X GERAL", "título visual")},
    )
    nodes = {node.code: node for node in tree.nodes}
    assert tree.review_required == []
    assert (nodes["21"].level, nodes["21"].parent_code) == (PROCESS, "D")
    assert nodes["21.A"].parent_code == "21"
    assert nodes["06.G"].parent_code == "06"
    assert "02.G" not in nodes
    assert [node.code for node in tree.nodes].count("15.B") == 1
    assert tree.ignored_header_rows == [2]
    assert not any(node.level is ISLAND and node.name == "GERAL" for node in tree.nodes)
    assert nodes["21"].as_dict()["source_corrections"][0]["source"] == "XX21"
    assert nodes["06.G"].as_dict()["source_corrections"][0] == {
        "source": "X02.G",
        "canonical": "X06.G",
        "reason": "digitação",
    }


def test_without_decisions_the_same_rows_stay_in_review() -> None:
    reasons = {(r.code, r.reason) for r in extract_tree(_correction_rows()).review_required}
    assert reasons == {
        (None, ISLAND_CODE_MISSING),
        ("02.G", POSITION_MISMATCH),
        ("15.B", DUPLICATE_CODE),
        ("21", MALFORMED_MARKER),
        ("21.A", MALFORMED_MARKER),
    }


def test_source_correction_refuses_row_with_unexpected_sector() -> None:
    corrections = {"XX21": SourceCorrection("XX21", "X21", "Outro nome", "digitação")}
    rows = _rows(("XD Ilha Sintética D", None), ("XX21", "Processo Sintético Ar"))
    with pytest.raises(EapResolutionError):
        extract_tree(rows, corrections=corrections)


def test_unused_correction_or_header_is_rejected() -> None:
    rows = _rows(("XD Ilha Sintética D", None), ("X01", "Processo Sintético A"))
    with pytest.raises(EapResolutionError):
        extract_tree(rows, corrections=_corrections())
    with pytest.raises(EapResolutionError):
        extract_tree(rows, ignored_headers={"X GERAL": IgnoredHeader("X GERAL", "título")})
