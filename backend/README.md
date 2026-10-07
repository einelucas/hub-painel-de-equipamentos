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

## Login local (e-mail e senha)

Usuários com login local ficam em `User` + `Account` (`providerId = credential`, senha com hash scrypt).
`POST /api/v1/auth/login` abre uma sessão na tabela `Session` (só o SHA-256 do token é gravado), válida por
`LOCAL_AUTH_SESSION_HOURS`. O mesmo comando cria o usuário ou redefine a senha de um existente:

```bash
python -m app.modules.local_auth create-user --email admin@inpasa.com.br --name Administrador --role ADMIN
```

A senha é pedida no terminal (ou lida de `LOCAL_AUTH_PASSWORD`), nunca passada como argumento. Os tokens
`dev-*` de `DEV_AUTH_ENABLED` continuam funcionando fora de produção.

## Catálogo global de fornecedores

A planilha aprovada é convertida em um artefato JSON versionado e validável sem banco. A carga consulta
o banco em `--dry-run`; a escrita só é liberada em DEV/TESTE com confirmação e nome exato do banco.

```bash
python -m app.modules.supplier_catalog extract fornecedores_hub_oficiais.xlsx
python -m app.modules.supplier_catalog validate
python -m app.modules.supplier_catalog seed --dry-run --env-file .env.test
python -m app.modules.supplier_catalog seed --apply --sync --confirm \
  --expect-database neondb_test --env-file .env.test
```

A carga altera somente `Supplier`, aliases oficiais em `SupplierAlias` e `AuditLog`; ela não cria vínculos
com equipamentos. Use `--sync` somente após revisar o dry-run, para atualizar campos oficiais divergentes.

## Rotas iniciais

- `GET /api/v1/health/live`
- `GET /api/v1/health/ready`
- `POST /api/v1/auth/login`
- `POST /api/v1/auth/logout`
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
├── controllers.py
├── schemas.py
├── services.py
└── repository.py
```

Consulte `../docs/migration/monday-import-architecture.md` antes de evoluir o apply definitivo da
migração. As regras pendentes não devem ser inferidas dos XLSX.
