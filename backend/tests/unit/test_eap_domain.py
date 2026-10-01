from __future__ import annotations

import pytest

from app.domain.eap import (
    EapIssueCode,
    EapLevel,
    EapRuleError,
    assert_equipment_eap_level,
    build_full_eap_code,
    check_against_catalog,
    parse_eap_reference,
    validate_eap_node,
)


@pytest.mark.parametrize(
    ("prefix", "eap", "expected"),
    [
        ("23", "01.A", "2301.A"),
        ("24", "01.A", "2401.A"),
        ("24", "08", "2408"),
        ("123", "01.A", "12301.A"),
        ("03", "08", "0308"),
    ],
)
def test_build_full_eap_code_from_project_prefix(prefix: str, eap: str, expected: str) -> None:
    assert build_full_eap_code(prefix, eap) == expected


@pytest.mark.parametrize(("prefix", "eap"), [("", "01.A"), ("2A", "01.A"), ("23", "  ")])
def test_build_full_eap_code_rejects_invalid_parts(prefix: str, eap: str) -> None:
    with pytest.raises(ValueError):
        build_full_eap_code(prefix, eap)


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
    assert (ref.eap_prefix, ref.eap_code, ref.label) == (prefix, eap, label)
    assert ref.raw == raw
    assert ref.issues == ()


def test_prefix_mismatch_is_flagged_never_corrected() -> None:
    ref = parse_eap_reference("2301.A Caldeira", expected_eap_prefix="24")
    assert ref is not None
    assert (ref.eap_prefix, ref.eap_code, ref.label) == ("23", "01.A", "Caldeira")
    [issue] = ref.issues
    assert issue.code is EapIssueCode.EAP_PREFIX_MISMATCH
    assert (issue.expected, issue.found) == ("24", "23")


def test_unit_prefix_mismatch_no_longer_exists() -> None:
    assert "UNIT_PREFIX_MISMATCH" not in EapIssueCode.__members__


@pytest.mark.parametrize(
    ("raw", "expected", "found", "eap"),
    [
        ("12301.A Caldeira", "23", "123", "01.A"),
        ("2301.A Caldeira", "123", "23", "01.A"),
        ("12308 Destilaria", "124", "123", "08"),
    ],
)
def test_prefix_mismatch_with_prefixes_of_other_lengths(
    raw: str, expected: str, found: str, eap: str
) -> None:
    ref = parse_eap_reference(raw, expected_eap_prefix=expected)
    assert ref is not None
    assert (ref.eap_prefix, ref.eap_code) == (found, eap)
    [issue] = ref.issues
    assert issue.code is EapIssueCode.EAP_PREFIX_MISMATCH
    assert (issue.expected, issue.found) == (expected, found)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("2304.A - Casa de Força", "23"), ("2401.A Caldeira", "24"), ("12301.A Caldeira", "123")],
)
def test_matching_prefix_has_no_issue(raw: str, expected: str) -> None:
    ref = parse_eap_reference(raw, expected_eap_prefix=expected)
    assert ref is not None and ref.issues == ()


@pytest.mark.parametrize(
    "raw", ["Diversos", "Pré-Obra", "Rede Provisória", "Caldeira", "210 Algo", "2.A Algo"]
)
def test_unstructured_values_never_become_eap(raw: str) -> None:
    ref = parse_eap_reference(raw)
    assert ref is not None
    assert ref.structured is False
    assert ref.eap_code is None and ref.eap_prefix is None
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
    assert (ref.eap_prefix, ref.eap_code, ref.label) == (None, eap, label)
    assert ref.issues == ()


def test_expected_prefix_is_context_only_never_copied_into_a_value_without_prefix() -> None:
    ref = parse_eap_reference("01.A Caldeira", expected_eap_prefix="24")
    assert ref is not None
    assert ref.eap_prefix is None
    assert ref.eap_code == "01.A"
    assert not ref.has_issue(EapIssueCode.EAP_PREFIX_MISMATCH)
    assert ref.issues == ()
    # composição posterior, com o prefixo do contexto do projeto
    assert build_full_eap_code("24", ref.eap_code) == "2401.A"


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
