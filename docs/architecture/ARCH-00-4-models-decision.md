# ARCH-00.4 — Decisão sobre models

Baseline: `3c42450`. **Decisão: manter `backend/app/models/` centralizado.** Nenhum model foi movido, nenhum reexport foi criado e nenhuma migration foi gerada.

## Inventário

Medido a partir do `Base.metadata` carregado por `import app.models`:

| Arquivo | Linhas | Conteúdo |
|---|---|---|
| `equipment.py` | 396 | `Unit`, `EapNode`, `ProjectEap`, `ProjectContext`, `Area`, `Discipline`, `WorkPackage`, `EquipmentWorkPackage`, `Equipment`, `EquipmentComponent`, `WorkflowTransition` |
| `workflow_extras.py` | 281 | `Comment`, `OperationalStatusEvent`, `ReopenRequest`, `RequirementWaiver`, `WorkflowException` |
| `monday_import.py` | 171 | `ExternalMapping`, `MondayImportBatch`, `MondayImportRecord`, `MondayImportIssue`, `MondayMigrationRun` |
| `process.py` | 148 | `Negotiation`, `LegalProcess`, `Contract`, `PurchaseRequest`, `PurchaseOrder` |
| `user.py` | 118 | `User`, `Account`, `Session`, `Verification`, `Role` |
| `supplier.py` | 113 | `Supplier`, `SupplierAlias`, `EquipmentSupplier` |
| `notification.py` | 64 | `NotificationEvent` |
| `access.py` | 38 | `UserUnitAccess` |
| `audit.py` | 34 | `AuditLog` |
| `common.py` | 28 | `uuid_pk`, `utcnow`, `Timestamp3` |
| `__init__.py` | 81 | Agrega e reexporta todas as classes; é o ponto de registro do metadata |

São **36 tabelas e 36 classes mapeadas**. `Base` (`DeclarativeBase`) fica em `app/core/database.py`.

## Dependências

**FKs e relationships cruzando arquivos de model:**
- **30 de 53 FKs** cruzam arquivos.
- **36 de 72 `relationship`** cruzam arquivos.
- Há relações **bidirecionais**:
  - `equipment ↔ process` (5 em cada sentido);
  - `equipment ↔ workflow_extras` (5 em cada sentido);
  - `equipment ↔ supplier`.
- `User` é alvo de FKs de `workflow_extras` (7), `equipment` (2), `access`, `audit`, `process` e `monday_import`.

**Imports entre arquivos de model:** `process`, `supplier`, `workflow_extras` e `access` importam `equipment` e/ou `user`. Todos importam `common`.

**Uso pelos módulos** (classes referenciadas, por módulo):

| Model | Módulos que o usam |
|---|---|
| `Equipment` | dashboard, eap_reconciliation, equipments, monday_import, notifications, processes, queues, workflow |
| `ProjectContext` | catalogs, dashboard, eap_catalog, eap_reconciliation, equipments, monday_import, queues, supplier_import |
| `User` | access, audit, equipments, monday_import, notifications, users, workflow |
| `AuditLog` | audit, comments, eap_catalog, eap_reconciliation, monday_import, workflow |
| `WorkflowTransition` | comments, equipments, monday_import, notifications, workflow |

**Volume de imports:** 62 arquivos fora de `app/models/` importam models (154 linhas de import), espalhados por `app/modules`, `app/core`, `app/shared`, `tests` e `scripts`.

**Alembic:** `alembic/env.py` faz `import app.models` e usa `target_metadata = Base.metadata`. As 11 migrations não importam `app.models`.

## Decisão

**Os models permanecem centralizados em `backend/app/models/`, como decisão explícita.** A estrutura dos módulos HTTP é `controllers.py` / `schemas.py` / `services.py`, sem `models.py` por módulo.

## Justificativa, validada no código

1. **Os models são um núcleo compartilhado, não propriedade de um módulo.** `Equipment` é usado por 8 módulos e `ProjectContext` também por 8. Colocá-los em `equipments/models.py` ou em `catalogs/models.py` faria a maioria dos módulos importar outro módulo de domínio.
2. **Os relacionamentos bidirecionais virariam ciclos entre módulos.** `equipment ↔ process ↔ workflow_extras` hoje fica contido em `app/models`. Distribuído, viraria `equipments ↔ processes ↔ workflow`.
3. **Os arquivos de model não seguem as fronteiras dos módulos HTTP.** `equipment.py` contém entidades de catálogo (`Unit`, `ProjectContext`, `EapNode`, `Area`, `Discipline`, `WorkPackage`) e de workflow (`WorkflowTransition`). Mover exigiria redesenhar o particionamento, não só renomear.
4. **O Alembic depende do metadata agregado.** Esquecer um import de model faria o autogenerate enxergar tabelas como removidas.
5. **Custo e risco altos com benefício funcional nulo.** Seriam 62 arquivos alterados, com risco em ordem de mapeamento, `relationship` por string e migrations, sem nenhuma melhoria para o produto.

**Reexports por módulo** (`modules/<x>/models.py` só com `from app.models... import ...`) **também foram rejeitados.** Criariam dois caminhos de import para a mesma classe, sem ganho.

## Riscos evitados

- Imports circulares entre módulos de domínio.
- Falhas de configuração de mapper do SQLAlchemy por ordem de import.
- Autogenerate do Alembic propondo `DROP TABLE` por metadata incompleto.
- Diff massivo misturado com mudanças funcionais.
- Divergência entre o estado do código e o estado das migrations.

## Quando reavaliar

- Se um domínio passar a ter tabelas próprias, **sem FKs de entrada de outros domínios**, e for extraído como serviço ou pacote independente.
- Se o volume de models crescer a ponto de `app/models/` ficar difícil de navegar. Nesse caso, primeiro subdividir **dentro** de `app/models/` (por exemplo, separar o catálogo de `equipment.py`), mantendo o `__init__.py` agregador.
- Se a organização do Hub definir um padrão de pacotes por bounded context que inclua persistência e migrations separadas.
