# C2 — Relatório do primeiro apply (DEV)

## Pré-checagens (antes do apply)

| Item | Resultado |
|---|---|
| Ambiente | `APP_ENV=development`, host `ep-red-field-b48nnf5d-pooler.c-6.us-east-2.aws.neon.tech`, sem indício de produção (guard `guard_write_target` passou) |
| Checkpoint | Sem Neon CLI/`pg_dump` disponíveis neste ambiente. Checkpoint lógico: todas as tabelas de domínio afetadas (Equipment, EquipmentComponent, Negotiation, LegalProcess, Contract, PurchaseRequest, PurchaseOrder, ExternalMapping, MondayMigrationRun) confirmadas **vazias** antes do apply → registrado em `c2-pre-apply-baseline.json` |
| Schema | `alembic current` = `0006_monday_apply_foundation (head)` ✅ |
| planSha256 | Replanejado a partir do estado atual do banco imediatamente antes do apply: `851b885928090ab4645ab4c1e76dc97540b0214f0704220abb63b0f1671be791` — idêntico ao aprovado ✅ |
| mappingSha256 | `c3675f2ce6ec7de5736c53259b4c2f27217ef3a2670f9a5f33538b9f4f472aa0` — idêntico ao aprovado ✅ |
| Actor | `dev+admin@example.com` (`aa11ad3f-a5ce-470c-81de-93bbf309e47d`), role **ADMIN**, ativo — não ANALYST ✅ |
| Warning aceito | `PURCHASE_REQUEST_KIND_UNRESOLVED` (Caldeira de Biomassa) mantido como está — nenhuma inferência de tipo SC/OCI foi feita |

Nenhuma condição de abort da seção 8 ocorreu.

## APPLY

- **Status da transação:** `APPLIED` (commit único, `session.begin_nested()` + `session.commit()`)
- **Actor:** `aa11ad3f-a5ce-470c-81de-93bbf309e47d` (ADMIN, dev+admin@example.com)
- **Migration run ID:** `02e57851-595b-4316-adb5-b28b6130754a`
- **Execução:** uma única chamada, com `--confirm`

| Entidade | CREATE | UPDATE | NOOP |
|---|---|---|---|
| Equipment | 41 | 0 | 0 |
| EquipmentComponent | 164 | 0 | 0 |
| Negotiation | 10 | 0 | 0 |
| LegalProcess | 10 | 0 | 0 |
| Contract | 4 | 0 | 0 |
| PurchaseRequest | 1 | 0 | 0 |
| PurchaseOrder | 1 | 0 | 0 |

**Warnings:** 1 — `PURCHASE_REQUEST_KIND_UNRESOLVED` (Caldeira de Biomassa), aceito conforme instrução.
**Conflicts:** nenhum.
**Erros:** nenhum.

## RECONCILE

Rodado imediatamente após o apply, comparando Hub aplicado × staging (`c2-reconcile.json`).

| Status | Contagem |
|---|---|
| MATCH | 364 |
| MISMATCH | **0** |
| NOT_COMPARABLE | 210 (campos de sub-processos onde o equipamento não tem aquele sub-registro na origem — ex.: `contract_number` para os 37 equipamentos sem contrato) |
| PENDING_MAPPING | 41 (campo `purchase_request_kind` — nenhuma origem tem tipo SC/OCI identificável; comportamento aceito, nenhuma inferência feita) |

- `equipmentsCompared`: **41**
- `componentsCompared`: **164**

**Distribuição por fase (Equipment / EquipmentComponent), via `current_stage`:**

| Fase | Equipment | Component |
|---|---|---|
| Fase 0 (`current_stage=0`) | 31 | 55 |
| Fase 4 (`current_stage=4`) | 6 | 8 |
| Fase 6 (`current_stage=6`) | 3 | 77 |
| Fase 8 (`current_stage=8`) | 1 | 24 |

Bate exatamente com o esperado (31/55, 6/8, 3/77, 1/24).

**Verificações adicionais (consulta direta ao banco):**

- Responsáveis: `responsible` = MATCH em 41/41 equipamentos.
- Areas: `area` = MATCH em 41/41. Confirmado por amostra de origem: equipamento "Ponte rolante 25 ton" veio de `area_name = "2104.A Casa de Força"` e "Suporte de mola..." veio de `area_name = "Casa de Força"` — **ambos resolvidos para o mesmo `area_id` `bdba7695-8196-4fde-80b6-4c66b840851f`**.
- Disciplines: `discipline` = MATCH em 41/41.
- Work Packages N:N: 71 vínculos em `equipment_work_package`; 17 equipamentos sem nenhum vínculo — todos os 17 conferidos contra `work_package_codes` de origem: **nenhum tinha código de WP na origem** (nenhum vínculo perdido).
- Duplicação de Equipment: **nenhuma** (sem nomes repetidos no contexto C2).
- Duplicação de Component: **nenhuma** por identidade real — 5 pares de componentes com o mesmo texto de nome sob o mesmo equipamento, mas cada um com `ID do elemento` (external_id Monday) **distinto**, confirmando que são peças fisicamente diferentes com descrição textual idêntica, não duplicação de importação.
- `external_mapping`: 41 linhas `equipment` + 164 linhas `component` = criadas corretamente, uma por registro.
- `AuditLog`: 231 linhas com `action="migration.import"` (uma por entidade criada: 41+164+10+10+4+1+1 = 231) ✅.
- XLSX de origem: SHA-256 nos dois arquivos em disco idêntico ao `file_sha256` gravado no staging no momento do `stage` — **nenhuma alteração**.

## IDEMPOTÊNCIA

Segundo `plan` executado com os **mesmos** batches, mapping e contexto, sem nenhum apply adicional.

- `planSha256` do segundo plan: `06d7d8f43731ada1e22f0be06fa5a813f84a15a640514f59d83b7d2c5206f420` (diferente do primeiro — esperado, pois o hash cobre o estado already-applied vs. not-yet-applied)
- `mappingSha256`: inalterado (`c3675f2ce6ec7de5736c53259b4c2f27217ef3a2670f9a5f33538b9f4f472aa0`)

| Entidade | CREATE | UPDATE | NOOP | BLOCKED |
|---|---|---|---|---|
| Equipment | 0 | 0 | **41** | 0 |
| EquipmentComponent | 0 | 0 | **164** | 0 |
| Negotiation/LegalProcess/Contract/PurchaseRequest/PurchaseOrder | 0 | 0 | 0 | 0 |

**Nenhum CREATE ou UPDATE inesperado.** Nenhuma recriação dos 41 equipamentos/164 componentes.

Nota sobre os sub-processos (Negotiation/LegalProcess/Contract/PurchaseRequest/PurchaseOrder): o `plan.py` só reavalia esses sub-registros quando o equipamento-pai está em `CREATE` (primeira vez) ou `UPDATE`; quando o pai é `NOOP` (como agora, em todos os 41), o `plan` não os relista — não é um erro, é o comportamento já existente no código (comentário no próprio `plan.py`, linha ~706). Por isso a tabela acima mostra 0/0/0/0 para eles, em vez de "10 NOOP" etc. A idempotência desses 5 já foi confirmada por contagem direta no banco (10/10/4/1/1, sem duplicar) na seção RECONCILE acima.

## DADOS PENDENTES

- **Caldeira de Biomassa** — `PurchaseRequest` criado com `request_number`/`requested_at` da origem, mas **sem tipo SC/OCI resolvido** (campo `purchase_request_kind` não existe/não é preenchido pela implementação atual). Warning `PURCHASE_REQUEST_KIND_UNRESOLVED` preservado, nenhuma inferência feita, conforme instruído.
- `purchase_request_kind` aparece como `PENDING_MAPPING` no reconcile para **todos os 41 equipamentos** — é um campo estrutural ainda sem lógica de resolução no domínio (não específico da Caldeira de Biomassa; é o único caso com dado real na origem, os demais 40 nem têm SC/OCI).
- 37 equipamentos sem Contract, 31 sem Negotiation/LegalProcess, 40 sem PurchaseRequest/PurchaseOrder — **NOT_COMPARABLE**, não MISMATCH: são equipamentos que genuinamente não têm esse sub-processo na origem (confirmado pelas contagens 10/10/4/1/1 batendo com o apply).
- E-mails dos 4 responsáveis continuam provisórios (`@inpasa.com.br` fictício até confirmação corporativa) — já documentado em `c2-cadastros-notes.md`.

---

Parado aqui, conforme pedido. Nenhuma correção adicional foi feita automaticamente.
