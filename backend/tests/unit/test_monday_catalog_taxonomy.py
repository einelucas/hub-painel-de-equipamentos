"""Taxonomia EXISTING/CREATE/CONFLICT/UNRESOLVED de catálogos da migração.

Dados totalmente sintéticos. Testes puros: não tocam no banco.
"""

from __future__ import annotations

from app.domain.eap import EapLevel
from app.modules.monday_import.catalog_evidence import (
    CatalogEvidence,
    EvidenceLookup,
    EvidenceSource,
    SupplierEvidence,
)
from app.modules.monday_import.catalog_taxonomy import (
    BLOCKING_ISSUE_CODES,
    NON_BLOCKING_ISSUE_CODES,
    CatalogAction,
    DisciplineEntry,
    EapCatalogEntry,
    SupplierEntry,
    SupplierIndex,
    WorkPackageEntry,
    decide_discipline,
    decide_eap,
    decide_project_eap,
    decide_supplier,
    decide_work_package,
    is_blocking_issue,
    split_supplier_codes,
)
from app.modules.monday_import.eap_resolution import EapResolver
from app.modules.monday_import.normalization import canonical_text

NONE = EvidenceLookup()


def _found(value: str, source: EvidenceSource = EvidenceSource.LGE) -> EvidenceLookup:
    return EvidenceLookup(value=value, source=source)


def _node(node_id: str, code: str, name: str, *, level: str = "AREA", active: bool = True) -> EapCatalogEntry:
    return EapCatalogEntry(id=node_id, code=code, name=name, level=level, active=active)


def _catalog(*nodes: EapCatalogEntry) -> dict[str, EapCatalogEntry]:
    return {node.code: node for node in nodes}


def _names(mapping: dict[str, str], source: EvidenceSource = EvidenceSource.OFFICIAL_CATALOG):
    def lookup(code: str) -> EvidenceLookup:
        return _found(mapping[code], source) if code in mapping else NONE

    return lookup


# --- EAP ---------------------------------------------------------------------


def test_eap_existing_with_compatible_name_is_existing() -> None:
    catalog = _catalog(_node("n1", "04.A", "Nome Sintético A"))
    decision = decide_eap(("04.A",), "nome sintetico a", catalog)
    assert decision.action is CatalogAction.EXISTING
    assert decision.node_id == "n1"
    assert decision.creates == ()


def test_eap_existing_without_source_name_is_existing() -> None:
    catalog = _catalog(_node("n1", "04.A", "Nome Sintético A"))
    assert decide_eap(("04.A",), None, catalog).action is CatalogAction.EXISTING


def test_eap_truncated_source_label_is_not_compared() -> None:
    catalog = _catalog(_node("n1", "04.A", "Nome Sintético Completo"))
    assert decide_eap(("04.A",), "Nome Sintético ...", catalog).action is CatalogAction.EXISTING


def test_eap_create_area_when_process_parent_exists() -> None:
    catalog = _catalog(_node("p1", "23", "Processo Sintético", level="PROCESS"))
    decision = decide_eap(("23.C",), None, catalog, _names({"23.C": "Área Sintética C"}))
    assert decision.action is CatalogAction.CREATE
    assert [(spec.code, spec.level, spec.parent_code) for spec in decision.creates] == [
        ("23.C", EapLevel.AREA, "23")
    ]
    assert decision.creates[0].evidence_source == "OFFICIAL_CATALOG"


def test_eap_create_process_alone_when_code_is_two_digits() -> None:
    decision = decide_eap(("23",), None, {}, _names({"23": "Processo Sintético"}))
    assert decision.action is CatalogAction.CREATE
    assert [(spec.code, spec.level, spec.parent_code) for spec in decision.creates] == [
        ("23", EapLevel.PROCESS, None)
    ]


def test_eap_create_parent_and_area_when_parent_name_is_evidenced() -> None:
    names = _names({"23": "Processo Sintético", "23.C": "Área Sintética C"}, EvidenceSource.LGE)
    decision = decide_eap(("23.C",), None, {}, names)
    assert decision.action is CatalogAction.CREATE
    assert [(spec.code, spec.level) for spec in decision.creates] == [
        ("23", EapLevel.PROCESS),
        ("23.C", EapLevel.AREA),
    ]
    assert decision.creates[0].name == "Processo Sintético"
    assert decision.creates[0].evidence_source == "LGE"


def test_eap_parent_required_when_parent_missing_without_evidence() -> None:
    decision = decide_eap(("23.C",), None, {}, _names({"23.C": "Área Sintética C"}))
    assert decision.action is CatalogAction.UNRESOLVED
    assert decision.issue_code == "EAP_PARENT_REQUIRED"
    assert decision.creates == ()  # nunca inventa o pai


def test_eap_parent_required_when_parent_inactive() -> None:
    catalog = _catalog(_node("p1", "23", "Processo Sintético", level="PROCESS", active=False))
    decision = decide_eap(("23.C",), None, catalog, _names({"23.C": "Área Sintética C"}))
    assert decision.action is CatalogAction.UNRESOLVED
    assert decision.issue_code == "EAP_PARENT_REQUIRED"


def test_eap_name_required_when_new_code_has_no_name() -> None:
    decision = decide_eap(("23",), None, {})
    assert decision.action is CatalogAction.UNRESOLVED
    assert decision.issue_code == "EAP_NAME_REQUIRED"


def _oil_catalog() -> dict[str, EapCatalogEntry]:
    return _catalog(
        _node("p77", "77", "Processo Sintético", level="PROCESS"),
        _node("a77c", "77.C", "Armazenamento Sintético"),
        _node("a77e", "77.E", "Expedição Sintética"),
        _node("a77s", "77.S", "Estação de Tratamento Sintética (ETS)"),
    )


def test_eap_same_code_same_official_name_is_existing_without_warning() -> None:
    decision = decide_eap(("77.C",), "Armazenamento Sintético", _oil_catalog())
    assert (decision.action, decision.issue_code) == (CatalogAction.EXISTING, None)


def test_eap_accent_case_punctuation_differences_are_the_same_name() -> None:
    for label in ("ARMAZENAMENTO SINTETICO", "armazenamento   sintético.", "Armazenamento, Sintético"):
        decision = decide_eap(("77.C",), label, _oil_catalog())
        assert (decision.action, decision.issue_code) == (CatalogAction.EXISTING, None), label


def test_eap_abbreviation_is_existing_with_label_variant_warning() -> None:
    decision = decide_eap(("77.S",), "ETS", _oil_catalog())
    assert decision.action is CatalogAction.EXISTING
    assert decision.node_id == "a77s"  # código + nome oficiais
    assert decision.issue_code == "EAP_LABEL_VARIANT"
    assert not is_blocking_issue("EAP_LABEL_VARIANT")


def test_eap_free_variant_label_is_existing_with_warning() -> None:
    decision = decide_eap(("77.C",), "Armazém de Coisas Sintéticas", _oil_catalog())
    assert (decision.action, decision.issue_code) == (CatalogAction.EXISTING, "EAP_LABEL_VARIANT")
    assert decision.detail == {
        "hubName": "Armazenamento Sintético",
        "sourceName": "Armazém de Coisas Sintéticas",
    }


def test_eap_label_equal_to_other_code_official_name_is_conflict() -> None:
    # Caso 20.C/20.E: rótulo é exatamente o nome oficial de OUTRO código.
    decision = decide_eap(("77.C",), "Expedição Sintética", _oil_catalog())
    assert decision.action is CatalogAction.CONFLICT
    assert decision.issue_code == "EAP_CODE_LABEL_CONFLICT"
    assert decision.detail["labelMatchesCodes"] == "77.E"
    assert is_blocking_issue("EAP_CODE_LABEL_CONFLICT")


def test_eap_label_close_to_other_code_name_is_never_fuzzy_matched() -> None:
    # Parecido com 77.E, mas não igual na forma comparável: só variante, sem conflito.
    decision = decide_eap(("77.C",), "Expedição Sintéticas", _oil_catalog())
    assert (decision.action, decision.issue_code) == (CatalogAction.EXISTING, "EAP_LABEL_VARIANT")


def test_eap_multiple_candidates_never_chooses() -> None:
    catalog = _catalog(_node("n1", "04.A", "Nome A"), _node("n2", "05.A", "Nome B"))
    decision = decide_eap(("04.A", "05.A"), None, catalog)
    assert decision.action is CatalogAction.UNRESOLVED
    assert decision.issue_code == "MULTIPLE_EAP_CANDIDATES"
    assert decision.node_id is None


def test_eap_no_code_is_no_eap_unresolved() -> None:
    decision = decide_eap((), "Diversos", {})
    assert decision.action is CatalogAction.UNRESOLVED
    assert decision.issue_code == "NO_EAP"


def test_eap_inactive_existing_code_is_not_recreated() -> None:
    catalog = _catalog(_node("n1", "04.A", "Nome A", active=False))
    decision = decide_eap(("04.A",), "Nome A", catalog, _names({"04.A": "Nome A"}))
    assert decision.action is CatalogAction.UNRESOLVED
    assert decision.creates == ()


def test_eap_evidence_conflict_creates_nothing() -> None:
    evidence = CatalogEvidence()
    evidence.add_eap_name("23", "Nome Um", EvidenceSource.MONDAY)
    evidence.add_eap_name("23", "Nome Dois", EvidenceSource.LGE)
    decision = decide_eap(("23",), None, {}, evidence.eap_name)
    assert decision.action is CatalogAction.UNRESOLVED
    assert decision.issue_code == "CATALOG_EVIDENCE_CONFLICT"
    assert not is_blocking_issue("CATALOG_EVIDENCE_CONFLICT")


def test_eap_reimport_after_create_is_existing() -> None:
    names = _names({"23": "Processo Sintético", "23.C": "Área Sintética C"})
    assert decide_eap(("23.C",), None, {}, names).action is CatalogAction.CREATE
    catalog = _catalog(
        _node("p1", "23", "Processo Sintético", level="PROCESS"),
        _node("a1", "23.C", "Área Sintética C"),
    )
    second = decide_eap(("23.C",), "Área Sintética C", catalog, names)
    assert second.action is CatalogAction.EXISTING
    assert second.creates == ()


def test_resolver_without_evidence_uses_own_label_as_monday_evidence() -> None:
    resolver = EapResolver(catalog=[_node("p1", "23", "Processo Sintético", level="PROCESS")])
    resolution = resolver.resolve("23.C - Área Sintética C")
    assert resolution.status == "CREATE"
    assert resolution.eap_node_id is None  # ID só existe após o apply
    assert [(spec.code, spec.evidence_source) for spec in resolution.creates] == [("23.C", "MONDAY")]


def test_resolver_with_official_evidence_prefers_official_name() -> None:
    evidence = CatalogEvidence()
    evidence.add_eap_name("23.C", "Nome Oficial", EvidenceSource.OFFICIAL_CATALOG)
    evidence.add_eap_name("23.C", "Nome do Monday", EvidenceSource.MONDAY)
    resolver = EapResolver(
        catalog=[_node("p1", "23", "Processo Sintético", level="PROCESS")], evidence=evidence
    )
    resolution = resolver.resolve("23.C - Nome do Monday")
    assert resolution.status == "CREATE"
    assert resolution.creates[0].name == "Nome Oficial"


def test_resolver_override_prevails_and_is_existing() -> None:
    resolver = EapResolver(catalog=[_node("n1", "04.A", "Nome A")], overrides={"valor sintetico": "n1"})
    resolution = resolver.resolve("Valor Sintético")
    assert resolution.status == "RESOLVED"
    assert resolution.from_mapping is True
    assert resolution.eap_node_id == "n1"


def test_resolver_keeps_legacy_status_names() -> None:
    resolver = EapResolver(catalog=[])
    assert resolver.resolve("Diversos").status == "NONE"
    area_without_parent = resolver.resolve("04.A - Nome Sintético")
    assert area_without_parent.status == "UNRESOLVED"
    assert area_without_parent.issue_code == "EAP_PARENT_REQUIRED"


# --- ProjectEap --------------------------------------------------------------


def test_project_eap_create_when_not_linked() -> None:
    assert decide_project_eap("n1", set()) is CatalogAction.CREATE


def test_project_eap_existing_when_linked() -> None:
    assert decide_project_eap("n1", {"n1"}) is CatalogAction.EXISTING


def test_project_eap_no_duplicate_on_repeated_planning() -> None:
    assert [decide_project_eap("n1", {"n1"}) for _ in range(3)] == [CatalogAction.EXISTING] * 3


# --- Discipline --------------------------------------------------------------


def _disc_indexes(*entries: DisciplineEntry) -> tuple[dict[str, DisciplineEntry], dict[str, DisciplineEntry]]:
    return (
        {canonical_text(e.name): e for e in entries},
        {canonical_text(e.code): e for e in entries},
    )


def test_discipline_existing_by_name() -> None:
    by_name, by_code = _disc_indexes(DisciplineEntry("d1", "SNA", "Disciplina Sintética", True))
    decision = decide_discipline("Disciplina Sintética", NONE, by_name, by_code)
    assert decision is not None and decision.action is CatalogAction.EXISTING
    assert decision.discipline_id == "d1"


def test_discipline_create_with_proven_code_records_source() -> None:
    by_name, by_code = _disc_indexes()
    decision = decide_discipline("Nova Sintética", _found("NSA"), by_name, by_code)
    assert decision is not None and decision.action is CatalogAction.CREATE
    assert (decision.code, decision.evidence_source) == ("NSA", "LGE")


def test_discipline_missing_code_is_unresolved_not_invented() -> None:
    by_name, by_code = _disc_indexes()
    decision = decide_discipline("Nova Sintética", NONE, by_name, by_code)
    assert decision is not None and decision.action is CatalogAction.UNRESOLVED
    assert decision.issue_code == "DISCIPLINE_CODE_REQUIRED"
    assert decision.code is None
    assert not is_blocking_issue("DISCIPLINE_CODE_REQUIRED")


def test_discipline_conflict_when_code_used_by_other_name() -> None:
    by_name, by_code = _disc_indexes(DisciplineEntry("d1", "NSA", "Outra Sintética", True))
    decision = decide_discipline("Nova Sintética", _found("NSA"), by_name, by_code)
    assert decision is not None and decision.action is CatalogAction.CONFLICT
    assert decision.issue_code == "DISCIPLINE_CONFLICT"


def test_discipline_conflict_when_same_name_has_other_code() -> None:
    by_name, by_code = _disc_indexes(DisciplineEntry("d1", "SNA", "Disciplina Sintética", True))
    decision = decide_discipline("Disciplina Sintética", _found("XYZ"), by_name, by_code)
    assert decision is not None and decision.action is CatalogAction.CONFLICT


def test_discipline_without_name_has_no_decision() -> None:
    by_name, by_code = _disc_indexes()
    assert decide_discipline(None, _found("NSA"), by_name, by_code) is None


# --- WorkPackage -------------------------------------------------------------


def _wp_index(*entries: WorkPackageEntry) -> dict[str, WorkPackageEntry]:
    return {canonical_text(e.code): e for e in entries}


def test_work_package_existing_in_context() -> None:
    decision = decide_work_package(
        "WP-S1", NONE, _wp_index(WorkPackageEntry("w1", "WP-S1", "Pacote S", True))
    )
    assert decision.action is CatalogAction.EXISTING
    assert decision.work_package_id == "w1"


def test_work_package_create_with_evidenced_name() -> None:
    decision = decide_work_package("WP-S2", _found("Pacote Novo", EvidenceSource.MANUAL_MAPPING), _wp_index())
    assert decision.action is CatalogAction.CREATE
    assert (decision.name, decision.evidence_source) == ("Pacote Novo", "MANUAL_MAPPING")


def test_work_package_code_only_creates_controlled_catalog_entry() -> None:
    decision = decide_work_package("WP-S2", NONE, _wp_index())
    assert decision.action is CatalogAction.CREATE
    assert decision.name == "WP-S2"


def test_work_package_conflict_same_code_other_name() -> None:
    index = _wp_index(WorkPackageEntry("w1", "WP-S1", "Pacote S", True))
    decision = decide_work_package("WP-S1", _found("Nome Diferente"), index)
    assert decision.action is CatalogAction.CONFLICT
    assert is_blocking_issue(decision.issue_code or "")


def test_work_package_wrong_context_is_not_reused() -> None:
    # O índice é escopado ao contexto atual: WP de outro contexto não está nele.
    decision = decide_work_package("WP-S1", NONE, {})
    assert decision.action is CatalogAction.CREATE
    assert decision.work_package_id is None


def test_work_package_reimport_after_create_is_existing() -> None:
    name = _found("Pacote Novo", EvidenceSource.MANUAL_MAPPING)
    assert decide_work_package("WP-S2", name, _wp_index()).action is CatalogAction.CREATE
    index = _wp_index(WorkPackageEntry("w2", "WP-S2", "Pacote Novo", True))
    assert decide_work_package("WP-S2", name, index).action is CatalogAction.EXISTING


# --- Supplier ----------------------------------------------------------------


def _supplier_index(
    *entries: SupplierEntry, aliases: dict[str, SupplierEntry] | None = None
) -> SupplierIndex:
    return SupplierIndex(
        by_code={e.corporate_code: e for e in entries if e.corporate_code},
        by_alias={canonical_text(k): v for k, v in (aliases or {}).items()},
        by_name={canonical_text(e.legal_name): e for e in entries},
    )


SUP_A = SupplierEntry("s1", "1001", "Fornecedor Sintético A Ltda", None, True)


def _no_manual(_: str) -> SupplierEvidence | None:
    return None


def test_supplier_by_corporate_code() -> None:
    decision = decide_supplier("1001", [], _supplier_index(SUP_A), _no_manual)
    assert decision is not None and decision.action is CatalogAction.EXISTING
    assert decision.supplier_id == "s1"


def test_supplier_by_alias() -> None:
    index = _supplier_index(SUP_A, aliases={"Apelido Sintético": SUP_A})
    decision = decide_supplier(None, ["apelido sintetico"], index, _no_manual)
    assert decision is not None and decision.action is CatalogAction.EXISTING


def test_supplier_by_exact_normalized_name() -> None:
    decision = decide_supplier(None, ["FORNECEDOR SINTÉTICO A LTDA"], _supplier_index(SUP_A), _no_manual)
    assert decision is not None and decision.action is CatalogAction.EXISTING


def test_supplier_similar_name_is_not_fuzzy_matched() -> None:
    decision = decide_supplier(None, ["Fornecedor Sintetico A"], _supplier_index(SUP_A), _no_manual)
    assert decision is not None and decision.action is CatalogAction.UNRESOLVED


def test_supplier_create_only_with_manual_legal_name() -> None:
    def manual(code: str) -> SupplierEvidence | None:
        return SupplierEvidence(legal_name="Novo Sintético SA") if code == "2002" else None

    decision = decide_supplier("2002", [], _supplier_index(SUP_A), manual)
    assert decision is not None and decision.action is CatalogAction.CREATE
    assert decision.payload == {"corporate_code": "2002", "legal_name": "Novo Sintético SA"}


def test_supplier_code_without_data_is_unresolved_not_blocking() -> None:
    decision = decide_supplier("2002", [], _supplier_index(SUP_A), _no_manual)
    assert decision is not None and decision.action is CatalogAction.UNRESOLVED
    assert decision.issue_code == "SUPPLIER_UNRESOLVED"
    assert not is_blocking_issue("SUPPLIER_UNRESOLVED")


def test_supplier_placeholder_is_unresolved() -> None:
    decision = decide_supplier("???", [], _supplier_index(SUP_A), _no_manual)
    assert decision is not None and decision.issue_code == "SUPPLIER_UNRESOLVED"


def test_supplier_multiple_codes_never_chooses() -> None:
    assert split_supplier_codes("1001/2002") == ["1001", "2002"]
    decision = decide_supplier("1001/2002", [], _supplier_index(SUP_A), _no_manual)
    assert decision is not None and decision.action is CatalogAction.UNRESOLVED
    assert decision.issue_code == "SUPPLIER_MULTIPLE_CANDIDATES"
    assert decision.supplier_id is None


def test_supplier_code_and_name_pointing_to_different_suppliers_is_conflict() -> None:
    other = SupplierEntry("s2", "3003", "Outro Sintético", None, True)
    decision = decide_supplier("1001", ["Outro Sintético"], _supplier_index(SUP_A, other), _no_manual)
    assert decision is not None and decision.action is CatalogAction.CONFLICT
    assert is_blocking_issue("SUPPLIER_CONFLICT")


def test_supplier_absent_has_no_decision() -> None:
    assert decide_supplier(None, [], _supplier_index(SUP_A), _no_manual) is None


# --- Blocking classification -------------------------------------------------


def test_blocking_and_non_blocking_sets_do_not_overlap() -> None:
    assert BLOCKING_ISSUE_CODES.isdisjoint(NON_BLOCKING_ISSUE_CODES)


def test_catalog_unresolved_codes_do_not_block_equipment() -> None:
    for code in (
        "RESPONSIBLE_UNRESOLVED",
        "DISCIPLINE_CODE_REQUIRED",
        "WORK_PACKAGE_UNRESOLVED",
        "MULTIPLE_EAP_CANDIDATES",
        "NO_EAP",
        "EAP_NAME_REQUIRED",
        "EAP_PARENT_REQUIRED",
        "SUPPLIER_UNRESOLVED",
        "SUPPLIER_MULTIPLE_CANDIDATES",
        "CATALOG_EVIDENCE_CONFLICT",
    ):
        assert not is_blocking_issue(code), code


def test_real_conflicts_block_equipment() -> None:
    for code in (
        "EAP_CODE_LABEL_CONFLICT",
        "MONDAY_ITEM_ID_CONFLICT",
        "DISCIPLINE_CONFLICT",
        "WORK_PACKAGE_CONFLICT",
        "SUPPLIER_CONFLICT",
        "STAGE_CONFLICT",
    ):
        assert is_blocking_issue(code), code


# --- Discipline: alias explícito e valores compostos ---------------------------


def test_discipline_explicit_alias_metal_mec_resolves_to_official_mec() -> None:
    from app.modules.monday_import.catalog_taxonomy import discipline_target_name

    evidence = CatalogEvidence()
    evidence.add_discipline("Metal Mecânica.", "MEC", EvidenceSource.OFFICIAL_CATALOG)
    target = discipline_target_name("Metal Mec.")
    assert target == "Metal Mecânica."
    decision = decide_discipline(target, evidence.discipline_code(target), {}, {})
    assert decision is not None and decision.action is CatalogAction.CREATE
    assert (decision.code, decision.evidence_source) == ("MEC", "OFFICIAL_CATALOG")


def test_discipline_alias_is_exact_not_fuzzy() -> None:
    from app.modules.monday_import.catalog_taxonomy import discipline_target_name

    assert discipline_target_name("metal mec") == "Metal Mecânica."  # mesma forma comparável
    assert discipline_target_name("Metal Mecan.") == "Metal Mecan."  # outra forma: sem alias


def test_discipline_composite_values_are_unresolved_not_blocking() -> None:
    evidence = CatalogEvidence()
    for name, code in (("Elétrica", "ELE"), ("Instrumentação", "EIA"), ("Civil", "CIV")):
        evidence.add_discipline(name, code, EvidenceSource.OFFICIAL_CATALOG)
    for raw in ("E&I", "Civil/Grãos"):
        decision = decide_discipline(raw, evidence.discipline_code(raw), {}, {})
        assert decision is not None and decision.action is CatalogAction.UNRESOLVED, raw
        assert decision.issue_code == "DISCIPLINE_COMPOSITE_UNRESOLVED"
        assert decision.code is None
    assert not is_blocking_issue("DISCIPLINE_COMPOSITE_UNRESOLVED")


def test_composite_value_is_not_resolved_by_legacy_record_with_same_name() -> None:
    # Registro legado "E&I" (código sintético LEG) existe no Hub: não é resolução automática.
    by_name, by_code = _disc_indexes(DisciplineEntry("d-leg", "LEG", "E&I", True))
    decision = decide_discipline("E&I", NONE, by_name, by_code)
    assert decision is not None and decision.action is CatalogAction.UNRESOLVED
    assert decision.issue_code == "DISCIPLINE_COMPOSITE_UNRESOLVED"
    assert decision.discipline_id is None


def test_text_longer_than_column_is_not_written_and_is_reported() -> None:
    from app.models.process import PurchaseRequest
    from app.modules.monday_import.plan import _fit_text_columns

    long_number = "/".join(f"SC{n:05d}" for n in range(30))  # sintético, > 80 caracteres
    payload = {"request_number": long_number, "requested_at": "2025-01-01"}
    fitted, issues, blocking = _fit_text_columns(PurchaseRequest, payload, source_key="k")
    assert "request_number" not in fitted and fitted["requested_at"] == "2025-01-01"
    assert [issue.code for issue in issues] == ["FIELD_TOO_LONG"] and blocking is False
    assert not is_blocking_issue("FIELD_TOO_LONG")


def test_required_text_longer_than_column_blocks() -> None:
    from app.models.equipment import Equipment
    from app.modules.monday_import.plan import _fit_text_columns

    _, issues, blocking = _fit_text_columns(Equipment, {"name": "X" * 500}, source_key="k")
    assert blocking is True and [issue.code for issue in issues] == ["FIELD_TOO_LONG_REQUIRED"]
    assert is_blocking_issue("FIELD_TOO_LONG_REQUIRED")
