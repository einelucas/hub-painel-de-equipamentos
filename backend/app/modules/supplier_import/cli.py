"""CLI da carga de fornecedores oficiais do LEM F2.

# validação só da planilha, sem abrir conexão com banco
python -m app.modules.supplier_import <planilha.xlsx> --dry-run --offline

# compara com o banco configurado em .env, sem gravar nada
python -m app.modules.supplier_import <planilha.xlsx> --dry-run

# carga real (DEV/TESTE apenas, mesma salvaguarda do importador Monday)
python -m app.modules.supplier_import <planilha.xlsx> --apply --confirm --actor-id <uuid>
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.modules.monday_import.cli import _load_actor
from app.modules.monday_import.safety import (
    UnsafeMigrationTargetError,
    describe_url_without_secret,
    guard_write_target,
)
from app.modules.supplier_import.database import (
    DatabaseReconciliation,
    SupplierImportBlockedError,
    apply_supplier_import,
    reconcile_with_database,
    resolve_project_context,
)
from app.modules.supplier_import.plan import (
    AMBIGUOUS,
    NOT_FOUND,
    PROBABLE,
    SupplierImportPlan,
    SupplierReconciliationError,
    build_supplier_import_plan,
)
from app.modules.supplier_import.workbook import SupplierWorkbookError, load_supplier_workbook


def _blocked_summary(plan: SupplierImportPlan) -> dict[str, Any]:
    def names(classification: str, level: str) -> list[str]:
        return [
            f"{item.name or '(vazio)'}" + (f" → {item.equipment_name}" if item.equipment_name else "")
            for item in plan.blocked
            if item.classification == classification and item.level == level
        ]

    other = [
        f"{item.equipment_name}: {item.reason}"
        for item in plan.blocked
        if item.level == "equipment" and item.classification not in {PROBABLE, AMBIGUOUS, NOT_FOUND}
    ]
    return {
        "aliasesProvaveis": names(PROBABLE, "alias"),
        "aliasesAmbiguos": names(AMBIGUOUS, "alias"),
        "aliasesNaoEncontrados": names(NOT_FOUND, "alias"),
        "equipamentosProvaveis": names(PROBABLE, "equipment"),
        "equipamentosAmbiguos": names(AMBIGUOUS, "equipment"),
        "equipamentosNaoEncontrados": names(NOT_FOUND, "equipment"),
        "equipamentosOutrosMotivos": other,
    }


def build_report(plan: SupplierImportPlan, db: DatabaseReconciliation | None) -> dict[str, Any]:
    report: dict[str, Any] = {
        "planilha": plan.source_file,
        "sha256": plan.file_sha256,
        "contextoAlias": plan.alias_context,
        "reconciliacao": [
            {"check": c.name, "esperado": c.expected, "planilha": c.actual, "ok": c.ok} for c in plan.checks
        ],
        "suppliersCandidatos": len(plan.suppliers),
        "aliasesCandidatos": len(plan.aliases),
        "vinculosCandidatos": len(plan.links),
        "ignorados": _blocked_summary(plan),
        "codigosInvalidos": plan.invalid_codes,
        "erros": plan.errors,
    }
    if db is None:
        report["banco"] = "não consultado (--offline): novos/existentes/atualizações não calculados"
    else:
        report["banco"] = {
            "projectContextId": db.project_context_id,
            "suppliersNovos": db.count("suppliers", "CREATE"),
            "suppliersExistentes": db.count("suppliers", "NOOP") + db.count("suppliers", "UPDATE"),
            "suppliersAtualizados": [
                {"codigo": a.corporate_code, "mudancas": a.changes}
                for a in db.suppliers
                if a.action == "UPDATE"
            ],
            "aliasesNovos": db.count("aliases", "CREATE"),
            "aliasesExistentes": db.count("aliases", "NOOP"),
            "vinculosNovos": db.count("links", "CREATE"),
            "vinculosExistentes": db.count("links", "NOOP"),
            "equipamentosNaoLocalizados": [
                f"{a.equipment_name} ({a.detail})" for a in db.links if a.action == "EQUIPMENT_NOT_FOUND"
            ],
            "conflitos": db.conflicts,
        }
    return report


def _render_human(report: dict[str, Any]) -> str:
    lines = [
        f"Planilha: {report['planilha']}",
        f"SHA-256: {report['sha256']}",
        "",
        "Reconciliação da planilha:",
    ]
    for check in report["reconciliacao"]:
        mark = "OK " if check["ok"] else "ERR"
        lines.append(
            f"  [{mark}] {check['check']}: esperado={check['esperado']} planilha={check['planilha']}"
        )
    lines += [
        "",
        f"Suppliers corporativos (por corporate_code): {report['suppliersCandidatos']}",
        f"Aliases MONDAY/{report['contextoAlias']}: {report['aliasesCandidatos']}",
        f"Vínculos equipment_supplier propostos: {report['vinculosCandidatos']}",
    ]
    banco = report["banco"]
    if isinstance(banco, str):
        lines.append(f"Banco: {banco}")
    else:
        lines += [
            f"Banco (contexto {banco['projectContextId'] or 'NÃO ENCONTRADO'}):",
            f"  suppliers novos: {banco['suppliersNovos']}",
            f"  suppliers já existentes: {banco['suppliersExistentes']}",
            f"  suppliers que seriam atualizados: {len(banco['suppliersAtualizados'])}",
            f"  aliases novos: {banco['aliasesNovos']} (existentes: {banco['aliasesExistentes']})",
            f"  vínculos novos: {banco['vinculosNovos']} (existentes: {banco['vinculosExistentes']})",
            f"  equipamentos não localizados: {len(banco['equipamentosNaoLocalizados'])}",
            f"  conflitos: {len(banco['conflitos'])}",
        ]
        lines += [f"    - {item}" for item in banco["conflitos"]]
    ignored = report["ignorados"]
    labels = {
        "aliasesProvaveis": "Aliases PROVÁVEIS ignorados",
        "aliasesAmbiguos": "Aliases AMBÍGUOS ignorados",
        "aliasesNaoEncontrados": "Aliases NÃO ENCONTRADOS / marcador ignorados",
        "equipamentosProvaveis": "Equipamentos PROVÁVEIS ignorados",
        "equipamentosAmbiguos": "Equipamentos AMBÍGUOS ignorados",
        "equipamentosNaoEncontrados": "Equipamentos NÃO ENCONTRADOS / marcador ignorados",
        "equipamentosOutrosMotivos": "Equipamentos ignorados por outros motivos",
    }
    lines.append("")
    for key, label in labels.items():
        lines.append(f"{label}: {len(ignored[key])}")
        lines += [f"    - {item}" for item in ignored[key]]
    lines += [
        f"Códigos corporativos inválidos: {len(report['codigosInvalidos'])}",
        f"Erros: {len(report['erros'])}",
    ]
    lines += [f"    - {item}" for item in report["erros"]]
    return "\n".join(lines)


def _load_plan(args: argparse.Namespace) -> SupplierImportPlan:
    try:
        workbook = load_supplier_workbook(args.workbook)
        return build_supplier_import_plan(workbook, alias_context=args.alias_context)
    except SupplierWorkbookError as exc:
        raise SystemExit(f"Planilha inválida: {exc}") from exc
    except SupplierReconciliationError as exc:
        raise SystemExit(str(exc)) from exc


async def _reconcile(args: argparse.Namespace, plan: SupplierImportPlan) -> DatabaseReconciliation:
    async with SessionLocal() as session:
        context_id = await resolve_project_context(
            session, unit_code=args.unit_code, context_code=args.context_code
        )
        return await reconcile_with_database(session, plan, project_context_id=context_id)


async def _apply(args: argparse.Namespace, plan: SupplierImportPlan) -> DatabaseReconciliation:
    actor = await _load_actor(args.actor_id)
    async with SessionLocal() as session:
        context_id = await resolve_project_context(
            session, unit_code=args.unit_code, context_code=args.context_code
        )
        return await apply_supplier_import(session, plan, project_context_id=context_id, actor=actor)


def _emit(args: argparse.Namespace, report: dict[str, Any]) -> None:
    serialized = json.dumps(report, ensure_ascii=False, indent=2, default=str)
    if args.json_out is not None:
        args.json_out.write_text(serialized + "\n", encoding="utf-8")
    print(serialized if args.json else _render_human(report))


def _cmd(args: argparse.Namespace) -> int:
    plan = _load_plan(args)
    if args.dry_run:
        db = None
        if not args.offline:
            target = describe_url_without_secret(get_settings().database_url)
            print(f"[supplier_import] dry-run somente leitura contra: {target}", file=sys.stderr)
            db = asyncio.run(_reconcile(args, plan))
        report = build_report(plan, db)
        _emit(args, report)
        return 1 if plan.errors or (db is not None and db.conflicts) else 0

    try:
        target = guard_write_target(get_settings())
    except UnsafeMigrationTargetError as exc:
        raise SystemExit(str(exc)) from exc
    if not args.confirm:
        raise SystemExit(f"--apply exige --confirm explícito (alvo: {target}). Rode --dry-run antes.")
    if not args.actor_id:
        raise SystemExit("--apply exige --actor-id (usuário responsável na auditoria).")
    print(f"[supplier_import] Alvo confirmado (sem senha): {target}", file=sys.stderr)
    try:
        db = asyncio.run(_apply(args, plan))
    except SupplierImportBlockedError as exc:
        raise SystemExit(f"Carga recusada: {exc}") from exc
    _emit(args, build_report(plan, db))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m app.modules.supplier_import",
        description="Carga de fornecedores oficiais CONFIRMADOS do LEM F2 (planilha auditada).",
    )
    parser.add_argument(
        "workbook", type=Path, help="Planilha Auditoria_Fornecedores_LEM_C2_F2_VALIDADA*.xlsx"
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true", help="Valida e compara sem gravar nada")
    mode.add_argument("--apply", action="store_true", help="Grava (DEV/TESTE; exige --confirm e --actor-id)")
    parser.add_argument("--offline", action="store_true", help="Com --dry-run: não abre conexão com banco")
    parser.add_argument("--confirm", action="store_true")
    parser.add_argument("--actor-id", default=None, help="UUID do usuário responsável (auditoria)")
    parser.add_argument("--unit-code", default="LEM")
    parser.add_argument("--context-code", default="F2")
    parser.add_argument("--alias-context", default="LEM_F2")
    parser.add_argument("--json", action="store_true", help="Imprime o relatório em JSON")
    parser.add_argument("--json-out", type=Path, default=None, help="Grava o relatório JSON neste caminho")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.offline and not args.dry_run:
        raise SystemExit("--offline só pode ser usado com --dry-run")
    return _cmd(args)
