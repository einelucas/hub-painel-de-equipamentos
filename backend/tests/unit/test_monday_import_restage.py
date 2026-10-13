"""Mesmo arquivo reenviado: reutilizar, reanalisar ou recusar (sem banco)."""

from __future__ import annotations

from app.modules.monday_import.parser import PARSER_VERSION
from app.modules.monday_import.service import restage_decision
from tests.unit.monday_profile_fixture import profile_a, profile_b


def _summary(profile) -> dict:
    return {"import_profiles": [profile.identity()]}


def _decide(status: str, staged_with, profile, parser_version: str = PARSER_VERSION) -> str:
    return restage_decision(
        existing_status=status,
        existing_parser_version=parser_version,
        existing_summary=_summary(staged_with),
        profile=profile,
    )


def test_same_profile_and_parser_reuses_the_batch() -> None:
    assert _decide("STAGED", profile_b(), profile_b()) == "reuse"
    assert _decide("APPLIED", profile_b(), profile_b()) == "reuse"


def test_unapplied_batch_is_restaged_with_a_newer_profile_version() -> None:
    # inclui análises que falharam (ex.: cabeçalho não identificado) na versão anterior
    newer = profile_b().model_copy(update={"version": 99})
    assert _decide("STAGED", profile_b(), newer) == "restage"
    assert _decide("STAGED", profile_b(), profile_b(), parser_version="monday-xlsx-old") == "restage"


def test_applied_batch_keeps_its_evidence_with_a_newer_profile_version() -> None:
    newer = profile_b().model_copy(update={"version": 99})
    assert _decide("APPLIED", profile_b(), newer) == "reuse"
    assert _decide("APPLIED", profile_b(), profile_b(), parser_version="monday-xlsx-old") == "reuse"


def test_another_profile_is_always_a_conflict() -> None:
    assert _decide("STAGED", profile_a(), profile_b()) == "conflict"
    assert _decide("APPLIED", profile_a(), profile_b()) == "conflict"
