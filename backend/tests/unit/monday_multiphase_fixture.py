"""Layout de board Monday exportado POR FASE: 49 colunas principais + 18 de subitem.

Reproduz só a ESTRUTURA do layout (nomes de coluna, títulos de grupo, rótulos de
status). Todos os valores são sintéticos: nomes "Sintético", códigos e datas
inventados. Nenhum registro, nome, fornecedor, documento ou ID de obra real.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from tests.unit.monday_xlsx_fixture import build_xlsx

MAIN_HEADERS = (
    "Name",
    "Subelementos",
    "A.Status",
    "0.Área",
    "0.Responsável",
    "0.Disciplina",
    "0.Origem",
    "0.Criticidade",
    "0.Startup/Grãos",
    "1.Equalização",
    "2.Data da Negociação",
    "3.Data de Abertura do Chamado",
    "3.Elab. Minuta",
    "3.Num Cham Juridico",
    "4.Minuta Aprovada",
    "5.Data Escrituração",
    "5.Data de Entrega pelo contrato",
    "5.Numero Contrato",
    "6.Bypass Suprimentos",
    "6.Data de SC/OCI",
    "6.Numero SC/OCI",
    "7.Data OC",
    "7.Numero OC",
    "A.Retomar Negociação",
    "A.Tempo Contrato",
    "A.Tempo Negociação",
    "Conferência",
    "Contador Neg Concluido",
    "Contador de OC",
    "Cód. Forn. CS",
    "DataLimiteNegociação Mês/Ano",
    "Diferença Negociação",
    "E.Data de Entrega contrato",
    "E.Dias Antes do Startup",
    "E.Lead Time de Fabricação",
    "ESPELHO-FORMULA",
    "Espelho/Fórmula2",
    "F.Contador Júridico",
    "F.Data Limite Negociação",
    "F.Data Limite para contrato/OC",
    "F.Limite Entrega Obra",
    "Pessoas",
    "Prazo Neg (dias)",
    "Projeto",
    "S.Escalonamento",
    "Status Necessidade Obra",
    "Status Prazo Negociação",
    "Status de Prazo",
    "Unidade",
)
SUB_HEADERS = (
    "Subitems",
    "Name",
    "TAG",
    "0.Startup/Grãos",
    "Data Limite de Entrega em Obra",
    "Setor",
    "Prazo",
    "Data limite para contrato/OC",
    "Lead Time de Fabricação",
    "Disponivel Coleta",
    "0.Dias Antes do Startup",
    "Data de Entrega pelo contrato",
    "Entrega planejada vs negociada",
    "Status da Data de Entrega",
    "Arquivos",
    "Frete (Dias)",
    "FÓRMULA-NÃO MEXER",
    "F.Data Limite Negociação_calc",
)

# Grupos ocupados no board; fases 2, 4 e 5 vazias não têm arquivo exportado.
PHASE_GROUPS = {
    0: "Fase 0 - Nova Demanda",
    1: "Fase 1 - Negociação",
    3: "Fase 3 - Abertura do Chamado",
    6: "Fase 6 - SC ou OCI",
    7: "Fase 7 - Aprovação da OC",
    8: "Fase 8 - Concluído",
}
PHASE_STATUS = {
    0: "0.Nova demanda",
    1: "1.Negociação",
    3: "3.Abertura do chamado",
    6: "6.SC ou OCI",
    7: "7.Aprovação da OC",
    8: "8.Concluído",
}
STANDBY_STATUS = "9.Em Definição/Standby"
BOARD_TITLE = "Equipamentos Obra Sintética"


@dataclass(slots=True)
class SynthEquipment:
    name: str
    location: str | None = "2303 - Sistema Sintético"
    status: str | None = None  # None = rótulo padrão da fase
    components: tuple[str, ...] = ("Componente Sintético 1",)
    values: dict[str, Any] = field(default_factory=dict)  # cabeçalho -> valor sobrescrito


def _main_row(equipment: SynthEquipment, phase: int, headers: tuple[str, ...]) -> list[Any]:
    defaults: dict[str, Any] = {
        "Name": equipment.name,
        "Subelementos": ", ".join(equipment.components),
        "A.Status": equipment.status or PHASE_STATUS[phase],
        "0.Área": equipment.location,
        "0.Responsável": "Responsável Sintético",
        "0.Disciplina": "Disciplina Sintética",
        "0.Origem": "Origem Sintética",
        "0.Criticidade": "Média",
        "0.Startup/Grãos": "2027/10/27",
        "Status Prazo Negociação": "✅NO PRAZO✅",
        "Status Necessidade Obra": "Status Sintético",
        "Cód. Forn. CS": "99001",
        "F.Data Limite Negociação": "2027/01/10",
        "F.Data Limite para contrato/OC": "2027/02/10",
        "F.Limite Entrega Obra": "2027/09/01",
        "E.Dias Antes do Startup": 10,
        "E.Lead Time de Fabricação": 30,
        "Espelho/Fórmula2": 0,
        # auxiliares do Monday (IGNORED_BY_PROFILE)
        "6.Bypass Suprimentos": "Click me",
        "A.Retomar Negociação": "Voltar",
        "ESPELHO-FORMULA": "5, 7",
        "Prazo Neg (dias)": 10,
        "Projeto": "Obra Sintética",
        "Unidade": "Unidade Sintética",
        "Contador de OC": 0,
        "Contador Neg Concluido": 0,
        "DataLimiteNegociação Mês/Ano": "2027-01",
        "Diferença Negociação": 0,
    }
    defaults.update(equipment.values)
    return [defaults.get(header) for header in headers]


def _sub_row(name: str, index: int, headers: tuple[str, ...]) -> list[Any]:
    values: dict[str, Any] = {
        "Name": name,
        "TAG": f"TAG-SINT-{index}",
        "0.Startup/Grãos": "2027/10/27",
        "Data Limite de Entrega em Obra": "2027/09/01",
        "Setor": "Setor Sintético",
        "Prazo": 30,
        "Data limite para contrato/OC": "2027/02/10",
        "Lead Time de Fabricação": 30,
        "Disponivel Coleta": "2027/08/27",
        "0.Dias Antes do Startup": 10,
        "Frete (Dias)": 5,
        "F.Data Limite Negociação_calc": "2027/01/10",
    }
    return [values.get(header) for header in headers]


def phase_board(
    phase: int,
    equipments: list[SynthEquipment],
    *,
    extra_main_headers: tuple[str, ...] = (),
) -> bytes:
    """Um XLSX = um grupo de fase ocupado (como o Monday exporta por grupo)."""
    main_headers = MAIN_HEADERS + extra_main_headers
    rows: list[list[Any]] = [[BOARD_TITLE], [PHASE_GROUPS[phase]], list(main_headers)]
    for equipment in equipments:
        rows.append(_main_row(equipment, phase, main_headers))
        rows.append(list(SUB_HEADERS))
        rows.extend(_sub_row(name, index, SUB_HEADERS) for index, name in enumerate(equipment.components, 1))
    return build_xlsx(rows)


def multiphase_boards() -> dict[int, bytes]:
    """Seis arquivos (fases 0, 1, 3, 6, 7, 8), um equipamento sintético por fase,
    mais um em Standby no grupo da Fase 0."""
    boards: dict[int, bytes] = {}
    for phase in PHASE_GROUPS:
        equipments = [SynthEquipment(name=f"Equipamento Sintético F{phase}")]
        if phase == 0:
            equipments.append(SynthEquipment(name="Equipamento Sintético Standby", status=STANDBY_STATUS))
        boards[phase] = phase_board(phase, equipments)
    return boards
