from __future__ import annotations

from dataclasses import replace

import pytest

from app.modules.monday_import.mappings import provisional_equipment_key
from app.modules.supplier_import.plan import (
    AMBIGUOUS,
    LEM_F2_EXPECTED,
    NOT_FOUND,
    PROBABLE,
    SupplierReconciliationError,
    build_supplier_import_plan,
)
from app.modules.supplier_import.workbook import SupplierWorkbookError, load_supplier_workbook
from tests.unit.monday_xlsx_fixture import build_workbook
from tests.unit.supplier_workbook_fixture import (
    alias,
    equipment,
    representative_supplier_workbook,
    supplier_workbook,
)


def _plan(data: bytes):
    return build_supplier_import_plan(
        load_supplier_workbook(data, source_name="t.xlsx"), alias_context="LEM_F2", expected=None
    )


def test_two_aliases_with_same_code_become_one_supplier() -> None:
    plan = _plan(representative_supplier_workbook())

    assert sorted(plan.suppliers) == ["13974", "3026"]
    agi = plan.suppliers["13974"]
    assert agi.aliases == ["AGI BRASIL (MM)", "AGI BRASIL (Grãos)"]
    assert agi.legal_name == "AGI BRASIL INDUSTRIA LTDA"
    assert [a.alias for a in plan.aliases if a.corporate_code == "13974"] == [
        "AGI BRASIL (MM)",
        "AGI BRASIL (Grãos)",
    ]
    assert {(a.source, a.context) for a in plan.aliases} == {("MONDAY", "LEM_F2")}
    assert plan.errors == []


def test_legal_name_comes_from_official_base_never_from_alias() -> None:
    plan = _plan(representative_supplier_workbook())
    assert plan.suppliers["3026"].legal_name == "FLOTTWEG SE"


def test_foreign_supplier_without_document_gets_null_tax_id() -> None:
    plan = _plan(representative_supplier_workbook())
    assert plan.suppliers["3026"].tax_id is None
    assert plan.suppliers["13974"].tax_id == "11111111000111"


def test_links_equipment_by_corporate_code_and_provisional_key() -> None:
    plan = _plan(representative_supplier_workbook())

    links = {link.equipment_name: link for link in plan.links}
    assert sorted(links) == ["Decanter", "Elevador de canecas", "Secador de grãos"]
    assert links["Secador de grãos"].corporate_code == "13974"
    assert links["Secador de grãos"].equipment_source_key == provisional_equipment_key("Secador de grãos")
    assert links["Decanter"].corporate_code == "3026"


def test_ambiguous_is_ignored_and_reported() -> None:
    plan = _plan(representative_supplier_workbook())

    assert [b.name for b in plan.blocked_by(AMBIGUOUS) if b.level == "alias"] == ["ASHCROFT"]
    assert [b.equipment_name for b in plan.blocked_by(AMBIGUOUS) if b.level == "equipment"] == ["Termômetros"]
    assert "692" not in plan.suppliers


def test_probable_is_ignored_even_when_item_says_confirmed() -> None:
    plan = _plan(representative_supplier_workbook())

    blocked = {b.equipment_name for b in plan.blocked_by(PROBABLE) if b.level == "equipment"}
    assert blocked == {"Moega", "Linha de alternativos"}
    assert "448" not in plan.suppliers
    assert all(link.corporate_code != "448" for link in plan.links)


def test_em_definicao_never_becomes_supplier() -> None:
    plan = _plan(representative_supplier_workbook())

    assert [b.name for b in plan.blocked_by(NOT_FOUND) if b.level == "alias"] == ["EM DEFINIÇÃO"]
    assert [b.equipment_name for b in plan.blocked_by(NOT_FOUND) if b.level == "equipment"] == [
        "Atuadores de requeima"
    ]
    assert all(c.legal_name != "EM DEFINIÇÃO" for c in plan.suppliers.values())


def test_em_definicao_inside_confirmed_is_an_error() -> None:
    plan = _plan(
        supplier_workbook(
            confirmed=[alias("EM DEFINIÇÃO", "999", "QUALQUER LTDA")],
            equipments=[],
        )
    )
    assert plan.suppliers == {}
    assert any("marcador" in error for error in plan.errors)


def test_conflicting_official_data_for_same_code_is_an_error() -> None:
    plan = _plan(
        supplier_workbook(
            confirmed=[
                alias("A (MM)", "10", "EMPRESA A LTDA"),
                alias("A (Grãos)", "10", "OUTRA RAZAO LTDA"),
            ],
            equipments=[],
        )
    )
    assert len(plan.suppliers) == 1
    assert any("divergentes" in error for error in plan.errors)


def test_invalid_corporate_code_is_reported() -> None:
    plan = _plan(supplier_workbook(confirmed=[alias("X", "ABC-1", "X LTDA")], equipments=[]))
    assert plan.suppliers == {}
    assert plan.invalid_codes == [{"sheet": "Confirmados", "row": 2, "alias": "X", "code": "ABC-1"}]


def test_item_code_diverging_from_confirmed_alias_is_not_linked() -> None:
    plan = _plan(
        supplier_workbook(
            confirmed=[alias("AMPLA", "3307", "AMPLA LTDA")],
            equipments=[equipment("Trocador", "AMPLA", "9999", "CONFIRMADO")],
        )
    )
    assert plan.links == []
    assert "diverge" in plan.blocked[0].reason


def test_aborts_when_essential_counts_do_not_match() -> None:
    workbook = load_supplier_workbook(representative_supplier_workbook(), source_name="t.xlsx")
    with pytest.raises(SupplierReconciliationError) as caught:
        build_supplier_import_plan(workbook, alias_context="LEM_F2", expected=LEM_F2_EXPECTED)
    assert "equipamentos F2: esperado=99" in str(caught.value)


def test_passes_when_counts_match_expected() -> None:
    workbook = load_supplier_workbook(representative_supplier_workbook(), source_name="t.xlsx")
    expected = replace(
        LEM_F2_EXPECTED,
        equipments=7,
        with_supplier_text=7,
        with_corporate_code=6,
        confirmed_aliases=3,
        confirmed_codes=2,
        probable=1,
        ambiguous=1,
        not_found=1,
    )
    plan = build_supplier_import_plan(workbook, alias_context="LEM_F2", expected=expected)
    assert plan.checks_ok


def test_missing_required_column_fails_explicitly() -> None:
    data = build_workbook(
        {
            "Fornecedores F2": [["Equipamento"]],
            "Confirmados": [["Nome original Monday"]],
            "Prováveis": [["Nome original Monday"]],
            "Ambíguos": [["Nome original Monday"]],
            "Não Encontrados": [["Nome original Monday"]],
        }
    )
    with pytest.raises(SupplierWorkbookError, match="coluna"):
        load_supplier_workbook(data, source_name="t.xlsx")
