"""Relatório Markdown da reconciliação EAP (gerado a partir do JSON, determinístico)."""

from __future__ import annotations

from typing import Any


def _cell(value: Any) -> str:
    if value is None or value == "":
        return "—"
    return str(value).replace("|", "\\|")


def render_markdown(report: dict[str, Any]) -> str:
    m = report["metrics"]
    lines = [
        f"# Reconciliação EAP — {report['project']} (dry run)",
        "",
        "> Relatório READ-ONLY gerado por `python -m app.modules.eap_reconciliation analyze`.",
        "> Nenhum vínculo foi gravado. MATCH é candidato a vínculo futuro, não decisão aplicada.",
        "",
        "## Fontes",
        "",
        f"- Catálogo EAP: `{report['catalog']['source']}` (catálogo SHA-256 `{report['catalog']['sha256']}`)",
    ]
    for alias in report.get("approved_aliases", []):
        lines.append(
            f"- Alias EAP aprovado (`app/data/eap_aliases.json`): `{alias['alias']}` → "
            f"`{alias['eapCode']}` — {alias['decision']}"
        )
    for source in report["sources"]:
        lines.append(
            f"- Export Monday: `{source['file']}` — {source['equipments']} equipamentos, "
            f"{source['components']} subitens (SHA-256 `{source['sha256'][:16]}…`)"
        )
    aux = report.get("auxiliary_exports")
    if aux:
        lines.append(
            f"- Exports auxiliares conferidos (não somados): {', '.join(f'`{a}`' for a in aux['files'])} — "
            f"{aux['equipments']} equipamentos, todos contidos nos canônicos: "
            f"{'sim' if aux['subset_of_canonical'] else 'NÃO'}; mesma área: "
            f"{'sim' if aux['same_area'] else 'NÃO'}"
        )
    lines += [
        "- Campo de EAP: `0.Área` → `normalized.area_name` do importador Monday "
        "(mesmo valor usado no apply).",
        "- Identidade: `source_key` do importador (= `external_mapping.external_id`).",
        "",
        "## Resumo",
        "",
        "| Métrica | Valor |",
        "|---|---|",
    ]
    lines += [f"| `{key}` | {value} |" for key, value in m.items()]
    lines += [
        "",
        f"**Matches seguros (`auto_match_safe_total`): {m['auto_match_safe_total']} "
        f"de {m['total_equipment']}.** "
        "REVIEW não conta como match.",
        "",
        "## Prefixos observados",
        "",
        "O prefixo esperado do projeto é desconhecido (não configurado), então não há "
        "`EAP_PREFIX_MISMATCH`: o prefixo encontrado é só evidência (`OBSERVED_EAP_PREFIX`).",
        "",
        "| Prefixo | Ocorrências | Equipamentos |",
        "|---|---|---|",
    ]
    for item in report["observed_prefixes"]:
        lines.append(f"| `{item['prefix']}` | {item['occurrences']} | {', '.join(item['equipments'])} |")
    if not report["observed_prefixes"]:
        lines.append("| — | 0 | — |")
    lines += [
        "",
        f"Consistente em todo o projeto: {'sim' if report['prefix_consistent'] else 'NÃO'}. "
        "Evidência apenas — não autoriza gravar `ProjectContext.eap_prefix`.",
        "",
    ]

    def table(category: str, title: str, columns: list[tuple[str, str]]) -> None:
        rows = [r for r in report["records"] if r["category"] == category]
        lines.extend([f"## {title} ({len(rows)})", ""])
        if not rows:
            lines.extend(["Nenhum.", ""])
            return
        lines.append("| " + " | ".join(label for label, _ in columns) + " |")
        lines.append("|" + "---|" * len(columns))
        for row in rows:
            lines.append("| " + " | ".join(_cell(row.get(key)) for _, key in columns) + " |")
        lines.append("")

    table(
        "MATCH",
        "Matches seguros",
        [
            ("Equipamento", "equipmentName"),
            ("Valor Monday", "rawEapValue"),
            ("Prefixo observado", "observedPrefix"),
            ("EAP oficial", "matchedEapCode"),
            ("Nome oficial", "matchedEapName"),
            ("Status", "status"),
        ],
    )
    table(
        "REVIEW",
        "Revisão humana necessária",
        [
            ("Equipamento", "equipmentName"),
            ("Valor Monday", "rawEapValue"),
            ("Status", "status"),
            ("Motivo / decisão necessária", "reason"),
        ],
    )
    table(
        "UNRESOLVED",
        "Não resolvidos",
        [
            ("Equipamento", "equipmentName"),
            ("Valor bruto", "rawEapValue"),
            ("Status", "status"),
            ("Motivo", "reason"),
        ],
    )
    lines += ["## Múltiplas EAP", ""]
    if report["multiple_eap_equipments"]:
        lines += [f"- {name}" for name in report["multiple_eap_equipments"]]
    else:
        lines.append(
            "Nenhum equipamento com mais de uma EAP. Para este projeto, o `equipment.eap_node_id` "
            "singular é suficiente."
        )
    lines += [
        "",
        "## EAPs candidatas a ProjectEap (não gravadas)",
        "",
        "Somente códigos de matches seguros: "
        + (", ".join(f"`{code}`" for code in report["candidate_project_eap_codes"]) or "nenhum")
        + ".",
        "",
    ]
    db = report.get("database_comparison")
    lines += ["## Comparação com o banco (somente leitura)", ""]
    if db is None:
        lines.append("Não executada nesta geração (`--compare-db` não informado).")
    else:
        lines += [
            f"- Banco: `{db['database']}` (alembic `{db['alembicRevision']}`); contextos: "
            f"{', '.join(db['contexts']) or '—'}",
            f"- Equipment no banco: {db['equipmentTotal']}; com mapping Monday: {db['mappedEquipments']}",
            f"- Export ↔ banco pela identidade externa: {db['matchedExportAndDatabase']} encontrados",
            f"- Export sem Equipment: {len(db['exportWithoutEquipment'])} "
            f"{db['exportWithoutEquipment'] or ''}",
            f"- Equipment sem fonte no export: {len(db['equipmentWithoutExport'])} "
            f"{db['equipmentWithoutExport'] or ''}",
            f"- Equipment sem mapping: {len(db['equipmentWithoutMapping'])}; "
            f"identidades duplicadas: {len(db['duplicateExternalIds'])}",
            "",
            "Área legada (`equipment.area_id`) × EAP reconciliada (não sincronizado):",
            "",
            "| Comparação | Equipamentos |",
            "|---|---|",
        ]
        lines += [f"| `{key}` | {value} |" for key, value in db["legacyAreaVsEap"].items()]
        different = [
            r
            for r in report["records"]
            if (r.get("database") or {}).get("legacyAreaVsEap") == "DIFFERENT_NAME"
        ]
        if different:
            lines += ["", "Diferenças de nome (área legada × EAP oficial):", ""]
            lines += [
                f"- {r['equipmentName']}: área `{r['database']['legacyAreaName']}` × "
                f"EAP `{r['matchedEapCode']} {r['matchedEapName']}`"
                for r in different
            ]
    lines.append("")
    return "\n".join(lines)
