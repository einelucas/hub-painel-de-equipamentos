# Etapa 01 — primeiro fluxo funcional

## Objetivo

Esta etapa entrega a primeira cadeia vertical do Painel de Equipamentos: PostgreSQL, API FastAPI, filtros globais no Nuxt, tabela operacional, detalhe, componentes, workflow e auditoria.

## Decisões arquiteturais

- O domínio é normalizado e independente da organização visual do Monday.
- `project_context` representa contextos internos de uma unidade, sem criar um terceiro filtro global.
- `equipment.current_stage` é a única fonte de verdade do estágio operacional.
- Toda alteração de estágio passa por `transition_stage`, no backend, e gera `workflow_transition` e auditoria.
- Os estágios aceitos nesta etapa são os valores inteiros de 0 a 8. Não foram criadas regras de pré-condição ainda não confirmadas.
- Filtros, paginação, busca e ordenação são executados no banco. A listagem carrega as relações necessárias sem N+1 e calcula a contagem de componentes por subconsulta.
- O frontend usa respostas `camelCase`; models e banco mantêm nomes de domínio em `snake_case`.
- A criação dos catálogos mínimos foi disponibilizada para ADMIN para que a solução não dependa de inserções manuais.

## Schema e migration

A migration reversível `0002_equipment_domain.py`, sucessora de `0001_shared_base`, cria:

- `unit`;
- `project_context`;
- `area`;
- `discipline`;
- `work_package`;
- `equipment`;
- `equipment_component`;
- `workflow_transition`.

Há chaves estrangeiras, índices de filtros, unicidades por contexto e constraints para etapas 0–8, valores monetários não negativos e prazos não negativos. A migration compartilhada `0001_shared_base` não foi alterada.

## API implementada

Leitura de catálogos:

- `GET /api/v1/units`
- `GET /api/v1/units/{unit_id}/project-contexts`
- `GET /api/v1/areas?unit_id=`
- `GET /api/v1/disciplines`
- `GET /api/v1/work-packages?project_context_id=`

Administração mínima de catálogos (ADMIN):

- `POST /api/v1/units`
- `POST /api/v1/units/{unit_id}/project-contexts`
- `POST /api/v1/areas`
- `POST /api/v1/disciplines`
- `POST /api/v1/work-packages`

Equipamentos e componentes:

- `GET /api/v1/equipments`
- `POST /api/v1/equipments`
- `GET /api/v1/equipments/{equipment_id}`
- `PATCH /api/v1/equipments/{equipment_id}`
- `GET /api/v1/equipments/{equipment_id}/components`
- `POST /api/v1/equipments/{equipment_id}/components`
- `PATCH /api/v1/components/{component_id}`
- `GET /api/v1/dashboard/summary?unit_id=&equipment_id=`

A listagem aceita `unit_id`, `project_context_id`, `equipment_id`, `search`, `stage`, `page`, `pageSize`, `sortBy` e `sortDir`. As chaves permitidas de ordenação são nome, etapa atual, startup e atualização; entradas desconhecidas voltam com segurança para nome.

## Filtros Unidade + Equipamento

O painel carrega as unidades pela API. Uma unidade única é pré-selecionada; com múltiplas unidades existe a visão “Todas as unidades”. O segundo filtro é carregado somente após a escolha da unidade e contém apenas seus equipamentos. Ao trocar a unidade, o equipamento anterior é limpo antes das novas requisições. Na visão de todas as unidades, o filtro de equipamento permanece em “Todos os equipamentos”.

Os IDs válidos são sincronizados em `?unit=<id>&equipment=<id>`. A busca textual é independente e aplicada no backend.

## Frontend

- `pages/dashboard/index.vue`: filtros, métricas, gráfico, tabela, estados de loading/erro/vazio, paginação e abertura do cadastro.
- `pages/equipamentos/[id].vue`: dados mestres, edição, componentes e histórico de transições.
- `components/equipment/EquipmentForm.vue`: criação/edição e mudança estruturada de etapa.
- `components/equipment/ComponentForm.vue`: criação/edição de subitem.
- `composables/useEquipmentDashboard.ts`: coordena filtros, query string e requisições.
- `types/equipment.ts`: contratos tipados da API.

## Permissões

- VIEWER: `equipments:read`, `catalogs:read`.
- ANALYST: permissões de VIEWER e `equipments:write`.
- ADMIN: permissões de ANALYST, `catalogs:manage`, `users:manage` e `audit:read`.

Criação e edição de equipamentos/componentes geram auditoria. Criação de catálogo também é auditada.

## Testes

Backend: `tests/integration/test_equipment_routes.py` cobre catálogos, permissões, estágio inicial, filtros, busca, paginação, relações cruzadas, componentes, resumo, auditoria e histórico.

Frontend: `tests/equipmentFilters.test.ts` cobre pré-seleção, compatibilidade Unidade → Equipamento, limpeza de seleção e parâmetros enviados ao backend. O build/typecheck valida as páginas e componentes Vue.

## Execução local

```powershell
cd backend
uv sync --extra dev
Copy-Item .env.test.example .env.test
.venv\Scripts\python.exe -m alembic upgrade head
.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

Em outro terminal:

```powershell
cd frontend
pnpm install
pnpm dev
```

Validação completa:

```powershell
cd backend
.venv\Scripts\python.exe -m ruff check app tests scripts
.venv\Scripts\python.exe -m mypy app
.venv\Scripts\python.exe -m pytest

cd ..\frontend
pnpm lint
pnpm typecheck
pnpm test
pnpm build
```

Os testes do backend exigem PostgreSQL exclusivo cujo nome termine em `_test`, migrado até `head`.

## Limitações e decisões pendentes

- Standby, Cancelado e Não se Aplica continuam fora do fluxo principal.
- Não há pré-condições finais entre etapas; apenas o intervalo 0–8 é validado.
- Criticidade permanece texto até a taxonomia oficial ser validada.
- Não há fórmula de prazo/risco, índice ou “Total de Aquisições”.
- A seleção de responsável preserva o usuário existente na edição; um catálogo operacional de responsáveis ainda precisa ser definido.
- Não existem seed ou dados reais inventados.

## Proposta para a Etapa 2

- aprofundar negociação e equalização;
- definir jurídico, minuta, contrato, SC/OCI e OC;
- validar regras e pré-condições das transições;
- definir estados especiais;
- definir catálogo de criticidade e responsáveis por unidade/contexto;
- implementar prazos e alertas somente após aprovação das fórmulas;
- planejar integração/migração de C2 e F2 com reconciliação explícita.
