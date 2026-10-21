# Arquitetura da aplicação

O Painel de Equipamentos é um módulo do Hub com frontend Nuxt e API FastAPI. O PostgreSQL é a fonte de verdade para dados de domínio, usuários, eventos e configurações operacionais persistidas. Arquivos corporativos e segredos devem permanecer fora do repositório.

~~~mermaid
flowchart TD
    UI["Nuxt 4 / Vue 3 / Pinia"] --> HTTP["useApi → Axios"]
    HTTP --> API["FastAPI /api/v1"]
    API --> POLICY["Autenticação, permissão e escopo"]
    POLICY --> DOM["Services de domínio"]
    DOM --> DB["SQLAlchemy async → PostgreSQL"]
    DOM --> OUT["Notificações / outbox"]
    DOM --> IMPORT["Importação Monday"]
    IMPORT --> DB
    OUT --> MAIL["Microsoft Graph ou Resend"]
~~~

## Frontend

- `frontend/pages/`: rotas de dashboard, equipamentos, engenharia, jurídico, suprimentos, fornecedores, administração, autenticação e Kanban.
- `frontend/components/`: componentes de interface, formulários, tabelas, cards, gráficos e shells reutilizáveis.
- `frontend/stores/moduleContext.ts`: filtros de unidade, contexto/projeto e equipamento; garante compatibilidade quando o filtro superior muda.
- `frontend/stores/auth.ts` e composables de autenticação: sessão e identidade.
- `frontend/composables/useApi.ts`: fachada pública de requisições.
- `frontend/services/api/http.ts`: instância **Axios** centralizada, normalização de URLs/erros, token Bearer, downloads e progresso de upload.
- `frontend/utils/navigation.ts`: itens e permissões da navbar. A auditoria e recursos administrativos também podem ser acessados por rotas/contextos próprios.

Não faça novas chamadas Axios diretamente das páginas: preserve a fachada compartilhada e os contratos dos componentes.

## Backend

`backend/app/main.py` cria a aplicação, configura middleware, CORS, erros e monta `app/api/v1/router.py` sob `/api/v1`. Este router agrega autenticação, saúde, usuários, acessos, auditoria, catálogos, comentários, equipamentos, notificações, processos, workflow, filas, fornecedores, dashboard e importação.

A organização predominante dos módulos em `backend/app/modules/` é:

~~~text
modulo/
  controllers.py    Rotas, dependências e contratos HTTP
  services.py       Regras transacionais e operações do domínio
  schemas.py        Entrada/saída Pydantic
~~~

Alguns domínios possuem serviços especializados, workers, validações e adaptadores. Os modelos SQLAlchemy continuam centralizados em `backend/app/models/`; não foram movidos automaticamente para cada módulo.

Módulos relevantes: `access`, `audit`, `catalogs`, `comments`, `dashboard`, `equipments`, `imports`, `monday_import`, `notifications`, `processes`, `queues`, `suppliers`, `users` e `workflow`; a EAP tem componentes de catálogo e reconciliação especializados.

## Persistência

- PostgreSQL, SQLAlchemy 2 assíncrono e drivers configurados em `backend/app/core/database.py`.
- Alembic em `backend/alembic/` versiona as tabelas; uma migration presente no Git não comprova a versão física de um banco.
- `app/models/equipment.py`, `process.py`, `notification.py`, `monday_import.py` e demais arquivos representam relacionamentos e registros de domínio.
- Processos de aquisição e mudanças de etapa são controlados por services, não por atualização livre do estado pelo frontend.
- Informações financeiras, datas contratuais e fornecedores são dados operacionais; políticas de acesso devem ser aplicadas também à leitura e exportação.

Veja [domínio e EAP](dominio-eap.md) para cardinalidades e invariantes.

## Segurança transversal

- `backend/app/core/auth.py` resolve identidade por login local, sessão ou OIDC/Keycloak; uma exceção de desenvolvimento é condicionada ao ambiente.
- `backend/app/core/permissions.py` e `scope.py` centralizam autorização por permissão e escopo por unidade; conhecer um UUID não concede acesso.
- Configuração em `backend/app/core/config.py` usa Pydantic Settings; credenciais do Neon, Graph, Resend e storage nunca devem estar embutidas na interface.
- Logs e trilhas de auditoria devem ser úteis sem expor senha, token ou conteúdo sensível desnecessário.

## Importação de fontes externas

O motor comum em `app/modules/monday_import/` lê planilhas XLSX de boards aprovados, usa `ImportProfile`, gera staging/plan, executa apply controlado e reconcilia. `app/modules/imports/` expõe parte do pipeline à interface administrativa, incluindo jobs de apply assíncronos.

**Monday é origem dos equipamentos reais importados.** A LGE não deve gerar equipamentos automaticamente. A Árvore oficial, disponível somente em fonte autorizada, é a referência para o catálogo EAP; decisões de reconciliação ambíguas não são inferidas por nome.

## Notificações

`app/modules/notifications/` mantém regras de destinatários e eventos, `email_template` e `email_delivery` no banco. Templates HTML passam por sanitização; a outbox usa controle de concorrência e integrações configuráveis com Microsoft Graph ou Resend. A execução do processamento e as permissões são responsabilidades do backend.

## Implantação e evolução

A API e o frontend podem ser implantados separadamente. O runtime exige variáveis de ambiente coerentes, migrations autorizadas, CORS, storage e identidade configurados. Não infira que a implantação em Railway está homologada apenas pela presença de arquivos de deploy.

Mudanças arquiteturais devem ser **incrementais**, preservar endpoints e schema publicados, incluir testes de regressão e atualizar esta documentação. Consulte [ambientes](ambientes-deploy.md) e [testes](testes.md).
