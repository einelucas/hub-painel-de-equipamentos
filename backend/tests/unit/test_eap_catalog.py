"""Catálogo EAP canônico: arquivo versionado, validador e extração da Árvore (sem banco)."""

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
    TreeRow,
    extract_tree,
)

ISLAND, PROCESS, AREA = EapLevel.ISLAND, EapLevel.PROCESS, EapLevel.AREA


@pytest.fixture(scope="module")
def catalog() -> EapCatalog:
    return load_catalog()


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
    assert summary == {ISLAND: 7, PROCESS: 21, AREA: 116}
    assert not catalog.review_codes & {node.code for node in catalog.nodes}
    assert {item["status"] for item in catalog.review_required} == {"EAP_REVIEW_REQUIRED"}
    assert catalog.review_codes == {"02.G", "15.B", "21", "21.A"}
    assert [item["level"] for item in catalog.review_required if item["code"] is None] == ["ISLAND"]
    assert catalog.source["file"].startswith("INPASA-DO-PRO-1700-001-07")


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
            ("XD Utilidades", None),
            ("X01", "Geração de vapor  "),
            ("X01.A", "Caldeira"),
            ("X01.A", "Caldeira"),
            ("X16", "Sistema de combate a incêndio"),
            ("Materiais", None),
            ("Geral", "Controle de listas de materiais"),
        )
    )
    assert [(n.level, n.code, n.name, n.parent_code) for n in tree.nodes] == [
        (ISLAND, "D", "Utilidades", None),
        (PROCESS, "01", "Geração de vapor", "D"),
        (PROCESS, "16", "Sistema de combate a incêndio", "D"),
        (AREA, "01.A", "Caldeira", "01"),
    ]
    assert tree.review_required == []
    assert tree.non_eap_rows == [7, 8]


def test_extract_sends_ambiguous_nodes_and_descendants_to_review() -> None:
    tree = extract_tree(
        _rows(
            ("X GERAL", None),
            ("X00", "Geral"),
            ("X00", "Layout Geral"),
            ("X00.A", "Pipe Rack"),
            ("XB Etanol", None),
            ("X02", "Cozimento"),
            ("X06", "Fermentação"),
            ("X02.G", "Fermentação-Executivo Civil"),
            ("XE Grãos", None),
            ("X15", "Recebimento"),
            ("X15.B", "Balanças"),
            ("X15.B", "Balanças - executivo civil"),
            ("XX21", "Ar comprimido"),
            ("XX21.A", "Distribuição de ar"),
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
    assert duplicated.source_rows == [3, 4] and duplicated.names_found == ["Geral", "Layout Geral"]


def test_general_areas_family_00_is_a_root_process_with_documented_resolution(catalog: EapCatalog) -> None:
    by_code = {node.code: node for node in catalog.nodes}
    general = by_code["00"]
    assert (general.level, general.name, general.parent_code) == (PROCESS, "Geral", None)
    children = sorted(node.code for node in catalog.nodes if node.parent_code == "00")
    assert children == ["00.0", "00.A", "00.B", "00.C", "00.D", "00.E", "00.H", "00.I", "00.J"]
    assert all(by_code[code].level is AREA for code in children)
    assert by_code["00.C"].name.startswith("Drenagem (boca de lobo")
    assert not any(node.level is ISLAND and node.name.upper() == "GERAL" for node in catalog.nodes)
    for code in ("00", "00.A", "00.C"):
        assert_equipment_eap_level(by_code[code].level)


def test_resolutions_file_documents_source_names_for_00() -> None:
    from app.modules.eap_catalog.catalog import load_resolutions

    resolution = load_resolutions()["00"]
    assert resolution.canonical_name == "Geral" and resolution.parent_code is None
    assert resolution.source_names == ("Geral INPASA AGROINDUSTRIAL", "Layout Geral", "ADM 3D")


def _general_block_rows() -> list[TreeRow]:
    return _rows(
        ("X GERAL", None),
        ("X00", "Geral INPASA AGROINDUSTRIAL"),
        ("X00", "Layout Geral"),
        ("X00", "ADM 3D"),
        ("X00.A", "Pipe Rack"),
        ("XB Etanol", None),
        ("X15", "Recebimento"),
        ("X15.B", "Balanças"),
        ("X15.B", "Balanças - executivo civil"),
    )


def _resolution(source_names: tuple[str, ...]) -> dict[str, EapResolution]:
    return {"00": EapResolution("00", PROCESS, "Geral", None, source_names, "decisão de teste")}


def test_resolution_turns_duplicate_00_into_root_process_and_releases_children() -> None:
    names = ("Geral INPASA AGROINDUSTRIAL", "Layout Geral", "ADM 3D")
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
        extract_tree(_general_block_rows(), _resolution(("Geral INPASA AGROINDUSTRIAL", "Layout Geral")))


def test_resolution_without_matching_code_is_rejected() -> None:
    rows = _rows(("XB Etanol", None), ("X02", "Cozimento"))
    with pytest.raises(EapResolutionError):
        extract_tree(rows, _resolution(("Geral",)))
