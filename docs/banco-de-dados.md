# Banco de dados

O banco usa PostgreSQL e SQLAlchemy 2 assíncrono. O Alembic controla o versionamento do schema.

## Schema inicial

A migration base cria somente estruturas compartilhadas:

- `User`
- `Session`
- `Account`
- `Verification`
- `AuditLog`
- enum `Role`

## Domínio de equipamentos

A migration `0002_equipment_domain` cria `unit`, `project_context`, `area`, `discipline`, `work_package`, `equipment`, `equipment_component` e `workflow_transition`. Relações cruzadas incompatíveis são rejeitadas pelo service; constraints do banco protegem etapas e valores não negativos.

## Processo de aquisição

A migration `0003_acquisition_process` cria `negotiation`, `legal_process`, `contract`, `purchase_request` e `purchase_order`. Cada tabela é 1:1 com o equipamento: `equipment_id` é FK com `ON DELETE CASCADE` e `UNIQUE`, o que impede duplicatas mesmo em chamadas concorrentes. `purchase_request.kind` aceita apenas `SC` ou `OCI` e `purchase_order.amount` não pode ser negativo.

Os registros são criados sob demanda no primeiro `PATCH`; até lá a API devolve o processo com `id` nulo sem gravar nada.

## Acesso e fornecedores

A migration `0004_access_and_suppliers` cria `user_unit_access`, `supplier` e `equipment_supplier`.

`user_unit_access` é UNIQUE por (`user_id`, `unit_id`) e não duplica perfil/permissão: o `role` continua no usuário. `supplier.tax_id` tem índice único **parcial**, que só vale quando o documento é informado. `equipment_supplier` é UNIQUE por (`equipment_id`, `supplier_id`) e tem índice único parcial em `equipment_id` onde `is_primary`, garantindo no banco um único fornecedor principal por equipamento.

O backfill da migration vincula os VIEWER/ANALYST existentes às unidades existentes, preservando o comportamento anterior de acesso global; ADMIN é global por perfil e usuários novos exigem atribuição explícita.

## Migrations

A execução de migrations é permitida somente em `development` ou `test` com `ALLOW_TEST_DB_MIGRATIONS=true`.

```bash
python -m alembic upgrade head
```

Use `python scripts/check_schema_drift.py` para comparar os models com um banco já migrado.

`0001_shared_base` permanece inalterada. O downgrade de `0002_equipment_domain` remove somente as tabelas do novo domínio, em ordem segura de dependências, o de `0003_acquisition_process` remove apenas as cinco tabelas do processo de aquisição e o de `0004_access_and_suppliers` remove as três tabelas de acesso e fornecedores.
