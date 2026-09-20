# Painel de Equipamentos

Módulo **Painel de Equipamentos**, pertencente à área de **Planejamento** do Hub.

O repositório contém o domínio operacional: catálogos, equipamentos, componentes, processo de aquisição, máquina de estados 0–8, fornecedores, autorização por unidade, auditoria, dashboard consolidado, filas por área e detalhe do equipamento integrados.

## Stack

- Frontend: Nuxt 4, Vue 3, TypeScript, Pinia e Tailwind CSS
- Backend: FastAPI, Pydantic v2 e SQLAlchemy assíncrono
- Persistência: PostgreSQL + Alembic
- Autenticação: OIDC/Keycloak, com bypass controlado para desenvolvimento
- Auditoria: trilha genérica para ações administrativas

## Estrutura

```text
painel-de-equipamentos/
├── backend/
│   ├── app/
│   │   ├── api/v1/
│   │   ├── core/
│   │   ├── models/
│   │   ├── modules/
│   │   │   ├── audit/
│   │   │   ├── catalogs/
│   │   │   ├── dashboard/
│   │   │   ├── equipments/
│   │   │   ├── access/
│   │   │   ├── processes/
│   │   │   ├── queues/
│   │   │   ├── suppliers/
│   │   │   ├── users/
│   │   │   └── workflow/
│   │   └── shared/
│   ├── alembic/
│   ├── scripts/
│   └── tests/
├── frontend/
│   ├── components/
│   │   ├── charts/
│   │   ├── layout/
│   │   └── ui/
│   ├── composables/
│   ├── layouts/
│   ├── middleware/
│   ├── pages/
│   ├── public/brand/
│   ├── services/
│   ├── stores/
│   └── utils/
└── docs/
```

Os componentes `BarChart.vue`, `DonutChart.vue`, `LineChart.vue` e `UnitProgressBars.vue` permanecem disponíveis em `frontend/components/charts/` para uso futuro.

## Etapa funcional atual

A navbar do módulo dá acesso a seis telas: **Dashboard**, **Equipamentos**, **Engenharia**, **Jurídico**, **Suprimentos** e **Auditoria** (esta só com permissão). Unidade e Equipamento são filtros globais compartilhados por todas elas e sincronizados com a URL.

O **Dashboard Geral** em `/dashboard` reúne totais, valor emitido em OC, CAPEX, distribuição pelas etapas 0–8, situação geral, negociação e próxima startup. Indicadores sem fórmula oficial — como a situação de prazos — aparecem explicitamente como não calculados, nunca estimados.

As filas `/engenharia`, `/juridico` e `/suprimentos` recortam o workflow por área (etapas 0–2, 3–5 e 6–7) e mostram, em cada linha, o que falta para a próxima etapa.

O detalhe em `/equipamentos/{id}` é a tela de operação do processo de aquisição: stepper das etapas 0–8, formulário da etapa atual (negociação, jurídico, contrato, SC/OCI e OC), painel com os requisitos da próxima etapa, avanço por ação explícita, reabertura administrativa justificada, componentes e histórico consolidado.

A etapa só muda pelo serviço de workflow no backend, que valida as pré-condições, registra a transição e gera auditoria de forma atômica. Salvar dados nunca avança o processo.

O acesso é escopado por unidade: o perfil define o que o usuário pode fazer e o vínculo usuário–unidade define onde. ADMIN enxerga todas as unidades; VIEWER e ANALYST, apenas as atribuídas. Conhecer o UUID de um equipamento de outra unidade não dá acesso a ele.

Cada equipamento pode ter fornecedores vinculados, com um principal que aparece na fila de Suprimentos. A exportação da listagem de equipamentos respeita todos os filtros aplicados.

A administração é contextual, dentro da aba em que o dado é usado e só para quem tem permissão: catálogos e acesso por unidade na aba **Equipamentos**, cadastro mestre de fornecedores na aba **Suprimentos** (também acessível em `/fornecedores`). O header pertence ao Hub corporativo e não recebe funções do módulo.

Consulte [docs/etapa-01-primeiro-fluxo.md](docs/etapa-01-primeiro-fluxo.md), [docs/etapa-02-workflow-aquisicao.md](docs/etapa-02-workflow-aquisicao.md) [docs/etapa-03-dashboard-navegacao-filas.md](docs/etapa-03-dashboard-navegacao-filas.md) [docs/etapa-04-consolidacao-operacional.md](docs/etapa-04-consolidacao-operacional.md) e [docs/etapa-04-1-administracao-contextual.md](docs/etapa-04-1-administracao-contextual.md) para contratos, decisões e limitações.

## Executar o backend

Requisitos: Python 3.12+ e PostgreSQL.

```bash
cd backend
python -m venv .venv
```

Windows PowerShell:

```powershell
.venv\Scripts\python.exe -m pip install -e ".[dev]"
Copy-Item .env.example .env
.venv\Scripts\python.exe -m alembic upgrade head
.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

Linux/macOS:

```bash
.venv/bin/python -m pip install -e ".[dev]"
cp .env.example .env
.venv/bin/python -m alembic upgrade head
.venv/bin/python -m uvicorn app.main:app --reload
```

A API fica em `http://localhost:8000` e o Swagger em `http://localhost:8000/docs`.

## Executar o frontend

Requisitos: Node.js 20+ e pnpm.

```bash
cd frontend
pnpm install
cp .env.example .env
pnpm dev
```

No Windows PowerShell, use `Copy-Item .env.example .env` no lugar de `cp`.

O frontend fica em `http://localhost:3000`.

## Validação

Frontend:

```bash
pnpm lint
pnpm typecheck
pnpm test
pnpm build
```

Backend:

```bash
python -m ruff check app tests scripts
python -m mypy app
python -m pytest
```

Os testes de integração do backend exigem um PostgreSQL de testes configurado em `.env.test`.
