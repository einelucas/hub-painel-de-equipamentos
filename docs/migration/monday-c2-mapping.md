# Mapeamento Monday C2 → Hub

Este catálogo descreve todos os campos encontrados nos headers reais de
`references/monday_exports/`. Todo valor, inclusive o classificado como `DESCARTAR`, continua no JSON
bruto do staging para auditoria.

As classes significam:

- `MIGRAR`: dado primário com destino conhecido;
- `TRANSFORMAR`: exige resolução de catálogo, relação ou enum;
- `DERIVAR`: deve ser calculado, não copiado como mirror/fórmula persistida;
- `DESCARTAR`: artefato estrutural/duplicado que não vira campo de domínio;
- `PENDENTE`: destino ou regra ainda depende de decisão humana.

## Equipamento (header principal)

| Campo Monday | Classe | Destino/conceito | Observação |
|---|---|---|---|
| Name | MIGRAR | `equipment.name` | Identidade por nome é apenas provisória. |
| Subelementos | DESCARTAR | relação `equipment.components` | Lista visual duplicada; filhos vêm das linhas Subitems. |
| Status Negociação | DERIVAR | serviço de prazo | Raw preservado; thresholds positivos pendentes. |
| F.Data Limite Negociação | DERIVAR | `MIN(component.negotiation_deadline)` | Cadeia confirmada nos dados. |
| Status Necessidade Obra | PENDENTE | futuro indicador | Fórmula exata não confirmada. |
| F.Limite Entrega Obra | DERIVAR | `MIN(component.delivery_deadline)` | Não persistir mirror. |
| A.Status | TRANSFORMAR | `equipment.current_stage` | Reconciliar também com o grupo/fase. |
| 0.Fornecedores | TRANSFORMAR | `equipment_supplier` | Connect Boards vira relação; cardinalidade pendente. |
| 0.Origem | MIGRAR | `equipment.origin` | Texto/status primário. |
| 0.Startup/Grãos | MIGRAR | `equipment.startup_at` | Datas específicas dos subitens são tratadas separadamente. |
| 0.Disciplina | TRANSFORMAR | `equipment.discipline_id` | Resolver por catálogo, sem criar automaticamente. |
| F.Data Limite para contrato/OC | DERIVAR | `MIN(component.contract_or_po_deadline)` | Não persistir fórmula. |
| 0.Criticidade | MIGRAR | `equipment.criticality` | Preserva rótulo observado; fórmula/taxonomia definitiva pendente. |
| E.Data de Entrega contrato | DERIVAR | contrato/componentes | Mirror; origem relacional deve prevalecer. |
| 0.Responsável | TRANSFORMAR | `equipment.responsible_user_id` | Exige mapa de identidade corporativa. |
| 0.Área | TRANSFORMAR | `equipment.area_id` | Resolver no contexto da unidade. |
| Work Package | TRANSFORMAR | relação com `work_package` | Staging usa lista; modelo final 1:N/N:N ainda pendente. |
| 1.Equalização | MIGRAR | `negotiation.equalized` | `v` normalizado somente neste campo booleano. |
| 2.Data da Negociação | MIGRAR | `negotiation.negotiated_at` | Data primária. |
| 3.Data de Abertura do Chamado | MIGRAR | `legal_process.opened_at` | Data primária. |
| 3.Chamado Jurídico | MIGRAR | `legal_process.ticket_number` | Mantido como string para não perder zeros/formato. |
| 3.Elab. Minuta | MIGRAR | `legal_process.draft_prepared` | Booleano. |
| 4.Minuta Aprovada | MIGRAR | `legal_process.draft_approved` | Booleano. |
| 5.Data Escrituração | MIGRAR | `contract.executed_at` | Cardinalidade ainda provisoriamente 1:1. |
| 5.Numero Contrato | MIGRAR | `contract.contract_number` | String; não inferir cardinalidade. |
| 5.Data de Entrega pelo contrato | MIGRAR | `contract.delivery_at` | Aderência negativa ainda pendente. |
| 6.Data de SC/OCI | MIGRAR | `purchase_request.requested_at` | Tipo SC/OCI deve ser resolvido sem inferência pelo número. |
| 6.Numero SC/OCI | MIGRAR | `purchase_request.request_number` | String. |
| 7.Data OC | MIGRAR | `purchase_order.ordered_at` | Data primária. |
| 7.Numero OC | MIGRAR | `purchase_order.order_number` | String. |
| E.Lead Time de Fabricação | DERIVAR | `MAX(component.lead_time_days)` | Mirror confirmado 41/41. |
| Espelho/Fórmula2 | DESCARTAR | cálculo de contrato/OC | Duplicata técnica; raw mantido. |
| E.Dias Antes do Startup | DERIVAR | `MAX(component.pre_start_days)` | Mirror confirmado 41/41. |
| ESPELHO-FORMULA-FRETE | DERIVAR | `MAX(component.freight_days)` | Mirror confirmado 41/41. |
| Kickoff | PENDENTE | futuro marco/evento | Não há campo de domínio confirmado. |
| Leadtime Negociação | DERIVAR | serviço de prazo | Fórmula final/uso operacional pendente. |
| Prazo Máximo Negociação | DERIVAR | serviço de prazo | Não persistir o resultado do Monday. |
| CAPEX Estimado | MIGRAR | `equipment.capex_estimated` | Decimal normalizado sem float binário. |

## Componente/Subitem (header Subitems)

| Campo Monday | Classe | Destino/conceito | Observação |
|---|---|---|---|
| Subitems | DESCARTAR | marcador estrutural | Identifica o início do header filho. |
| Name | MIGRAR | `equipment_component.name` | Subitem técnico; unidade de aquisição ainda não confirmada. |
| TAG | MIGRAR | `equipment_component.tag` | Vazio permanece nulo. |
| 0.Startup/Grãos | PENDENTE | startup do componente | Necessário às fórmulas, mas o modelo atual só possui startup no equipamento. |
| Data Limite de Entrega em Obra | DERIVAR | `startup - pre_start_days` | Relação confirmada 164/164. |
| Setor | MIGRAR | `equipment_component.sector` | Texto atual. |
| Prazo Neg | DERIVAR | `negotiation_deadline - reference_date` | Data-base deve ser explícita. |
| Data limite para contrato/OC | DERIVAR | `collection - lead_time_days` | Relação confirmada. |
| Lead Time de Fabricação | MIGRAR | `equipment_component.lead_time_days` | Inteiro não negativo. |
| Disponivel Coleta | DERIVAR | `delivery_deadline - freight_days` | Relação confirmada. |
| 0.Dias Antes do Startup | MIGRAR | `equipment_component.pre_start_days` | Inteiro não negativo. |
| Data de Entrega pelo contrato | MIGRAR | `equipment_component.contract_delivery_at` | Já existe no modelo atual. |
| Entrega planejada vs negociada | DERIVAR | margem em dias | `delivery_deadline - contract_delivery_at`. |
| Status da Data de Entrega | DERIVAR | indicador de aderência | Positivo→ATENDE observado; demais casos pendentes. |
| Arquivos | PENDENTE | futuro módulo de anexos | Nenhum download/cópia nesta etapa. |
| Frete (Dias) | MIGRAR | `equipment_component.freight_days` | Inteiro não negativo. |
| FÓRMULA-NÃO MEXER | DESCARTAR | fórmula técnica duplicada | Raw mantido; não vira coluna. |
| F.Data Limite Negociação_calc | DERIVAR | prazo de negociação | `contract_or_po_deadline - 21 dias`. |
| ID do elemento | MIGRAR | `external_mapping.external_id` | Identidade preferencial do subitem. |

## Tradução de conceitos

| Monday | Hub |
|---|---|
| Grupo + A.Status | `equipment.current_stage` + histórico/reconciliação |
| Subitem | `EquipmentComponent` por enquanto; `Acquisition` pendente |
| Connect Boards fornecedor | relação `equipment_supplier` |
| Mirror de prazo/fornecedor | JOIN, agregação SQL ou cálculo de serviço |
| Formula | função pura testada com dados primários e data-base explícita |
| Lista visual Subelementos | relação pai/filho, sem string duplicada |
| ID do elemento | identidade externa genérica e auditável |

As decisões de domínio ainda abertas, inclusive 163 versus 164 aquisições, estão centralizadas em
[`monday-import-architecture.md`](monday-import-architecture.md#decisões-ainda-pendentes).
