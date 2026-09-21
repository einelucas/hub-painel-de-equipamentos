# Etapa 6C.1 — Status Necessidade da Obra + Card de Situação de Prazos (GAP-015)

Data: 2026-09-21

Extensão pequena da Etapa 6C: mesma arquitetura de domínio único
(`app/domain/equipment_calculations.py`), sem tocar workflow, XLSX ou
reimportar dados.

## 1. Fórmula oficial recebida (implementada exatamente como especificada)

Data-base: `deliveryDeadline` (`F.Limite Entrega Obra`), já calculada em
`aggregate_component_deadlines` desde a Etapa 6B — **nenhuma fórmula nova de
data**, só a classificação por faixa de dias sobre um valor que já existia.

| Dias restantes (`deliveryDeadline - referenceDate`) | Resultado |
|---|---|
| `deliveryDeadline` ausente | `null` (nunca classificado artificialmente) |
| `< 0` | `CHECK_DELIVERY_FUP` (Checar entrega/FUP) |
| `0` | `NEEDED_TODAY` (Necessita hoje) |
| `1`–`29` | `LT_30_DAYS` (< 30 dias) |
| `30`–`59` | `LT_60_DAYS` (< 60 dias) |
| `60`–`89` | `LT_90_DAYS` (< 90 dias) |
| `>= 90` | `SAFE` (Prazo seguro) |

## 2. Implementação (domínio único)

`app/domain/equipment_calculations.py`:

- `WorkNeedStatus` (enum `str`): `CHECK_DELIVERY_FUP`, `NEEDED_TODAY`,
  `LT_30_DAYS`, `LT_60_DAYS`, `LT_90_DAYS`, `SAFE` — valor estável de
  domínio, nunca os emojis/rótulos do Monday (ex.: `"2. < 30 DIAS 🔥"`).
- `calculate_work_need_status(*, delivery_deadline, reference_date)` — nunca
  consulta o relógio; `reference_date` é sempre explícito.
- `component_deadline_values(...)` — novo helper extraído de
  `equipments/service.py` para o domínio, empacotando
  `calculate_component_deadlines` em `ComponentDeadlineValues`. É o único
  ponto de conversão campos-base-do-componente → prazos, e agora é usado
  **tanto** pelo detalhe/listagem de equipamento **quanto** pelo card do
  Dashboard — nenhum threshold duplicado entre as duas telas.

`app/modules/monday_import/calculations.py` (shim de compatibilidade):
`WorkNeedStatus`/`calculate_work_need_status` adicionados ao re-export.

### API — detalhe do equipamento

`EquipmentOut.calculated` ganhou dois campos, calculados em
`_equipment_calculated_out` (`equipments/service.py`) a partir do mesmo
agregado (`aggregates.min_delivery_deadline`) já usado por
`deliveryDeadline`:

- `workNeedDaysRemaining: number | null` — dinâmico, nunca persistido.
- `workNeedStatus: WorkNeedStatus | null` — `null` quando `deliveryDeadline`
  é `null`.

Proteção: `workNeedDaysRemaining`/`work_need_days_remaining`,
`workNeedStatus`/`work_need_status` adicionados ao conjunto de campos
calculados rejeitados em `EquipmentCreateIn`/`EquipmentUpdateIn` (422 se
enviado).

### API — Dashboard (`GET /api/v1/dashboard/summary`)

`DeadlinesSummaryOut` deixou de ser só `{available, reason}` e passou a
carregar a distribuição do recorte atual:

```jsonc
// Antes (Etapa 6B/6C)
{ "available": false, "reason": "Regras oficiais de prazo ainda não formalizadas pelo negócio." }

// Depois (Etapa 6C.1)
{
  "available": true,
  "reason": null,
  "total": 41,
  "withDeadline": 41,
  "withoutDeadline": 0,
  "checkDeliveryFup": 0,
  "neededToday": 0,
  "lt30Days": 1,
  "lt60Days": 0,
  "lt90Days": 0,
  "safe": 40
}
```

`available=false` fica reservado a um cenário técnico (o schema permanece
pronto, mas deixou de ser o caminho normal). Nova função
`_deadlines_summary` em `dashboard/service.py`: carrega os equipamentos do
recorte já filtrado (`scope`, o mesmo Subquery usado por todos os outros
blocos do summary — unidade/equipamento/permissões por unidade, sem
lógica nova de filtro), calcula `component_deadline_values` +
`aggregate_component_deadlines` + `calculate_work_need_status` por
equipamento (mesmas três funções de domínio do detalhe), e agrega por
contagem. Equipamento sem `deliveryDeadline` (sem componente, ou nenhum
componente com startup/pré-start preenchidos) entra em `withoutDeadline`,
nunca em `SAFE` ou qualquer outra categoria.

Invariantes garantidos (e testados): `withDeadline = checkDeliveryFup +
neededToday + lt30Days + lt60Days + lt90Days + safe`; `total = withDeadline
+ withoutDeadline`.

### Frontend

- `types/equipment.ts`: `WorkNeedStatus`, campos novos em
  `EquipmentCalculated`, `DeadlinesSummary` com a distribuição completa.
- `utils/workNeedStatus.ts` (novo, mesmo padrão de
  `utils/negotiationStatus.ts`): só rótulo em português + classe CSS por
  valor de enum já calculado pela API — **nenhum threshold recalculado no
  Vue**.
- `pages/equipamentos/[id].vue`: badge "Status necessidade da obra" em
  "Prazos e planejamento", ao lado de "Limite entrega em obra"
  (`data-testid="work-need-status-badge"`).
- `pages/dashboard/index.vue`: card "Situação de prazos" deixa de mostrar
  só o aviso "indicador aguardando regra oficial" e passa a listar as 6
  categorias, na ordem de urgência pedida (Checar entrega/FUP → Necessita
  hoje → < 30 dias → < 60 dias → < 90 dias → Prazo seguro), mais "Sem prazo
  calculável" com a contagem de `withoutDeadline`
  (`data-testid="deadlines-summary"`). Identidade visual preservada
  (mesmas classes `.info-card`/`.surface`, cores reaproveitadas de
  `negotiation-badge--*`). O caminho `available=false` continua existindo
  no template para o cenário técnico residual do schema.

## 3. Testes unitários (backend)

`tests/unit/test_work_need_status.py` (novo, 13 testes): tabela oficial
completa (`null`→`null`, `-1`→CHECK_DELIVERY_FUP, `0`→NEEDED_TODAY,
`1`/`29`→LT_30_DAYS, `30`/`59`→LT_60_DAYS, `60`/`89`→LT_90_DAYS,
`90`/`120`→SAFE), atraso extremo continua CHECK_DELIVERY_FUP, e teste
explícito provando que a função usa `reference_date` (não o relógio do
sistema): a mesma `deliveryDeadline` com duas `reference_date` diferentes
produz `LT_30_DAYS` e `SAFE`.

Suite completa do backend: **81/81 testes unitários passando** (68 antes
desta etapa + 13 novos).

## 4. Testes de integração do Dashboard

`tests/integration/test_dashboard_and_queues.py`:

- `test_summary_deadlines_are_not_calculated` (obsoleto, assumia
  `available=false` hardcoded) **substituído** por
  `test_summary_deadlines_card_is_active_with_real_distribution`.
- Novos: `test_summary_deadlines_categories_sum_to_with_deadline_and_total`
  (garante as duas invariantes pedidas),
  `test_summary_deadlines_without_deadline_is_never_classified_as_safe`,
  `test_summary_deadlines_respects_equipment_filter`,
  `test_summary_deadlines_respects_unit_scoping_and_permissions` (unidade
  sem acesso concedido devolve 404, mesmo padrão de
  `assert_unit_allowed`/`NotFoundError` já usado no resto da API).

Resultado real da primeira rodada (evidência, não assumido): `1 failed, 4
passed in 697.08s (11m37s)`. A falha não era do código de produção: o teste
`test_summary_deadlines_respects_unit_scoping_and_permissions` tentava criar
o equipamento da unidade **não autorizada** usando o usuário de teste
`ANALYST` (que só tem acesso à unidade `first`, concedido por
`_unit_with_context`/`grant_unit`) — `POST /equipments` corretamente devolveu
404 (`assert_unit_allowed`/`NotFoundError`), porque o próprio create já é
protegido por unidade. Teste corrigido para criar o equipamento de `second`
como `ADMIN` (acesso global por perfil, sem depender de vínculo) — o
create em si não fazia parte do que o teste queria provar. Resultado após a
correção:

```
5 passed in <tempo> (rodada de reexecução isolada)
```

## 5. Regressão C2 (41 equipamentos reais, DEV, somente leitura)

Comparação entre o Status Necessidade da Obra calculado agora e o valor que
o Monday tinha registrado no momento da migração
(`work_need_status_observed`, staged em `monday_import_record` desde a
MIG-001.1 — não foi tocado, só lido). Valores reais observados: `5. PRAZO
SEGURO 🟢` (40×), `2. < 30 DIAS 🔥` (1×, equipamento "Caldeira de Biomassa").

```
Comparáveis: 41/41
NOT_COMPARABLE: 0
MATCH exato: 41
Divergência esperada por passagem de tempo: 0
MISMATCH real: 0 []

Distribuição real do card Dashboard para o C2:
  CHECK_DELIVERY_FUP = 0
  NEEDED_TODAY       = 0
  LT_30_DAYS         = 1
  LT_60_DAYS         = 0
  LT_90_DAYS         = 0
  SAFE               = 40
  WITHOUT_DEADLINE   = 0
with_deadline=41 without_deadline=0 total=41
```

**41/41 MATCH exato**, nenhuma fórmula foi ajustada para "fazer bater". Essa
distribuição é dinâmica (depende de `reference_date = hoje`) — vai
naturalmente mudar conforme os prazos avançam; o card sempre reflete o
estado real do momento da consulta, nunca um snapshot congelado.

## 6. Pendência da Etapa 6C confirmada com evidência real

O teste de integração `test_negotiation_status_routes.py` (GAP-014, Etapa
6C), que estava rodando em segundo plano por causa da lentidão do banco de
teste neste ambiente sandboxed, **terminou**: `4 passed in 560.07s
(9m20s)`, exit code 0. Não é um resultado assumido — evidência coletada do
processo real.

## 7. Não implementado nesta etapa (por instrução explícita)

Histórico de migração, novos filtros gerais, permissão departamental,
atalho 2→4, bypass de Suprimentos, reabertura, conclusão alternativa 7→8,
notificações, e-mail, anexos, comentários, Kanban, Saved Views, ERP —
nenhum destes foi tocado.

## Baseline DEV — confirmada intacta

```
Equipment: 41
EquipmentComponent: 164
equipment_work_package: 71
```

Nenhum dado do C2 foi criado, alterado ou removido nesta etapa. Os scripts
de verificação (`inspect_work_need_status_observed.py`,
`verify_work_need_status_c2_regression.py`) são somente leitura contra DEV.
