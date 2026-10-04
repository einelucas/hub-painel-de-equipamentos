# ARCH-00 — Segurança do banco da suíte de testes

## Incidente

Durante a validação da ARCH-00.3b, o `pytest` foi executado no repositório com variáveis de ambiente apontando para um PostgreSQL local isolado. O `tests/conftest.py` carregava `backend/.env.test` com `load_dotenv(..., override=True)`. Esse arquivo local apontava para o banco remoto `neondb_test` (Neon). O override substituiu as variáveis explícitas, e a suíte rodou contra o banco remoto.

O fixture `_clean_database` executa `TRUNCATE ... RESTART IDENTITY CASCADE` em todas as tabelas após cada teste de integração. Uma auditoria somente leitura confirmou que o estado C2 do `neondb_test` foi apagado.

## Por que a proteção antiga não bastou

- O `.env.test` sobrescrevia o ambiente explícito.
- As únicas barreiras eram `APP_ENV=test` e o nome do banco terminando em `_test`. Um banco remoto chamado `*_test` passava nas duas.
- A checagem só acontecia no teardown, depois de a aplicação já ter subido e se conectado.

## Nova política

A suíte destrutiva só roda se **todas** as condições abaixo forem verdadeiras:

1. `APP_ENV=test`.
2. `ALLOW_DESTRUCTIVE_TESTS=true` (opt-in explícito).
3. `DATABASE_URL` é uma URL PostgreSQL válida.
4. O host é estritamente local: `localhost`, `127.0.0.1` ou `::1`.
5. O nome do banco termina em `_test`.
6. `MIGRATION_DATABASE_URL`, quando presente, cumpre a mesma política. Se uma URL for local e a outra remota, a suíte é bloqueada.

Também são recusados: múltiplos hosts, e parâmetros de query que redirecionam a conexão (`host`, `hostaddr`, `dbname`, `service`, `port`).

Qualquer host Neon, IP remoto ou host arbitrário é recusado, mesmo que o banco termine em `_test`.

**Banco remoto é proibido para o pytest.** Isso vale para o `neondb_test`, para DEV e para produção.

## Prioridade das variáveis

`.env.test` é carregado com `override=False`. Uma variável já definida no ambiente sempre prevalece sobre o arquivo. Uma variável ausente do ambiente é lida do arquivo e passa pela mesma validação.

## Preflight antes dos imports

A política fica em `tests/db_safety.py`, como uma função pura: não importa `app`, não abre conexão e não resolve DNS. O `tests/conftest.py` segue esta ordem:

1. Carrega o `.env.test` (`override=False`).
2. Chama `validate_destructive_test_target(os.environ)`.
3. Só então importa `app.models`, `app.core.database` e `app.main`.

Se a validação falhar, ela levanta `UnsafeTestDatabaseError` (um `RuntimeError`). Nesse caso o pytest aborta ao carregar o conftest, sem engine criada, sem conexão e sem nenhum teste executado.

A segunda barreira continua no teardown, antes do `TRUNCATE`: confere o host da engine efetiva, `APP_ENV` e `current_database()` terminando em `_test`.

## Testes da guarda

`tests/unit/test_db_safety.py` cobre:

- **Aceitação:** `localhost`, `127.0.0.1`, `::1` e o driver `+asyncpg`.
- **Rejeição:** host Neon, IPs remotos, host arbitrário, banco sem `_test`, `APP_ENV` diferente de `test`, opt-in ausente ou falso, `MIGRATION_DATABASE_URL` remota e URL inválida.
- **Bloqueio real:** um subprocesso roda o pytest com a URL fictícia `ep-fake.neon.tech/fake_test`, com socket e DNS bloqueados. O teste verifica que a suíte aborta, que nenhum módulo `app` foi importado e que não houve nenhuma tentativa de rede.

Nenhum desses testes conecta em banco.

## CI

O `.github/workflows/ci.yml` fornece `ALLOW_DESTRUCTIVE_TESTS=true` e continua usando apenas o service `postgres:16-alpine` temporário do GitHub Actions (`localhost`, banco `painel_equipamentos_test`).

## Ambiente local

O `backend/.env.test.example` documenta só o PostgreSQL local, com o aviso explícito de nunca apontar o arquivo para Neon, DEV ou produção. O `backend/.env.test` real é gitignored e não é versionado. Uma cópia local que ainda aponte para host remoto passa a ser recusada pela guarda.

## Estado do `neondb_test`

Por decisão do projeto, os dados C2 do `neondb_test` **não serão restaurados agora**. O banco não deve voltar a ser usado pelo pytest.
