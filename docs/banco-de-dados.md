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

## Migrations

A execução de migrations é permitida somente em `development` ou `test` com `ALLOW_TEST_DB_MIGRATIONS=true`.

```bash
python -m alembic upgrade head
```

Use `python scripts/check_schema_drift.py` para comparar os models com um banco já migrado.

`0001_shared_base` permanece inalterada. O downgrade de `0002_equipment_domain` remove somente as tabelas do novo domínio, em ordem segura de dependências, e o de `0003_acquisition_process` remove apenas as cinco tabelas do processo de aquisição.
