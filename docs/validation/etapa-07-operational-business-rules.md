# Etapa 7 — Consolidação do Modelo Operacional e Regras de Negócio

Data: 2026-09-22 / 2026-09-23

Blocos 7A→7G implementados e verificados nesta sessão. 7H (este documento)
registra testes executados, resultado real, reconciliação de baseline e
pendências. Dashboard **não foi tocado** — nenhuma mudança funcional ou
visual, conforme exigido.

Baseline C2 confirmada intacta em múltiplos pontos da sessão (após 0007,
após 0008, e ao final): **41 Equipment / 164 EquipmentComponent / 71
EquipmentWorkPackage**.

---

## 1. Arquitetura implementada (visão geral)

Separação explícita entre **fase do processo** (`Equipment.current_stage`,
0–8, mecanismo inalterado: `WorkflowTransition` + `execute_transition`) e
**estado operacional** (`Equipment.operational_status`: `ACTIVE` / `STANDBY`
/ `CANCELLED` / `IN_SANITATION`, mecanismo novo: `OperationalStatusEvent`).
As duas trilhas de auditoria nunca se misturam: uma mudança de estado
operacional nunca fabrica uma `WorkflowTransition` (exceto a própria
mudança real de `current_stage`, que ocorre só no caso do Saneamento —
reset para fase 0 — e é registrada no próprio `OperationalStatusEvent`, não
como transição de fluxo).

Novos módulos backend:

| Módulo | Responsabilidade |
|---|---|
| `app/modules/workflow/operational_status.py` | Standby/Cancelado/Saneamento (entrar/sair) |
| `app/modules/workflow/exceptions.py` | Exceções de fluxo (FIXED_SUPPLIER/IMPORTATION) |
| `app/modules/workflow/reopen.py` | Reabertura com aprovação (`ReopenRequest`) |
| `app/modules/comments/` | Comentários do equipamento (schemas/service/router) |
| `app/modules/notifications/` | Kickoff/FUP (adapter/service/schemas/router) |
| `app/core/storage.py` | Abstração de storage para arquivo de contrato |

---

## 2. Migrações

- **`0007_operational_business_rules`**: colunas novas em `equipment`
  (`operational_status`, `project_total_value`, `contractual_delivery_start`,
  `contractual_delivery_end`); migra `contract.delivery_at` existente para
  `equipment.contractual_delivery_end` **antes** de derrubar a coluna antiga
  (preserva os 3 contratos reais do DEV que tinham `delivery_at`); remove
  `UniqueConstraint(equipment_id)` de `contract`/`purchase_request`/
  `purchase_order` (1:1 → 1:N); adiciona colunas de arquivo em `contract`;
  substitui o índice único parcial de fornecedor "principal" por um índice
  único total por `equipment_id` (máx. 1 vínculo); cria as tabelas
  `operational_status_event`, `workflow_exception`, `reopen_request`,
  `comment`.
- **`0008_notification_events`**: cria `notification_event`, com índice
  único `(workflow_transition_id, kind)` — idempotência de Kickoff/FUP.

Ambas aplicadas em **DEV** (`neondb`) e **TEST** (`neondb_test`)
separadamente, confirmadas via `alembic current` mostrando `head` nos dois
bancos.

---

## 3. Modelo antes/depois (resumo)

| Entidade | Antes (Etapa 6) | Depois (Etapa 7A) |
|---|---|---|
| Contract | 1:1 com Equipment | 1:N, cada um com arquivo próprio |
| PurchaseRequest | 1:1 | 1:N |
| PurchaseOrder | 1:1 | 1:N |
| EquipmentSupplier | N:N, "principal" por flag | 1:N→1 efetivo (máx. 1 vínculo ativo, índice único garante) |
| Entrega contratual | `contract.delivery_at` (por contrato) | `equipment.contractual_delivery_start/end` (janela, por equipamento) |
| Estado operacional | inexistente | `equipment.operational_status` + `OperationalStatusEvent` |
| Exceção de fluxo | inexistente | `WorkflowException` |
| Reabertura | 1 permissão, ação imediata via `/transitions` | `ReopenRequest` (solicitação + aprovação separada) |
| Comentário | inexistente | `Comment` (sem anexos) |
| Notificação | inexistente | `NotificationEvent` (Kickoff/FUP) |

---

## 4. Estados especiais (7B)

Implementado em `app/modules/workflow/operational_status.py` +
`app/models/workflow_extras.py::OperationalStatusEvent`.

- **Standby**: `enter_standby` exige `operational_status == ACTIVE`,
  justificativa obrigatória, registra fase corrente no evento, **não altera
  `current_stage`**. `lift_standby` exige `operational_status == STANDBY`,
  volta para `ACTIVE` na mesma fase. `execute_transition` bloqueia qualquer
  avanço enquanto `operational_status != ACTIVE`.
- **Cancelado**: `cancel_equipment` exige justificativa, é definitivo — uma
  segunda chamada (`CANCELLED` → `CANCELLED`) é rejeitada, e nenhum avanço é
  permitido depois.
- **Em Saneamento**: `enter_sanitation` registra a fase de origem no
  evento, zera `current_stage` para 0 e marca `IN_SANITATION`.
  `end_sanitation` volta para `ACTIVE`, **permanece na fase 0** — o usuário
  retoma o fluxo normal a partir daí.

Todas as quatro ações geram `OperationalStatusEvent` (usuário, timestamp,
fase, justificativa) e um `AuditLog` companheiro (`equipment.standby_entered`
etc.) — a linha do tempo (`workflow/service.py::history`) funde
`WorkflowTransition` + `AuditLog` + `OperationalStatusEvent` num só feed,
com `kind="operational_status"` distinguindo visualmente sem exigir o
usuário decifrar `AuditLog`.

---

## 5. Exceções de fluxo (7B)

`app/modules/workflow/exceptions.py` + `app/modules/workflow/stages.py`.

- Tipos: `FIXED_SUPPLIER` (destino fixo = fase 5) e `IMPORTATION` (destino
  fixo = fase 7) — o destino não é escolhido pelo usuário, é inerente ao
  tipo.
- Só uma exceção `ACTIVE` por equipamento (índice único parcial no banco +
  checagem no serviço → 409 explícito).
- `EXCEPTION_DISPENSED_REQUIREMENT_CODES` (em `stages.py`) mapeia tipo →
  conjunto de `RequirementSpec.code` dispensados enquanto a exceção estiver
  ativa. Decisão registrada como interpretação explícita (não estava
  verbatim na especificação):
  - `FIXED_SUPPLIER` dispensa `negotiation_equalized_required` e
    `negotiation_date_required`.
  - `IMPORTATION` dispensa `contract_number_required`,
    `contract_executed_at_required`, `purchase_request_kind_required`,
    `purchase_request_number_required`, `purchase_request_date_required`.
- O avanço continua **manual, fase por fase** — nenhum salto automático;
  `_classify()` só aceita `target == current + 1`.
- A exceção é concluída automaticamente (`status = COMPLETED`) quando o
  equipamento **chega de fato** ao `intended_target_stage` via avanço
  manual — nunca antes.
- Contrato/SC-OCI seguem **preenchíveis normalmente** mesmo sob exceção
  (nunca bloqueados, nunca autopreenchidos com "N/A" ou número artificial).

---

## 6. Reabertura com aprovação (7C)

`app/modules/workflow/reopen.py` + `app/models/workflow_extras.py::ReopenRequest`.

O antigo caminho de reabertura imediata (`kind="reopen"` em
`POST /transitions`, restrito a `WORKFLOW_REOPEN`) foi **removido** — ele
fabricava a transição no mesmo clique, o que contraria a exigência de
"nunca fabricar transição antes da aprovação". Substituído por:

1. `POST /equipments/{id}/reopen-requests` — `target_stage < current_stage`
   (validado), justificativa obrigatória, só 1 `PENDING` por vez (índice
   único parcial). Equipamento **permanece na fase atual** enquanto pendente.
2. `POST .../{request_id}/approve` ou `/reject` — exige
   `workflow:reopen_approve` (hoje, só ADMIN — hierarquia corporativa real
   ainda não definida pelo time de Automação/Microsoft, então o "superior"
   é, por ora, uma permissão de perfil, não uma relação de gestor real,
   documentada como pendência abaixo). Quem solicitou não pode aprovar a
   própria solicitação. Aprovação gera `WorkflowTransition` real (from=
   `source_stage`, to=`target_stage`) + `AuditLog`; rejeição não altera nada.

Novas permissões (least-invasive, adicionadas à matriz existente em
`app/core/permissions.py`): `workflow:reopen_request` (ANALYST+ADMIN, mesmo
grupo que já edita o processo) e `workflow:reopen_approve` (ADMIN).

Dados de fases posteriores **nunca são apagados/zerados** por uma
reabertura — o modelo simplesmente move `current_stage` para trás; os
registros de Contract/PurchaseRequest/PurchaseOrder das fases "à frente"
continuam no banco, editáveis por quem tiver permissão.

---

## 7. Cardinalidade 1:N (Contratos / SC-OCI / OC)

`app/modules/processes/{schemas,service,router}.py` — CRUD genérico
(`list_items`/`create_item`/`update_item`/`delete_item`) sobre
`Contract`/`PurchaseRequest`/`PurchaseOrder`, todos com FK não-única para
`equipment_id`. Endpoints: `GET/POST /equipments/{id}/contracts`,
`PATCH/DELETE /equipments/{id}/contracts/{contract_id}` (e equivalentes
para `purchase-requests`/`purchase-orders`).

Requisitos de fase adaptados via `_any_filled(items, getter)`
(`workflow/stages.py`): a fase 5→6 exige número+escrituração em **ao menos
um** contrato; a fase 6→7 exige tipo+número+data em **ao menos uma**
SC/OCI — mesma semântica de negócio da Etapa 6, só adaptada à cardinalidade
nova (nenhum threshold novo inventado).

---

## 8. Fornecedor único por equipamento

`app/models/supplier.py` — trocado `equipment_supplier_primary_key`
(único parcial em `is_primary`) por `equipment_supplier_single_key` (único
total em `equipment_id`): no máximo 1 vínculo, ponto final. Tabela de
relacionamento **mantida** (evita migração destrutiva) — só a regra de
negócio mudou.

- `link_supplier` rejeita qualquer segunda tentativa de vínculo (409),
  mesmo para um fornecedor diferente.
- `replace_supplier` (novo) + `PUT /equipments/{id}/suppliers` fazem a
  substituição explícita (remove o vínculo atual + cria o novo, mesma
  transação) — a única forma de trocar de fornecedor.

---

## 9. Entrega contratual (janela)

`equipment.contractual_delivery_start`/`contractual_delivery_end`
substituem `contract.delivery_at` (que não fazia sentido por contrato
individual quando um equipamento pode ter vários). Constraint
`equipment_delivery_window_order_check` garante `start <= end` quando ambos
preenchidos. Dado legado migrado como END da janela (ver seção 2). Nenhuma
fórmula existente (FUN-001, dashboard) foi alterada — o campo é só
armazenado e validado nesta etapa, não veio um pedido para ele bloquear
transição alguma.

---

## 10. Valor Total do Projeto

`equipment.project_total_value` — campo manual, **nunca** somado
automaticamente a partir das OCs. Usado como requisito de conclusão (ver
seção 11).

---

## 11. Conclusão (Fase 7 → 8)

`workflow/stages.py::COMPLETION_REQUIREMENTS` substitui a antiga
reexecução de todos os requisitos anteriores por 3 requisitos explícitos,
**nenhum dispensável por exceção**:
`completion_supplier_required` / `completion_purchase_order_required` /
`completion_project_total_value_required`. Bug autocorrigido durante o
desenvolvimento: um gate de janela de entrega contratual foi adicionado por
engano e removido antes do commit final (a especificação nunca pediu isso
como bloqueio de transição).

---

## 12. Comentários (7E)

`app/modules/comments/` — CRUD completo (`GET/POST` lista/cria,
`PATCH/DELETE` só pelo próprio autor ou ADMIN). Schema não tem nenhum
campo de anexo — sem tabela de arquivo associada. Não vira `AuditLog`
(conceito à parte: conversa, não mudança de dado) e não aparece misturado
com `WorkflowTransition`. Permissão de leitura = `equipments:read`
(inclui Jurídico/Suprimentos, coerente com "só consulta"); escrita =
`process:write` (reaproveitada, mesmo grupo que já edita o processo —
nenhuma permissão nova).

---

## 13. Arquivo por contrato

`app/core/storage.py` — `ContractFileStorage` Protocol +
`LocalContractFileStorage` (filesystem, só DEV/teste) +
`get_contract_file_storage()` (bloqueia produção com erro explícito,
já que nenhum provider real — S3/Azure Blob — foi definido). Metadados
(`file_name`, `file_content_type`, `file_size_bytes`, `file_uploaded_by`,
`file_uploaded_at`) ficam no Postgres, em `Contract`. Upload/download via
`PUT`/`GET /equipments/{id}/contracts/{contract_id}/file`, autenticados
pela mesma cadeia de permissão dos demais endpoints de processo. Sem
attachments em Comentários nem tab genérica de anexos no equipamento — só
existe arquivo vinculado a um contrato específico.

**Pendência de infraestrutura**: provider real de object storage para
produção não está definido — documentado aqui, não decidido nesta etapa.

---

## 14. Kickoff / FUP (7F)

`app/modules/notifications/` — gatilho embutido em
`workflow/service.py::execute_transition`, rodando **depois** do commit da
fase (falha de notificação nunca desfaz nem bloqueia a transição real).

- Ao concluir a fase 5 (`from_stage=5`, ou seja, a transição 5→6): gera
  `NotificationEvent(kind=KICKOFF)`.
- Ao concluir a fase 7 (transição 7→8): gera `NotificationEvent(kind=FUP)`.
- Idempotência: índice único `(workflow_transition_id, kind)` — uma
  segunda chamada do gatilho para a mesma transição real não duplica (
  captura `IntegrityError`, retorna sem criar nada).
- Destinatário: responsável do equipamento (`User` existente). Superiores
  ficam como lista vazia — hierarquia corporativa (Microsoft Graph ou
  equivalente) ainda não definida pelo time de Automação; **nunca
  hardcoded**, `_resolve_recipients` já está pronto para receber essa fonte
  quando existir.
- Sem provedor real de e-mail configurado: `LogNotificationAdapter`
  registra o envio (nunca finge mandar e-mail real). Falha do adapter é
  capturada e vira `status=FAILED` + `failure_reason` no próprio evento —
  nunca propaga como erro HTTP.
- `GET /equipments/{id}/notifications` expõe o histórico (evento
  auditável, conforme exigido).

**Fora de escopo, conforme instruído**: recorrência de FUP, agendamento
futuro de Kickoff, integração real com Microsoft Graph.

---

## 15. Kanban (7G)

`frontend/pages/equipamentos/kanban.vue` — **só leitura**: nenhuma ação
altera `current_stage`/`operational_status`/dado algum do equipamento;
sem drag-and-drop de propósito. Reaproveita o mesmo endpoint
`GET /equipments` já usado pela listagem (com paginação percorrida até um
teto de segurança), respeitando unidade/contexto/filtros e a autorização
por unidade já aplicada pelo backend — nenhum endpoint novo, nenhuma cópia
paralela de `Equipment`.

Colunas: 0–8 (rótulos de `EQUIPMENT_STAGES`) + Standby + Cancelado + Em
Saneamento. Regra de posicionamento (`columnFor`): `operational_status !=
ACTIVE` manda para a coluna do próprio estado (inclusive Em Saneamento,
mesmo com `current_stage` resetado para 0 — não aparece em "Nova Demanda"
enquanto durar o saneamento); `ACTIVE` usa a fase normal. Cards mostram
nome, unidade/contexto, disciplina, área (quando disponível), limite de
entrega em obra (`calculated.deliveryDeadline`), responsável e badge de
estado especial quando aplicável.

---

## 16. Permissões

Regra de negócio confirmada: só Engenharia/Planejamento fazem alterações
operacionais; Jurídico e Suprimentos só consultam. Nada disso foi
hardcoded no frontend — toda ação de escrita desta etapa reaproveita
permissões já existentes na matriz (`workflow:transition`, `process:write`)
ou adiciona novas seguindo o mesmo padrão (`workflow:reopen_request`,
`workflow:reopen_approve`), sempre checadas no backend
(`app/core/permissions.py` + `require_permission`/`assert_can`). O
frontend só consome `user.permissions` devolvido por `/auth/me` (GAP-016,
Etapa 6D) — nenhuma regra de perfil duplicada na UI.

Hierarquia corporativa real (grupos do Microsoft/Automação) permanece
como pendência explícita — `workflow:reopen_approve` usa o perfil ADMIN
como substituto provisório, documentado, não uma decisão definitiva.

---

## 17. Testes executados

### 17.1 Backend — lint/tipos

- `ruff check app/` — **limpo** (0 erros).
- `mypy app/` — **limpo**, exceto 1 erro pré-existente e não relacionado
  (`app/modules/dashboard/service.py:196`, função sem anotação de retorno
  — Dashboard está congelado nesta etapa, não foi tocado).

### 17.2 Backend — verificação funcional direta (scripts, banco TEST, não DEV/C2)

Como a suíte pytest completa ficou bloqueada por instabilidade de infra
(seção 18), cada bloco foi verificado com um script direto
(`SessionLocal`, sem HTTP) contra `neondb_test`, criando e limpando dados
fictícios próprios — nunca tocando nos 41 equipamentos reais do C2:

| Script | Resultado |
|---|---|
| `scripts/verify_etapa7b_workflow_states.py` | ✅ Standby mantém fase e bloqueia avanço; lift volta a ACTIVE na mesma fase; Saneamento reseta para fase 0 e registra a fase de origem; fim do saneamento mantém fase 0; Cancelamento é definitivo; exceção FIXED_SUPPLIER dispensa negociação e permite avanço manual até a fase 2 |
| `scripts/verify_etapa7c_reopen_flow.py` | ✅ Alvo igual/futuro rejeitado; solicitação não muda a fase; segunda solicitação pendente simultânea rejeitada; solicitante não pode aprovar a própria solicitação; aprovação muda a fase; rejeição não altera nada |
| `scripts/verify_etapa7e_comments.py` | ✅ Lista vazia inicial; criação com autor/timestamp corretos; listagem; outro usuário não pode editar comentário alheio; autor pode editar o próprio; exclusão remove da listagem |
| `scripts/verify_etapa7f_notifications.py` | ✅ Conclusão da fase 5 gera exatamente 1 evento KICKOFF, `status=SENT`, destinatário resolvido; retry do gatilho não duplica (idempotência) |

### 17.3 Backend — suíte pytest de integração

Nova suíte HTTP criada: `tests/integration/test_operational_business_rules.py`
(13 testes cobrindo os mesmos cenários acima **via API real**, mais
cardinalidade 1:N, fornecedor único, conclusão da fase 8 e Kickoff/FUP via
transições reais). **Ainda não executada com sucesso** — ver seção 18.

Um subconjunto pré-existente (`test_smoke.py` + `test_users_routes.py` +
`test_audit_routes.py`, 19 testes) rodou até o fim em 47 minutos: **12
passaram, 4 falharam** — todas as 4 falhas são
`ConnectionDoesNotExistError: connection was closed in the middle of
operation` em `test_audit_routes.py` (arquivo não tocado nesta etapa),
confirmadas como falha de infraestrutura, não de asserção (ver seção 18).

### 17.4 Frontend

- `npx eslint . --ext .vue,.ts` — **limpo**.
- `npx vue-tsc --noEmit` — **limpo**.
- `npx vitest run` — **103/103 testes passando** (16 arquivos), incluindo
  os arquivos reescritos para a nova cardinalidade
  (`WorkflowComponents.test.ts`, `EquipmentSuppliers.test.ts`,
  `workflow.test.ts`, `EquipmentTable.test.ts`).
- `npx nuxt build` — **build completo com sucesso** (rodado 3 vezes, após
  7D, após 7E/7G, e após os ajustes do card do Kanban).

### 17.5 Baseline C2 (read-only)

`scripts/audit_c2_db.py` rodado após a migração 0007, após a 0008 e no
fechamento da sessão: **41 Equipment / 164 EquipmentComponent / 71
EquipmentWorkPackage** em todas as execuções — nenhuma alteração.

---

## 18. Instabilidade de infraestrutura observada nesta sessão

Duas ocorrências, ambas no banco **TEST** (`neondb_test`), nunca no DEV:

1. Um processo pytest ficou preso ~13 minutos com uma conexão Postgres em
   estado `active`/`wait_event=ClientRead` (servidor esperando o cliente
   ler a resposta) — mesmo padrão já relatado na Etapa 6D. Identificado via
   `pg_stat_activity`, processo encerrado (`Stop-Process`), conexão voltou
   a `idle` imediatamente.
2. Depois disso, uma rodada pequena (19 testes) levou 47 minutos com 4
   quedas de conexão no meio da execução. Um `SELECT 1` isolado medido
   nesse momento levou **6,25 segundos** de ida-e-volta (esperado: <100ms)
   — confirma que o problema é latência/instabilidade do lado do banco de
   teste hospedado (Neon), não do código desta etapa.

**Consequência**: a suíte completa de integração não foi executada até o
fim nesta sessão. Os 4 testes falhos são de `test_audit_routes.py`,
inalterado nesta etapa — não há evidência de regressão introduzida pela
Etapa 7. Recomenda-se re-executar
`pytest tests/integration -q` (banco TEST) numa janela em que a latência do
Neon esteja normal, e então rodar especificamente
`tests/integration/test_operational_business_rules.py` (novo) e
`tests/integration/test_workflow_routes.py` (reescrito) para confirmar via
pytest o que os scripts diretos já confirmaram funcionalmente.

---

## 19. Decisões interpretativas (não verbatim na especificação)

Registradas para revisão do negócio, já implementadas com a interpretação
mais conservadora possível:

1. Códigos exatos dispensados por cada exceção (seção 5).
2. `workflow:reopen_approve` = perfil ADMIN, como substituto provisório de
   "permissão superior" até existir hierarquia corporativa real (seção 6 e 16).
3. "Concluir uma fase" = a transição que **sai** daquela fase (5→6 dispara
   Kickoff; 7→8 dispara FUP) — não a chegada nela.
4. Justificativa é obrigatória para entrar em Standby/Saneamento/Cancelado;
   opcional para sair de Standby/Saneamento (a especificação só exigia
   explicitamente para as entradas e para o cancelamento).
5. `equipment:read` para ler comentários (inclui Jurídico/Suprimentos);
   `process:write` para escrever (Engenharia/Planejamento) — nenhuma
   permissão nova só para comentários.

---

## 20. Fora de escopo (confirmado intencional)

Dashboard; recorrência de FUP; agendamento futuro de Kickoff; integração
real com Microsoft Graph; descoberta automática de gestor/supervisor; ERP;
Saved Views; anexos em comentários; módulo genérico de anexos; movimentação
de fase via Kanban; geração de número de SC/OCI por IA; migração adicional
do Monday; alteração arbitrária dos 41 equipamentos reais.
