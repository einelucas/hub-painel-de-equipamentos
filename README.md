# Painel de Equipamentos | Hub de Automação

Módulo corporativo de **Planejamento → Painel de Equipamentos** para cadastro, acompanhamento técnico e controle das etapas de aquisição de equipamentos por unidade e contexto de projeto.

O Hub centraliza equipamentos, componentes, responsáveis, fornecedores, prazos, processos de negociação e jurídico, contratos, solicitações de compra (SC/OCI), ordens de compra (OC), histórico e indicadores. Os dados originados no Monday.com são incorporados por um processo controlado de importação, sem reproduzir um aplicativo por board.

> **Situação:** aplicação em consolidação/homologação. O código contém funcionalidades operacionais e administrativas, mas a prontidão de produção depende da validação do ambiente, das permissões, das integrações e da CI. A presença de uma migration no Git não comprova sua aplicação no banco implantado.

## Tecnologias

| Camada | Tecnologias |
| --- | --- |
| Interface | Nuxt 4, Vue 3, TypeScript, Pinia, Tailwind CSS |
| HTTP | Axios centralizado em `frontend/services/api/http.ts` e `frontend/composables/useApi.ts` |
| API | Python 3.12+, FastAPI, Pydantic v2 |
| Persistência | PostgreSQL, SQLAlchemy assíncrono, Alembic |
| Segurança | Login local e integração OIDC/Keycloak; perfis e escopo por unidade |
| Qualidade | Vitest, pytest, Ruff, mypy, ESLint e GitHub Actions |

## Principais capacidades

- Dashboard com indicadores, status e alertas de prazo.
- Equipamentos e componentes com filtros por unidade, projeto e equipamento.
- Filas operacionais de Engenharia, Jurídico e Suprimentos, além do Kanban.
- Workflow de aquisição nas fases 0–8; estados operacionais independentes; dispensa auditada de requisitos e fluxo controlado de reabertura.
- Fornecedores, work packages, EAP, negociação, contratos, SC/OCI e OC.
- Administração de usuários, permissões, regras de notificação e modelos HTML de e-mail.
- Importação Monday via perfis de origem, staging, planejamento, aplicação controlada e reconciliação.
- Auditoria e histórico das operações.

## Organização

~~~text
backend/
  app/api/v1/         Agregação de rotas FastAPI
  app/core/           Configuração, autenticação, segurança e infraestrutura
  app/models/         Entidades SQLAlchemy
  app/modules/        Módulos por domínio (controllers/services/schemas)
  alembic/            Evolução do esquema
  tests/              Testes unitários e de integração
frontend/
  components/         Componentes reutilizáveis
  composables/        Composição e fachada HTTP
  pages/              Rotas da interface
  services/api/       Cliente Axios, cache e contratos HTTP
  stores/             Sessão e filtros globais
docs/                 Documentação técnica consolidada
~~~

## Execução local

**Backend** (use PostgreSQL local e variáveis de desenvolvimento apropriadas):

~~~bash
cd backend
python -m venv .venv
python -m pip install -e ".[dev]"
# Configure .env a partir de .env.example, sem versioná-lo.
python -m alembic upgrade head
python -m uvicorn app.main:app --reload
~~~

**Frontend** (em outro terminal):

~~~bash
cd frontend
pnpm install --frozen-lockfile
pnpm dev
~~~

Endereços locais padrão: frontend em `http://localhost:3000` e backend em `http://localhost:8000`. A API usa o prefixo `/api/v1`. Configure o frontend com `NUXT_PUBLIC_API_BASE_URL` quando necessário.

**Nunca execute migrations ou testes destrutivos apontando para Neon remoto, DEV corporativo ou produção.** Consulte a documentação de ambientes e testes antes de prosseguir.

## Verificações

~~~bash
# frontend/
pnpm lint
pnpm typecheck
pnpm test
pnpm build

# backend/
python -m ruff check app tests scripts
python -m mypy app
python -m pytest
~~~

A suíte de integração com operações destrutivas exige um PostgreSQL **local**, banco com sufixo `_test` e autorização explícita por `ALLOW_DESTRUCTIVE_TESTS=true`.

## Documentação

Comece pelo [índice técnico](docs/README.md). Ele reúne arquitetura, funcionalidades, domínio e EAP, API, autenticação, importação Monday, notificações, ambientes e testes.

Para procedimentos de backend consulte também [backend/README.md](backend/README.md). Não utilize relatórios antigos de etapas ou escopos como especificação vigente: as decisões técnicas atuais devem ser verificadas contra o código, migrations e documentação consolidada.

## Segurança e operação

Este repositório não deve conter exports corporativos do Monday, LGE, Árvore de Localização, dados reais de usuários, dumps ou segredos de ambiente. Valores sensíveis pertencem à configuração protegida da infraestrutura; dados operacionais pertencem ao banco e aos armazenamentos autorizados. Qualquer incidente ou credencial antiga exige tratamento próprio, inclusive revisão do histórico Git.
