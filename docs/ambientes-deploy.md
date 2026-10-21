# Ambientes, configuração e implantação

Este documento separa **configuração suportada pelo código** de **estado efetivo dos serviços**. Não há garantia de que o banco DEV, TEST ou produção esteja migrado até o head do Alembic apenas porque o repositório foi atualizado.

## Pré-requisitos

- Node.js e pnpm compatíveis com `frontend/package.json`, lockfile e `pnpm-workspace.yaml`.
- Python 3.12+ e PostgreSQL.
- Acesso a infraestrutura autorizada para configurações de autenticação, storage e e-mails.
- Credenciais fora do repositório e fora dos logs.

## Desenvolvimento local

Backend:

~~~bash
cd backend
python -m venv .venv
python -m pip install -e ".[dev]"
# Copie .env.example para .env e configure PostgreSQL LOCAL.
python -m alembic upgrade head
python -m uvicorn app.main:app --reload
~~~

Frontend (segundo terminal):

~~~bash
cd frontend
pnpm install --frozen-lockfile
pnpm dev
~~~

Por padrão, o frontend utiliza `http://localhost:3000` e o backend `http://localhost:8000/api/v1`; configure URLs e CORS quando estiverem em serviços diferentes.

## Variáveis de ambiente — backend

A referência definitiva de nomes/defaults está em `backend/app/core/config.py` e `backend/.env.example`. Principais grupos:

| Grupo | Variáveis |
| --- | --- |
| Ambiente e banco | `APP_ENV`, `DATABASE_URL`, `MIGRATION_DATABASE_URL` |
| Migração e teste | `ALLOW_TEST_DB_MIGRATIONS`, `ALLOW_DESTRUCTIVE_TESTS` (testes locais) |
| API | `CORS_ORIGINS`, `LOG_LEVEL`, `APP_PUBLIC_URL` |
| OIDC | `KEYCLOAK_ISSUER`, `KEYCLOAK_AUDIENCE`, `KEYCLOAK_JWKS_URL`, `KEYCLOAK_ALLOWED_ALGORITHMS` |
| Auth local | `LOCAL_AUTH_SESSION_HOURS` |
| Desenvolvimento | `DEV_AUTH_ENABLED`, `DEV_AUTH_USER_EMAIL` |
| Notificações | `NOTIFICATION_PROVIDER`, `NOTIFICATION_MODE`, `NOTIFICATION_TEST_INBOX`, `NOTIFICATION_TIMEZONE` |
| Microsoft Graph | `GRAPH_TENANT_ID`, `GRAPH_CLIENT_ID`, `GRAPH_CLIENT_SECRET`, `GRAPH_SENDER` |
| Resend | `RESEND_API_KEY`, `RESEND_FROM_EMAIL` |
| Arquivos | `STORAGE_PROVIDER`, `STORAGE_LOCAL_DIR`, `STORAGE_S3_BUCKET`, `STORAGE_S3_ENDPOINT_URL`, `STORAGE_S3_REGION`, `STORAGE_S3_ACCESS_KEY_ID`, `STORAGE_S3_SECRET_ACCESS_KEY`, `STORAGE_S3_PREFIX` |
| Importação | `IMPORT_MAX_UPLOAD_BYTES` e configurações do motor/perfis |

**Não coloque valores reais de secrets em exemplos, tickets públicos, Markdown ou arquivos de CI.** As variáveis sensíveis devem ser cadastradas na plataforma de infraestrutura e ter acesso restrito.

## Variáveis públicas — frontend

`frontend/nuxt.config.ts` utiliza:

- `NUXT_PUBLIC_API_BASE_URL` — URL pública da API incluindo `/api/v1`.
- `NUXT_PUBLIC_OIDC_ISSUER`, `NUXT_PUBLIC_OIDC_CLIENT_ID` — dados **públicos** do client OIDC (não seu secret).
- `NUXT_PUBLIC_OIDC_REDIRECT_URI` e `NUXT_PUBLIC_OIDC_POST_LOGOUT_REDIRECT_URI` — retorno/callback da autenticação.

Variáveis `NUXT_PUBLIC_*` chegam ao navegador: **nunca** use nelas senha, API key, private key, connection string ou client secret.

## Banco, Alembic e segurança de ambiente

- Alembic lê configuração de conexão no backend. Verifique `alembic current` e `alembic heads` no alvo autorizado antes de qualquer upgrade.
- Faça backup e estabeleça rollback/teste de restauração para ambientes persistentes.
- **TEST destrutivo exige PostgreSQL local.** O código de `backend/tests/db_safety.py` rejeita host remoto mesmo com nome terminando em `_test`.
- A importação Monday possui guardas próprios de ambiente e confirmação; eles não substituem revisão do plan, autorização de escrita e reconciliação.
- Nada neste documento autoriza migração ou escrita em DEV/produção. Execute essas ações somente com autorização explícita do responsável.

## Deploy (por exemplo Railway)

1. Separar serviços de backend/frontend e configurar build/start compatíveis com a stack real.
2. Configurar URLs públicas, CORS, saúde da API e integração com identidade corporativa.
3. Cadastrar segredos do banco, providers e storage na plataforma, **não** no Git.
4. Verificar o conjunto de migrations exigidas e aplicar somente após testes e plano de rollback.
5. Usar storage corporativo durável (por exemplo S3 compatível) para arquivos de contrato; diretório local do container não deve ser considerado persistência corporativa.
6. Definir e homologar execução/agendamento do worker de notificações, quando necessário.
7. Validar escopo, importações, links de e-mail e acesso público/privado à aplicação.
8. Executar smoke tests e checar logs **sem expor valores sensíveis**.

As URLs e credenciais da implantação dependem de cada ambiente. Não fixar um endpoint Railway como verdade corporativa permanente na documentação.

## Checklist de promoção

- [ ] CI, lint, typecheck, testes e build executados com resultado válido para o commit alvo.
- [ ] Migrations verificadas em TEST local/ambiente autorizado; backup e rollback prontos.
- [ ] Autenticação e permissões corporativas homologadas; bypass de DEV desabilitado.
- [ ] Dados importados e catálogos validados, inclusive EAP e reconciliação.
- [ ] Segredos protegidos; credenciais antigas expostas tratadas.
- [ ] Envio de e-mail em modo seguro até liberação expressa de live.
- [ ] Storage, logs, observabilidade e recuperação revisados.
- [ ] Aprovação explícita para qualquer escrita/migration em DEV ou produção.

Veja [autenticação](autenticacao.md), [notificações](notificacoes.md), [importação](importacao-monday.md) e [testes](testes.md).
