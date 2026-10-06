"""Seed controlada da base auxiliar de sugestões de fornecedores.

Exemplos:
  python scripts/seed_supplier_evidence.py --dry-run --offline
  python scripts/seed_supplier_evidence.py --dry-run
  python scripts/seed_supplier_evidence.py --apply --confirm --actor-id UUID
  python scripts/seed_supplier_evidence.py relacao_fornecedores_hub.xlsx \
    --export-json app/data/supplier_evidence_seed.json

O apply nunca cria Supplier nem EquipmentSupplier. O alvo ainda passa pela
mesma guarda de escrita das migrações Monday.
"""

from __future__ import annotations

import argparse
import asyncio
import json
from collections import Counter
from pathlib import Path
from typing import Any

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.modules.monday_import.cli import _load_actor
from app.modules.monday_import.safety import describe_url_without_secret, guard_write_target
from app.modules.supplier_import.evidence_seed import (
    EvidenceSeedAction,
    EvidenceSeedRow,
    apply_evidence_seed,
    export_evidence_seed,
    load_evidence_seed,
    load_evidence_seed_json,
    reconcile_evidence_seed,
)

DEFAULT_SEED = Path(__file__).resolve().parents[1] / "app" / "data" / "supplier_evidence_seed.json"


def _load_rows(path: Path) -> list[EvidenceSeedRow]:
    return load_evidence_seed_json(path) if path.suffix.lower() == ".json" else load_evidence_seed(path)


def _summary(actions: list[EvidenceSeedAction]) -> dict[str, int]:
    counts = Counter(action.action for action in actions)
    return {name.lower(): counts[name] for name in ("CREATE", "UPDATE", "NOOP", "DEACTIVATE")}


async def _database_actions(path: Path, *, apply: bool, actor_id: str | None) -> list[EvidenceSeedAction]:
    rows = _load_rows(path)
    actor = await _load_actor(actor_id) if apply and actor_id is not None else None
    async with SessionLocal() as session:
        if not apply:
            return await reconcile_evidence_seed(session, rows)
        assert actor is not None
        return await apply_evidence_seed(session, rows, actor=actor)


def _report(path: Path, rows: int, actions: list[EvidenceSeedAction] | None) -> dict[str, Any]:
    return {
        "file": path.name,
        "evidenceRows": rows,
        "database": None if actions is None else _summary(actions),
        "createsSuppliers": False,
        "createsEquipmentLinks": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed das evidências de sugestão de fornecedores")
    parser.add_argument("source", type=Path, nargs="?", default=DEFAULT_SEED)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--apply", action="store_true")
    mode.add_argument("--export-json", type=Path)
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--confirm", action="store_true")
    parser.add_argument("--actor-id")
    args = parser.parse_args()

    rows = _load_rows(args.source)
    if args.export_json is not None:
        if args.source.suffix.lower() != ".xlsx":
            parser.error("--export-json exige a planilha .xlsx como origem")
        args.export_json.parent.mkdir(parents=True, exist_ok=True)
        export_evidence_seed(rows, args.export_json)
        print(json.dumps(_report(args.export_json, len(rows), None), ensure_ascii=False, indent=2))
        return 0
    if args.offline:
        if not args.dry_run:
            parser.error("--offline só pode ser usado com --dry-run")
        print(json.dumps(_report(args.source, len(rows), None), ensure_ascii=False, indent=2))
        return 0

    settings = get_settings()
    target = describe_url_without_secret(settings.database_url)
    if args.apply:
        guard_write_target(settings)
        if not args.confirm or not args.actor_id:
            parser.error("--apply exige --confirm e --actor-id")
    actions = asyncio.run(
        _database_actions(args.source, apply=args.apply, actor_id=args.actor_id)
    )
    report = _report(args.source, len(rows), actions)
    report["target"] = target
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
