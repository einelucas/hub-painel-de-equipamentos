# ARCH-00.3b — `service.py` → `services.py` nos módulos HTTP

Baseline: `f3b589f` (`refactor: rename HTTP routers to controllers`), `main`, CI verde.

## Objetivo

Adequar a camada de serviços dos módulos HTTP à convenção `controllers.py` / `schemas.py` / `services.py`. A mudança é estrutural: sem alteração funcional, de regra de negócio, de banco ou de contrato HTTP.

## Módulos migrados (12)

`access`, `audit`, `catalogs`, `comments`, `dashboard`, `equipments`, `notifications`, `processes`, `queues`, `suppliers`, `users`, `workflow`.

Cada um: `modules/<dominio>/service.py` → `modules/<dominio>/services.py`, via `git mv`.

## Imports atualizados

- **Controllers (12):** `from app.modules.<x> import service` → `import services`, e chamadas `service.f(...)` → `services.f(...)`. Não foi usado alias permanente.
- **Dependências cruzadas entre services:**
  - `queues/services.py` → `suppliers.services` (`primary_suppliers`)
  - `workflow/services.py` → `notifications.services` (`trigger_for_transition`)
  - `workflow/reopen.py`, `workflow/waivers.py`, `workflow/operational_status.py` → `workflow.services` (`_get_equipment`)
  - `workflow/controllers.py` → `operational_status, services`
  - `queues/controllers.py` → `queues.services` (`QueueFilters`)
- **Testes:** `tests/integration/test_dashboard_and_queues.py`.
- **Scripts (14 arquivos):** `scripts/*.py` que importavam `<modulo>.service`.
- **Comentários/docstrings** com caminho atual `<modulo>/service.py` → `services.py` (`app/domain/equipment_calculations.py`, `app/shared/audit.py`, `workflow/operational_status.py`, `workflow/waivers.py`, `workflow/reopen.py`, `equipments/services.py`, `workflow/services.py`).
- **`backend/README.md`:** árvore de exemplo em "Estrutura dos módulos".

## Dependências cruzadas encontradas

Além das duas citadas no pedido, foram encontradas `workflow → equipments` (indireta, via `_get_equipment`), `queues → suppliers`, e os imports de `workflow.service` em `reopen`/`waivers`/`operational_status`. Nenhuma dependência externa inesperada.

## Mantido deliberadamente

- `app/modules/monday_import/service.py` — módulo de carga, fora do escopo; será formalizado como exceção na ARCH-00.3c. Seus imports (`apply.py`, `cli.py`, testes de importação) não foram alterados.
- `app/modules/dashboard/schemas.py` — **não alterado**. Um docstring nele cita `dashboard/service.py` e aparece na descrição do schema `NegotiationDeadlineStatusSummaryOut` no OpenAPI. Alterá-lo mudaria o contrato público; fica como resíduo.
- `schemas.py`, `app/models/`, migrations, frontend, `eap_*`, `supplier_import` — intocados.

## Ausência de mudança funcional

Diff restrito a: renames, imports, chamadas de módulo nos controllers e comentários/docstrings. Nenhuma assinatura, nome de função, query, transação, validação, exceção ou auditoria foi alterada.

## OpenAPI antes/depois

- Antes (`f3b589f`): sha256 `62f8462d71ade1d8dc3773ba2bb310d05408ce0001ee273605c80ce49d23b929`
- Depois: sha256 `62f8462d71ade1d8dc3773ba2bb310d05408ce0001ee273605c80ce49d23b929`
- Arquivos byte a byte idênticos (`json.dumps(app.openapi(), sort_keys=True, indent=2)`).
- 59 paths, 87 operações, 121 schemas.

## Verificações

- **Ruff** (`python -m ruff check app tests scripts`): All checks passed.
- **mypy** (`python -m mypy app`): Success, 124 arquivos.
- **pytest** (`python -m pytest`): 433 passed, 4 skipped, 0 failed — igual ao baseline.
- **Banco:** PostgreSQL 16.10 portátil, isolado, em diretório temporário fora do repo, porta local dedicada, banco `painel_equipamentos_b3b_test`. Migrations aplicadas até `0011_eap_foundation (head)`.

## Incidente de ambiente

Uma primeira execução do pytest foi feita no repo com `backend/.env.test` ativo. O `conftest.py` carrega esse arquivo com `override=True`, o que sobrescreveu o ambiente exportado e apontou para o banco corporativo de teste. A execução foi interrompida sem verificação de efeitos. Os resultados reportados acima vêm exclusivamente da execução no banco isolado. Ver recomendação de guarda no conftest.

## Riscos residuais

- Documentação técnica atual ainda cita `service.py` em `docs/arquitetura.md`, `docs/Auditoria_Tecnica_Funcional_Painel_de_Equipamentos.md`, `docs/etapa-02-workflow-aquisicao.md` e `docs/migration/*`. Não foram alterados nesta etapa; decidir na consolidação ARCH-00.
- Registros históricos em `docs/validation/` e `docs/architecture/ARCH-00-1` / `ARCH-00-3a` seguem citando `service.py`, por design.
- Docstring em `dashboard/schemas.py` (ver acima) só sai junto de uma mudança de contrato.
- `conftest.py` aceita qualquer banco cujo nome termine em `_test` e sobrescreve o ambiente com `.env.test`; isso permitiu a execução acidental no banco corporativo. Recomendado endurecer antes de novas execuções.
- CI remoto ainda não rodou para este commit (execução local apenas).
