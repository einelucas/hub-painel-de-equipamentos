# Testes, CI e regressão

Os testes protegem o domínio, o fluxo de aquisição, a autorização por unidade, a importação e a interface. Este documento contém **como executar**; não declara que a pipeline atual esteja verde sem consultar a execução do commit correspondente.

## Frontend

No diretório `frontend/`:

~~~bash
pnpm install --frozen-lockfile
pnpm lint
pnpm typecheck
pnpm test
pnpm build
~~~

O projeto utiliza Vitest para componentes e regras do frontend, além de ESLint e typecheck. Para alterações no cliente HTTP, valide `frontend/services/api/http.ts`, `frontend/composables/useApi.ts`, o store de autenticação, tratamento de erro e upload. Novos componentes devem incluir testes focados nos fluxos alterados.

## Backend

No diretório `backend/`, com ambiente virtual instalado:

~~~bash
python -m ruff check app tests scripts
python -m mypy app
python -m pytest
~~~

Os testes incluem casos unitários de regras, serviços, validação e integração com PostgreSQL. Para inspeção de migrações no **banco local autorizado**:

~~~bash
python -m alembic heads
python -m alembic current
python -m alembic upgrade head
~~~

`upgrade head` escreve no banco. Não o execute em DEV remoto ou produção sem autorização.

## Proteção para testes destrutivos

**Houve um incidente histórico envolvendo testes contra um banco remoto.** A proteção atual está em `backend/tests/db_safety.py` e nos fixtures:

- `APP_ENV=test`.
- `ALLOW_DESTRUCTIVE_TESTS=true`, opt-in explícito.
- `DATABASE_URL` PostgreSQL com host estritamente **local**: `localhost`, `127.0.0.1` ou `::1`.
- Nome do banco terminando em `_test`.
- URLs com hosts remotos, múltiplos hosts ou redirecionamentos suspeitos são recusadas.

Mesmo um banco chamado `neondb_test` em Neon **não** é um alvo aceitável para a suíte destrutiva. Não desative essas verificações para fazer testes passarem.

## GitHub Actions

`.github/workflows/ci.yml` define jobs de frontend e backend. A sequência esperada é:

- Frontend: instalação congelada, lint, typecheck, test, build.
- Backend: PostgreSQL local em container, configuração `.env.test` temporária, Alembic, Ruff, mypy e pytest.

O estado de cada job deve ser consultado na execução correspondente ao SHA do commit; um relatório histórico de CI não certifica a main de hoje.

## Matriz mínima de regressão

| Área | Casos fundamentais |
| --- | --- |
| Autenticação | Login, logout, troca inicial, expiração, usuário inativo, credenciais inválidas |
| Autorização | VIEWER/ANALYST/ADMIN, escopo por unidade, recurso de outra unidade, área administrativa |
| Catálogos/EAP | Hierarquia, prefixo manual, família 00, aliases aprovados, casos unresolved |
| Equipamentos | CRUD, componentes, filtros Unidade/Projeto/Equipamento, paginação |
| Workflow | Requisitos por etapa, avanço sequencial, waiver, estados operacionais, reabertura |
| Compras | Contratos/SC/OCI/OC 1:N, registro completo, fornecedor único, documentos |
| Importação Monday | Profile, parse, stage idempotente, mapping, plan, job apply, reconcile, conflitos |
| Notificações | Destinatários, variáveis, sanitização HTML, preview, sandbox, outbox, deduplicação, retry |
| Frontend | Estados de carregamento, erros, formulários, navegação, responsividade e permissões |

A regressão de importação deve usar **fixtures sintéticas**; não copie exports corporativos para o repositório.

## Validação documental

Ao editar documentação ou mudar rotas/models:

1. Confira nomes e caminhos no código atual.
2. Inspecione links relativos para Markdown removidos.
3. Confirme que endpoints documentados existem nos controllers e OpenAPI.
4. Verifique ausência de e-mails reais, senhas, tokens, dados privados e nomes de ambientes como exemplos com segredos.
5. Não altere código para fazer uma documentação antiga parecer correta.

## Critério de homologação

Testes passando localmente e CI verde são condições necessárias, mas **não suficientes**: é preciso validar migrations, segregação dos ambientes, autenticação corporativa, reconciliação de dados, storage, notificações e aceite operacional antes do deploy de produção.

Veja [ambientes](ambientes-deploy.md), [API](api.md) e [domínio](dominio-eap.md).
