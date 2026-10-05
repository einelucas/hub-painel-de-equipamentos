from __future__ import annotations

import pytest

from app.domain.eap import (
    EapIssueCode,
    EapLevel,
    EapLocationKind,
    EapRuleError,
    assert_equipment_eap_level,
    check_against_catalog,
    extract_eap_codes,
    parse_eap_reference,
    validate_eap_node,
)


@pytest.mark.parametrize(
    ("raw", "prefix", "eap", "label"),
    [
        ("2301.A Caldeira", "23", "01.A", "Caldeira"),
        ("2401.A Caldeira", "24", "01.A", "Caldeira"),
        ("12301.A Caldeira", "123", "01.A", "Caldeira"),
        ("2304.A - Casa de Força", "23", "04.A", "Casa de Força"),
        ("2408 Destilaria", "24", "08", "Destilaria"),
        ("2604.a   Casa de Força", "26", "04.A", "Casa de Força"),
        ("2301.A", "23", "01.A", None),
        ("12308 Destilaria", "123", "08", "Destilaria"),
    ],
)
def test_parses_structured_monday_values(raw: str, prefix: str, eap: str, label: str | None) -> None:
    ref = parse_eap_reference(raw)
    assert ref is not None
    assert ref.structured is True
    assert (ref.context_prefix, ref.eap_code, ref.label) == (prefix, eap, label)
    assert ref.raw == raw
    assert ref.issues == ()


def test_prefix_mismatch_concept_no_longer_exists() -> None:
    assert "EAP_PREFIX_MISMATCH" not in EapIssueCode.__members__
    assert "UNIT_PREFIX_MISMATCH" not in EapIssueCode.__members__


@pytest.mark.parametrize(
    "raw", ["Diversos", "Pré-Obra", "Rede Provisória", "Caldeira", "210 Algo", "2.A Algo"]
)
def test_unstructured_values_never_become_eap(raw: str) -> None:
    ref = parse_eap_reference(raw)
    assert ref is not None
    assert ref.structured is False
    assert ref.eap_code is None and ref.context_prefix is None
    assert ref.has_issue(EapIssueCode.UNSTRUCTURED_EAP_VALUE)


@pytest.mark.parametrize(
    ("raw", "eap", "label"),
    [
        ("01.A Caldeira", "01.A", "Caldeira"),
        ("08 Destilaria", "08", "Destilaria"),
        ("04.A - Casa de Força", "04.A", "Casa de Força"),
    ],
)
def test_corporate_code_without_prefix_is_structured(raw: str, eap: str, label: str) -> None:
    ref = parse_eap_reference(raw)
    assert ref is not None
    assert ref.structured is True
    assert (ref.context_prefix, ref.eap_code, ref.label) == (None, eap, label)
    assert ref.issues == ()


def test_code_without_prefix_must_still_exist_in_catalog() -> None:
    catalog = {"01.A": "Caldeira", "08": "Destilaria"}
    known = parse_eap_reference("08 Destilaria")
    unknown = parse_eap_reference("99.Z Inexistente")
    assert known and unknown
    assert check_against_catalog(known, catalog) == ()
    [issue] = check_against_catalog(unknown, catalog)
    assert issue.code is EapIssueCode.UNKNOWN_EAP_CODE
    assert issue.found == "99.Z"


@pytest.mark.parametrize("raw", [None, "", "   "])
def test_empty_values_return_none(raw: str | None) -> None:
    assert parse_eap_reference(raw) is None


def test_catalog_check_reports_unknown_code_and_name_mismatch() -> None:
    catalog = {"01.A": "Caldeira", "04.A": "Casa de Força"}
    unknown = parse_eap_reference("2199.Z Algo")
    renamed = parse_eap_reference("2101.A Gerador de Vapor")
    same = parse_eap_reference("2601.A CALDEIRA")
    assert unknown and renamed and same

    [issue] = check_against_catalog(unknown, catalog)
    assert issue.code is EapIssueCode.UNKNOWN_EAP_CODE
    [issue] = check_against_catalog(renamed, catalog)
    assert issue.code is EapIssueCode.EAP_NAME_MISMATCH
    assert (issue.expected, issue.found) == ("Caldeira", "Gerador de Vapor")
    assert check_against_catalog(same, catalog) == ()


def test_catalog_check_ignores_unstructured_values() -> None:
    ref = parse_eap_reference("Diversos")
    assert ref is not None
    assert check_against_catalog(ref, {"01.A": "Caldeira"}) == ()


@pytest.mark.parametrize("level", [EapLevel.PROCESS, EapLevel.AREA])
def test_equipment_may_point_to_process_or_area(level: EapLevel) -> None:
    assert_equipment_eap_level(level)


def test_equipment_may_not_point_to_island() -> None:
    with pytest.raises(EapRuleError, match="ISLAND"):
        assert_equipment_eap_level(EapLevel.ISLAND)


def test_process_may_stay_at_root_or_under_an_island_only() -> None:
    assert validate_eap_node(code="08", level=EapLevel.PROCESS, parent_code=None, parent_level=None) == []
    assert (
        validate_eap_node(code="08", level=EapLevel.PROCESS, parent_code="I-1", parent_level=EapLevel.ISLAND)
        == []
    )


def test_island_code_only_needs_to_be_non_empty_without_spaces() -> None:
    for code in ("I-1", "ILHA_UTILIDADES", "A", "07"):
        assert validate_eap_node(code=code, level=EapLevel.ISLAND, parent_code=None, parent_level=None) == []
    assert validate_eap_node(code="ILHA 1", level=EapLevel.ISLAND, parent_code=None, parent_level=None)


def test_valid_hierarchy() -> None:
    assert validate_eap_node(code="01", level=EapLevel.PROCESS, parent_code=None, parent_level=None) == []
    assert (
        validate_eap_node(code="01.A", level=EapLevel.AREA, parent_code="01", parent_level=EapLevel.PROCESS)
        == []
    )
    assert validate_eap_node(code="ILHA-1", level=EapLevel.ISLAND, parent_code=None, parent_level=None) == []


@pytest.mark.parametrize(
    ("code", "level", "parent_code", "parent_level"),
    [
        ("2101.A", EapLevel.AREA, "01", EapLevel.PROCESS),  # prefixo da unidade no código
        ("2108", EapLevel.PROCESS, None, None),  # prefixo da unidade no código
        ("04.A", EapLevel.AREA, "01", EapLevel.PROCESS),  # área de outro processo
        ("01.A", EapLevel.AREA, None, None),  # área sem processo
        ("01", EapLevel.PROCESS, "01.A", EapLevel.AREA),  # processo abaixo de área
        ("I1", EapLevel.ISLAND, "01", EapLevel.PROCESS),  # ilha com pai
        ("01 A", EapLevel.AREA, "01", EapLevel.PROCESS),  # espaço no código
    ],
)
def test_invalid_hierarchy(
    code: str, level: EapLevel, parent_code: str | None, parent_level: EapLevel | None
) -> None:
    assert validate_eap_node(code=code, level=level, parent_code=parent_code, parent_level=parent_level)


# P1.3.1 — EAP canônico sem prefixo ------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "codes"),
    [
        ("2303 - Sistema Sintético X", ("03",)),
        ("2316 - Sistema Sintético Y", ("16",)),
        ("2323.I Escritório Sintético", ("23.I",)),
        ("2104.A Área Sintética X", ("04.A",)),
        ("2404.A Área Sintética X", ("04.A",)),
        ("2300 - Geral Sintético", ("00",)),
        ("2300. Geral Sintético", ("00",)),
        ("03 Sistema Sintético", ("03",)),
        ("2304.A - Casa Sintética/Subestação", ("04.A",)),
    ],
)
def test_contextual_prefix_is_removed_from_single_eap(raw: str, codes: tuple[str, ...]) -> None:
    location = extract_eap_codes(raw)
    assert (location.codes, location.kind) == (codes, EapLocationKind.SINGLE)
    assert location.raw == raw  # valor bruto preservado


def test_same_eap_under_different_contextual_prefixes_is_the_same_code() -> None:
    assert extract_eap_codes("2104.A X").codes == extract_eap_codes("2304.A X").codes == ("04.A",)


@pytest.mark.parametrize(
    ("raw", "codes"),
    [
        ("2309 Sintético X / 2319 Sintético Y", ("09", "19")),
        ("2309 X/2319 Y", ("09", "19")),
        ("2309.C Sintético / 2127.B Sintético", ("09.C", "27.B")),
    ],
)
def test_multiple_eaps_are_all_kept_and_never_chosen(raw: str, codes: tuple[str, ...]) -> None:
    location = extract_eap_codes(raw)
    assert (location.codes, location.kind) == (codes, EapLocationKind.MULTIPLE)


def test_same_code_twice_in_one_value_counts_once() -> None:
    assert extract_eap_codes("2309 X / 2309 Y").codes == ("09",)


@pytest.mark.parametrize(
    "raw", ["Diversos", "Pré-Obra", "Outros/Diversos", "Tanques 10/20", "2.A Algo", "210 Algo", "", None]
)
def test_values_without_eap_have_no_candidate(raw: str | None) -> None:
    location = extract_eap_codes(raw)
    assert (location.codes, location.kind) == ((), EapLocationKind.NONE)


def test_unknown_code_is_detected_but_resolution_needs_the_catalog() -> None:
    location = extract_eap_codes("2399.Z Inexistente")
    assert location.codes == ("99.Z",)  # candidato detectado; validação contra EapNode é do plan
