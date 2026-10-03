"""CLI da reconciliação EAP.

`analyze` é somente leitura. `apply` grava `equipment.eap_node_id` só a partir do
JSON versionado, em DEV/TESTE, com --confirm e --expect-database.

# offline: exports Monday + catálogo versionado → JSON + Markdown
python -m app.modules.eap_reconciliation analyze --project "LEM C2" \
    --export "<fase-0>.xlsx" --export "<…0920>.xlsx" \
    --auxiliary "<…0895>.xlsx" --auxiliary "<…0910>.xlsx" \
    --json-out app/data/reconciliation/lem_c2_eap_reconciliation.json \
    --markdown-out ../docs/reconciliation/lem-c2-eap.md

# + comparação com banco, em transação READ ONLY
    ... --compare-db --env-file .env

# apply controlado a partir do JSON versionado (nunca recalcula a reconciliação)
python -m app.modules.eap_reconciliation apply --dry-run --env-file .env.test \
    --artifact app/data/reconciliation/lem_c2_eap_reconciliation.json \
    --unit-code LEM --context-code C2 \
    --expect-total 41 --expect-safe 40 --expect-review 0 --expect-unresolved 1
    ... --apply --confirm --expect-database neondb_test
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from app.modules.eap_catalog.catalog import CATALOG_PATH, load_catalog
from app.modules.eap_reconciliation.monday import build_reconciliation, check_auxiliary_exports
from app.modules.eap_reconciliation.reconcile import ALIASES_PATH, load_decisions
from app.modules.eap_reconciliation.report import render_markdown

HISTORY_MARKER = "<!-- HISTÓRICO: mantido manualmente; preservado ao regenerar este relatório -->"


async def _compare(report: dict[str, Any]) -> dict[str, Any]:
    from app.core.database import SessionLocal
    from app.modules.eap_reconciliation.database import compare_with_database

    async with SessionLocal() as session:
        return await compare_with_database(session, report)


def _cmd_analyze(args: argparse.Namespace) -> int:
    report = build_reconciliation(
        project=args.project,
        paths=args.export,
        catalog=load_catalog(args.catalog),
        decisions=load_decisions(args.aliases),
    )
    if args.auxiliary:
        report["auxiliary_exports"] = check_auxiliary_exports(args.export, args.auxiliary)
    if args.compare_db:
        _load_env(args.env_file)
        from app.core.config import get_settings
        from app.modules.monday_import.safety import describe_url_without_secret

        target = describe_url_without_secret(get_settings().database_url)
        print(f"[eap_reconciliation] comparação READ ONLY contra (sem senha): {target}", file=sys.stderr)
        report["database_comparison"] = asyncio.run(_compare(report))
    serialized = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_bytes(serialized.encode("utf-8"))
    if args.markdown_out:
        args.markdown_out.parent.mkdir(parents=True, exist_ok=True)
        content = render_markdown(report)
        # O histórico de decisões/aplicações é escrito à mão abaixo do marcador
        # e sobrevive à regeneração do relatório.
        if args.markdown_out.is_file():
            previous = args.markdown_out.read_text(encoding="utf-8")
            if HISTORY_MARKER in previous:
                content = content.rstrip("\n") + "\n\n" + previous[previous.index(HISTORY_MARKER) :]
        args.markdown_out.write_bytes(content.encode("utf-8"))
    print(json.dumps(report["metrics"], indent=2))
    return 0


def _load_env(env_file: Path | None) -> None:
    if env_file is None:
        return
    from dotenv import load_dotenv

    if not env_file.is_file():
        raise SystemExit(f"--env-file não encontrado: {env_file}")
    load_dotenv(env_file, override=True)


async def _apply(args: argparse.Namespace) -> dict[str, Any]:
    from sqlalchemy import text

    from app.core.database import SessionLocal
    from app.modules.eap_reconciliation.apply import (
        Expectations,
        ReconciliationApplyBlocked,
        apply_reconciliation,
        load_artifact,
    )
    from app.modules.supplier_import.database import resolve_project_context

    artifact, artifact_sha = load_artifact(args.artifact)
    catalog = load_catalog(args.catalog)
    expect = Expectations(args.expect_total, args.expect_safe, args.expect_review, args.expect_unresolved)
    async with SessionLocal() as session:
        database = (await session.execute(text("SELECT current_database()"))).scalar_one()
        revision = (await session.execute(text("SELECT version_num FROM alembic_version"))).scalar_one()
        eap_nodes = (await session.execute(text("SELECT count(*) FROM eap_node"))).scalar_one()
        print(
            f"[eap_reconciliation] banco={database} alembic={revision} eap_node={eap_nodes}", file=sys.stderr
        )
        if args.apply and database != args.expect_database:
            raise SystemExit(f"Banco '{database}' difere de --expect-database '{args.expect_database}'.")
        context_id = await resolve_project_context(
            session, unit_code=args.unit_code, context_code=args.context_code
        )
        if context_id is None:
            raise SystemExit(f"ProjectContext {args.unit_code}/{args.context_code} não existe neste banco.")
        try:
            result = await apply_reconciliation(
                session,
                artifact=artifact,
                artifact_sha256=artifact_sha,
                catalog=catalog,
                project_context_id=context_id,
                apply=args.apply,
                expect=expect,
                actor_id=args.actor_id,
            )
        except ReconciliationApplyBlocked as exc:
            details = "\n- ".join(exc.errors)
            raise SystemExit(f"APPLY ABORTADO antes de escrever:\n- {details}") from exc
    return {
        "database": database,
        "alembicRevision": revision,
        "artifactSha256": result.artifact_sha256,
        "summary": result.summary(),
        "plannedUpdates": result.planned_updates,
        "unchanged": result.unchanged,
        "skippedUnresolved": result.skipped_unresolved,
        "skippedReview": result.skipped_review,
    }


def _cmd_apply(args: argparse.Namespace) -> int:
    _load_env(args.env_file)
    from app.core.config import get_settings
    from app.modules.monday_import.safety import (
        UnsafeMigrationTargetError,
        describe_url_without_secret,
        guard_write_target,
    )

    settings = get_settings()
    if args.apply:
        if not args.confirm or not args.expect_database:
            raise SystemExit("--apply exige --confirm e --expect-database <nome do banco>.")
        try:
            target = guard_write_target(settings)
        except UnsafeMigrationTargetError as exc:
            raise SystemExit(str(exc)) from exc
    else:
        target = describe_url_without_secret(settings.database_url)
    mode = "APPLY" if args.apply else "dry-run"
    print(f"[eap_reconciliation] {mode} contra (sem senha): {target}", file=sys.stderr)
    print(json.dumps(asyncio.run(_apply(args)), ensure_ascii=False, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m app.modules.eap_reconciliation",
        description="Reconciliação READ-ONLY dos equipamentos do Monday com o catálogo EAP oficial.",
    )
    commands = parser.add_subparsers(dest="command", required=True)
    analyze = commands.add_parser("analyze", help="Classifica a EAP de cada equipamento (sem escrita)")
    analyze.add_argument("--project", required=True)
    analyze.add_argument("--export", type=Path, action="append", required=True)
    analyze.add_argument("--auxiliary", type=Path, action="append", default=[])
    analyze.add_argument("--catalog", type=Path, default=CATALOG_PATH)
    analyze.add_argument("--aliases", type=Path, default=ALIASES_PATH)
    analyze.add_argument("--json-out", type=Path, default=None)
    analyze.add_argument("--markdown-out", type=Path, default=None)
    analyze.add_argument(
        "--compare-db", action="store_true", help="Compara com o banco em transação READ ONLY"
    )
    analyze.add_argument("--env-file", type=Path, default=None)
    analyze.set_defaults(handler=_cmd_analyze)

    apply = commands.add_parser("apply", help="Grava eap_node_id a partir do JSON versionado (DEV/TESTE)")
    mode = apply.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--apply", action="store_true")
    apply.add_argument("--confirm", action="store_true")
    apply.add_argument("--expect-database", default=None)
    apply.add_argument("--artifact", type=Path, required=True)
    apply.add_argument("--catalog", type=Path, default=CATALOG_PATH)
    apply.add_argument("--unit-code", required=True)
    apply.add_argument("--context-code", required=True)
    apply.add_argument("--expect-total", type=int, default=None)
    apply.add_argument("--expect-safe", type=int, default=None)
    apply.add_argument("--expect-review", type=int, default=None)
    apply.add_argument("--expect-unresolved", type=int, default=None)
    apply.add_argument("--env-file", type=Path, default=None)
    apply.add_argument("--actor-id", default=None, help="Usuário registrado no AuditLog (opcional)")
    apply.set_defaults(handler=_cmd_apply)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.handler(args))
