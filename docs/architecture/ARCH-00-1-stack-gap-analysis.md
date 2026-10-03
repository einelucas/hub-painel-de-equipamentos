# ARCH-00.1 — Estabilização da CI e análise de lacunas da stack

> **Baseline:** `main` @ `7192beb95573878865b907e8730ae30a81a7f7e5`.
> **Escopo:** estabilizar a CI e levantar a distância entre a arquitetura atual e o
> padrão alvo do Hub/Automação. **Nenhuma refatoração arquitetural foi feita.** Nada
> foi movido nem renomeado, não houve troca de cliente HTTP, e endpoints, payloads,
> banco e migrations ficaram inalterados.

Classificação de risco usada neste documento:

| Risco | Significado |
|---|---|
| **BAIXO RISCO** | Mudança estrutural com detecção automática de erro (import quebrado falha no mypy, no pytest ou no typecheck). |
| **MÉDIO RISCO** | Exige revisão manual de comportamento, ou toca código com acoplamento relevante. |
| **ALTO RISCO** | Pode alterar comportamento em runtime sem que os testes atuais detectem, ou envolve persistência e migrations. |

---

## 1. Estado da CI (o que estava quebrado e o que foi feito)

### 1.1 Frontend

A CI fixava **pnpm 9** e **Node 20**. O projeto, porém, é instalado com **pnpm 11.15.1**
(é o que gera o lockfile atual) e usa Nuxt 4.5.2. Havia três defeitos encadeados:

| # | Sintoma | Causa real | Correção |
|---|---|---|---|
| F1 | `packages field missing or empty` | O pnpm 9 exige `packages` quando existe `pnpm-workspace.yaml`; o arquivo só tem `allowBuilds` e `overrides` (configurações do pnpm 11). | **Não** foi preciso mexer no `pnpm-workspace.yaml`. Adicionar só `packages` foi testado e **não basta**: o pnpm 9 então falha com `ERR_PNPM_LOCKFILE_CONFIG_MISMATCH`, porque não lê `overrides` desse arquivo e o lockfile registra o override `@vitejs/plugin-vue>vite`. A causa é a versão: a CI passou a usar `pnpm 11.15.1`. |
| F2 | (seria o próximo erro) | O Nuxt 4.5.2 travado no lockfile exige Node `^22.19 \|\| ^24.11`; o pnpm 11 exige Node `>=22.13`. | A CI passou a usar **Node 24**, o mesmo do ambiente local. |
| F3 | `pnpm lint` falha numa instalação limpa (`Cannot find module .nuxt/eslint.config.mjs`) | O `eslint.config.mjs` importa `./.nuxt/eslint.config.mjs`, gerado pelo `nuxt prepare`, e nada o gerava depois do `install`. Localmente passava só porque o `.nuxt/` já existia. | Script padrão do Nuxt `"postinstall": "nuxt prepare"` em `frontend/package.json`. |

Nenhuma dependência foi atualizada. O `pnpm-lock.yaml` e o `pnpm-workspace.yaml`
(`allowBuilds`/`overrides`) ficaram intactos.

**Validação:** cópia limpa do `HEAD` (via `git archive`, sem `node_modules`, `.nuxt` ou `.output`), na
ordem da CI: `install --frozen-lockfile` → `lint` → `typecheck` → `test` (31 arquivos, 254
testes) → `build`, tudo passando. A mesma régua também passou no diretório real.

> Dois falsos negativos de ambiente apareceram durante a investigação e **não** são defeitos do
> projeto: `esbuild.exe ENOENT` (limite de 260 caracteres de caminho no Windows, só na pasta temporária)
> e `vue-router` não resolvido (artefato do `subst`). A CI roda Linux.

### 1.2 Backend

`python -m ruff check app tests scripts` acusava 46 erros: 33 E501, 7 F401, 4 ASYNC230 e
2 I001. Nenhum estava em `app/`; eram todos de scripts de verificação e de 4 linhas de teste.
Também havia **1 erro de mypy preexistente** em `app/`.

| Grupo | Arquivos | Correção | Prova de que não muda comportamento |
|---|---|---|---|
| E501 (33) | 10 arquivos (`scripts/`, 2 testes) | Quebra manual e pontual de linha (o `ruff format` alteraria ~370 linhas, por isso não foi usado) | AST idêntica ao `HEAD` |
| F401 (7) + I001 (2) | 7 scripts | Remoção de import não usado e reordenação, com `--fix` restrito a essas regras e esses arquivos | AST idêntica fora dos nós de import |
| ASYNC230 (4) | `audit_c2_db.py`, `seed_c2_catalog.py`, 2 `inspect_*` | Escrita do arquivo de saída movida para função síncrona (`_write_json`/`_write_text`) com os mesmos argumentos | Diff revisado: mesmos caminhos, encoding e argumentos de `json.dump` |
| mypy (1) | `app/modules/dashboard/service.py` | Anotação de retorno `-> EquipmentDeadlineAggregates` em `_component_deadline_aggregates` | AST idêntica fora da anotação e do import; só tipagem |

**Resultado:** Ruff 0 erros; mypy limpo (124 arquivos); 266 testes unitários passando;
coleta da suíte completa com 437 testes, dos quais 171 de integração.

> **Testes de integração não executados localmente:** eles fazem `TRUNCATE` no banco de teste
> configurado (`neondb_test`), que guarda o estado validado do LEM/C2 e do catálogo EAP. O banco
> está fora do escopo desta etapa. Na CI eles rodam contra o Postgres efêmero do próprio workflow.
> As únicas mudanças em testes de integração são de formatação, com AST idêntica.

---

## 2. Frontend — inventário

### 2.1 Stack

| Item | Versão resolvida |
|---|---|
| Nuxt | 4.5.2 |
| Vue | 3.5.41 |
| Pinia / @pinia/nuxt | 3.0.4 / 0.11.3 |
| TypeScript | 5.9.3 (`strict: true`) |
| Vitest | 3.2.7 (happy-dom) |
| Cliente HTTP | `$fetch` (ofetch, embutido no Nuxt) — **Axios não é dependência** |
| Gerenciador | pnpm 11.15.1 |

### 2.2 Camada HTTP atual

- **Centralizada** em `frontend/composables/useApi.ts`. Uma função `request<T>(path, options)` usa
  `$fetch` e expõe os atalhos `get`, `post`, `put`, `patch` e `delete`, além do próprio `request`.
- **baseURL:** `useRuntimeConfig().public.apiBaseUrl` (env `NUXT_PUBLIC_API_BASE_URL`, padrão
  `http://localhost:8000/api/v1`), normalizada para terminar em `/api/vN`.
- **Autenticação:** header `Authorization: Bearer <token>` lido de `useAuthStore().token`, que é um
  cookie `painel_equipamentos_access_token` (OIDC ou bypass de desenvolvimento `dev-<role>`). Não há
  refresh de token nem tratamento central de 401 (sem redirect).
- **Erros:** todo erro vira `ApiError(message, status, data)` (`services/api/error.ts`), com a
  mensagem extraída de `detail` (string ou lista do FastAPI), `message` ou `error`.
- **Consumidores:** 24 arquivos chamam `useApi()` (26 chamadas): 14 componentes, 2 composables,
  6 páginas e 2 stores (incluindo `stores/auth.ts`).
- **Chamadas fora do `useApi`:** **nenhuma.** Não há `$fetch`, `fetch(`, `useFetch`,
  `useAsyncData`, `ofetch`, `XMLHttpRequest` nem `axios` fora de `composables/useApi.ts`.
- **Vazamento de API do ofetch:** a assinatura de `request()` é `Parameters<typeof $fetch>[1]`, ou
  seja, aceita opções nativas do ofetch. **Um** consumidor usa isso:
  `components/equipment/EquipmentContractsList.vue` faz upload (`body: FormData`, `PUT`) e download
  (`responseType: "blob"`) de contrato.
- **Testes:** 7 arquivos de teste mockam `useApi` via `vi.stubGlobal("useApi", …)` com
  `{ get, post, patch, … }`. Nenhum teste depende de `$fetch`.

### 2.3 Impacto de `$fetch` → Axios **dentro** do `useApi`

| Aspecto | Avaliação |
|---|---|
| Mudança | Trocar a implementação de `request()`: instância Axios com `baseURL` do runtime config e interceptor de request (Bearer) e de response (erro → `ApiError`). Mapear `query` → `params` e `body` → `data`. |
| Contrato público | Manter **idêntica** a assinatura de `get/post/put/patch/delete` e a classe `ApiError`. Os 24 consumidores e os 7 testes mockados não mudam. |
| Ponto de atenção | `request()` precisa de uma assinatura **própria** (não mais `Parameters<typeof $fetch>`), com equivalentes para `responseType: "blob"` e `FormData`. Isso afeta `EquipmentContractsList.vue`. |
| Diferenças de semântica a preservar | `$fetch` serializa `query` omitindo `undefined`; Axios mantém `params` com `undefined` de forma diferente (testar filtros do dashboard e das filas). `$fetch` lança erro em status ≥400, assim como o Axios; a extração de `response._data` vira `error.response.data`. Com `responseType: "blob"`, o Axios devolve `data` como `Blob`. |
| SSR | O `useApi` roda no cliente (token em cookie). Se algum dia rodar no servidor, a instância Axios precisa ser criada por requisição (não global). |
| Dependência nova | `axios` (pacote único). Não exige upgrade de Nuxt/Vue. |
| Risco | **MÉDIO RISCO**: contrato externo estável e consumidores isolados, mas a semântica de `query`, erro e blob precisa de testes próprios do `useApi` (hoje não há teste unitário do `useApi`). |

**Arquivos que provavelmente mudam:** `frontend/composables/useApi.ts`,
`frontend/services/api/error.ts` (adaptar a leitura do erro do Axios),
`frontend/components/equipment/EquipmentContractsList.vue` (opções de upload/download),
`frontend/package.json` e `frontend/pnpm-lock.yaml` (dependência `axios`), além de um teste novo
`frontend/tests/useApi.test.ts`.

**Arquivos que não deveriam mudar:** os outros 23 consumidores do `useApi` (páginas,
componentes, `stores/auth.ts`, `stores/moduleContext.ts`, `composables/useQueue.ts`,
`composables/useEquipmentWorkflow.ts`), os 7 testes que mockam `useApi`, `nuxt.config.ts`
e os tipos em `types/`.

**Recomendação:** `useApi` → Axios, encapsulado. **Nunca** importar `axios` em páginas e
componentes. O `useApi` continua sendo o único ponto HTTP, inclusive para upload e download.

---

## 3. Backend — inventário por módulo

Composição de rotas: `app/api/v1/router.py` importa `router` de 12 módulos e os inclui; `app/main.py`
monta tudo em `/api/v1`. Os SQLAlchemy models ficam **centralizados** em `app/models/`. Regras
puras ficam em `app/domain/` (EAP, prazos).

| Módulo | Linhas | Arquivos | router | schemas | service | Especializados | Models centrais | Adaptação ao padrão alvo | Risco |
|---|---|---|---|---|---|---|---|---|---|
| access | 196 | router, schemas, service | sim | sim | sim | — | access, equipment, user | renomear router/service | BAIXO RISCO |
| audit | 178 | router, schemas, service | sim | sim | sim | — | audit, user | renomear | BAIXO RISCO |
| catalogs | 625 | router, schemas, service | sim | sim | sim | — | equipment | renomear | BAIXO RISCO |
| comments | 218 | router, schemas, service | sim | sim | sim | — | workflow_extras | renomear | BAIXO RISCO |
| dashboard | 448 | router, schemas, service | sim | sim | sim | — | equipment, process | renomear | BAIXO RISCO |
| equipments | 1170 | router, schemas, service | sim | sim | sim | — | equipment, user, supplier | renomear; `service` importado em **14** pontos | MÉDIO RISCO |
| notifications | 206 | router, schemas, service, **adapter** | sim | sim | sim | `adapter.py` | notification, equipment, user, common | renomear; manter `adapter.py` | BAIXO RISCO |
| processes | 905 | router, schemas, service | sim | sim | sim | — | equipment, process | renomear (`service` em 6 pontos) | BAIXO RISCO |
| queues | 577 | router, schemas, service | sim | sim | sim | — | equipment, process, supplier, workflow_extras | renomear | BAIXO RISCO |
| suppliers | 604 | router, schemas, service | sim | sim | sim | — | supplier | renomear | BAIXO RISCO |
| users | 263 | router, schemas, service | sim | sim | sim | — | user | renomear | BAIXO RISCO |
| workflow | 1827 | router, schemas, service, **stages, waivers, reopen, operational_status** | sim | sim | sim | 4 arquivos de regra | equipment, user, process, audit, supplier, workflow_extras, common | renomear; máquina de estados com transações e bloqueios (`service` em 9 pontos) | MÉDIO RISCO |
| eap_catalog | 937 | catalog, tree, seed, cli, `__main__` | não | não | não | extração/seed (CLI) | equipment | **Não é módulo HTTP.** Não precisa de `controllers.py` | n/a (não adaptar) |
| eap_reconciliation | 1254 | reconcile, monday, apply, database, report, cli, `__main__` | não | não | não | reconciliação/apply (CLI) | equipment, monday_import | Não é módulo HTTP | n/a (não adaptar) |
| monday_import | 3868 | parser, xlsx, plan, apply, reconciliation, domain_reconciliation, mapping_file, mappings, normalization, dry_run, safety, calculations, schemas, service, cli, `__main__` | não | sim | sim | 13 arquivos de pipeline | equipment, user, process, monday_import, audit, common | Não é módulo HTTP; `service`/`schemas` têm papel interno | n/a (não adaptar agora) |
| supplier_import | 1119 | workbook, plan, database, cli, `__main__` | não | não | não | carga (CLI) | equipment, supplier, monday_import | Não é módulo HTTP | n/a (não adaptar) |

**Observações:**

- Os 12 módulos HTTP já seguem **router + schemas + service**. Para o padrão alvo falta só a
  **nomenclatura** (`controllers.py`, `services.py`). Não há lógica de negócio nos routers que precise
  ser extraída antes.
- Os 4 módulos de carga (CLI) são **fronteiras administrativas sem endpoint**. Forçá-los a ter
  `controllers.py` seria artificial. Recomenda-se documentá-los como exceção ao padrão ("módulos de
  pipeline").
- Não há nenhuma referência em **string** a `app.modules.*.service` ou `*.router` (como
  `monkeypatch.setattr("…")`). Toda referência é import normal, detectado por mypy e pytest.

---

## 4. As quatro mudanças, analisadas separadamente

### A) `router.py` → `controllers.py`

| Item | Avaliação |
|---|---|
| Benefício | Nomenclatura alinhada ao padrão Hub/Automação. |
| Imports afetados | 1 import por módulo, todos em `app/api/v1/router.py` (12 linhas). Nenhum teste importa router diretamente. |
| Testes afetados | Nenhum arquivo de teste muda; os testes de rota usam a app via HTTP. |
| Estrutura × comportamento | **Só estrutura.** Paths, operações, `operationId` e OpenAPI não mudam: o FastAPI gera o `operationId` pelo nome da função, não do arquivo. |
| Verificação | Comparar `openapi.json` antes e depois (`scripts/export_openapi.py`); ele deve ser **idêntico**. |
| Risco | **BAIXO RISCO** |

### B) `service.py` → `services.py`

| Item | Avaliação |
|---|---|
| Benefício | Nomenclatura alinhada. |
| Imports afetados | ~51 imports em `app`, `tests` e `scripts`. Os maiores focos são `equipments` (14), `workflow` (9) e `processes` (6). Inclui imports entre módulos, como `workflow` usando `equipments.service`. |
| Testes afetados | Testes que importam funções de service diretamente (unitários e integração) só têm o import atualizado. |
| Estrutura × comportamento | **Só estrutura**, se feita como renomeação pura (`git mv` + atualização de imports). |
| Cuidado | `monday_import/service.py` e `catalogs/service.py` são importados por scripts e CLIs. Renomear o `monday_import` não é necessário (não é módulo HTTP). |
| Risco | **BAIXO RISCO** por módulo; **MÉDIO RISCO** para `equipments` e `workflow` pelo volume de imports cruzados. |

### C) Models centralizados → `models.py` por módulo

| Item | Avaliação |
|---|---|
| Situação real | 10 arquivos em `app/models/` com 37 classes e 72 arquivos que importam `app.models`. `models/equipment.py` (11 classes, 58 `relationship`/`ForeignKey`) é usado por **12 dos 16 módulos**; `models/user.py` por 7; `models/process.py` e `models/supplier.py` por 5 cada. |
| Natureza | Os models são um **núcleo de domínio compartilhado** (Equipment, ProjectContext, EapNode e outros são usados por quase todos os módulos), não propriedade de um módulo. |
| Benefício | Baixo. Mover `Equipment` para `equipments/models.py` faria outros 11 módulos importarem de `equipments`, criando acoplamento entre módulos maior que o atual. |
| Riscos | Ordem de import e mapeamento do SQLAlchemy (`relationship` por string entre arquivos, `TYPE_CHECKING`); **Alembic** depende de `import app.models` para registrar todo o `metadata` (autogenerate pode passar a ver tabelas "removidas" se algum model deixar de ser importado); risco de imports circulares; diff muito grande. |
| Testes afetados | Potencialmente todos (72 arquivos importam models). |
| Estrutura × comportamento | Estrutura, mas com **risco real de efeito em runtime** (mapeamento, metadata, migrations). |
| Alternativa de baixo risco | Manter `app/models/` como fonte de verdade e, se o padrão exigir `models.py` por módulo, criar arquivos **fachada** que só reexportam (`from app.models.equipment import Equipment`). Sem mover classes nem tocar no Alembic. |
| Risco (mover de fato) | **ALTO RISCO** |
| Recomendação | **Não mover.** Decidir na ARCH-00.4 entre manter centralizado (documentado como decisão) ou criar fachadas. |

### D) `$fetch` → Axios

Ver §2.3: **MÉDIO RISCO**, só estrutura se o contrato do `useApi` for preservado. Exige testes
novos para `query`, erro e blob.

### Ordem recomendada

1. **D** (frontend), isolada do backend, com testes próprios do `useApi`.
2. **A** (rename de routers), de impacto mínimo, verificado pelo OpenAPI idêntico.
3. **B** (rename de services), módulo a módulo, começando pelos pequenos e deixando
   `equipments` e `workflow` por último.
4. **C** só depois de uma decisão explícita, e de preferência na forma de fachadas.

---

## 5. Proposta das próximas etapas (não executadas)

| Etapa | Escopo | Critério de pronto | Risco |
|---|---|---|---|
| **ARCH-00.2** | Frontend: `$fetch` → Axios **dentro** do `useApi`; assinatura própria de `request()` (cobrindo blob e FormData); `ApiError` preservado; testes unitários novos do `useApi` (`query`, Bearer, erro FastAPI 4xx/422, blob). | CI verde; os 24 consumidores sem alteração (exceto `EquipmentContractsList.vue`); upload e download de contrato verificados manualmente. | MÉDIO |
| **ARCH-00.3a** | Backend: `router.py` → `controllers.py` nos 12 módulos HTTP, num commit só. | `openapi.json` idêntico ao baseline; CI verde. | BAIXO |
| **ARCH-00.3b** | Backend: `service.py` → `services.py`, um módulo por commit (`access`, `audit`, `catalogs`, `comments`, `dashboard`, `notifications`, `suppliers`, `users`, `queues`, `processes`, depois `equipments` e por fim `workflow`). | Por commit: mypy e pytest verdes, `openapi.json` idêntico. | BAIXO → MÉDIO |
| **ARCH-00.3c** | Documentar os módulos de pipeline (`monday_import`, `supplier_import`, `eap_catalog`, `eap_reconciliation`) como exceção ao padrão HTTP. | Documento de convenções atualizado. | BAIXO |
| **ARCH-00.4** | Decisão sobre models: manter centralizado (recomendado) ou fachadas `models.py` por módulo. Mover classes só com uma justificativa concreta. | Decisão registrada; se houver fachadas, `alembic check` sem diferença de metadata. | BAIXO (fachada) / ALTO (mover) |
| **ARCH-00.5** | Regressão completa: CI no GitHub (incluindo os 171 testes de integração no Postgres efêmero), smoke manual das telas principais e novo baseline com tag. | CI verde no GitHub; OpenAPI e payloads idênticos ao baseline `7192beb`. | — |

**Pré-requisito sugerido antes da ARCH-00.2:** confirmar no GitHub Actions que esta
ARCH-00.1 deixa a CI verde de ponta a ponta. A execução local não cobre os testes de
integração (ver §1.2).
