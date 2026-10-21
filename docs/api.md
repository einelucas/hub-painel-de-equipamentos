# Referência da API

**Base:** `/api/v1`. As rotas abaixo são relativas a esse prefixo e foram conferidas nos decorators dos controllers atuais. Os contratos de campos, códigos de erro e documentação interativa são definidos pelos schemas Pydantic e pelo OpenAPI gerado pelo FastAPI no ambiente executado.

A maioria dos recursos exige `Authorization: Bearer <token>`, além de permissão e escopo por unidade. O frontend usa `useApi` e o cliente Axios centralizado. Não crie integrações baseadas em endpoints de documentos antigos.

## Identidade, usuários e acesso

| Método | Caminho | Finalidade |
| --- | --- | --- |
| POST | `/auth/login` | Login com e-mail e senha |
| POST | `/auth/set-password` | Definição de senha no fluxo de primeiro acesso existente |
| POST | `/auth/logout` | Encerrar sessão |
| GET | `/auth/me` | Identidade, papel e permissões do usuário |
| GET | `/usuarios` | Listar usuários (permissão administrativa) |
| POST | `/usuarios` | Criar usuário |
| PATCH | `/usuarios/{user_id}` | Atualizar usuário |
| GET | `/usuarios/{user_id}/units` | Consultar acessos por unidade |
| PUT | `/usuarios/{user_id}/units` | Substituir vínculos por unidade |
| GET | `/responsibles` | Responsáveis acessíveis |
| GET | `/module-context/defaults` | Preferências/defaults de contexto do usuário |
| GET | `/auditoria` | Consulta de trilha de auditoria |

Também existem endpoints `/health/live` e `/health/ready` no router de saúde.

## Catálogos

| Método | Caminho / família | Finalidade |
| --- | --- | --- |
| GET, POST, PATCH | `/units`, `/units/{id}` | Unidades |
| GET, POST, PATCH | `/units/{unit_id}/project-contexts`, `/project-contexts/{id}` | Contextos/projetos |
| GET, POST, PATCH | `/eap-nodes`, `/eap-nodes/{id}` | Nós da EAP |
| GET | `/project-contexts/{project_context_id}/eap-nodes` | Nós associados a um contexto |
| GET, POST, PATCH | `/areas`, `/areas/{id}` | Áreas |
| GET, POST, PATCH | `/disciplines`, `/disciplines/{id}` | Disciplinas |
| GET, POST, PATCH | `/criticality-labels`, `/criticality-labels/{id}` | Rótulos de criticidade |
| GET, POST, PATCH | `/work-packages`, `/work-packages/{id}` | Work packages |

Os métodos específicos são definidos em `backend/app/modules/catalogs/controllers.py`; nem toda coleção aceita PATCH no caminho sem ID. Não presuma hard delete: o cadastro usa manutenção de ativação/edição.

## Equipamentos, componentes e comentários

| Método | Caminho | Finalidade |
| --- | --- | --- |
| GET, POST | `/equipments` | Listar/criar equipamentos |
| GET, PATCH | `/equipments/{equipment_id}` | Detalhar/editar equipamento |
| GET, POST | `/equipments/{equipment_id}/components` | Consultar/criar componentes |
| PATCH | `/components/{component_id}` | Editar componente |
| GET, POST | `/equipments/{equipment_id}/comments` | Listar/criar comentários |
| PATCH, DELETE | `/equipments/{equipment_id}/comments/{comment_id}` | Editar/excluir comentário |

Os parâmetros de consulta de listagem e filtro são declarados nos schemas/controllers; use os nomes reais, como `unit_id` e `project_context_id`, conforme a operação. Atualizações comuns não substituem o serviço de transições de workflow.

## Processos de aquisição

Os caminhos abaixo utilizam o prefixo `/equipments/{equipment_id}`.

| Métodos | Sufixo | Operação |
| --- | --- | --- |
| GET | `/processes` | Resumo do processo |
| GET, PATCH | `/negotiation` | Negociação |
| GET, PATCH | `/legal` | Processo jurídico |
| GET, POST | `/contracts` | Contratos 1:N |
| PATCH, DELETE | `/contracts/{contract_id}` | Manutenção de contrato |
| PUT, GET | `/contracts/{contract_id}/file` | Upload/download de arquivo |
| GET, POST | `/purchase-requests` | SC/OCI 1:N |
| PATCH, DELETE | `/purchase-requests/{request_id}` | Manutenção de SC/OCI |
| GET, POST | `/purchase-orders` | OCs 1:N |
| PATCH, DELETE | `/purchase-orders/{order_id}` | Manutenção de OC |

## Workflow

Prefixo `/equipments/{equipment_id}`:

- `GET /available-transitions` e `POST /transitions`: consultar/executar transição permitida.
- `GET /history`: histórico de transições.
- `GET /operational-status`, `POST /standby`, `POST /standby/lift`, `POST /cancel`, `POST /sanitation` e `POST /sanitation/end`: estados operacionais independentes.
- `GET /requirement-waivers`, `POST /requirement-waivers`, `POST /requirement-waivers/{waiver_id}/revoke`: dispensas por grupo com auditoria.
- `GET /reopen-requests`, `POST /reopen-requests`, `POST /reopen-requests/{request_id}/approve` e `POST /reopen-requests/{request_id}/reject`: reabertura com aprovação.

Requisitos de conclusão e políticas de autorização residem no backend. Consulte [domínio e EAP](dominio-eap.md).

## Painel, filas e fornecedores

| Método | Caminho | Operação |
| --- | --- | --- |
| GET | `/dashboard/summary` | Resumo e indicadores |
| GET | `/queues/engineering` | Fila de Engenharia |
| GET | `/queues/legal` | Fila de Jurídico |
| GET | `/queues/procurement` | Fila de Suprimentos |
| GET, POST | `/suppliers` | Consulta/cadastro de fornecedor |
| POST | `/suppliers/import` | Importação de fornecedores |
| GET, PATCH | `/suppliers/{supplier_id}` | Detalhe e manutenção de fornecedor |
| GET, POST, PUT | `/equipments/{equipment_id}/suppliers` | Consulta e vínculo/substituição |
| PATCH, DELETE | `/equipments/{equipment_id}/suppliers/{...}` | Manutenção do vínculo (ver OpenAPI para parâmetro exato) |

O limite de um fornecedor por equipamento é uma regra de negócio, mesmo havendo associação no modelo.

## Importação Monday

Prefixo `/imports/monday`:

| Método | Caminho | Operação |
| --- | --- | --- |
| GET | `/profiles` | Lista perfis de importação disponíveis |
| POST | `/batches` | Upload XLSX e criação de staging |
| GET | `/batches/{batch_id}` | Análise de lote e issues |
| POST | `/plan` | Plano e validação de mapeamentos |
| POST | `/apply` | Solicita aplicação; retorna `202 Accepted` + job |
| GET | `/apply/{job_id}` | Acompanha progresso/resultado |

Os uploads não alteram o domínio até o apply controlado; ver [importação Monday](importacao-monday.md).

## Notificações e templates

- `GET /equipments/{equipment_id}/notifications`: eventos do equipamento.
- `GET /notifications/settings`: condição/configuração do módulo (sem revelar segredos).
- `GET /notifications/rules` e `PUT /notifications/rules/{kind}`: regras e destinatários.
- `GET /notifications/templates`, `GET/PUT /notifications/templates/{kind}` e `POST /notifications/templates/{kind}/reset`: modelos.
- `POST /notifications/templates/{kind}/preview` e `POST /notifications/templates/{kind}/test`: prévia e envio de teste.
- `GET /notifications/deliveries`: outbox/histórico de envio.
- `POST /notifications/test`, `POST /notifications/process` e `POST /notifications/deliveries/{delivery_id}/retry`: operações de teste, processamento e retry, sujeitas a permissões.

## Erros, paginação e contratos

- Validação dos dados de entrada é feita com Pydantic; recursos são protegidos pelas dependências de autenticação e autorização.
- Recursos de outra unidade não devem permitir enumeração por identificador; verifique respostas com escopo.
- Listagens usam filtros/paginação quando oferecidos pelo controller, não necessariamente os mesmos parâmetros para todos os endpoints.
- Em migrações e operações demoradas, trate status assíncrono e mensagens de conflito (por exemplo plano desatualizado e apply já em execução).
- Para gerar o contrato real: instancie a API no ambiente seguro e consulte `/openapi.json` ou o comando de exportação definido no backend; não copie snapshots de documentos históricos.

**Fonte de verificação:** `backend/app/api/v1/router.py`, `backend/app/modules/*/controllers.py`, `backend/app/api/v1/auth.py` e schemas correspondentes.
