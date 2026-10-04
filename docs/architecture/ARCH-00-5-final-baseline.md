# ARCH-00.5 — Regressão final e baseline arquitetural do Hub

## 1. Objetivo da ARCH-00

Alinhar o Painel de Equipamentos ao padrão arquitetural do Hub antes de retomar o produto:

- CI confiável;
- cliente HTTP do frontend padronizado;
- convenção `controllers.py` / `schemas.py` / `services.py` nos módulos HTTP;
- decisões explícitas sobre models e módulos de processamento.

Tudo isso **sem mudança funcional**: endpoints, contrato OpenAPI, banco, migrations e regras de negócio inalterados.

## 2. Baseline inicial

`main` @ `7192beb` (`fix: apply approved EAP tree corrections`). A CI estava quebrada no frontend (toolchain) e no backend (Ruff/mypy).

## 3. ARCH-00.1 — Estabilização da CI e análise de lacunas (`bf85297`)

- **CI:** passou a usar pnpm 11.15.1 e Node 24, alinhados ao lockfile, com `postinstall: nuxt prepare`.
- **Backend:** Ruff zerado e anotação de tipo para o mypy.
- **Análise das quatro mudanças:** router→controllers, service→services, models e `$fetch`→Axios, com ordem e risco de cada uma.

Detalhes: [`ARCH-00-1-stack-gap-analysis.md`](ARCH-00-1-stack-gap-analysis.md).

## 4. ARCH-00.1.1 — Suíte de integração alinhada ao contrato (`1d5a184`)

Testes de integração ajustados ao contrato vigente da API, deixando a CI oficial verde antes das refatorações.

## 5. ARCH-00.2 — `$fetch` → Axios (`1ee3c08`)

O Axios fica atrás do `useApi`, com instância única em `services/api/http.ts`. Páginas, componentes e stores não importam Axios. Detalhes: [`ARCH-00-2-axios.md`](ARCH-00-2-axios.md).

## 6. ARCH-00.3a — `router.py` → `controllers.py` (`f3b589f`)

12 módulos HTTP, com OpenAPI idêntico. Detalhes: [`ARCH-00-3a-controllers.md`](ARCH-00-3a-controllers.md).

## 7. ARCH-00.3b — `service.py` → `services.py` (`43c37f8`)

12 módulos HTTP, com imports e dependências cruzadas atualizados e OpenAPI idêntico. Detalhes: [`ARCH-00-3b-services.md`](ARCH-00-3b-services.md).

## 8. Segurança do banco de testes (`3c42450`)

**Incidente:** uma execução local do pytest carregou o `.env.test` com `override=True` e truncou o `neondb_test` remoto.

**Correção:**
- preflight puro (`tests/db_safety.py`) antes de qualquer import de `app`;
- exige localhost, banco `*_test`, `APP_ENV=test` e `ALLOW_DESTRUCTIVE_TESTS=true`, também para `MIGRATION_DATABASE_URL`;
- `override=False`;
- segunda barreira mantida no teardown;
- 35 testes da guarda, incluindo um bloqueio real sem rede.

Detalhes: [`ARCH-00-test-database-safety.md`](ARCH-00-test-database-safety.md).

## 9. ARCH-00.3c — Módulos não HTTP

`monday_import`, `supplier_import`, `eap_catalog` e `eap_reconciliation` são pipelines de processamento por CLI. Ficam como exceções deliberadas, com estrutura especializada e sem `controllers.py` artificial. `monday_import/service.py` mantém o nome. Nenhum shim foi criado. Detalhes: [`ARCH-00-3c-non-http-modules.md`](ARCH-00-3c-non-http-modules.md).

## 10. ARCH-00.4 — Models

`app/models/` **permanece centralizado** por decisão explícita:
- 36 tabelas;
- 30 de 53 FKs e 36 de 72 relationships cruzam arquivos, com relações bidirecionais `equipment ↔ process/workflow_extras`;
- o Alembic depende do metadata agregado;
- 62 arquivos importam models.

Não foi criado nenhum reexport por módulo. Detalhes: [`ARCH-00-4-models-decision.md`](ARCH-00-4-models-decision.md).

## 11. Arquitetura final

```
Frontend   Nuxt 4 · Vue 3 · TypeScript · Pinia · Axios atrás de useApi

Backend    FastAPI
  app/api/v1/router.py           agrega os controllers
  app/modules/<dominio>/         12 módulos HTTP
      controllers.py             rotas (APIRouter)
      schemas.py                 contratos HTTP (Pydantic)
      services.py                regras/orquestração
      [arquivos especializados]  ex.: workflow/stages.py, notifications/adapter.py
  app/models/                    models SQLAlchemy centralizados (decisão ARCH-00.4)
  app/domain/, app/shared/       cálculos de domínio e utilitários compartilhados

Processamento (CLI, sem HTTP — exceções ARCH-00.3c)
  monday_import/  supplier_import/  eap_catalog/  eap_reconciliation/

Persistência  PostgreSQL · SQLAlchemy async · Alembic (head 0011_eap_foundation)
```

## 12. OpenAPI final

**Método canônico** (vale daqui em diante):

```python
data = json.dumps(app.openapi(), sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
sha256(data)
```

O método foi aplicado com o mesmo script, o mesmo interpretador e o mesmo ambiente sobre snapshots `git archive` de cada commit, sem nenhuma conexão de banco:

| Commit | SHA-256 canônico | Paths | Operações | Schemas |
|---|---|---|---|---|
| `1ee3c08` | `703d8509adf6ba6eba5e84f2c13ca9140e175e6fd881b3f50f092a436216dbf8` | 59 | 87 | 121 |
| `f3b589f` | idem | 59 | 87 | 121 |
| `43c37f8` | idem | 59 | 87 | 121 |
| `3c42450` (HEAD inicial) | idem | 59 | 87 | 121 |

**Comparação estrutural:** idêntica em todos os commits nos seguintes eixos:
- paths (59);
- métodos (87);
- operationIds (87, únicos);
- tags (12);
- parâmetros;
- request bodies (44 operações);
- response models;
- status codes (200/201/204/422);
- `components/schemas` (121).

**A divergência histórica era só de serialização.** Os dois hashes antigos foram reproduzidos exatamente, a partir do mesmo spec, em todos os commits:

| Etapa | Hash reportado | Serialização usada na época |
|---|---|---|
| ARCH-00.3a | `7b3ee2555edb…b251` | `json.dumps(spec, sort_keys=True, indent=1, ensure_ascii=False)`, UTF-8, sem `\n` final |
| ARCH-00.3b | `62f8462d71ad…b929` | `json.dumps(spec, sort_keys=True, indent=2, ensure_ascii=False) + "\n"`, UTF-8 |

Não houve mudança de contrato em nenhuma etapa da ARCH-00.

## 13. Regressão backend

PostgreSQL 16.10 local, temporário e descartável (`localhost`, banco `painel_equipamentos_final_test`), com `APP_ENV=test` e `ALLOW_DESTRUCTIVE_TESTS=true`, sobre o HEAD `3c42450`.

| Etapa | Resultado |
|---|---|
| `alembic upgrade head` | OK, `0011_eap_foundation (head)` |
| `ruff check app tests scripts` | All checks passed |
| `mypy app` | Success, 124 arquivos |
| `pytest` | **472 passed, 0 skipped, 0 failed**, 779,81s (12min59s), exit code 0 |

**Execução anterior descartada (registro de transparência).** A primeira execução, feita em paralelo com o build do frontend e com a geração dos snapshots do OpenAPI, terminou em 1 failed / 471 passed (24min42s). Quem falhou foi `test_conftest_aborts_on_fake_neon_url_before_importing_app`, por `subprocess.TimeoutExpired` (120s) ao iniciar o pytest filho.

Isolado, o mesmo teste passa em 1,6s, e o subprocesso puro leva 1,4s. Na reexecução sem carga concorrente, acima, ele passou. Nenhum teste altera o ambiente do processo.

**Classificação:** flake de infraestrutura (máquina saturada), não regressão. Não foi usado retry automático. **Risco residual:** o teste depende de iniciar um interpretador filho dentro de 120s. Em CI com runner muito carregado, ele pode voltar a oscilar.

Os 4 testes que dependem dos exports versionados em `references/monday_exports/` rodam e passam quando a suíte executa dentro do repositório. Numa cópia só de `backend/`, eles aparecem como skipped.

## 14. Regressão frontend

| Etapa | Resultado |
|---|---|
| `pnpm install --frozen-lockfile` | OK |
| `pnpm lint` | OK |
| `pnpm typecheck` | OK |
| `pnpm test` | 32 arquivos, **286 testes passed** |
| `pnpm build` | Build complete |

## 15. CI

A CI oficial (GitHub Actions) está verde no `3c42450`, assim como em `f3b589f`, `1ee3c08` e `1d5a184`. O backend usa só o service `postgres:16-alpine` temporário, com `ALLOW_DESTRUCTIVE_TESTS=true`.

## 16. Dívidas deixadas deliberadamente para o produto

**Dados**
- O `neondb_test` não contém mais a carga C2. **Ela não será restaurada agora**: os dados reais serão reimportados na validação/UAT, a partir dos exports LEM/C2, que continuam sendo a fonte. Dados não são requisito para concluir o desenvolvimento.

**Contrato e documentação**
- Docstring de `dashboard/schemas.py` cita `dashboard/service.py` e aparece na descrição do schema `NegotiationDeadlineStatusSummaryOut`. Só deve ser corrigida junto com uma mudança de contrato aceita.
- Documentação técnica não canônica (`docs/arquitetura.md`, `docs/Auditoria_Tecnica_Funcional_*`, `docs/etapa-02-*`, `docs/migration/*`) ainda cita `routers` e `service.py`. Os registros históricos em `docs/validation/` permanecem como estão.

**Ambiente local**
- O `backend/.env.test` local deve ser trocado pelo modelo de `.env.test.example`. A guarda já recusa a versão atual, que aponta para host remoto.

**Frontend (não bloqueante)**
- Aviso de chunk acima de 500 kB no build.
- 14 avisos `Failed to resolve component` nos testes, em componentes não registrados nos stubs.

**Testes**
- Monitorar `test_conftest_aborts_on_fake_neon_url_before_importing_app` (seção 13). Se oscilar na CI, aumentar o timeout do subprocesso, sem enfraquecer as asserções.

## 17. Encerramento

Confirmações finais:
- módulos HTTP com `controllers.py` / `schemas.py` / `services.py`;
- módulos não HTTP com estrutura especializada, incluindo `monday_import/service.py` mantido deliberadamente;
- models centralizados em `backend/app/models/`, sem nenhum model movido e sem nenhuma migration criada;
- nenhuma regra funcional alterada;
- frontend verde e sem alterações;
- OpenAPI canônico idêntico;
- nenhum banco remoto acessado nas validações desta etapa.

**A ARCH-00 está encerrada.** O baseline arquitetural do Hub fica registrado neste documento e no commit que o introduz.

A próxima atividade deixa de ser ARCH-00. A próxima prioridade é **P1.1 — Motor genérico de importação Monday**: novo board → mapping/configuração → pipeline existente → Hub, sem criar módulos específicos por obra.

## Anexo — Atualizações para os documentos canônicos 00–06

Os documentos `00_INSTRUCOES_MESTRAS_DO_PROJETO.md` a `06_MAPA_DO_REPOSITORIO.md` são **fontes canônicas externas ao repositório** e por isso não foram criados nem editados aqui. As atualizações necessárias estão listadas abaixo para aplicação posterior, onde esses documentos são mantidos. Elas substituem apenas o que ficou obsoleto. Regras de domínio, EAP, prefixos, fornecedor, cardinalidades, workflow, LGE, Monday e ProjectContext não mudam.

| Documento | Atualização |
|---|---|
| 00 — Instruções mestras | O pytest só roda contra PostgreSQL **local** (`localhost`, `*_test`, `ALLOW_DESTRUCTIVE_TESTS=true`). É proibido usar banco remoto (Neon/DEV/produção) na suíte. Convenção HTTP: `controllers/schemas/services`. Models centralizados. |
| 01 — Estado atual | CI verde. ARCH-00 encerrada (baseline neste doc). `neondb_test` sem a carga C2, sem restauração por ora. Próxima prioridade: P1.1. |
| 02 — Arquitetura e stack | Axios atrás de `useApi` implementado. `router.py`→`controllers.py` e `service.py`→`services.py` concluídos nos 12 módulos HTTP. `app/models/` centralizado (ARCH-00.4). Módulos de processamento como exceções (ARCH-00.3c). Guarda do banco de testes. Hash OpenAPI canônico `703d8509…`. |
| 03 — Regras de domínio e EAP | Nenhuma alteração. Só registrar, se citado, que o estado C2 no `neondb_test` não existe mais. |
| 04 — Migração Monday e fontes | Os exports LEM/C2 em `references/monday_exports/` seguem como fonte da reimportação futura (UAT). O motor genérico de importação é a P1.1. |
| 05 — Decisões, pendências e roadmap | Decisões ARCH-00.3c, ARCH-00.4 e de segurança do banco de testes. Pendências da seção 16. Roadmap: P1.1 em seguida. |
| 06 — Mapa do repositório | `modules/<dominio>/{controllers,schemas,services}.py`, `tests/db_safety.py`, `docs/architecture/ARCH-00-*`, `monday_import/service.py` como exceção nomeada. |
