# Painel de Equipamentos — Backend

API FastAPI do módulo Painel de Equipamentos.

A base inicial preserva apenas infraestrutura compartilhada: configuração, conexão assíncrona com PostgreSQL, autenticação OIDC/Keycloak, usuários, permissões administrativas, auditoria, logging, tratamento de erros e health checks.

Nenhuma entidade ou regra de negócio de equipamentos foi criada nesta etapa.

## Stack

- Python 3.12+
- FastAPI + Pydantic v2
- SQLAlchemy 2 assíncrono com `asyncpg`
- PostgreSQL
- Alembic
- pytest / pytest-asyncio
- Ruff e mypy

## Instalação

```bash
python -m venv .venv
```

Windows:

```powershell
.venv\Scripts\python.exe -m pip install -e ".[dev]"
Copy-Item .env.example .env
```

Linux/macOS:

```bash
.venv/bin/python -m pip install -e ".[dev]"
cp .env.example .env
```

Ajuste `DATABASE_URL` e `MIGRATION_DATABASE_URL` antes de aplicar as migrations.

## Comandos

```bash
python -m alembic upgrade head
python -m uvicorn app.main:app --reload
python -m ruff check app tests scripts
python -m mypy app
python scripts/export_openapi.py
python scripts/check_schema_drift.py
```

Para testes de integração, copie `.env.test.example` para `.env.test`, use um banco cujo nome termine em `_test`, aplique `alembic upgrade head` e execute `python -m pytest`.

## Rotas iniciais

- `GET /api/v1/health/live`
- `GET /api/v1/health/ready`
- `GET /api/v1/auth/me`
- `GET /api/v1/usuarios`
- `POST /api/v1/usuarios`
- `PATCH /api/v1/usuarios/{user_id}`
- `GET /api/v1/auditoria`

As rotas administrativas exigem perfil `ADMIN`.

## Estrutura para os próximos módulos

Novas funcionalidades podem ser adicionadas em pacotes próprios, por exemplo:

```text
app/modules/equipments/
├── router.py
├── schemas.py
├── service.py
└── repository.py
```

Crie models e migrations somente depois que o domínio de equipamentos estiver especificado.
