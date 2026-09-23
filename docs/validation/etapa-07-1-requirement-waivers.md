# Etapa 7.1 — Dispensa de Requisitos por Fase (RequirementWaiver)

Data: 2026-09-23

Substitui o mecanismo de exceções de fluxo rígidas da Etapa 7B
(`WorkflowException`, tipos `FIXED_SUPPLIER`/`IMPORTATION`, destino fixo por
tipo) por um mecanismo flexível de **dispensa por grupo de requisitos**
(`RequirementWaiver`), conforme decisão de negócio registrada nesta etapa: o
equipamento sempre continua passando manualmente por todas as fases; não
existe mais salto automático nem uma tabela rígida "tipo de compra →
requisitos ignorados"; quando uma informação realmente não existe para
aquela aquisição, o usuário marca aquele **grupo de requisitos** como "Não
possui", com motivo + justificativa obrigatórios e decisão auditável.

Dashboard, Kanban, comentários, recorrência de FUP, agendamento de Kickoff,
integração Microsoft, storage de produção, Saved Views, dados reais do C2 e
fórmulas de prazo **não foram tocados**.

Baseline C2 confirmada intacta após a migração desta etapa: **41 Equipment /
164 EquipmentComponent / 71 EquipmentWorkPackage**.

---

## 1. Modelo antigo (Etapa 7B) — o que existia

`WorkflowException` (`app/models/workflow_extras.py`): tipo fixo
(`FIXED_SUPPLIER`/`IMPORTATION`), cada tipo com uma tabela rígida no código
(`EXCEPTION_DISPENSED_REQUIREMENT_CODES`, em `workflow/stages.py`) mapeando
tipo → conjunto fixo de códigos de requisito individuais (por campo, não por
grupo) dispensados enquanto a exceção estivesse `ACTIVE`. Destino
(`intended_target_stage`) fixo por tipo (5 para `FIXED_SUPPLIER`, 7 para
`IMPORTATION`), não escolhido pelo usuário. Só uma exceção ativa por
equipamento (não por fase) — não era possível dispensar dois grupos de
fases diferentes ao mesmo tempo com motivos diferentes.

**Registros reais verificados antes de alterar**: consultado
`SELECT * FROM workflow_exception` em **DEV** (`neondb`) — **0 registros**.
TEST (`neondb_test`) tinha só dados fictícios de scripts de verificação
descartáveis desta sessão, sem valor histórico. Como não há nenhum registro
real em produção, o mecanismo foi **deprecado** (não migrado
automaticamente): a tabela `workflow_exception` e o model SQLAlchemy
`WorkflowException` continuam existindo no schema só por compatibilidade —
nenhum código novo depende deles, nenhum endpoint os expõe mais. Isso
evita uma migração destrutiva desnecessária sobre uma tabela vazia.

Arquivo **removido**: `app/modules/workflow/exceptions.py` (service). Rotas
removidas de `app/modules/workflow/router.py`:
`GET/POST /equipments/{id}/workflow-exceptions`,
`POST /equipments/{id}/workflow-exceptions/{id}/cancel`. Schemas
`WorkflowException*` removidos de `workflow/schemas.py`.

---

## 2. Modelo novo — RequirementWaiver

`app/models/workflow_extras.py::RequirementWaiver`:

| Campo | Tipo | Observação |
|---|---|---|
| `id` | uuid | |
| `equipment_id` | FK | |
| `stage` | int (0-8) | fase à qual o grupo pertence |
| `requirement_group_code` | string(40) | validado contra os grupos conhecidos pelo backend |
| `reason_code` | string(20) | `IMPORTATION`/`FIXED_SUPPLIER`/`EXCEPTIONAL_PROCESS`/`OTHER` — **só classificação/auditoria**, nunca determina o que é dispensado |
| `justification` | text, obrigatório | `CheckConstraint` garante não-vazio |
| `status` | `ACTIVE`/`REVOKED` | nunca apagado — revogar é um novo estado |
| `created_by_id` / `created_at` | | |
| `revoked_by_id` / `revoked_at` / `revoke_reason` | nullable | preenchidos só na revogação |

Índice único parcial `requirement_waiver_one_active_key` em
`(equipment_id, stage, requirement_group_code)` `WHERE status='ACTIVE'` —
só uma dispensa ativa por combinação equipamento+fase+grupo.

**Migração**: `alembic/versions/0009_requirement_waivers.py`, aplicada em
DEV e TEST separadamente (confirmado via `alembic current` mostrando
`head` nos dois bancos).

---

## 3. Grupos dispensáveis (fonte de verdade: backend)

`app/modules/workflow/stages.py::GROUPS_BY_STAGE` / `COMPLETION_GROUPS` —
o backend é a **única** fonte de verdade sobre quais grupos existem, a
qual fase pertencem e se são dispensáveis. Não existe endpoint que aceite
dispensar uma string arbitrária: `create_waiver` valida
`group_spec(code)` (existe?) e `is_waivable_group(stage, code)` (é
dispensável E pertence exatamente a essa fase?).

| Fase (`from_stage`) | Grupo | Campos | Dispensável |
|---|---|---|---|
| 1 | `NEGOTIATION_EQUALIZATION` | `negotiation.equalized` | Sim |
| 2 | `COMMERCIAL_NEGOTIATION` | `negotiation.negotiatedAt` | Sim |
| 3 | `LEGAL_TICKET` | `legal.openedAt` + `legal.ticketNumber` | Sim |
| 4 | `LEGAL_DRAFT` | `legal.draftPrepared` + `legal.draftApproved` | Sim |
| 5 | `CONTRACT` | número + data de escrituração + arquivo, **no mesmo contrato** | Sim |
| 6 | `PURCHASE_REQUEST` | tipo + número + data, **na mesma SC/OCI** | Sim |
| 7 → 8 (conclusão) | `SUPPLIER` | fornecedor vinculado | **Não** |
| 7 → 8 (conclusão) | `PURCHASE_ORDER` | número + data + valor, **na mesma OC** | **Não** |
| 7 → 8 (conclusão) | `PROJECT_TOTAL_VALUE` | Valor Total do Projeto | **Não** |

Os três grupos de conclusão nunca aceitam dispensa (backend rejeita com
422 se `stage=7` for tentado) — fornecedor, OC e valor total continuam
sempre obrigatórios, e a passagem efetiva pela fase 7 continua garantida
pela própria state machine (só avança uma fase por vez).

---

## 4. Motor de validação

`app/modules/workflow/service.py::_evaluate` — para cada grupo da fase:

1. `spec.check(state)` → `True` → **SATISFIED**.
2. `False`, mas existe `RequirementWaiver` `ACTIVE` para
   `(equipment_id, stage, group.code)` → **WAIVED**.
3. Caso contrário → **MISSING** (bloqueia o avanço).

A transição só é permitida quando **todos** os grupos da fase estão
`SATISFIED` ou `WAIVED`. Nenhum `force=true` genérico — o motor sempre
consulta o banco de dispensas reais, nunca aceita um parâmetro que
"força" a validação.

---

## 5. Correção das validações 1:N (seção 4 da especificação)

Antes (Etapa 7A): um requisito 1:N contava como satisfeito se **qualquer**
registro tivesse o campo preenchido — permitindo, por exemplo, satisfazer
"número do contrato" com um contrato e "data de escrituração" com outro
contrato diferente.

Agora (`_any_complete`, em `stages.py`): o grupo só fica `SATISFIED` quando
existe **um único registro** com **todos** os campos exigidos preenchidos:

- `CONTRACT`: `contract_number` + `executed_at` + `file_storage_key` no
  mesmo `Contract`.
- `PURCHASE_REQUEST`: `kind` + `request_number` + `requested_at` na mesma
  `PurchaseRequest`.
- `PURCHASE_ORDER` (conclusão): `order_number` + `ordered_at` + `amount`
  na mesma `PurchaseOrder`.

Isso é uma correção de comportamento sobre a Etapa 7A, exigida
explicitamente por esta etapa. **Impacto**: o fluxo normal de teste
(`_advance` em `tests/integration/test_workflow_routes.py` e
`test_dashboard_and_queues.py`) precisou passar a fazer upload de um
arquivo de contrato (antes não fazia) para satisfazer o grupo `CONTRACT`
sem dispensa — ajustado nos dois arquivos de teste.

---

## 6. Endpoints (API)

Todos sob `app/modules/workflow/router.py`, gate de permissão
`workflow:transition` (mesmo grupo Engenharia/Planejamento que já edita o
processo — nenhuma permissão nova):

- `GET /equipments/{id}/requirement-waivers` — lista (leitura:
  `workflow:read`, inclui Jurídico/Suprimentos).
- `POST /equipments/{id}/requirement-waivers` — cria. Valida: equipamento
  acessível (escopo por unidade), `stage` 0-8, `requirement_group_code`
  conhecido, grupo dispensável **e** correspondente à fase informada,
  `reason_code` num dos 4 valores conhecidos, `justification` não vazia
  (Pydantic `min_length=1` + checagem de serviço), sem dispensa `ACTIVE`
  duplicada (409 se houver).
- `POST /equipments/{id}/requirement-waivers/{waiver_id}/revoke` — marca
  `REVOKED`, registra `revoked_by`/`revoked_at`/`revoke_reason`; rejeita
  revogar uma dispensa que já não está `ACTIVE`.

`GET /equipments/{id}/available-transitions` — `TransitionOptionOut` agora
tem `requirement_groups: RequirementGroupOut[]` (substitui
`requirements`/`satisfied_requirements`/`missing_requirements`, por
campo). Cada grupo: `code`, `label`, `status`
(`SATISFIED`/`WAIVED`/`MISSING`), `waivable`, `fields`, `message`,
`waiver` (objeto completo quando `WAIVED`). O frontend nunca reconstrói a
regra localmente — só reflete o que o backend calculou.

Filas (`GET /queues/engineering|legal|procurement`) também respeitam
dispensas ativas: `queues/service.py::_bulk_waived_groups` garante que um
grupo dispensado não apareça mais como "pendente" na fila, mesma fonte de
verdade do detalhe do equipamento.

---

## 7. Frontend

`frontend/components/equipment/WorkflowRequirements.vue` — reescrito para
renderizar por **grupo** (não mais por campo individual). A ação "Não
possui {grupo}" aparece **junto do requisito**, na aba Processo — não
existe mais tela/botão global de "Exceção de fluxo". Componente
autocontido (chama a API diretamente, como `EquipmentSuppliers.vue`):

- Grupo `MISSING` + `waivable` + permissão → botão "Não possui X" abre
  modal (Motivo * / Justificativa * / aviso "não pula a fase, dados
  preservados").
- Grupo `WAIVED` → mostra motivo + autor + data, "Ver justificativa"
  (expande texto completo) e "Revogar dispensa" (só com permissão).
- Emite `changed` → a página recarrega `workflow.load()`.

`frontend/pages/equipamentos/[id].vue`: removido o botão/painel/modal de
"Abrir exceção de fluxo"; `EquipmentWorkflowStepper`'s
`next-stage-blocked` agora deriva de
`requirementGroups.some(g => g.status === 'MISSING')`.

`useEquipmentWorkflow.ts`: removidos `exceptions`/`activeException`/
`createException`/`cancelException`; adicionados `createWaiver`/
`revokeWaiver` (usados apenas como referência — o componente
`WorkflowRequirements` chama a API diretamente para ficar autocontido).

Tipos (`types/equipment.ts`): `WorkflowException*` removidos;
`RequirementWaiver`, `RequirementGroup`, `RequirementGroupStatus`,
`RequirementWaiverReasonCode` adicionados; `TransitionOption` usa
`requirementGroups` no lugar de `requirements`/`satisfiedRequirements`/
`missingRequirements`.

---

## 8. Reabertura

Nenhuma mudança de código foi necessária: `ReopenRequest` já move só
`current_stage`, nunca toca em `RequirementWaiver`. Como a dispensa é
indexada por `(equipment_id, stage, group_code)` e nunca é apagada nem
recalculada por transição, uma dispensa `ACTIVE` de uma fase sobrevive
naturalmente a qualquer reabertura para aquela fase — confirmado por
`test_reopen_approval_preserves_active_waiver`.

---

## 9. Histórico

`workflow/service.py::history` — eventos `requirementwaiver.create`/
`requirementwaiver.revoke` (gravados como `AuditLog` pelo serviço de
waivers) ganham tratamento especial na linha do tempo: título com o
código do grupo entre parênteses (ex.: "Requisito marcado como
dispensado (CONTRACT)") e o campo `justification` do
`HistoryEntryOut` populado a partir do `AuditLog.newData` (mesma vitrine
já usada por Standby/Cancelado/Saneamento) — nunca precisa abrir o JSON
bruto para ler o motivo. Não é misturado com Comentários nem duplicado
como `WorkflowTransition`.

---

## 10. Permissões

Sem permissão nova: criar/revogar dispensa usa `workflow:transition`
(mesmo grupo Engenharia/Planejamento de sempre); ler usa `workflow:read`
(inclui Jurídico/Suprimentos, só consulta). Nenhum nome de departamento
hardcoded no frontend — `WorkflowRequirements.vue` só consulta
`auth.can('workflow:transition')`, devolvido pelo backend.

---

## 11. Testes executados

### 11.1 Lint/tipos

- `ruff check app/` — limpo.
- `mypy app/` — limpo, exceto 1 erro pré-existente não relacionado
  (`dashboard/service.py`, Dashboard congelado nesta etapa).
- Frontend: `eslint`, `vue-tsc --noEmit`, `vitest run` (**103/103**),
  `nuxt build` — todos verdes.

### 11.2 Verificação funcional direta (script, banco TEST, dados
descartáveis — `scripts/verify_etapa7_1_requirement_waivers.py`)

Todos os 10 cenários passaram: grupo incompleto sem waiver → MISSING
bloqueia avanço; grupo não dispensável (`SUPPLIER`, fase 7) rejeita
criação; justificativa vazia rejeitada; waiver criado → grupo WAIVED;
segunda dispensa ativa simultânea rejeitada (409); waiver permite avançar
só 1 fase (salto continua bloqueado); revogação registrada
(`status=REVOKED`, `revoked_by` preenchido); revogar dispensa já revogada
rejeitado; contrato parcial (só número) continua `MISSING` mesmo com
outro contrato tendo os demais campos; contrato completo no mesmo
registro → `SATISFIED`.

### 11.3 Suíte pytest (HTTP, `tests/integration/test_operational_business_rules.py`
+ ajustes em `test_workflow_routes.py`/`test_dashboard_and_queues.py`)

19 cenários cobertos (novos + ajustados), incluindo: Standby/Cancelado/
Saneamento (já existentes, sem mudança de comportamento); dispensa de
`NEGOTIATION_EQUALIZATION` (validações de fase/grupo/justificativa,
duplicata, revogação, não-pular-fase); dispensa de `CONTRACT`/
`PURCHASE_REQUEST` levando até a fase 7 sem dado real, com os campos
continuando opcionalmente preenchíveis; reabertura com aprovação;
fornecedor único; cardinalidade 1:N; conclusão da fase 8 (fornecedor + OC
+ valor total, nenhum dispensável); comentários; Kickoff/FUP; grupo
`SATISFIED` quando dado completo; dispensa nunca apaga dado parcial
existente; SC/OCI exige tipo+número+data no mesmo registro; reabertura
preserva waiver ativo; permissões de leitura/escrita; histórico registra
criação/revogação com justificativa legível.

**Execução real**: ver seção "Resultado da suíte" abaixo — preenchida
após a rodada em segundo plano desta sessão (o TEST DB do Neon esteve com
latência anormal ao longo de toda a Etapa 7/7.1; a suíte roda mais devagar
que o normal, mas as falhas anteriores observadas nesta sessão foram todas
de infraestrutura — `ConnectionDoesNotExistError` em arquivo não
relacionado — não de asserção).

### 11.4 Baseline C2

`scripts/audit_c2_db.py` (DEV, read-only) rodado após a migração `0009`:
**41 Equipment / 164 EquipmentComponent / 71 EquipmentWorkPackage** —
intacto.

---

## 12. Registros legacy encontrados

`WorkflowException` em DEV: **0 registros**. Nenhuma migração/conversão
automática foi necessária — mecanismo deprecado sem perda de dado real
(ver seção 1).

---

## 13. Pendências

- Suíte pytest completa (todos os arquivos de integração) não pôde ser
  confirmada até o fim nesta sessão por instabilidade do Neon TEST —
  mesma pendência já registrada em `etapa-07-operational-business-rules.md`.
  Recomenda-se reexecutar `pytest tests/integration -q` numa janela de
  latência normal.
- Hierarquia corporativa real para `workflow:reopen_approve` — pendência
  herdada da Etapa 7C, não afetada por esta etapa.
