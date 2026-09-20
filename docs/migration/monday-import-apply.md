# MIG-001.1 — Apply controlado Monday → Hub

## Escopo desta etapa

Esta etapa estende a fundação do MIG-001 (`docs/migration/monday-import-architecture.md`) sem
refazê-la: `parse_monday_xlsx`, `build_dry_run_report`, `stage_import`, `reconcile_counts` e
`external_mapping` continuam exatamente como estavam. O que muda é que agora existe um caminho
completo e controlado

```text
XLSX → dry-run → stage → validate (mapping) → plan → apply → PostgreSQL/domínio → reconcile
```

O `apply` só grava no domínio depois de um `plan` explícito, revisável por humano, e nunca em
produção — `guard_write_target()` recusa qualquer alvo que não pareça DEV/TEST, no mesmo espírito de
`alembic/env.py::_guard_migration_target`. Não há endpoint HTTP nem tela de upload: tudo continua
CLI/backend administrativo.

## Pipeline e módulos novos

Dentro de `backend/app/modules/monday_import/`:

- `mapping_file.py`: carrega e valida um arquivo JSON explícito de mapeamento (responsáveis, áreas,
  disciplinas, Work Packages). Nunca cria catálogo; entradas sem correspondência viram issue de erro
  e ficam fora do mapeamento resolvido — o `plan` trata a ausência como `BLOCKED`, nunca como criação
  automática.
- `plan.py`: compara staging + mapping + estado atual do domínio e produz um `MigrationPlan`
  determinístico (`plan_sha256`). Não escreve nada. Resolve identidade, detecta conflito entre
  batches sobrepostos (`IMPORT_CONFLICT`), conflito de nome com equipamento já existente
  (`PARENT_IDENTITY_CONFLICT`), divergência entre `A.Status` e a fase do grupo (`STAGE_CONFLICT`) e
  edição humana pós-migração (`hub_monday_conflict`, via inspeção de `AuditLog`).
- `apply.py`: aplica exatamente o que o plano decidiu, de forma transacional (uma `SAVEPOINT` por
  execução) e tudo-ou-nada por contexto — um plano com qualquer item `BLOCKED` é recusado inteiro
  (`PlanBlockedError`), nunca aplicado parcialmente. Registra `MondayMigrationRun` para
  rastreabilidade e `AuditLog` (`action="migration.import"`) em cada escrita.
- `domain_reconciliation.py`: reconciliação campo a campo (Hub aplicado × staging mais recente),
  separada da `reconciliation.py` original (contagens agregadas), com status `MATCH` / `MISMATCH` /
  `NOT_COMPARABLE` / `PENDING_MAPPING`.
- `safety.py`: guarda de destino seguro reutilizada pelo `apply`.

## CLI

Da raiz de `backend/`, o invocação antiga continua funcionando sem alteração:

```powershell
.venv\Scripts\python.exe -m app.modules.monday_import ..\references\monday_exports
```

Isso é tratado como um atalho para `dry-run`. Os novos subcomandos:

```powershell
.venv\Scripts\python.exe -m app.modules.monday_import dry-run <arquivo-ou-diretorio>
.venv\Scripts\python.exe -m app.modules.monday_import stage <arquivo> --project-context-id <id>
.venv\Scripts\python.exe -m app.modules.monday_import plan --batch <id> [--batch <id> ...] \
    --mapping-file <mapping.json> --project-context-id <id>
.venv\Scripts\python.exe -m app.modules.monday_import apply --batch <id> [--batch <id> ...] \
    --mapping-file <mapping.json> --project-context-id <id> --actor-id <user-id> --confirm
.venv\Scripts\python.exe -m app.modules.monday_import reconcile --project-context-id <id>
```

`apply` exige `--confirm` e `--actor-id` (usuário real, nunca sintético) e recusa executar se o
`plan_sha256` recalculado divergir do plano revisado (`PlanStaleError`) — staging ou mapping mudaram
entre a revisão humana e a execução.

## Arquivo de mapeamento

JSON com quatro seções (`responsibles`, `areas`, `disciplines`, `workPackages`), cada uma um dicionário
`"valor observado na origem" -> "UUID existente no Hub"`. `validate_mapping` confere, para cada
entrada: existência, status ativo, e escopo correto (usuário com acesso à unidade do contexto; área da
mesma unidade; Work Package do mesmo `project_context`). Chaves de origem que colidem após
normalização (`duplicate_source_value`) também são erro. Nada é inferido nem criado — valor sem
entrada correspondente vira `unmapped_*` no plano, bloqueando o item.

## Idempotência e conflitos

- Segunda execução de `stage` com o mesmo arquivo não duplica batch (já era assim no MIG-001).
- Segundo `plan`/`apply` sobre dados já aplicados produz `NOOP` para tudo — nenhuma escrita, nenhuma
  auditoria nova.
- Duas fontes com a mesma identidade e payload idêntico mesclam silenciosamente; com payload
  diferente, o item vira `BLOCKED` com issue `IMPORT_CONFLICT` — nunca escolhemos a mais recente.
- Um Hub já editado por algo além da migração (detectado por `AuditLog.action != "migration.import"`)
  bloqueia a atualização em vez de sobrescrever (`hub_monday_conflict`).
- Subitem sem `ID do elemento` não pode ser aplicado de forma idempotente e fica `BLOCKED`
  (`missing_component_identity`) em vez de virar um registro não reconciliável.

## Work Package (1:1 → N:N)

A migration `0006_monday_apply_foundation` adiciona `equipment_work_package` (N:N, com backfill dos
dados existentes em `equipment.work_package_id`). A FK singular permanece como referência primária de
compatibilidade e só é preenchida pela migração quando há exatamente um Work Package na origem —
nenhuma lógica escolhe arbitrariamente "o primeiro" quando há mais de um.

## `startup_at` de componente

A mesma migration adiciona `equipment_component.startup_at`. Não é derivado nem herdado do
`equipment.startup_at`: quando a origem traz um startup próprio do subitem, ele prevalece nos cálculos
de prazo daquele componente.

## Campos efetivamente aplicados

Equipamento: `name`, `origin`, `startup_at`, `discipline_id`, `area_id`, `responsible_user_id`,
`criticality`, `current_stage` (validado contra a fase do grupo), `capex_estimated`,
`work_packages` (N:N). Sub-processos (criados/atualizados apenas quando a origem tem dado):
`Negotiation`, `LegalProcess`, `Contract` (1:1, mantido), `PurchaseRequest` (`kind` sempre `null`, com
warning `PURCHASE_REQUEST_KIND_UNRESOLVED` — nunca inferido do número), `PurchaseOrder`. Componente:
`name`, `tag`, `startup_at`, `sector`, `lead_time_days`, `pre_start_days`, `contract_delivery_at`,
`freight_days`.

Pendente (registrado como warning, não implementado): `SUPPLIER_MIGRATION_PENDING` quando a origem tem
`0.Fornecedores`; `ATTACHMENT_MIGRATION_PENDING` quando o subitem tem `Arquivos`. Nenhum fornecedor ou
anexo é criado por esta versão.

## Identidade

Sem mudança de estratégia em relação ao MIG-001: equipamento por
`project_context + normalized-name`, componente por `ID do elemento` Monday via `external_mapping`.
Colisão de nome com equipamento sem vínculo de origem vira `PARENT_IDENTITY_CONFLICT` — sem fusão
automática.

## Sem simulação de workflow

`current_stage` é escrito diretamente pelo serviço de apply. Nenhum `WorkflowTransition` sintético é
criado para "andar" 0→1→...→N — os testes de integração confirmam ausência dessas linhas após o
apply.

## Reconciliação

`reconcile` roda `domain_reconciliation.reconcile_domain`, comparando Hub × staging mais recente campo
a campo. A divergência 163×164 registrada no MIG-001 continua sem "correção" automática: ela deve
aparecer explicitamente no relatório humano, nunca ser resolvida por exclusão silenciosa.

## Testes

`tests/integration/test_monday_import_apply.py` cobre: plano sem escrita com valores não mapeados
bloqueados; validação de mapping (usuário inexistente/inativo/sem acesso à unidade, área de outra
unidade, Work Package de outro contexto); apply criando equipamento com múltiplos Work Packages e
startup próprio de componente; ausência de `WorkflowTransition` fictício; presença de `AuditLog`
`migration.import`; idempotência do apply; recusa de plano com hash divergente
(`PlanStaleError`); recusa de plano com item bloqueado (`PlanBlockedError`); `PARENT_IDENTITY_CONFLICT`;
`IMPORT_CONFLICT` entre batches sobrepostos com payload divergente (e merge silencioso quando
idêntico); bloqueio por edição humana pós-migração; rollback transacional em falha forçada (o
`MondayMigrationRun` registra `status="FAILED"` e o batch permanece `STAGED`); e registro de
`external_mapping` com a estratégia correta para equipamento e componente.

## Bloqueios antes do primeiro apply real em DEV

- Definir o arquivo de mapeamento real (responsáveis, áreas, disciplinas, Work Packages) para o
  `project_context` de destino — sem ele, o `plan` bloqueará todos os 41 equipamentos por campos não
  mapeados.
- Revisar humanamente o resultado de `plan` contra os dois arquivos canônicos
  (`Equipamentos_LEM_C2_ fase-0.xlsx` + `Equipamentos_LEM_C2_1789930920.xlsx`) antes de qualquer
  `apply --confirm`.
- Fornecedores e anexos continuam fora do escopo desta etapa.
