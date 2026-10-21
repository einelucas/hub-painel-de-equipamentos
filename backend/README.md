# Backend | Painel de Equipamentos

API FastAPI do módulo corporativo de Planejamento/Painel de Equipamentos. Este README contém os comandos de backend; consulte o [índice de documentação](../docs/README.md) para arquitetura, regras de domínio, rotas e segurança.

## Stack e organização

- Python 3.12+, FastAPI, Pydantic v2, SQLAlchemy 2 assíncrono, PostgreSQL e Alembic.
- `app/api/v1/router.py` agrega os controllers de domínio sob `/api/v1`.
- `app/modules/` organiza `controllers.py`, `services.py`, `schemas.py` e módulos especializados.
- `app/models/` concentra as entidades SQLAlchemy; `alembic/versions/` contém o histórico de schema.
- `app/core/` contém configuração, autenticação, escopo, banco, logging e armazenamento.

## Instalação local

~~~bash
cd backend
python -m venv .venv
python -m pip install -e ".[dev]"
# Copie .env.example para .env e configure um banco de desenvolvimento autorizado.
python -m alembic upgrade head
python -m uvicorn app.main:app --reload
~~~

No Windows, ative o virtualenv ou utilize diretamente `.venv\Scripts\python.exe`. Ajuste `DATABASE_URL` e `MIGRATION_DATABASE_URL` antes de qualquer migration. **Não use bancos remotos de produção como alvo de experimentação.**

## Validação

~~~bash
python -m ruff check app tests scripts
python -m mypy app
python -m pytest
~~~

Os testes de integração potencialmente destrutivos só são permitidos com `APP_ENV=test`, `ALLOW_DESTRUCTIVE_TESTS=true` e PostgreSQL em host **local** com nome terminado em `_test`. A proteção está em `tests/db_safety.py`; não a contorne.

## Autenticação e API

- Login local: `POST /api/v1/auth/login` e `POST /api/v1/auth/set-password` (fluxo de primeiro acesso presente no código).
- Alternativa de identidade: OIDC/Keycloak mediante configuração.
- Perfis: `VIEWER`, `ANALYST` e `ADMIN`, com políticas de permissão e escopo por unidade.
- Swagger/OpenAPI: consulte a instância FastAPI no ambiente autorizado e [docs/api.md](../docs/api.md).

**Atenção:** os scripts com identidades reais e dumps operacionais foram removidos do estado atual do Git. O legado de senha inicial compartilhada ainda precisa de correção e rotação de credenciais; apagar arquivos não apaga o histórico de commits.

## Importação e notificações

A importação Monday **já dispõe de endpoints de administração** sob `/api/v1/imports/monday`: perfis, upload/staging, plan e apply acompanhado por job. O núcleo em `app/modules/monday_import/` também oferece CLI `python -m app.modules.monday_import` para dry-run, stage, plan, apply e reconcile. A escrita no domínio requer confirmação/controles de segurança; não é um simples upload imediato.

As notificações usam regras e modelos no PostgreSQL, com editor e prévia HTML; há integrações configuráveis Microsoft Graph e Resend, outbox e processamento. O envio real depende de ambiente e credenciais protegidas.

Documentação: [importação](../docs/importacao-monday.md), [notificações](../docs/notificacoes.md), [ambientes](../docs/ambientes-deploy.md).
