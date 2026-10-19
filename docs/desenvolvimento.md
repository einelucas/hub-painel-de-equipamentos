# Desenvolvimento

## Frontend

```bash
cd frontend
pnpm install
pnpm dev
```

Validação:

```bash
pnpm lint
pnpm typecheck
pnpm test
pnpm build
```

## Backend

```bash
cd backend
python -m venv .venv
python -m pip install -e ".[dev]"
python -m alembic upgrade head
python -m uvicorn app.main:app --reload
```

Validação:

```bash
python -m ruff check app tests scripts
python -m mypy app
python -m pytest
```

Os testes de integração exigem `.env.test` e banco PostgreSQL exclusivo terminado em `_test`.

### Windows e `--reload`

Com `--reload`, alterações em arquivos `.py` sob `backend/` reiniciam o worker. No Windows o reloader faz isso
enviando `CTRL_C_EVENT` ao processo filho, o que produz no terminal um traceback com `KeyboardInterrupt` e
`asyncio.exceptions.CancelledError` durante o `lifespan`. **Isso é esperado e não indica falha**: logo antes
aparece `WatchFiles detected changes in ... Reloading...` e, logo depois, um novo `Started server process`.
O servidor continua no ar.

O watcher observa todo o diretório (inclusive `.venv` e arquivos gerados) e só filtra `*.py`. Para limitar o
reload ao código da aplicação e evitar reinícios por mudanças em dependências:

```powershell
cd backend
.venv\Scripts\python.exe -m uvicorn app.main:app --reload --reload-dir app
```

Um traceback igual a esse **sem** a linha de `WatchFiles` e **sem** novo `Started server process` indica queda
real do worker: nesse caso, verifique as linhas anteriores do log.
