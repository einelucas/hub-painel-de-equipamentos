"""CLI segura para extrair, validar e carregar o catálogo de fornecedores."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from app.modules.supplier_catalog.catalog import (
    CATALOG_PATH,
    SupplierCatalogError,
    build_catalog_document,
    load_catalog,
    parse_catalog,
    validate_catalog,
)
from app.modules.supplier_catalog.workbook import SupplierWorkbookError, load_supplier_workbook


def _cmd_extract(args: argparse.Namespace) -> int:
    try:
        workbook = load_supplier_workbook(args.workbook)
        document = build_catalog_document(workbook)
        errors = validate_catalog(parse_catalog(document))
    except (OSError, SupplierWorkbookError, SupplierCatalogError) as exc:
        raise SystemExit(f"Extração interrompida: {exc}") from exc
    if errors:
        print("\n".join(errors), file=sys.stderr)
        raise SystemExit("Extração gerou catálogo inválido; nada foi gravado.")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(document["summary"], ensure_ascii=False, indent=2))
    print(f"Catálogo gravado em {args.out}", file=sys.stderr)
    return 0


def _cmd_validate(args: argparse.Namespace) -> int:
    try:
        catalog = load_catalog(args.catalog)
        errors = validate_catalog(catalog)
    except SupplierCatalogError as exc:
        raise SystemExit(str(exc)) from exc
    print(
        json.dumps(
            {"sha256": catalog.sha256, "suppliers": len(catalog.suppliers), "errors": errors},
            ensure_ascii=False,
            indent=2,
        )
    )
    return 1 if errors else 0


def _report(
    *, database: str, revision: str, catalog: Any, result: Any
) -> dict[str, Any]:
    return {
        "database": database,
        "alembicRevision": revision,
        "catalogSha256": catalog.sha256,
        "catalogSuppliers": len(catalog.suppliers),
        "summary": result.summary(),
        "suppliers": [
            {
                "corporateCode": item.corporate_code,
                "action": item.action,
                "differences": item.differences,
                "detail": item.detail,
            }
            for item in result.suppliers
        ],
        "aliases": [
            {
                "corporateCode": item.corporate_code,
                "alias": item.alias,
                "action": item.action,
                "detail": item.detail,
            }
            for item in result.aliases
        ],
        "conflicts": result.conflicts,
        "extraInDatabase": result.extra_in_database,
    }


async def _seed(args: argparse.Namespace) -> tuple[dict[str, Any], bool]:
    from sqlalchemy import text

    from app.core.database import SessionLocal
    from app.modules.supplier_catalog.seed import (
        SupplierCatalogBlockedError,
        seed_supplier_catalog,
    )

    catalog = load_catalog(args.catalog)
    async with SessionLocal() as session:
        database = (await session.execute(text("SELECT current_database()"))).scalar_one()
        revision = (await session.execute(text("SELECT version_num FROM alembic_version"))).scalar_one()
        print(f"[supplier_catalog] banco={database} alembic={revision}", file=sys.stderr)
        if args.apply and database != args.expect_database:
            raise SystemExit(
                f"Banco conectado '{database}' difere de --expect-database "
                f"'{args.expect_database}'. Nada foi gravado."
            )
        try:
            result = await seed_supplier_catalog(
                session,
                catalog,
                apply=args.apply,
                sync=args.sync,
                actor_id=args.actor_id,
            )
        except SupplierCatalogBlockedError as exc:
            return _report(database=database, revision=revision, catalog=catalog, result=exc.result), True
    return _report(database=database, revision=revision, catalog=catalog, result=result), bool(
        result.conflicts
    )


def _cmd_seed(args: argparse.Namespace) -> int:
    if args.env_file is not None:
        from dotenv import load_dotenv

        if not args.env_file.is_file():
            raise SystemExit(f"--env-file não encontrado: {args.env_file}")
        load_dotenv(args.env_file, override=True)

    if args.apply and (not args.confirm or not args.expect_database):
        raise SystemExit("--apply exige --confirm e --expect-database <nome do banco>.")

    # Estes imports permanecem depois do load_dotenv: database.py cria o engine
    # no import e deve enxergar exclusivamente o arquivo escolhido pelo operador.
    from app.core.config import get_settings
    from app.modules.monday_import.safety import (
        UnsafeMigrationTargetError,
        describe_url_without_secret,
        guard_write_target,
    )

    settings = get_settings()
    if args.apply:
        try:
            target = guard_write_target(settings)
        except UnsafeMigrationTargetError as exc:
            raise SystemExit(str(exc)) from exc
    else:
        target = describe_url_without_secret(settings.database_url)
    mode = "APPLY" if args.apply else "dry-run"
    print(f"[supplier_catalog] {mode} contra (sem senha): {target}", file=sys.stderr)
    try:
        report, blocked = asyncio.run(_seed(args))
    except SupplierCatalogError as exc:
        raise SystemExit(str(exc)) from exc
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 1 if blocked else 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m app.modules.supplier_catalog",
        description="Catálogo global e canônico de fornecedores oficiais.",
    )
    commands = parser.add_subparsers(dest="command", required=True)

    extract = commands.add_parser("extract", help="Extrai a planilha aprovada para JSON canônico")
    extract.add_argument("workbook", type=Path)
    extract.add_argument("--out", type=Path, default=CATALOG_PATH)
    extract.set_defaults(handler=_cmd_extract)

    validate = commands.add_parser("validate", help="Valida o JSON canônico sem acessar banco")
    validate.add_argument("--catalog", type=Path, default=CATALOG_PATH)
    validate.set_defaults(handler=_cmd_validate)

    seed = commands.add_parser("seed", help="Reconcilia/carrega somente Supplier e SupplierAlias")
    mode = seed.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--apply", action="store_true")
    seed.add_argument("--sync", action="store_true")
    seed.add_argument("--confirm", action="store_true")
    seed.add_argument("--expect-database", default=None)
    seed.add_argument("--env-file", type=Path, default=None)
    seed.add_argument("--actor-id", default=None)
    seed.add_argument("--catalog", type=Path, default=CATALOG_PATH)
    seed.set_defaults(handler=_cmd_seed)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.handler(args))
