"""CLI do catálogo EAP canônico.

# DESENVOLVIMENTO: extrai a Árvore oficial (somente leitura) para o JSON versionado
python -m app.modules.eap_catalog extract "<Árvore>.xlsx" [--out app/data/eap_catalog.json]

# valida o JSON versionado, sem banco
python -m app.modules.eap_catalog validate

# compara com o banco, sem gravar
python -m app.modules.eap_catalog seed --dry-run --env-file .env.test

# carga real (DEV/TESTE; exige --confirm e o nome exato do banco esperado)
python -m app.modules.eap_catalog seed --apply --confirm --expect-database neondb_test --env-file .env.test

`--env-file` é aplicado ANTES de qualquer import que crie o engine: o banco
alvo é sempre o do arquivo informado, nunca um `.env` carregado por engano.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import sys
from collections import Counter
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from app.modules.eap_catalog.catalog import (
    CATALOG_PATH,
    EapCatalogError,
    build_catalog_document,
    load_catalog,
    parse_catalog,
    validate_catalog,
)
from app.modules.eap_catalog.tree import TreeRow, extract_tree


def _cmd_extract(args: argparse.Namespace) -> int:
    from app.modules.monday_import.xlsx import read_first_sheet

    raw = args.workbook.read_bytes()
    sheet = read_first_sheet(raw)
    rows = [TreeRow(row.number, row.value(1), row.value(2)) for row in sheet.rows if row.number > 1]
    tree = extract_tree(rows)
    levels = Counter(node.level.value for node in tree.nodes)
    distinct_codes = {node.code for node in tree.nodes if node.level.value != "ISLAND"} | {
        item.code for item in tree.review_required if item.code and item.level.value != "ISLAND"
    }
    document = build_catalog_document(
        nodes=[node.as_dict() for node in tree.nodes],
        review_required=[item.as_dict() for item in tree.review_required],
        source={
            "file": args.workbook.name,
            "sha256": hashlib.sha256(raw).hexdigest(),
            "sheet": sheet.name,
            "eap_rows": tree.eap_rows,
            "island_rows": tree.island_rows,
            "non_eap_rows": tree.non_eap_rows,
        },
        summary={
            "distinct_eap_codes": len(distinct_codes),
            "nodes": len(tree.nodes),
            "island": levels.get("ISLAND", 0),
            "process": levels.get("PROCESS", 0),
            "area": levels.get("AREA", 0),
            "review_required": len(tree.review_required),
        },
    )
    errors = validate_catalog(parse_catalog(document))
    if errors:
        print("\n".join(errors), file=sys.stderr)
        raise SystemExit("Extração gerou catálogo inválido; nada foi gravado.")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(document["summary"], ensure_ascii=False, indent=2))
    print(f"Catálogo gravado em {args.out}", file=sys.stderr)
    return 0


def _cmd_validate(args: argparse.Namespace) -> int:
    catalog = load_catalog(args.catalog)
    errors = validate_catalog(catalog)
    print(json.dumps({"sha256": catalog.sha256, "nodes": len(catalog.nodes), "errors": errors}, indent=2))
    return 1 if errors else 0


async def _seed(args: argparse.Namespace) -> dict[str, Any]:
    from sqlalchemy import text

    from app.core.database import SessionLocal
    from app.modules.eap_catalog.seed import seed_eap_catalog

    catalog = load_catalog(args.catalog)
    async with SessionLocal() as session:
        database = (await session.execute(text("SELECT current_database()"))).scalar_one()
        revision = (await session.execute(text("SELECT version_num FROM alembic_version"))).scalar_one()
        print(f"[eap_catalog] banco={database} alembic={revision}", file=sys.stderr)
        if args.apply and database != args.expect_database:
            raise SystemExit(
                f"Banco conectado '{database}' difere de --expect-database '{args.expect_database}'. "
                "Nada foi gravado."
            )
        result = await seed_eap_catalog(session, catalog, apply=args.apply, actor_id=args.actor_id)
    return {
        "database": database,
        "alembicRevision": revision,
        "catalogSha256": catalog.sha256,
        "summary": result.summary(),
        "created": result.created,
        "conflicts": result.conflicts,
        "skippedReviewRequired": result.skipped_review_required,
        "extraInDatabase": result.extra_in_database,
    }


def _cmd_seed(args: argparse.Namespace) -> int:
    if args.env_file is not None:
        from dotenv import load_dotenv

        if not args.env_file.is_file():
            raise SystemExit(f"--env-file não encontrado: {args.env_file}")
        load_dotenv(args.env_file, override=True)

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
    print(f"[eap_catalog] {mode} contra (sem senha): {target}", file=sys.stderr)
    try:
        report = asyncio.run(_seed(args))
    except EapCatalogError as exc:
        raise SystemExit(str(exc)) from exc
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 1 if report["conflicts"] else 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m app.modules.eap_catalog", description="Catálogo EAP canônico (Árvore oficial)."
    )
    commands = parser.add_subparsers(dest="command", required=True)

    extract = commands.add_parser("extract", help="DEV: extrai a Árvore oficial para o JSON versionado")
    extract.add_argument("workbook", type=Path)
    extract.add_argument("--out", type=Path, default=CATALOG_PATH)
    extract.set_defaults(handler=_cmd_extract)

    validate = commands.add_parser("validate", help="Valida o JSON versionado (sem banco)")
    validate.add_argument("--catalog", type=Path, default=CATALOG_PATH)
    validate.set_defaults(handler=_cmd_validate)

    seed = commands.add_parser("seed", help="Carga idempotente em eap_node")
    mode = seed.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--apply", action="store_true")
    seed.add_argument("--confirm", action="store_true")
    seed.add_argument("--expect-database", default=None)
    seed.add_argument("--env-file", type=Path, default=None)
    seed.add_argument("--actor-id", default=None, help="Usuário registrado no AuditLog (opcional)")
    seed.add_argument("--catalog", type=Path, default=CATALOG_PATH)
    seed.set_defaults(handler=_cmd_seed)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.handler(args))
