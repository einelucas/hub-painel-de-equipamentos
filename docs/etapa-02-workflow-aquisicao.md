# Etapa 02 — workflow de aquisição 0–8

## Objetivo

Transformar a fundação da Etapa 1 em um processo operacional de aquisição. O equipamento percorre as etapas 0 a 8 por uma máquina de estados transacional no backend, com pré-condições explícitas, histórico e auditoria. O detalhe do equipamento passa a ser a tela de operação do processo.

## Decisões arquiteturais

- `equipment.current_stage` continua sendo a única fonte de verdade do estágio.
- Toda transição passa por `app/modules/workflow/service.py`. Não existe outro caminho para alterar o estágio.
- As pré-condições são declarativas (`app/modules/workflow/stages.py`), separadas da execução, para receber novos validadores sem reescrever o serviço.
- As automações redundantes do Monday foram consolidadas em uma regra determinística por transição.
- Os cinco processos são 1:1 com o equipamento, criados sob demanda e nunca duplicados.
- O frontend apenas apresenta a decisão do backend: `canExecute` nunca é calculado no navegador.

## Migration

`0003_acquisition_process.py`, sucessora de `0002_equipment_domain`. Sobe e desce sem resíduo (verificado com `upgrade`/`downgrade`/`upgrade` e `scripts/check_schema_drift.py`). Cria:

| Tabela | Campos próprios |
| --- | --- |
| `negotiation` | `equalized`, `negotiated_at` |
| `legal_process` | `opened_at`, `ticket_number`, `draft_prepared`, `draft_approved` |
| `contract` | `contract_number`, `executed_at`, `delivery_at` |
| `purchase_request` | `kind` (`SC`/`OCI`), `request_number`, `requested_at` |
| `purchase_order` | `order_number`, `ordered_at`, `amount` |

Todas têm `id`, `equipment_id` (FK `CASCADE` + `UNIQUE`) e timestamps. `purchase_request.kind` tem CHECK `IN ('SC','OCI')`; `purchase_order.amount` tem CHECK `>= 0`.

## Endpoints

Dados do processo (leitura com `equipments:read`, escrita com `process:write`):

- `GET /api/v1/equipments/{id}/processes` — os cinco processos em uma chamada
- `GET|PATCH /api/v1/equipments/{id}/negotiation`
- `GET|PATCH /api/v1/equipments/{id}/legal`
- `GET|PATCH /api/v1/equipments/{id}/contract`
- `GET|PATCH /api/v1/equipments/{id}/purchase-request`
- `GET|PATCH /api/v1/equipments/{id}/purchase-order`

Um processo ainda não iniciado é devolvido com `id: null` e valores padrão, sem gravar nada no banco. O `PATCH` cria o registro quando necessário.

Workflow:

- `GET /api/v1/equipments/{id}/available-transitions` (`workflow:read`)
- `POST /api/v1/equipments/{id}/transitions` (`workflow:transition`)
- `GET /api/v1/equipments/{id}/history` (`workflow:read`)

## Máquina de estados

Fluxo principal sequencial, uma etapa por vez. O endpoint público não permite pular etapas.

| Transição | Pré-condições implementadas |
| --- | --- |
| 0 → 1 Negociação | nenhuma além do cadastro mestre válido — é uma ação explícita do usuário |
| 1 → 2 Equalização | `negotiation.equalized` |
| 2 → 3 Abertura do chamado | `negotiation.negotiated_at` |
| 3 → 4 Aprovação da minuta | `legal_process.opened_at`, `legal_process.ticket_number` |
| 4 → 5 Escrituração do contrato | `legal_process.draft_prepared`, `legal_process.draft_approved` |
| 5 → 6 SC ou OCI | `contract.contract_number`, `contract.executed_at` |
| 6 → 7 Aprovação da OC | `purchase_request.kind`, `request_number`, `requested_at` |
| 7 → 8 Concluído | `purchase_order.order_number`, `ordered_at`, `contract.delivery_at` **e** os requisitos de todas as etapas anteriores |

`contract.delivery_at` é preservado como dado contratual desde a etapa 5, mas só é exigido na conclusão.

`available-transitions` devolve, para cada opção, a lista completa de requisitos com `satisfied`, mais as listas derivadas `satisfiedRequirements` e `missingRequirements`, cada requisito com `code`, `field` e uma `message` de negócio.

## Reabertura

Regra **provisória**, pendente de validação de negócio:

- única reabertura disponível: estágio `>= 2` → `1 — Negociação`;
- exige `reason` não vazio;
- restrita a `workflow:reopen`, hoje concedida apenas ao ADMIN;
- registra `workflow_transition` e auditoria com `metadata.kind = "reopen"`.

Nenhuma transição reversa ocorre por edição de dados. `Standby`, `Cancelado` e `Não se Aplica` continuam fora do fluxo.

## Bloqueio da alteração direta do estágio

`EquipmentUpdateIn` não tem mais `current_stage` nem `transition_reason`. Enviar `currentStage` no `PATCH /equipments/{id}` retorna **422** com mensagem explícita apontando o endpoint correto, em vez de ignorar o campo em silêncio. O formulário de equipamento no frontend perdeu o seletor de etapa.

## Concorrência

`execute_transition` roda em uma transação:

1. `SELECT ... FOR UPDATE` do equipamento;
2. classificação da transição e validação das pré-condições sob o lock;
3. releitura do `current_stage` antes do commit;
4. gravação de `workflow_transition` + `current_stage` + auditoria;
5. commit atômico.

Pedir uma etapa já aplicada (ou anterior à atual, fora da reabertura) retorna **409**. Uma transição que falha não grava `workflow_transition` nem altera o estágio.

## Permissões

| Permissão | VIEWER | ANALYST | ADMIN |
| --- | --- | --- | --- |
| `workflow:read` | sim | sim | sim |
| `process:write` | não | sim | sim |
| `workflow:transition` | não | sim | sim |
| `workflow:reopen` | não | não | sim |

As permissões da Etapa 1 foram preservadas. `app/core/permissions.py` continua sendo a fonte de verdade; `stores/auth.ts` espelha a matriz para habilitar/desabilitar controles.

## Auditoria

Usa o `audit_event` existente (`AuditLog`), sem infraestrutura paralela. São auditados: criação/edição de equipamento e componentes (Etapa 1), edição dos cinco processos, mudança de estágio e reabertura — sempre com valor anterior, valor novo, usuário e timestamp. A auditoria dos processos carrega `metadata.equipmentId`, o que permite ao histórico consolidar tudo por equipamento.

`GET /history` retorna transições (`kind: "transition"`) e alterações de dados (`kind: "change"`) em uma lista única ordenada da mais recente para a mais antiga.

## Frontend

- `pages/equipamentos/[id].vue`: resumo, stepper, abas Processo/Componentes/Histórico, avanço, reabertura.
- `components/equipment/EquipmentWorkflowStepper.vue`: etapas 0–8 com estados concluída/atual/bloqueada/futura. É apenas visual — não há controle clicável que mude a etapa.
- `components/equipment/EquipmentStageForm.vue`: formulário da etapa atual (negociação, jurídico, contrato, SC/OCI, OC) com **Salvar alterações**.
- `components/equipment/WorkflowRequirements.vue`: painel de requisitos da próxima etapa.
- `components/equipment/ProcessSummary.vue`: todos os processos em leitura, para consultar etapas anteriores.
- `composables/useEquipmentWorkflow.ts`: carrega processos/transições/histórico e executa salvar e transicionar.
- `utils/workflow.ts`: lógica pura (mapa etapa → formulário, estados do stepper, rótulos).

**Salvar não é avançar.** São dois botões distintos: `Salvar alterações` grava os dados da etapa; `Avançar para <etapa>` pede a transição e só fica habilitado quando o backend informa `canExecute = true`. Erros de transição preservam o que o usuário digitou, porque o formulário mantém estado local e só é ressincronizado após um salvamento bem-sucedido.

Após uma transição, o detalhe recarrega equipamento, processos, transições e histórico. O dashboard recarrega ao ser montado novamente, refletindo a nova contagem por estágio.

## Testes

Backend — `tests/integration/test_workflow_routes.py`:

- criação 1:1 idempotente dos processos e leitura do processo vazio;
- fluxo completo 0 → 8 com todas as transições registradas;
- avanço bloqueado por requisito pendente, com `missingRequirements` correto e nenhuma transição gravada;
- tentativa de pular etapa (422) e repetição de transição já aplicada (409);
- `currentStage` rejeitado no `PATCH` comum;
- reabertura sem motivo, sem permissão (VIEWER/ANALYST) e com permissão (ADMIN);
- auditoria da reabertura com motivo e estágio anterior;
- histórico consolidando transições e alterações de dados, ordenado;
- VIEWER bloqueado para transição e escrita de processo.

`tests/integration/test_equipment_routes.py` foi ajustado: a mudança de etapa agora usa o endpoint de transições.

Frontend — `tests/workflow.test.ts` (lógica pura) e `tests/WorkflowComponents.test.ts` (componentes): stepper 0–8 e destaque da etapa atual, ausência de controle clicável de etapa, requisitos atendidos/pendentes, motivo de bloqueio, formulário correto por etapa preenchido com os dados do processo, salvar sem avançar, edição bloqueada sem permissão.

## Comandos

```powershell
cd backend
.venv\Scripts\python.exe -m alembic upgrade head
.venv\Scripts\python.exe -m ruff check app tests scripts
.venv\Scripts\python.exe -m mypy app
.venv\Scripts\python.exe -m pytest

cd ..\frontend
pnpm lint
pnpm typecheck
pnpm test
pnpm build
```

## Divergências entre especificação e código

- A especificação lista `negotiation.max_deadline_at`, mas condiciona o campo a "já houver definição segura no domínio". A fórmula do prazo de negociação continua não confirmada, então **a coluna não foi criada** — seguindo a regra do projeto de manter ausente o campo derivado sem fórmula oficial, em vez de criar uma coluna morta ou inventar cálculo.
- A especificação sugere permissões separadas por departamento (`negotiation:write`, `legal:write`, `contract:write`, `procurement:write`). Como a política por departamento é declaradamente pendente, foi criada uma única `process:write`, evitando fixar uma matriz fina ainda não validada.
- O `PATCH` de equipamento passou a **rejeitar** `currentStage` em vez de ignorá-lo, entre as três alternativas oferecidas pela especificação.

## Decisões provisórias e pendências de negócio

- Reabertura restrita ao ADMIN e limitada a `>= 2 → 1`: quem pode reabrir, cancelar ou colocar em standby ainda não foi definido.
- Cardinalidade 1:1 mantida conforme a Etapa 1. Múltiplos contratos/SCs/OCs por equipamento segue em aberto; a modelagem está preparada para evoluir, mas não foi redesenhada sem evidência.
- `0 → 1` não tem pré-condição adicional além do cadastro mestre — nenhuma regra extra foi inventada.
- Sem fórmulas de prazo, risco, índices ou "Total de Aquisições".
- Matriz fina por Engenharia/Jurídico/Suprimentos pendente.
- `criticality` continua texto livre, aguardando taxonomia oficial.

## Escopo proposto para a Etapa 3

- definir e implementar a política de reabertura/cancelamento/standby;
- validar as fórmulas de prazo e risco e só então implementá-las;
- decidir a cardinalidade definitiva de contratos/SCs/OCs;
- fornecedores e processo competitivo;
- FUP, notificações e kickoff;
- anexos e comentários por etapa;
- exportações e saved views;
- planejar a migração/reconciliação de C2 e F2.
