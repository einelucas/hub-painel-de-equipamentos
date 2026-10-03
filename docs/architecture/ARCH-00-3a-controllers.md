# ARCH-00.3a — `router.py` → `controllers.py`

> **Baseline:** `main` @ `1ee3c08` (CI verde).
> **Objetivo:** alinhar o nome dos arquivos HTTP dos módulos do backend ao padrão do
> Hub. A mudança é **somente estrutural**: o contrato HTTP fica idêntico.

## Antes e depois

```
ANTES                                    DEPOIS
app/modules/<dominio>/router.py          app/modules/<dominio>/controllers.py
app/api/v1/router.py (agregador)         app/api/v1/router.py (agregador, mesmo nome)
```

Dentro de cada `controllers.py`, o objeto continua sendo
`router = APIRouter(...)`. Só mudaram o nome do arquivo e o import no agregador.

## Módulos migrados (12)

Todos os renames foram feitos com `git mv` e têm 100% de similaridade, sem nenhuma
linha de conteúdo alterada:

| Módulo | Arquivo |
|---|---|
| `access` | `router.py` → `controllers.py` |
| `audit` | `router.py` → `controllers.py` |
| `catalogs` | `router.py` → `controllers.py` |
| `comments` | `router.py` → `controllers.py` |
| `dashboard` | `router.py` → `controllers.py` |
| `equipments` | `router.py` → `controllers.py` |
| `notifications` | `router.py` → `controllers.py` |
| `processes` | `router.py` → `controllers.py` |
| `queues` | `router.py` → `controllers.py` |
| `suppliers` | `router.py` → `controllers.py` |
| `users` | `router.py` → `controllers.py` |
| `workflow` | `router.py` → `controllers.py` |

**Imports alterados:** os 12 `from app.modules.<m>.router import router as <m>_router`
em `app/api/v1/router.py` passaram a importar de `app.modules.<m>.controllers`.
Nenhum teste, script ou monkeypatch dependia desses caminhos, e nenhum shim
`router.py` de compatibilidade foi criado.

**Documentação:** a árvore de exemplo em `backend/README.md`, que orienta a criação
de módulos novos, passou a mostrar `controllers.py`. Os registros históricos de
validação (`docs/validation/etapa-06a`, `etapa-06b`, `etapa-07-1` e
`c2-functional-validation`) e a ARCH-00.1 descrevem o código da época e não foram
alterados.

## Fora do escopo (deliberadamente não tocados)

- Módulos de carga e processamento, sem camada HTTP: `monday_import`,
  `supplier_import`, `eap_catalog` e `eap_reconciliation`.
- `service.py` (sem `services.py`), `schemas.py`, `app/models/`, `app/api/v1/auth.py`,
  `app/api/v1/health.py` e o agregador `app/api/v1/router.py`, que só teve os imports
  alterados.
- Frontend, migrations e banco.

## Verificação

| Check | Resultado |
|---|---|
| OpenAPI | **Idêntico** ao `1ee3c08`: SHA-256 `7b3ee2555edb…b251` antes e depois; 59 paths, 87 operações, 121 schemas. O diff estrutural de operationIds, tags, status codes, parâmetros e request/response schemas não teve diferenças. |
| Ruff | `All checks passed!` |
| mypy | `no issues found in 124 source files` |
| pytest | Suíte completa num PostgreSQL 16 isolado: **433 passed, 4 skipped**, 0 falhas. |

## Riscos residuais

- **Branches ou forks** que importem `app.modules.<m>.router` vão quebrar no import,
  um erro imediato e fácil de diagnosticar. Dentro deste repositório não há nenhum.
- **`__pycache__` antigo** com `router.cpython-*.pyc` pode continuar em máquinas
  locais. É inofensivo, porque o Python não importa `.pyc` órfão sem o fonte.
