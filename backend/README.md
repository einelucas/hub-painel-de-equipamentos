# Painel de Equipamentos — Backend

API FastAPI do módulo Painel de Equipamentos.

Além do domínio operacional, o backend possui a fundação administrativa do importador Monday: parser
XLSX semântico, normalização, dry-run, staging idempotente e reconciliação. O importador não está exposto
por endpoint e ainda não aplica os dados às entidades definitivas.

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
python -m app.modules.monday_import ../references/monday_exports
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

## Estrutura dos módulos

Novas funcionalidades podem ser adicionadas em pacotes próprios, por exemplo:

```text
app/modules/equipments/
├── router.py
├── schemas.py
├── service.py
└── repository.py
```

Consulte `../docs/migration/monday-import-architecture.md` antes de evoluir o apply definitivo da
migração. As regras pendentes não devem ser inferidas dos XLSX.
