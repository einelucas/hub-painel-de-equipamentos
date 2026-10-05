"""P1.3.1 — layout exportado por fase: aliases, ignorados, Standby e fases vazias (só sintético)."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from app.modules.monday_import.normalization import canonical_header
from app.modules.monday_import.parser import parse_monday_xlsx
from app.modules.monday_import.profile import ImportProfile, ImportProfileError, default_profile
from tests.unit.monday_multiphase_fixture import (
    MAIN_HEADERS,
    PHASE_GROUPS,
    STANDBY_STATUS,
    SUB_HEADERS,
    SynthEquipment,
    multiphase_boards,
    phase_board,
)

IGNORED = {
    "6.Bypass Suprimentos",
    "A.Retomar Negociação",
    "A.Tempo Negociação",
    "A.Tempo Contrato",
    "F.Contador Júridico",
    "Contador de OC",
    "Contador Neg Concluido",
    "DataLimiteNegociação Mês/Ano",
    "ESPELHO-FORMULA",
    "Prazo Neg (dias)",
    "Projeto",
    "Unidade",
}
# Sem semântica comprovada (vazias ou sem conceito no Hub): continuam UNKNOWN.
STILL_UNKNOWN = {"Conferência", "Pessoas", "S.Escalonamento", "Status de Prazo", "Diferença Negociação"}


def _parse(content: bytes):
    return parse_monday_xlsx(content, source_name="fase.xlsx", profile=default_profile())


def _codes(parsed) -> list[str]:
    return [issue.code for issue in parsed.issues]


def _one(values: dict | None = None, **kwargs):
    equipment = SynthEquipment(name="Equipamento Sintético A", values=values or {}, **kwargs)
    parsed = _parse(phase_board(1, [equipment]))
    [equipment] = parsed.equipments
    return parsed, equipment


def test_layout_has_49_main_and_18_subitem_columns() -> None:
    assert (len(MAIN_HEADERS), len(SUB_HEADERS)) == (49, 18)
    assert len(set(MAIN_HEADERS)) == 49 and len(set(SUB_HEADERS)) == 18


# 1-4. aliases validados semanticamente --------------------------------------------------------


def test_status_prazo_negociacao_is_the_observed_negotiation_status() -> None:
    _, equipment = _one({"Status Prazo Negociação": "💥ATRASADO💥"})
    assert equipment.normalized["negotiation_status_observed"] == "💥ATRASADO💥"


def test_cod_forn_cs_is_the_supplier_corporate_code() -> None:
    _, equipment = _one({"Cód. Forn. CS": 99123.0})
    assert equipment.normalized["supplier_corporate_code"] == "99123"


def test_num_cham_juridico_is_the_legal_ticket_number() -> None:
    _, equipment = _one({"3.Num Cham Juridico": "CHAMADO-SINT-01"})
    assert equipment.normalized["legal_ticket_number"] == "CHAMADO-SINT-01"


def test_subitem_prazo_is_the_negotiation_days_remaining() -> None:
    _, equipment = _one()
    [component] = equipment.components
    assert component.normalized["negotiation_days_remaining_observed"] == 30


# 5-6. ignorados x desconhecidos ---------------------------------------------------------------


def test_ignored_auxiliary_columns_are_not_unknown_and_stay_in_raw() -> None:
    parsed, equipment = _one({"A.Tempo Contrato": "123:45:00", "F.Contador Júridico": 12})
    assert not IGNORED & parsed.unknown_equipment_fields
    assert parsed.unknown_component_fields == set()
    # preservados no raw payload, nunca descartados
    assert set(equipment.raw) >= IGNORED
    assert equipment.raw["ESPELHO-FORMULA"] == "5, 7"
    # lista de espelho NÃO é forçada para inteiro nem para o conceito de frete
    assert "freight_days_mirror" not in equipment.normalized


def test_unvalidated_columns_and_really_new_columns_stay_unknown() -> None:
    parsed = _parse(
        phase_board(
            1,
            [SynthEquipment(name="Equipamento Sintético A", values={"Coluna Nova Sintética": "x"})],
            extra_main_headers=("Coluna Nova Sintética",),
        )
    )
    assert parsed.unknown_equipment_fields == STILL_UNKNOWN | {"Coluna Nova Sintética"}


def test_every_header_is_recognized_ignored_or_unknown() -> None:
    profile = default_profile()
    parsed, _ = _one()
    recognized = set(profile.equipment.alias_map())
    ignored = profile.equipment.ignored_set()
    for header in MAIN_HEADERS:
        key = canonical_header(header)
        buckets = [key in recognized, key in ignored, header in parsed.unknown_equipment_fields]
        assert buckets.count(True) == 1, header


# 7-8. Standby ---------------------------------------------------------------------------------


def test_standby_label_is_operational_status_never_stage_9() -> None:
    parsed = _parse(
        phase_board(0, [SynthEquipment(name="Equipamento Sintético Standby", status=STANDBY_STATUS)])
    )
    [equipment] = parsed.equipments
    assert equipment.normalized["current_stage"] is None  # nunca 9
    assert equipment.normalized["operational_status"] == "STANDBY"
    assert not equipment.normalized.get("current_stage_unrecognized")
    assert "unknown_status_value" not in _codes(parsed)
    assert equipment.group_name == "Fase 0 - Nova Demanda"  # fase estrutural segue o grupo
    assert equipment.raw["A.Status"] == STANDBY_STATUS  # raw preservado


def test_regular_status_has_no_operational_status() -> None:
    _, equipment = _one()
    assert equipment.normalized["current_stage"] == 1
    assert "operational_status" not in equipment.normalized


@pytest.mark.parametrize("label", ["CANCELADO", "Standby", "9.Outro Estado"])
def test_unproven_special_states_are_explicit_unknown_status(label: str) -> None:
    parsed, equipment = _one(status=label)
    assert equipment.normalized["current_stage"] is None
    assert equipment.normalized["current_stage_unrecognized"] is True
    assert "operational_status" not in equipment.normalized
    assert "unknown_status_value" in _codes(parsed)


def test_profile_rejects_stage_9_and_unknown_operational_states() -> None:
    document = default_profile().model_dump(mode="json")
    document["status"]["values"]["9.Em Definição"] = 9
    with pytest.raises((ImportProfileError, ValueError), match="0..8"):
        ImportProfile.model_validate(document)
    document = default_profile().model_dump(mode="json")
    document["status"]["operational_values"]["Saneando"] = "IN_SANITATION"
    with pytest.raises(ValueError):
        ImportProfile.model_validate(document)


# 9. fases vazias ------------------------------------------------------------------------------


def test_occupied_phases_without_2_4_5_parse_cleanly() -> None:
    boards = multiphase_boards()
    assert sorted(boards) == [0, 1, 3, 6, 7, 8]
    for phase, content in boards.items():
        parsed = _parse(content)
        assert not [issue for issue in parsed.issues if issue.severity == "error"], phase
        assert {equipment.group_name for equipment in parsed.equipments} == {PHASE_GROUPS[phase]}
        assert not any("phase" in code.lower() for code in _codes(parsed))
        stages = {equipment.normalized["current_stage"] for equipment in parsed.equipments}
        assert stages <= {phase, None}


# espelho de datas de entrega e identidade de subitem sem ID ----------------------------------


def test_contract_delivery_mirror_list_is_normalized_not_an_error() -> None:
    parsed, equipment = _one({"E.Data de Entrega contrato": "2027-03-05, 2027-03-01, 2027-03-05"})
    assert equipment.normalized["contract_delivery_mirror"] == ["2027-03-01", "2027-03-05"]
    assert "invalid_date" not in _codes(parsed)


def test_subitems_without_element_id_get_parent_name_ordinal_identity() -> None:
    components = ("Componente Sintético 1", "Componente Sintético 1", "Componente Sintético 2")
    first = _parse(phase_board(1, [SynthEquipment(name="Equipamento Sintético A", components=components)]))
    # mesmo equipamento com outro acima dele (linhas deslocadas) e em outro arquivo de fase
    second = _parse(
        phase_board(
            6,
            [
                SynthEquipment(name="Equipamento Sintético Outro"),
                SynthEquipment(name="Equipamento Sintético A", components=components),
            ],
        )
    )
    keys_first = [c.source_key for c in first.equipments[0].components]
    keys_second = [c.source_key for c in second.equipments[1].components]
    assert keys_first == keys_second
    assert len(set(keys_first)) == 3  # irmãos homônimos distintos pelo ordinal
    assert all(key.startswith("parent-name-ordinal:") for key in keys_first)
    assert "fragile_component_identity" in _codes(first)
    assert "missing_component_external_id" not in _codes(first)


# 10. nenhum dado real -------------------------------------------------------------------------


def test_fixture_values_are_synthetic_only() -> None:
    fixture = Path(__file__).with_name("monday_multiphase_fixture.py").read_text(encoding="utf-8")
    assert not re.search(r"\b(RDN|LEM|NMT|RVD|C2|F2|F1)\b", fixture)
    assert not re.search(r"\d{9,}", fixture)  # nada com cara de chamado/contrato/OC real
    for phase, content in multiphase_boards().items():
        for equipment in _parse(content).equipments:
            assert "Sintético" in equipment.normalized["name"], phase
            assert all("Sintético" in c.normalized["name"] for c in equipment.components)
