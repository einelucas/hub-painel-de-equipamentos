"""CLI da reconciliação EAP (somente análise — não existe modo de escrita).

# offline: exports Monday + catálogo versionado → JSON + Markdown
python -m app.modules.eap_reconciliation analyze --project "LEM C2" \
    --export "<fase-0>.xlsx" --export "<…0920>.xlsx" \
    --auxiliary "<…0895>.xlsx" --auxiliary "<…0910>.xlsx" \
    --json-out app/data/reconciliation/lem_c2_eap_reconciliation.json \
    --markdown-out ../docs/reconciliation/lem-c2-eap.md

# + comparação com banco, em transação READ ONLY
    ... --compare-db --env-file .env
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
from app.modules.eap_reconciliation.report import render_markdown


async def _compare(report: dict[str, Any]) -> dict[str, Any]:
    from app.core.database import SessionLocal
    from app.modules.eap_reconciliation.database import compare_with_database

    async with SessionLocal() as session:
        return await compare_with_database(session, report)


def _cmd_analyze(args: argparse.Namespace) -> int:
    report = build_reconciliation(project=args.project, paths=args.export, catalog=load_catalog(args.catalog))
    if args.auxiliary:
        report["auxiliary_exports"] = check_auxiliary_exports(args.export, args.auxiliary)
    if args.compare_db:
        if args.env_file is not None:
            from dotenv import load_dotenv

            if not args.env_file.is_file():
                raise SystemExit(f"--env-file não encontrado: {args.env_file}")
            load_dotenv(args.env_file, override=True)
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
        args.markdown_out.write_bytes(render_markdown(report).encode("utf-8"))
    print(json.dumps(report["metrics"], indent=2))
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
    analyze.add_argument("--json-out", type=Path, default=None)
    analyze.add_argument("--markdown-out", type=Path, default=None)
    analyze.add_argument(
        "--compare-db", action="store_true", help="Compara com o banco em transação READ ONLY"
    )
    analyze.add_argument("--env-file", type=Path, default=None)
    analyze.set_defaults(handler=_cmd_analyze)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.handler(args))
