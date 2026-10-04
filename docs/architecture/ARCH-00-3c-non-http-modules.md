# ARCH-00.3c — Módulos não HTTP: exceções deliberadas

Baseline: `3c42450` (`main`, CI verde). **Etapa só de documentação:** nenhum arquivo de código foi alterado.

## Convenção

A convenção `controllers.py` / `schemas.py` / `services.py` vale para os **módulos HTTP**, isto é, os 12 cujo `controllers.router` está registrado em `app/api/v1/router.py`:

`access`, `audit`, `catalogs`, `comments`, `dashboard`, `equipments`, `notifications`, `processes`, `queues`, `suppliers`, `users`, `workflow`.

Um módulo HTTP pode ter, além desses três arquivos, arquivos especializados de domínio. Hoje são `workflow/stages.py`, `workflow/reopen.py`, `workflow/waivers.py`, `workflow/operational_status.py` e `notifications/adapter.py`. A convenção define o mínimo, não um teto.

## Módulos analisados

Nenhum dos quatro importa `fastapi` nem `APIRouter`, e nenhum está registrado no `api_router`. Nenhum módulo HTTP, nem `app/api`, `app/shared` ou `app/domain`, importa algum deles. São chamados pelas CLIs (`python -m app.modules.<m>`), pelos scripts e pelos testes, e uns pelos outros.

### `monday_import`: importação auditável das exportações XLSX do Monday

| Arquivo | Responsabilidade |
|---|---|
| `xlsx.py`, `parser.py` | Leitura XLSX somente leitura e parser semântico da exportação hierárquica |
| `normalization.py`, `mappings.py`, `mapping_file.py` | Normalização de campos e mapeamento Monday → Hub (colunas, identidades, catálogos) |
| `schemas.py` | Contratos internos do importador (não são schemas HTTP) |
| `service.py` | Persistência **somente no staging** (`stage_import`, `register_external_mapping`) |
| `plan.py`, `dry_run.py` | Plano determinístico staging + mapping + banco; dry-run sem sessão de banco |
| `apply.py`, `safety.py` | Apply transacional do plano validado; trava contra execução acidental em produção |
| `reconciliation.py`, `domain_reconciliation.py` | Conferência de contagens e reconciliação campo a campo Hub × staging |
| `calculations.py` | Compatibilidade: reexporta `app.domain.equipment_calculations` |
| `cli.py`, `__main__.py` | CLI administrativa |

### `supplier_import`: carga de fornecedores oficiais (código corporativo + aliases)

`workbook.py` lê a planilha auditada. `plan.py` consolida sem banco. `database.py` reconcilia com o banco e aplica de forma idempotente. `cli.py` é a CLI.

### `eap_catalog`: catálogo EAP canônico versionado

`tree.py` extrai a árvore de Localização (puro, sem I/O). `catalog.py` lê e valida `app/data/eap_catalog.json`. `seed.py` faz a carga idempotente em `eap_node`. `cli.py` é a CLI.

### `eap_reconciliation`: reconciliação Área/EAP dos equipamentos

`reconcile.py` faz o match puro com o catálogo. `monday.py` monta o relatório a partir dos exports. `report.py` gera o Markdown. `database.py` compara em modo somente leitura. `apply.py` grava `equipment.eap_node_id` sob controle, com AuditLog `eap_reconciliation.apply`. `cli.py` é a CLI.

## Por que não fazem parte da camada HTTP

São pipelines de processamento administrativo: parsing, staging, plano, dry-run, apply, reconciliação e seed de catálogo. Rodam por CLI, de forma controlada e auditada, e não atendem requisições. Encaixá-los em `controllers.py` / `services.py` exigiria:

- criar `controllers.py` vazios ou artificiais, sem nenhuma rota;
- espremer responsabilidades distintas (parser, plano, apply, reconciliação) num único `services.py`, ou renomear arquivos que já descrevem bem o que fazem.

## Exceções deliberadas

- **`monday_import/service.py` continua com esse nome.** Ele não é a camada de serviço HTTP de um domínio. É o componente de **staging** do pipeline de importação, ao lado de `plan.py`, `apply.py` e outros. Renomeá-lo só por uniformidade mudaria imports em `apply.py`, `cli.py` e nos testes de importação sem nenhum ganho.
- **Os quatro módulos mantêm estrutura especializada** (`cli.py`, `plan.py`, `apply.py`, `reconcile.py`, `seed.py` etc.), sem `controllers.py`.
- **`monday_import/schemas.py`** contém contratos internos do pipeline, não modelos de request/response da API.

## Shims e estruturas artificiais

Nenhum é necessário. Não foram criados `controllers.py` vazios, nem `services.py` de fachada, nem aliases de import. Se um desses fluxos ganhar endpoint HTTP no futuro (por exemplo, um upload de board na P1.1), o endpoint deve nascer num módulo HTTP com `controllers.py` / `schemas.py` / `services.py`, e esse `services.py` chama o pipeline. O pipeline não vira controller.
