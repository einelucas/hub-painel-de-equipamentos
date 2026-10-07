"""ImportProfile: contrato declarativo e parser dirigido por profile (só dados sintéticos)."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from app.modules.monday_import.dry_run import build_dry_run_report
from app.modules.monday_import.parser import parse_monday_xlsx
from app.modules.monday_import.profile import (
    ExpectedCounts,
    ImportProfile,
    ImportProfileError,
    default_profile,
    load_profile,
)
from tests.unit.monday_profile_fixture import (
    PROFILE_A_PATH,
    PROFILES_DIR,
    layout_a_xlsx,
    layout_b_xlsx,
    profile_a,
    profile_b,
)
from tests.unit.monday_xlsx_fixture import representative_xlsx


def _profile_dict() -> dict:
    return json.loads(PROFILE_A_PATH.read_text(encoding="utf-8"))


def _codes(parsed) -> list[str]:
    return [issue.code for issue in parsed.issues]


# 1. profile válido ---------------------------------------------------------------------------


def test_valid_profiles_load_and_have_stable_identity() -> None:
    a, b = profile_a(), profile_b()
    assert (a.profile_id, a.version) == ("synthetic-equipment-board-a", 1)
    assert a.sha256 == load_profile(PROFILE_A_PATH).sha256
    assert a.sha256 != b.sha256
    assert (default_profile().profile_id, default_profile().version) == (
        "monday-equipamentos-legacy",
        3,
    )


# 2. profile inválido -------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("mutate", "fragment"),
    [
        (lambda d: d["equipment"]["aliases"].update(nome_inventado=["X"]), "conceito canônico desconhecido"),
        (lambda d: d["equipment"]["aliases"]["area_name"].append("Equipment"), "aponta para"),
        (lambda d: d["equipment"]["required"].append("contract_number"), "required sem alias"),
        (lambda d: d["equipment"].update(ignored_headers=["Area"]), "ignorado e mapeado"),
        (lambda d: d["status"]["values"].update(Bad=9), "fora de 0..8"),
        (lambda d: d.update(script="import os"), "Extra inputs are not permitted"),
        (lambda d: d.update(profile_id="X Inválido"), "pattern"),
        (lambda d: d["component"].update(header_markers=[]), "header_markers"),
        (lambda d: d["equipment"].update(external_id_concept="contract_number"), "external_id_concept"),
    ],
)
def test_invalid_profiles_are_rejected(tmp_path, mutate, fragment) -> None:
    document = _profile_dict()
    mutate(document)
    path = tmp_path / "profile.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    with pytest.raises(ImportProfileError, match=re.escape(fragment)):
        load_profile(path)


def test_profile_is_data_only() -> None:
    assert ImportProfile.model_config.get("extra") == "forbid"
    assert ImportProfile.model_config.get("frozen") is True


# 3. alias diferente -> mesmo conceito canônico ----------------------------------------------


def test_different_aliases_produce_same_canonical_concepts() -> None:
    a = parse_monday_xlsx(layout_a_xlsx(), profile=profile_a())
    b = parse_monday_xlsx(layout_b_xlsx(), profile=profile_b())
    first_a, first_b = a.equipments[0].normalized, b.equipments[0].normalized
    for concept in (
        "name",
        "external_id",
        "current_stage",
        "area_name",
        "responsible_name",
        "discipline_name",
    ):
        assert first_a[concept] == first_b[concept], concept
    assert first_a["startup_at"] == first_b["startup_at"] == "2027-10-27"
    assert first_a["work_package_codes"] == first_b["work_package_codes"] == ["WP-S1", "WP-S2"]


# 4/5. obrigatório ausente x opcional ausente ------------------------------------------------


def test_missing_required_column_is_an_error() -> None:
    parsed = parse_monday_xlsx(layout_a_xlsx(drop_status_column=True), profile=profile_a())
    missing = [issue for issue in parsed.issues if issue.code == "missing_required_column"]
    # sem "Status" a linha deixa de casar com a assinatura do cabeçalho principal
    assert missing or "missing_main_header" in _codes(parsed)
    assert any(issue.severity == "error" for issue in parsed.issues)


def test_missing_required_column_reported_when_signature_still_matches(tmp_path) -> None:
    document = _profile_dict()
    document["equipment"]["required"] = ["name", "current_stage", "contract_number"]
    document["equipment"]["aliases"]["contract_number"] = ["Contract Number"]
    path = tmp_path / "p.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    parsed = parse_monday_xlsx(layout_a_xlsx(), profile=load_profile(path))
    issue = next(issue for issue in parsed.issues if issue.code == "missing_required_column")
    assert (issue.severity, issue.field) == ("error", "contract_number")


def test_missing_optional_column_is_silent() -> None:
    # "discipline_name" é opcional no profile B; o layout A não tem "Trade" etc.
    parsed = parse_monday_xlsx(layout_a_xlsx(), profile=profile_a())
    assert "missing_required_column" not in _codes(parsed)
    assert "contract_number" not in parsed.equipments[0].normalized


# 6/7. ignored x unknown ----------------------------------------------------------------------


def test_ignored_column_is_not_unknown_but_stays_in_raw() -> None:
    parsed = parse_monday_xlsx(layout_a_xlsx(), profile=profile_a())
    assert "Notes" not in parsed.unknown_equipment_fields
    assert "Attachments" not in parsed.unknown_component_fields
    assert parsed.equipments[0].raw["Notes"] == "nota livre"


def test_new_column_is_reported_as_unknown_and_preserved() -> None:
    parsed = parse_monday_xlsx(layout_a_xlsx(extra_header="Coluna Nova"), profile=profile_a())
    assert parsed.unknown_equipment_fields == {"Coluna Nova"}
    assert parsed.equipments[0].raw["Coluna Nova"] == "valor novo"
    report = build_dry_run_report([parsed])
    assert "equipment:Coluna Nova" in report.unknown_fields


# 8/9. identidade de Equipment ----------------------------------------------------------------


def test_equipment_with_stable_external_id() -> None:
    parsed = parse_monday_xlsx(layout_a_xlsx(), profile=profile_a())
    assert parsed.equipments[0].source_key == "monday-item-id:7001"


def test_equipment_without_id_uses_name_fallback_with_warning() -> None:
    parsed = parse_monday_xlsx(layout_a_xlsx(), profile=profile_a())
    second = parsed.equipments[1]
    assert second.source_key == "normalized-name:equipamento sintetico b"
    fragile = [issue for issue in parsed.issues if issue.code == "fragile_equipment_identity"]
    assert (
        len(fragile) == 1 and fragile[0].severity == "warning" and fragile[0].row_number == second.row_number
    )


def test_profile_without_equipment_id_always_falls_back_explicitly() -> None:
    parsed = parse_monday_xlsx(representative_xlsx())  # profile histórico: sem ID de equipamento
    assert parsed.equipments[0].source_key.startswith("normalized-name:")
    assert "fragile_equipment_identity" in _codes(parsed)


# 10/11. identidade de Component --------------------------------------------------------------


def test_component_with_and_without_external_id() -> None:
    parsed = parse_monday_xlsx(layout_a_xlsx(), profile=profile_a())
    with_id, without_id = parsed.equipments[0].components
    assert with_id.source_key == "monday-item-id:8001" and with_id.external_id == "8001"
    assert without_id.source_key.startswith("missing-external-id:")
    assert "missing_component_external_id" in _codes(parsed)
    again = parse_monday_xlsx(layout_a_xlsx(), profile=profile_a())
    assert again.equipments[0].components[1].source_key == without_id.source_key  # determinístico


# 12/13. status ------------------------------------------------------------------------------


def test_known_status_maps_to_stage_and_group_is_not_authority() -> None:
    # grupo "Stage 2", mas o status do segundo equipamento é "Contract" (5): status prevalece
    parsed = parse_monday_xlsx(layout_a_xlsx(), profile=profile_a())
    stages = [equipment.normalized["current_stage"] for equipment in parsed.equipments]
    assert stages == [2, 5]
    assert all(equipment.normalized["stage_from_group_allowed"] is False for equipment in parsed.equipments)


def test_unknown_status_is_not_stage_zero_and_is_reported() -> None:
    parsed = parse_monday_xlsx(layout_a_xlsx(status_override="Status Inventado"), profile=profile_a())
    equipment = parsed.equipments[0]
    assert equipment.normalized["current_stage"] is None
    assert equipment.normalized["current_stage_unrecognized"] is True
    assert equipment.raw["Status"] == "Status Inventado"
    assert "unknown_status_value" in _codes(parsed)


def test_not_applicable_status_is_not_stage_zero() -> None:
    parsed = parse_monday_xlsx(layout_a_xlsx(status_override="Not Applicable"), profile=profile_a())
    equipment = parsed.equipments[0]
    assert equipment.normalized["current_stage"] is None
    assert equipment.normalized["stage_not_applicable"] is True
    assert "unknown_status_value" not in _codes(parsed)


# 14/15. board compatível x incompatível ------------------------------------------------------


def test_compatible_board_is_recognized() -> None:
    parsed = parse_monday_xlsx(layout_b_xlsx(), profile=profile_b())
    assert parsed.board_title == "Quadro Sintético de Ativos - Projeto B"
    assert parsed.import_profile == profile_b().identity()
    assert not [issue for issue in parsed.issues if issue.severity == "error"]


def test_incompatible_board_is_an_error_not_a_silent_parse() -> None:
    parsed = parse_monday_xlsx(layout_b_xlsx(), profile=profile_a())
    codes = _codes(parsed)
    assert "board_not_recognized" in codes
    assert "missing_main_header" in codes
    assert parsed.equipments == []


# 16/17. dois profiles e contagens esperadas --------------------------------------------------


def test_two_profiles_process_two_formats_with_the_same_pipeline() -> None:
    """Prova do motor genérico: dois layouts, dois profiles, o mesmo parser, o mesmo resultado."""
    a = parse_monday_xlsx(layout_a_xlsx(), profile=profile_a())
    b = parse_monday_xlsx(layout_b_xlsx(), profile=profile_b())

    def canonical(parsed):
        return [
            (
                equipment.source_key,
                {k: v for k, v in equipment.normalized.items() if k != "group_name"},
                [(c.source_key, c.normalized) for c in equipment.components],
            )
            for equipment in parsed.equipments
        ]

    def without_markers(items):
        return [
            (
                key,
                normalized,
                [(ckey, {k: v for k, v in c.items() if k != "subitems_marker"}) for ckey, c in comps],
            )
            for key, normalized, comps in items
        ]

    assert without_markers(canonical(a)) == without_markers(canonical(b))
    assert len(a.equipments) == len(b.equipments) == 2
    assert sum(len(e.components) for e in a.equipments) == 3
    # cross-check: o layout B NÃO é entendido pelo profile A (nada específico de board no código)
    assert parse_monday_xlsx(layout_b_xlsx(), profile=profile_a()).equipments == []


def test_expected_counts_are_optional() -> None:
    parsed = parse_monday_xlsx(layout_a_xlsx(), profile=profile_a())
    assert build_dry_run_report([parsed]).expected_counts_check is None

    ok = build_dry_run_report([parsed], expected=ExpectedCounts(equipments=2, components=3))
    assert ok.expected_counts_check == {"matched": True, "mismatches": []}

    bad = build_dry_run_report([parsed], expected=ExpectedCounts(equipments=9, components=3))
    assert bad.expected_counts_check["matched"] is False
    assert bad.expected_counts_check["mismatches"][0]["metric"] == "equipments"


def test_dry_run_records_profile_identity() -> None:
    report = build_dry_run_report([parse_monday_xlsx(layout_b_xlsx(), profile=profile_b())])
    assert report.to_dict()["import_profiles"] == [profile_b().identity()]


# 18. nenhum dado corporativo nas fixtures ----------------------------------------------------


def test_fixtures_contain_no_corporate_data() -> None:
    texts = [path.read_text(encoding="utf-8") for path in PROFILES_DIR.glob("*.json")]
    texts.append(Path(__file__).with_name("monday_profile_fixture.py").read_text(encoding="utf-8"))
    joined = "\n".join(texts)
    assert texts and not list(PROFILES_DIR.glob("*.xlsx"))
    assert not re.search(r"@inpasa|inpasa\.com", joined, re.IGNORECASE)
    assert not re.search(r"\b(LEM|RDN|NMT)\b", joined)
    assert not re.search(
        r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", joined, re.IGNORECASE
    )
    assert not re.search(r"postgres(ql)?://", joined)
    for path in PROFILES_DIR.glob("*.json"):
        assert json.loads(path.read_text(encoding="utf-8"))["profile_id"].startswith("synthetic-")
