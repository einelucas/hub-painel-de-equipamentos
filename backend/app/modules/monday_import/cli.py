"""CLI administrativa do importador Monday.

Preserva o uso original (compatibilidade retroativa):

    python -m app.modules.monday_import <arquivo-ou-diretorio>

que é tratado como `dry-run`. Os demais passos do fluxo administrativo
(stage → plan → apply → reconcile) são subcomandos explícitos, cada um
com sua própria salvaguarda de segurança quando grava no banco.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from app.core.auth import CurrentUser
from app.core.config import get_settings
from app.core.database import SessionLocal
from app.core.permissions import Role
from app.models.user import User
from app.modules.monday_import.apply import ApplyResult, PlanBlockedError, PlanStaleError, apply_plan
from app.modules.monday_import.domain_reconciliation import (
    DomainReconciliationReport,
    reconcile_domain,
    render_human,
)
from app.modules.monday_import.dry_run import build_dry_run_report, merge_workbooks
from app.modules.monday_import.mapping_file import (
    EMPTY_MAPPING_SCHEMA,
    ValidatedMapping,
    load_mapping_file,
    validate_mapping,
)
from app.modules.monday_import.parser import parse_monday_xlsx
from app.modules.monday_import.plan import MigrationPlan, build_plan
from app.modules.monday_import.reconciliation import C2_EXPECTED, count_records, reconcile_counts
from app.modules.monday_import.safety import UnsafeMigrationTargetError, guard_write_target
from app.modules.monday_import.service import stage_import

_SUBCOMMANDS = {"dry-run", "stage", "plan", "apply", "reconcile"}


def _files(inputs: Sequence[str]) -> list[Path]:
    found: list[Path] = []
    for raw in inputs:
        path = Path(raw)
        if path.is_dir():
            found.extend(sorted(path.glob("*.xlsx")))
        elif path.suffix.casefold() == ".xlsx":
            found.append(path)
        else:
            raise ValueError(f"fonte não é diretório nem XLSX: {path}")
    unique: dict[Path, None] = {}
    for path in found:
        unique[path.resolve()] = None
    return list(unique)


def _human_dry_run(report: dict, reconciliation: dict) -> str:
    lines = [
        f"Arquivos: {', '.join(report['files'])}",
        f"Boards: {', '.join(report['board_titles']) or 'não identificado'}",
        f"Equipamentos encontrados: {report['equipments']}",
        f"Subitens encontrados: {report['components']}",
        "Grupos:",
    ]
    for name, count in report["groups"].items():
        lines.append(f"  {name}: {count['equipments']} equipamentos / {count['components']} subitens")
    lines.extend(
        [
            f"Campos desconhecidos: {len(report['unknown_fields'])}",
            f"Datas inválidas: {report['invalid_dates']}",
            f"Responsáveis sem mapeamento: {len(report['unmapped_responsibles'])}",
            f"Áreas sem mapeamento: {len(report['unmapped_areas'])}",
            f"Work Packages sem mapeamento: {len(report['unmapped_work_packages'])}",
            f"Registros repetidos entre snapshots: {report['duplicate_records']}",
            f"Avisos: {report['warnings']}",
            f"Erros: {report['errors']}",
            f"Reconciliação C2 (41/164): {'OK' if reconciliation['matched'] else 'DIVERGENTE'}",
        ]
    )
    for mismatch in reconciliation["mismatches"]:
        lines.append("  {scope} {metric}: origem={source}, esperado={destination}".format(**mismatch))
    return "\n".join(lines)


def _cmd_dry_run(args: argparse.Namespace) -> int:
    try:
        paths = _files(args.inputs)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    if not paths:
        raise SystemExit("nenhum arquivo .xlsx encontrado")
    workbooks = [parse_monday_xlsx(path) for path in paths]
    report = build_dry_run_report(workbooks)
    equipments, _ = merge_workbooks(workbooks)
    reconciliation = reconcile_counts(count_records(equipments), C2_EXPECTED)
    payload = report.to_dict()
    payload["c2_reconciliation"] = reconciliation.to_dict()
    serialized = json.dumps(payload, ensure_ascii=False, indent=2)
    if args.json_out is not None:
        args.json_out.write_text(serialized + "\n", encoding="utf-8")
    print(serialized if args.json else _human_dry_run(report.to_dict(), reconciliation.to_dict()))
    return 0 if report.errors == 0 else 1


async def _stage_one(project_context_id: str, path: Path) -> dict[str, object]:
    async with SessionLocal() as session:
        result = await stage_import(session, project_context_id=project_context_id, source=path)
        await session.commit()
        return {
            "file": path.name,
            "batchId": result.batch_id,
            "created": result.created,
            "records": result.records,
            "issues": result.issues,
        }


def _cmd_stage(args: argparse.Namespace) -> int:
    settings = get_settings()
    try:
        target = guard_write_target(settings)
    except UnsafeMigrationTargetError as exc:
        raise SystemExit(str(exc)) from exc
    print(f"[monday_import] Alvo confirmado (sem senha): {target}")

    try:
        paths = _files(args.inputs)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    if not paths:
        raise SystemExit("nenhum arquivo .xlsx encontrado")

    results = [asyncio.run(_stage_one(args.project_context_id, path)) for path in paths]
    print(json.dumps(results, ensure_ascii=False, indent=2))
    return 0


async def _load_mapping(mapping_file: Path | None, *, project_context_id: str) -> ValidatedMapping:
    schema = EMPTY_MAPPING_SCHEMA if mapping_file is None else load_mapping_file(mapping_file)
    async with SessionLocal() as session:
        return await validate_mapping(session, schema, project_context_id=project_context_id)


async def _run_plan(args: argparse.Namespace) -> tuple[ValidatedMapping, MigrationPlan]:
    mapping = await _load_mapping(args.mapping_file, project_context_id=args.project_context_id)
    async with SessionLocal() as session:
        plan = await build_plan(
            session,
            project_context_id=args.project_context_id,
            batch_ids=args.batch,
            mapping=mapping,
        )
    return mapping, plan


def _cmd_plan(args: argparse.Namespace) -> int:
    mapping, plan = asyncio.run(_run_plan(args))
    payload = plan.to_dict()
    payload["mapping"] = mapping.to_summary()
    serialized = json.dumps(payload, ensure_ascii=False, indent=2, default=str)
    if args.json_out is not None:
        args.json_out.write_text(serialized + "\n", encoding="utf-8")
    if args.json:
        print(serialized)
    else:
        print(f"Plano (hash {plan.plan_sha256}):")
        for name, items in plan.all_groups.items():
            counts = {"CREATE": 0, "UPDATE": 0, "NOOP": 0, "BLOCKED": 0}
            for item in items:
                counts[item.action] += 1
            print(
                f"  {name}: CREATE={counts['CREATE']} UPDATE={counts['UPDATE']} "
                f"NOOP={counts['NOOP']} BLOCKED={counts['BLOCKED']}"
            )
        print(f"Mappings sem resolução: {sum(1 for i in mapping.issues if i.category == 'error')}")
        print(f"Avisos: {len(plan.warnings)}")
        for warning in plan.warnings:
            print(f"  [{warning.code}] {warning.message}")
        if plan.has_blocked:
            print("\nItens bloqueados:")
            for name, items in plan.all_groups.items():
                for item in items:
                    if item.action != "BLOCKED":
                        continue
                    for issue in item.issues:
                        print(f"  [{name}] {item.source_key}: [{issue.code}] {issue.message}")
    return 1 if plan.has_blocked else 0


async def _load_actor(actor_id: str) -> CurrentUser:
    async with SessionLocal() as session:
        user = await session.get(User, actor_id)
        if user is None:
            raise SystemExit(f"--actor-id inválido: usuário {actor_id} não existe")
        if not user.active:
            raise SystemExit(f"--actor-id inválido: usuário {actor_id} está inativo")
        role = Role(user.role.value if hasattr(user.role, "value") else user.role)
        return CurrentUser(id=user.id, email=user.email, name=user.name, role=role, active=user.active)


async def _run_apply(args: argparse.Namespace) -> ApplyResult:
    mapping = await _load_mapping(args.mapping_file, project_context_id=args.project_context_id)
    actor = await _load_actor(args.actor_id)
    async with SessionLocal() as session:
        plan = await build_plan(
            session,
            project_context_id=args.project_context_id,
            batch_ids=args.batch,
            mapping=mapping,
        )
        result = await apply_plan(
            session, plan=plan, expected_plan_sha256=args.plan_hash, actor=actor
        )
    return result


def _cmd_apply(args: argparse.Namespace) -> int:
    settings = get_settings()
    try:
        target = guard_write_target(settings)
    except UnsafeMigrationTargetError as exc:
        raise SystemExit(str(exc)) from exc
    if not args.confirm:
        raise SystemExit(
            "apply exige --confirm explícito. Revise o `plan` antes de prosseguir "
            f"(alvo: {target})."
        )
    print(f"[monday_import] Alvo confirmado (sem senha): {target}")
    try:
        result = asyncio.run(_run_apply(args))
    except PlanStaleError as exc:
        raise SystemExit(f"PLAN_STALE: {exc}") from exc
    except PlanBlockedError as exc:
        lines = ["Apply recusado: plano tem itens bloqueados.", *[
            f"  {item.kind} {item.source_key}: {[issue.code for issue in item.issues]}"
            for item in exc.blocked
        ]]
        raise SystemExit("\n".join(lines)) from exc
    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    return 0


async def _run_reconcile(args: argparse.Namespace) -> DomainReconciliationReport:
    mapping = (
        await _load_mapping(args.mapping_file, project_context_id=args.project_context_id)
        if args.mapping_file
        else None
    )
    async with SessionLocal() as session:
        return await reconcile_domain(
            session, project_context_id=args.project_context_id, mapping=mapping
        )


def _cmd_reconcile(args: argparse.Namespace) -> int:
    report = asyncio.run(_run_reconcile(args))
    if args.json:
        print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2, default=str))
    else:
        print(render_human(report))
    return 1 if report.field_totals["MISMATCH"] > 0 else 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m app.modules.monday_import",
        description="Administração do importador Monday: dry-run, stage, plan, apply, reconcile.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    dry_run = subparsers.add_parser(
        "dry-run", help="Analisa XLSX sem gravar no banco (padrão retrocompatível)"
    )
    dry_run.add_argument("inputs", nargs="+", help="Arquivo(s) XLSX ou diretório com exports")
    dry_run.add_argument("--json-out", type=Path, help="Grava o relatório JSON neste caminho")
    dry_run.add_argument("--json", action="store_true", help="Imprime JSON no stdout")
    dry_run.set_defaults(func=_cmd_dry_run)

    stage = subparsers.add_parser("stage", help="Grava raw+normalizado no staging (idempotente)")
    stage.add_argument("inputs", nargs="+", help="Arquivo(s) XLSX ou diretório com exports")
    stage.add_argument("--project-context-id", required=True)
    stage.set_defaults(func=_cmd_stage)

    plan = subparsers.add_parser("plan", help="Compara staging+mapping+banco; não grava")
    plan.add_argument("--project-context-id", required=True)
    plan.add_argument("--batch", action="append", required=True, dest="batch", help="Pode repetir")
    plan.add_argument("--mapping-file", type=Path, default=None)
    plan.add_argument("--json-out", type=Path, default=None)
    plan.add_argument("--json", action="store_true")
    plan.set_defaults(func=_cmd_plan)

    apply_cmd = subparsers.add_parser("apply", help="Executa o plano validado (DEV/TESTE apenas)")
    apply_cmd.add_argument("--project-context-id", required=True)
    apply_cmd.add_argument("--batch", action="append", required=True, dest="batch")
    apply_cmd.add_argument("--mapping-file", type=Path, default=None)
    apply_cmd.add_argument("--plan-hash", required=True, help="Hash impresso por `plan`")
    apply_cmd.add_argument("--actor-id", required=True, help="UUID do usuário responsável (auditoria)")
    apply_cmd.add_argument("--confirm", action="store_true")
    apply_cmd.set_defaults(func=_cmd_apply)

    reconcile = subparsers.add_parser("reconcile", help="Compara Hub aplicado x staging, campo a campo")
    reconcile.add_argument("--project-context-id", required=True)
    reconcile.add_argument("--mapping-file", type=Path, default=None)
    reconcile.add_argument("--json", action="store_true")
    reconcile.set_defaults(func=_cmd_reconcile)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    raw_argv = list(sys.argv[1:] if argv is None else argv)
    if raw_argv and raw_argv[0] not in _SUBCOMMANDS and not raw_argv[0].startswith("-"):
        raw_argv = ["dry-run", *raw_argv]
    args = build_parser().parse_args(raw_argv)
    return int(args.func(args))
