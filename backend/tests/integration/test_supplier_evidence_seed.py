"""Seed da planilha corporativa: evidência idempotente, nunca vínculo."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import func, select

from app.core.auth import CurrentUser
from app.core.permissions import Role as PermissionRole
from app.models.supplier import EquipmentSupplier, Supplier, SupplierRecommendationEvidence
from app.models.user import Role as UserRole
from app.models.user import User
from app.modules.supplier_import.evidence_seed import (
    apply_evidence_seed,
    load_evidence_seed,
    load_evidence_seed_json,
)
from tests.unit.monday_xlsx_fixture import build_workbook


def _workbook() -> bytes:
    return build_workbook(
        {
            "Mapa_Tipos_Equipamento": [
                [
                    "EQUIPAMENTO PADRONIZADO",
                    "CANDIDATO DE FORNECEDOR",
                    "RECOMENDAÇÃO OCs REAIS",
                    "Nº OCs",
                    "PARTICIPAÇÃO",
                    "REFERENCIAIS LGE",
                    "QTD REFERENCIAIS",
                    "CLASSIFICAÇÃO",
                    "AÇÃO NO HUB",
                ],
                ["Bomba", "Fornecedor A", "Fornecedor A", 3, 0.8, None, 0, "CANDIDATO_OC", "Sugerir"],
            ],
            "Recomendacoes_OC": [
                [
                    "TIPO PADRONIZADO",
                    "FORNECEDOR RECOMENDADO",
                    "Nº DE OCs",
                    "PARTICIPAÇÃO NO TIPO (%)",
                    "FORNECEDORES CONCORRENTES",
                    "ALTERNATIVAS (TOP 3)",
                ],
                ["Bomba", "Fornecedor A", 3, 0.8, 1, "Fornecedor B"],
            ],
            "Fornecedores_LGE": [
                [
                    "FORNECEDOR REFERENCIAL",
                    "GRUPO / EMPRESA CONSOLIDADA",
                    "CONFIABILIDADE",
                    "STATUS DA CONSOLIDAÇÃO",
                    "Nº DE OCs (ERP LEM F1)",
                    "TIPOS FORNECIDOS (ERP)",
                ],
                ["Fornecedor A", "Fornecedor A", "Alta", "Consolidado", 3, "Bomba; Motor"],
            ],
            "Codigos_Monday_RDN_RVD": [
                [
                    "EQUIPAMENTO (NOME EXATO NO MONDAY)",
                    "CÓD. FORN. CS — RDN F1",
                    "CÓD. FORN. CS — RVD F1",
                    "CÓDIGO CONSOLIDADO (SÓ QUANDO SEGURO)",
                    "STATUS DA COMPARAÇÃO",
                ],
                ["Bomba", 9001, 9001, 9001, "Consistente"],
                ["Motor", 9001, 9002, None, "DIVERGENTE — REVISAR"],
            ],
            "Pendencias_Validacao": [
                ["TIPO", "ITEM", "EVIDÊNCIA", "MOTIVO", "TRATAMENTO"],
                ["Fornecedor", "Compressor", "Dados divergentes", "Sem código seguro", "Revisar"],
            ],
        }
    )


def test_committed_seed_was_generated_from_the_supplied_workbook() -> None:
    seed_path = Path(__file__).resolve().parents[2] / "app" / "data" / "supplier_evidence_seed.json"
    rows = load_evidence_seed_json(seed_path)
    assert len(rows) == 548
    assert {row.source for row in rows} == {
        "MAPA_TIPOS",
        "RECOMENDACOES_OC",
        "LGE",
        "MONDAY_CODES",
        "PENDENCIAS",
    }
    assert any(row.review_required for row in rows)


async def test_seed_is_idempotent_and_never_creates_supplier_or_link(db_session) -> None:
    actor = User(name="Admin seed", email="seed@example.com", role=UserRole.ADMIN)
    db_session.add(actor)
    await db_session.flush()
    current_user = CurrentUser(
        id=actor.id,
        email=actor.email,
        name=actor.name,
        role=PermissionRole.ADMIN,
        active=True,
    )
    rows = load_evidence_seed(_workbook())
    assert len(rows) == 7
    divergent = next(row for row in rows if row.source == "MONDAY_CODES" and row.equipment_label == "Motor")
    assert divergent.corporate_code is None
    assert divergent.review_required is True

    first = await apply_evidence_seed(db_session, rows, actor=current_user)
    assert sum(action.action == "CREATE" for action in first) == 7
    second = await apply_evidence_seed(db_session, rows, actor=current_user)
    assert sum(action.action == "NOOP" for action in second) == 7

    evidence_count = await db_session.scalar(
        select(func.count()).select_from(SupplierRecommendationEvidence)
    )
    assert evidence_count == 7
    assert await db_session.scalar(select(func.count()).select_from(Supplier)) == 0
    assert await db_session.scalar(select(func.count()).select_from(EquipmentSupplier)) == 0
