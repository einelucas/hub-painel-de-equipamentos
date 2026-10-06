"""Evidências para criar catálogos: prioridade, fonte oficial, LGE, mapping manual.

Planilhas sintéticas montadas em memória; nenhum dado real.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.modules.eap_catalog.consolidated import ConsolidatedCatalogError, load_consolidated_catalog
from app.modules.monday_import.catalog_evidence import (
    CatalogEvidence,
    EvidenceSource,
    build_catalog_evidence,
    evidence_key,
    load_lge_evidence,
    reliable_label,
)
from app.modules.monday_import.mapping_file import MappingFileSchema, mapping_file_sha256
from tests.unit.monday_xlsx_fixture import build_workbook


def test_evidence_key_is_deterministic_without_fuzzy() -> None:
    assert evidence_key("Disciplína  Sintética.") == evidence_key("disciplina sintetica")
    assert evidence_key("Disc. Sint.") != evidence_key("Disciplina Sintetica")


def test_truncated_label_is_not_reliable() -> None:
    assert reliable_label("Nome Sintético ...") is None
    assert reliable_label("Nome Sintético…") is None
    assert reliable_label("  Nome   Sintético ") == "Nome Sintético"


def test_priority_monday_then_lge_then_manual() -> None:
    evidence = CatalogEvidence()
    evidence.add_discipline("Disc Sintética", "AAA", EvidenceSource.MANUAL_MAPPING)
    assert evidence.discipline_code("disc sintetica").source is EvidenceSource.MANUAL_MAPPING
    evidence.add_discipline("Disc Sintética", "AAA", EvidenceSource.LGE)
    assert evidence.discipline_code("disc sintetica").source is EvidenceSource.LGE


def test_diverging_sources_never_choose() -> None:
    evidence = CatalogEvidence()
    evidence.add_discipline("Disc Sintética", "AAA", EvidenceSource.LGE)
    evidence.add_discipline("Disc Sintética", "BBB", EvidenceSource.MANUAL_MAPPING)
    lookup = evidence.discipline_code("Disc Sintética")
    assert not lookup.found
    assert {item.value for item in lookup.conflict} == {"AAA", "BBB"}


def test_same_source_ambiguous_never_chooses() -> None:
    evidence = CatalogEvidence()
    evidence.add_eap_name("23", "Nome Um", EvidenceSource.MONDAY)
    evidence.add_eap_name("23", "Nome Dois", EvidenceSource.MONDAY)
    assert not evidence.eap_name("23").found


def test_official_catalog_is_authoritative() -> None:
    evidence = CatalogEvidence()
    evidence.add_eap_name("23", "Nome Monday", EvidenceSource.MONDAY)
    evidence.add_eap_name("23", "Nome LGE", EvidenceSource.LGE)
    evidence.add_eap_name("23", "Nome Oficial", EvidenceSource.OFFICIAL_CATALOG)
    lookup = evidence.eap_name("23")
    assert (lookup.value, lookup.source) == ("Nome Oficial", EvidenceSource.OFFICIAL_CATALOG)


def test_lge_does_not_provide_work_package_evidence() -> None:
    evidence = CatalogEvidence()
    evidence.add_work_package("WP-S1", "Nome", EvidenceSource.LGE)
    assert not evidence.work_package_name("WP-S1").found


def _lge_bytes() -> bytes:
    support = [
        ["TABELA DE APOIO SINTÉTICA"],
        [],
        [],
        [
            "PARÂMETRO",
            None,
            None,
            None,
            "DISCIPLINA",
            "SIGLA DISCIPLINA",
            None,
            "CÓD. ÁREA (EAP)",
            "ÁREA / SETOR",
            "PROCESSO",
        ],
        [
            None,
            None,
            None,
            None,
            "Disciplina Sintética A.",
            "DSA",
            None,
            "77",
            "Processo Sintético",
            "Processo Sintético",
        ],
        [
            None,
            None,
            None,
            None,
            "Disciplina Sintética B",
            "DSB",
            None,
            "77.A",
            "Área Sintética A",
            "Processo Sintético",
        ],
        [None, None, None, None, None, None, None, "#REF!", "#REF!", "#REF!"],
        [
            None,
            None,
            None,
            None,
            "LT MÁXIMO",
            "123",
            None,
            "78.B",
            "Área Sem Processo",
            "Processo Pai Sintético",
        ],
    ]
    return build_workbook({"Escopo": [["ignorada"]], "Apoio": support})


def test_lge_reader_extracts_discipline_and_eap_tables(tmp_path: Path) -> None:
    path = tmp_path / "lge.xlsx"
    path.write_bytes(_lge_bytes())
    evidence = load_lge_evidence(path)
    assert evidence.discipline_code("Disciplina Sintética A").value == "DSA"  # ponto final trivial
    assert evidence.discipline_code("Disciplina Sintética B").value == "DSB"
    assert not evidence.discipline_code("LT MÁXIMO").found  # fora do bloco contíguo / sigla inválida
    assert evidence.eap_name("77.A").value == "Área Sintética A"
    assert evidence.eap_name("77").value == "Processo Sintético"
    assert evidence.eap_name("78").value == "Processo Pai Sintético"  # processo pela coluna PROCESSO
    assert evidence.eap_name("77.A").source is EvidenceSource.LGE


def test_build_catalog_evidence_aggregates_monday_labels_and_manual() -> None:
    manual = MappingFileSchema.model_validate(
        {
            "catalogEvidence": {
                "disciplines": {"Disc Monday": {"code": "DMO"}},
                "workPackages": {"WP-S9": {"name": "Pacote Manual"}},
                "eapProcesses": {"88": {"name": "Processo Manual"}},
                "suppliers": {"9009": {"legalName": "Fornecedor Manual SA"}},
            }
        }
    ).catalog_evidence
    records = [
        {"area_name": "2388.C - Área Monday C"},
        {"area_name": "2388.D - Área truncada ..."},
        {"area_name": "Sem código"},
    ]
    evidence = build_catalog_evidence(records, manual=manual)
    assert evidence.eap_name("88.C").value == "Área Monday C"
    assert evidence.eap_name("88.C").source is EvidenceSource.MONDAY
    assert not evidence.eap_name("88.D").found
    assert evidence.eap_name("88").source is EvidenceSource.MANUAL_MAPPING
    assert evidence.discipline_code("Disc Monday").value == "DMO"
    assert evidence.work_package_name("WP-S9").value == "Pacote Manual"
    supplier = evidence.supplier("9009")
    assert supplier is not None and supplier.legal_name == "Fornecedor Manual SA"


def test_mapping_sha_unchanged_without_catalog_evidence() -> None:
    legacy = MappingFileSchema.model_validate({"disciplines": {"X": "id-1"}})
    explicit_empty = MappingFileSchema.model_validate({"disciplines": {"X": "id-1"}, "catalogEvidence": {}})
    with_evidence = MappingFileSchema.model_validate(
        {"disciplines": {"X": "id-1"}, "catalogEvidence": {"disciplines": {"X": {"code": "XXX"}}}}
    )
    assert mapping_file_sha256(legacy) == mapping_file_sha256(explicit_empty)
    assert mapping_file_sha256(legacy) != mapping_file_sha256(with_evidence)


def _consolidated_bytes(*, extra_eap: list[list[object]] | None = None) -> bytes:
    eap = [
        [
            "Código EAP",
            "Nível",
            "Nome consolidado",
            "Área / Setor (Apoio)",
            "Processo (Apoio)",
            "Ilha de Processo (Apoio)",
            "Cód. Ilha",
        ],
        ["77", "PROCESSO", "Processo Sintético", None, None, "Ilha Sintética", "ILS"],
        ["77.A", "ÁREA", "Área Sintética A", None, None, "Ilha Sintética", "ILS"],
        ["79", "PROCESSO", "Processo Sem Ilha"],
        ["79.A", "ÁREA", "Área Sem Ilha"],
        *(extra_eap or []),
    ]
    disciplines = [["Disciplina", "Sigla"], ["Disciplina Sintética", "DSI"]]
    return build_workbook({"EAP Consolidada": eap, "Disciplinas": disciplines})


def test_consolidated_catalog_builds_islands_processes_and_areas(tmp_path: Path) -> None:
    path = tmp_path / "consolidado.xlsx"
    path.write_bytes(_consolidated_bytes())
    catalog = load_consolidated_catalog(path)
    assert catalog.errors == []
    by_code = {node["code"]: node for node in catalog.nodes}
    assert by_code["ILS"]["level"] == "ISLAND"
    assert by_code["77"]["parent_code"] == "ILS"
    assert by_code["79"]["parent_code"] is None  # sem ilha: raiz, nenhuma ilha inventada
    assert by_code["77.A"]["parent_code"] == "77"
    assert [(d.name, d.code) for d in catalog.disciplines] == [("Disciplina Sintética", "DSI")]


def test_consolidated_catalog_reports_orphan_area(tmp_path: Path) -> None:
    path = tmp_path / "consolidado.xlsx"
    path.write_bytes(_consolidated_bytes(extra_eap=[["80.A", "ÁREA", "Área Órfã"]]))
    assert any("80.A" in error for error in load_consolidated_catalog(path).errors)


def test_consolidated_catalog_requires_headers(tmp_path: Path) -> None:
    path = tmp_path / "consolidado.xlsx"
    path.write_bytes(build_workbook({"EAP Consolidada": [["x"]], "Disciplinas": [["Disciplina", "Sigla"]]}))
    with pytest.raises(ConsolidatedCatalogError):
        load_consolidated_catalog(path)
