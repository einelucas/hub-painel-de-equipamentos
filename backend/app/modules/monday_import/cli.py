"""CLI administrativo de dry-run do importador Monday."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path

from app.modules.monday_import.dry_run import build_dry_run_report, merge_workbooks
from app.modules.monday_import.parser import parse_monday_xlsx
from app.modules.monday_import.reconciliation import C2_EXPECTED, count_records, reconcile_counts


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


def _human(report: dict, reconciliation: dict) -> str:
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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m app.modules.monday_import",
        description="Analisa exportações XLSX do Monday sem gravar no banco.",
    )
    parser.add_argument("inputs", nargs="+", help="Arquivo(s) XLSX ou diretório com exports")
    parser.add_argument("--json-out", type=Path, help="Grava o relatório JSON neste caminho")
    parser.add_argument("--json", action="store_true", help="Imprime JSON no stdout")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
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
    print(serialized if args.json else _human(report.to_dict(), reconciliation.to_dict()))
    return 0 if report.errors == 0 else 1
