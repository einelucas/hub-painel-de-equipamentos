# Auditoria Técnica e Funcional do Painel de Equipamentos

*Aderência entre o Hub de Automação e o processo real no Monday*

Repositório auditado: einelucas/hub-painel-de-equipamentos

Board principal: Equipamentos - LEM C2

Contexto operacional: Luís Eduardo Magalhães, Fase 2, Caldeira 2

Data de corte: 20 de setembro de 2026

Commit analisado: 67701b51d2c10ed683ea6000362cbc0da401f078

Este relatório documenta o estado atual do código, o processo observado no Monday, a aderência entre ambos e o backlog necessário para que o Hub substitua o Monday sem reproduzir suas limitações. A análise foi realizada em modo somente leitura; nenhum arquivo, dado, automação, filtro salvo ou configuração foi alterado.

**Conclusão principal:** o Hub já possui um núcleo arquitetural coerente e parte relevante do MVP, mas ainda não pode substituir o Monday. Os bloqueadores são as regras oficiais de prazo e indicadores, exceções do workflow, matriz de responsabilidades, recursos operacionais de notificação/documentos e uma migração reconciliada dos dados.

# 1. Resumo executivo

| **Dimensão**    | **Situação** | **Conclusão**                                                                                 |
|-----------------|--------------|-----------------------------------------------------------------------------------------------|
| **Cadastro**    | **PRONTO**   | Equipamentos, componentes, catálogos, responsáveis e fornecedores possuem persistência e API. |
| **Workflow**    | **PARCIAL**  | Fluxo 0 a 8 está centralizado, mas exceções do Monday e estados especiais não existem.        |
| **Negociação**  | **PARCIAL**  | Equalização e data existem; prazos, criticidade derivada e FUP estão ausentes.                |
| **Jurídico**    | **PARCIAL**  | Chamado, minuta e contrato existem; atalho observado e documentos jurídicos não.              |
| **Suprimentos** | **PARCIAL**  | SC ou OCI, OC, valor e fornecedor existem; bypass, competição e integrações não.              |
| **Dashboard**   | **PARCIAL**  | Contagens básicas existem; indicadores de prazo, aderência e criticidade não.                 |
| **Histórico**   | **PRONTO**   | Transições e mudanças de processo são consolidadas e auditadas.                               |
| **Permissões**  | **PARCIAL**  | Há RBAC e escopo por unidade; falta segregação real por departamento/equipe.                  |
| **Migração**    | **AUSENTE**  | Não existe importador, mapeamento versionado nem reconciliação C2/F2.                         |

**\[REPOSITÓRIO\]** Branch main no commit 67701b5; 224 arquivos rastreados, quatro migrations, 54 testes backend e 52 testes frontend declarados.

**\[MONDAY\]** C2 mantém 41 equipamentos, 164 subitens informados pelos grupos, 21 automações e dashboard com 163 aquisições.

**\[COMPARAÇÃO\]** A base do Hub cobre o núcleo cadastral e o caminho feliz, mas não cobre todos os mecanismos operacionais necessários para o corte.

# 2. Arquitetura atual do repositório

O projeto é um monorepositório com duas aplicações independentes. O frontend Nuxt consome a API FastAPI; serviços de domínio concentram validações e persistem no PostgreSQL por SQLAlchemy assíncrono. Alembic versiona o schema. OIDC e Keycloak são previstos para produção, com bypass restrito ao desenvolvimento.

| **Camada**       | **Tecnologia**                   | **Responsabilidade**                                                 | **Evidência**                                       |
|------------------|----------------------------------|----------------------------------------------------------------------|-----------------------------------------------------|
| **Frontend**     | Nuxt 4, Vue 3, TypeScript, Pinia | Telas, contexto Unidade → Equipamento, formulários, filas e gráficos | frontend/pages, components, stores/moduleContext.ts |
| **API**          | FastAPI, Pydantic                | Contratos REST, autenticação e autorização                           | backend/app/api/v1 e modules/\*/router.py           |
| **Domínio**      | Services Python                  | Regras, escopo, transições, auditoria e agregações                   | modules/\*/service.py e workflow/stages.py          |
| **Persistência** | PostgreSQL, SQLAlchemy 2 async   | Entidades normalizadas e constraints                                 | models e alembic/versions                           |
| **Identidade**   | OIDC/Keycloak + DEV bypass       | JWT, usuário, perfis e permissões                                    | core/auth.py e core/permissions.py                  |
| **Qualidade**    | Pytest, Vitest, Ruff, MyPy       | Testes de rotas, regras e componentes                                | backend/tests e frontend/tests                      |

Fluxo atual: Nuxt/Vue → /api/v1 → routers → services e regras de domínio → SQLAlchemy async → PostgreSQL. A mudança de etapa é exceção importante: somente workflow/service.py pode alterar equipment.current_stage.

# 3. Funcionalidades já existentes

| **Funcionalidade**                     | **Classificação**             | **Evidência resumida**                                                      |
|----------------------------------------|-------------------------------|-----------------------------------------------------------------------------|
| **Equipamentos**                       | **IMPLEMENTADA**              | CRUD parcial sem exclusão; filtros, paginação, ordenação e exportação XLSX. |
| **Componentes**                        | **IMPLEMENTADA**              | Listagem, criação e edição com lead time, frete e datas.                    |
| **Unidades e contextos**               | **IMPLEMENTADA**              | Catálogos e filtro global encadeado Unidade → Equipamento.                  |
| **Áreas, disciplinas e Work Packages** | **IMPLEMENTADA**              | Cadastros estruturados e administração contextual.                          |
| **Responsáveis**                       | **IMPLEMENTADA**              | FK para User e seletor restrito ao acesso da unidade.                       |
| **Fornecedores**                       | **IMPLEMENTADA**              | Cadastro mestre e vínculo N:N; um principal por equipamento.                |
| **Negociação**                         | **PARCIALMENTE IMPLEMENTADA** | Equalização e data; sem fórmulas ou processo competitivo.                   |
| **Jurídico**                           | **PARCIALMENTE IMPLEMENTADA** | Abertura, chamado, minuta e contrato; sem anexos e aprovações formais.      |
| **SC ou OCI e OC**                     | **PARCIALMENTE IMPLEMENTADA** | Número, tipo, datas e valor; sem integração ERP e bypass.                   |
| **CAPEX**                              | **IMPLEMENTADA**              | Valor estimado no equipamento e soma no dashboard.                          |
| **Workflow**                           | **PARCIALMENTE IMPLEMENTADA** | 0–8, pré-condições, concorrência, reabertura e histórico.                   |
| **Histórico e auditoria**              | **IMPLEMENTADA**              | AuditLog + WorkflowTransition; tela administrativa de auditoria.            |
| **Notificações**                       | ESTRUTURA PREPARADA           | Sino do shell preservado; nenhuma notificação de domínio local.             |
| **Arquivos e comentários**             | NÃO ENCONTRADA                | Sem tabelas, endpoints ou interface do módulo.                              |
| **Dashboards**                         | **PARCIALMENTE IMPLEMENTADA** | Totais básicos, estágio, negociação e startup; prazos indisponíveis.        |
| **Views, agrupamentos e Kanban**       | NÃO ENCONTRADA                | Filas fixas existem, mas não há saved views nem Kanban.                     |
| **Permissões**                         | **PARCIALMENTE IMPLEMENTADA** | VIEWER, ANALYST, ADMIN e escopo por unidade; sem perfis por área.           |
| **Migração Monday**                    | NÃO ENCONTRADA                | Nenhum importador ou rotina de reconciliação.                               |

# 4. Modelo de banco atual

| **Tabela**                               | **Cardinalidade principal**   | **Campos-chave**                    | **Observação**                             |
|------------------------------------------|-------------------------------|-------------------------------------|--------------------------------------------|
| **User, Session, Account, Verification** | Identidade                    | role, active, externalUserId        | Base compartilhada de autenticação.        |
| **AuditLog**                             | N:1 User                      | action, entity, before/after JSONB  | Auditoria genérica.                        |
| **unit**                                 | 1:N project_context e area    | code, name, active                  | Unidade corporativa.                       |
| **project_context**                      | N:1 unit                      | code, name                          | Representa C2/F2 sem duplicar schema.      |
| **area**                                 | N:1 unit                      | name                                | Cadastro por unidade.                      |
| **discipline**                           | 1:N equipment                 | code, name                          | Catálogo global.                           |
| **work_package**                         | N:1 project_context           | code, name                          | Pacote por contexto.                       |
| **equipment**                            | N:1 contexto; 1:N componentes | name, startup, current_stage, CAPEX | Estado canônico 0–8.                       |
| **equipment_component**                  | N:1 equipment                 | tag, sector, lead_time, freight     | Subitem técnico.                           |
| **negotiation**                          | 1:1 equipment                 | equalized, negotiated_at            | Cardinalidade provisória.                  |
| **legal_process**                        | 1:1 equipment                 | opened_at, ticket, draft flags      | Sem documentos.                            |
| **contract**                             | 1:1 equipment                 | number, executed_at, delivery_at    | Uma contratação por equipamento.           |
| **purchase_request**                     | 1:1 equipment                 | kind, number, requested_at          | kind restrito a SC ou OCI.                 |
| **purchase_order**                       | 1:1 equipment                 | number, ordered_at, amount          | Uma OC por equipamento.                    |
| **workflow_transition**                  | N:1 equipment                 | from, to, reason, actor             | Histórico imutável de etapa.               |
| **user_unit_access**                     | N:N User ↔ unit               | user_id, unit_id                    | Escopo territorial.                        |
| **supplier e equipment_supplier**        | N:N supplier ↔ equipment      | role, is_primary                    | Um principal garantido por índice parcial. |

**\[INFERÊNCIA\]** A estrutura 1:1 de negociação, contrato, SC/OCI e OC é adequada apenas se a operação confirmar uma ocorrência de cada por equipamento. O próprio código registra essa decisão como pendente.

# 5. Backend atual

| **Método**       | **Endpoint**                            | **Finalidade**              | **Banco**                  | **Estado**       |
|------------------|-----------------------------------------|-----------------------------|----------------------------|------------------|
| **GET**          | /health/live; /health/ready             | Saúde da API e banco        | Infraestrutura             | **IMPLEMENTADA** |
| **GET**          | /auth/me                                | Usuário e permissões        | User                       | **IMPLEMENTADA** |
| **GET/POST**     | /usuarios                               | Listar e criar usuários     | User                       | **IMPLEMENTADA** |
| **PATCH**        | /usuarios/{id}                          | Editar usuário              | User                       | **IMPLEMENTADA** |
| **GET/PUT**      | /usuarios/{id}/units                    | Consultar/substituir escopo | user_unit_access           | **IMPLEMENTADA** |
| **GET**          | /responsibles                           | Responsáveis permitidos     | User + access              | **IMPLEMENTADA** |
| **GET**          | /auditoria                              | Eventos auditáveis          | AuditLog                   | **IMPLEMENTADA** |
| **GET/POST**     | /units                                  | Catálogo de unidades        | unit                       | **IMPLEMENTADA** |
| **PATCH**        | /units/{id}                             | Editar/ativar unidade       | unit                       | **IMPLEMENTADA** |
| **GET/POST**     | /units/{id}/project-contexts            | Contextos da unidade        | project_context            | **IMPLEMENTADA** |
| **PATCH**        | /project-contexts/{id}                  | Editar/ativar contexto      | project_context            | **IMPLEMENTADA** |
| **GET/POST**     | /areas                                  | Áreas por unidade           | area                       | **IMPLEMENTADA** |
| **PATCH**        | /areas/{id}                             | Editar/ativar área          | area                       | **IMPLEMENTADA** |
| **GET/POST**     | /disciplines                            | Disciplinas                 | discipline                 | **IMPLEMENTADA** |
| **PATCH**        | /disciplines/{id}                       | Editar/ativar disciplina    | discipline                 | **IMPLEMENTADA** |
| **GET/POST**     | /work-packages                          | Work Packages               | work_package               | **IMPLEMENTADA** |
| **PATCH**        | /work-packages/{id}                     | Editar/ativar pacote        | work_package               | **IMPLEMENTADA** |
| **GET/POST**     | /equipments                             | Listar/criar equipamento    | equipment                  | **IMPLEMENTADA** |
| **GET/PATCH**    | /equipments/{id}                        | Detalhar/editar equipamento | equipment                  | **IMPLEMENTADA** |
| **GET/POST**     | /equipments/{id}/components             | Listar/criar componentes    | equipment_component        | **IMPLEMENTADA** |
| **PATCH**        | /components/{id}                        | Editar componente           | equipment_component        | **IMPLEMENTADA** |
| **GET**          | /equipments/{id}/processes              | Resumo dos cinco processos  | process tables             | **IMPLEMENTADA** |
| **GET/PATCH**    | /equipments/{id}/negotiation            | Negociação                  | negotiation                | **PARCIAL**      |
| **GET/PATCH**    | /equipments/{id}/legal                  | Jurídico                    | legal_process              | **PARCIAL**      |
| **GET/PATCH**    | /equipments/{id}/contract               | Contrato                    | contract                   | **PARCIAL**      |
| **GET/PATCH**    | /equipments/{id}/purchase-request       | SC ou OCI                   | purchase_request           | **PARCIAL**      |
| **GET/PATCH**    | /equipments/{id}/purchase-order         | OC                          | purchase_order             | **PARCIAL**      |
| **GET**          | /equipments/{id}/available-transitions  | Opções e requisitos         | workflow                   | **IMPLEMENTADA** |
| **POST**         | /equipments/{id}/transitions            | Avançar ou reabrir          | workflow_transition        | **PARCIAL**      |
| **GET**          | /equipments/{id}/history                | Timeline consolidada        | AuditLog + transitions     | **IMPLEMENTADA** |
| **GET/POST**     | /suppliers                              | Catálogo de fornecedores    | supplier                   | **IMPLEMENTADA** |
| **GET/PATCH**    | /suppliers/{id}                         | Detalhar/editar fornecedor  | supplier                   | **IMPLEMENTADA** |
| **GET/POST**     | /equipments/{id}/suppliers              | Listar/vincular             | equipment_supplier         | **IMPLEMENTADA** |
| **PATCH/DELETE** | /equipments/{id}/suppliers/{supplierId} | Atualizar/remover vínculo   | equipment_supplier         | **IMPLEMENTADA** |
| **GET**          | /queues/engineering                     | Fila etapas 0–2             | equipment + processes      | **PARCIAL**      |
| **GET**          | /queues/legal                           | Fila etapas 3–5             | equipment + legal/contract | **PARCIAL**      |
| **GET**          | /queues/procurement                     | Fila etapas 6–7             | request/order/supplier     | **PARCIAL**      |
| **GET**          | /dashboard/summary                      | Agregações do painel        | equipment/processes        | **PARCIAL**      |

Pontos fortes: transações com SELECT FOR UPDATE, prevenção de pulo de etapa, 409 em concorrência, auditoria atômica e escopo por unidade com resposta 404 para evitar enumeração. Pontos pendentes: regras de prazo, eventos assíncronos, documentos, exceções do workflow e integração corporativa.

# 6. Frontend atual

| **Rota**                    | **Função**                                               | **Backend**                   | **Estado**          |
|-----------------------------|----------------------------------------------------------|-------------------------------|---------------------|
| **/dashboard**              | Visão geral e gráficos                                   | /dashboard/summary            | **PARCIAL**         |
| **/equipamentos**           | Lista, filtros, exportação e administração               | /equipments e catálogos       | **IMPLEMENTADA**    |
| **/equipamentos/\[id\]**    | Detalhe, processo, componentes, fornecedores e histórico | equipments/processes/workflow | **PARCIAL**         |
| **/engenharia**             | Fila fixa 0–2                                            | /queues/engineering           | **PARCIAL**         |
| **/juridico**               | Fila fixa 3–5                                            | /queues/legal                 | **PARCIAL**         |
| **/suprimentos**            | Fila fixa 6–7 e fornecedores                             | /queues/procurement           | **PARCIAL**         |
| **/fornecedores**           | Cadastro auxiliar                                        | /suppliers                    | **IMPLEMENTADA**    |
| **/dashboard/auditoria**    | Consulta administrativa                                  | /auditoria                    | **IMPLEMENTADA**    |
| **/login e /auth/callback** | Entrada OIDC                                             | /auth/me                      | ESTRUTURA PREPARADA |

Todas as telas operacionais tratam loading, erro, vazio e ausência de permissão. O contexto Unidade + Equipamento é compartilhado por Pinia. O equipamento é opcional; sem seleção, o sistema consolida a unidade. Fase, contexto, área e responsável permanecem filtros secundários ou atributos estruturados.

# 7. Workflow inferido do código

| **Transição**                 | **Pré-condição do código**                                         | **Permissão**       |
|-------------------------------|--------------------------------------------------------------------|---------------------|
| **0 → 1 Negociação**          | Nenhuma além do cadastro                                           | workflow:transition |
| **1 → 2 Equalização**         | negotiation.equalized = true                                       | workflow:transition |
| **2 → 3 Abertura do chamado** | negotiation.negotiated_at preenchida                               | workflow:transition |
| **3 → 4 Aprovação da minuta** | opened_at e ticket_number                                          | workflow:transition |
| **4 → 5 Escrituração**        | draft_prepared e draft_approved                                    | workflow:transition |
| **5 → 6 SC ou OCI**           | contract_number e executed_at                                      | workflow:transition |
| **6 → 7 Aprovação da OC**     | kind, request_number e requested_at                                | workflow:transition |
| **7 → 8 Concluído**           | OC number/date, contract delivery e todos os requisitos anteriores | workflow:transition |
| **\>=2 → 1 Reabrir**          | motivo obrigatório; ADMIN                                          | workflow:reopen     |

**\[REPOSITÓRIO\]** workflow/stages.py e workflow/service.py são a fonte única; PATCH comum rejeita currentStage.

# 8. Dívidas técnicas encontradas

| **Achado**                                   | **Evidência**                         | **Impacto**                                                        |
|----------------------------------------------|---------------------------------------|--------------------------------------------------------------------|
| **Cardinalidade 1:1 provisória**             | models/process.py                     | Não suporta múltiplos contratos, SCs ou OCs.                       |
| **Permissão process:write ampla**            | core/permissions.py                   | ANALYST pode editar todas as áreas do processo.                    |
| **criticality e origin livres**              | models/equipment.py                   | Catálogo e validação ainda inconsistentes.                         |
| **Filas por intervalo fixo**                 | queues/service.py QUEUE_STAGES        | Não reproduzem filtros salvos ou exceções reais.                   |
| **Prazos indisponíveis**                     | dashboard DEADLINE_UNAVAILABLE_REASON | Bloqueia indicadores operacionais essenciais.                      |
| **Exportação client-side paginada**          | pages/equipamentos/index.vue          | Teto de volume e custo no navegador.                               |
| **Sem worker/outbox**                        | não encontrado                        | Notificações e integrações não possuem execução confiável.         |
| **Sem anexo/comentário**                     | não encontrado                        | Perda de documentos e contexto operacional na substituição.        |
| **Sem seed/importador**                      | não encontrado                        | Não há caminho reproduzível para homologação e corte.              |
| **Documentação mistura decisão e pendência** | docs/etapas                           | Algumas regras podem parecer definitivas sem validação de negócio. |

# 9. Estrutura real do Monday

| **Elemento**          | **Nome**                                              | **Volume ou configuração**                          | **Papel**                              |
|-----------------------|-------------------------------------------------------|-----------------------------------------------------|----------------------------------------|
| **Workspace**         | 08\. Luis Eduardo Magalhães                           | Planejamento, aquisições e contratos                | Contexto da unidade LEM.               |
| **Board principal**   | Equipamentos - LEM C2                                 | 41 equipamentos; 164 subitens; 21 automações        | Operação da Caldeira 2.                |
| **Board relacionado** | Equipamentos LEM F2                                   | 77 equipamentos; 540 subitens; 19 automações        | Referência semelhante e mais populada. |
| **Views C2**          | Principal, Engenharia, Jurídico, Suprimentos, Gráfico | Filtros e colunas por área                          | Trabalho diário e gestão.              |
| **Grupos C2**         | Fases 0 a 8                                           | 31 em fase 0; 6 em fase 4; 3 em fase 6; 1 concluído | Representação visual do workflow.      |

**\[MONDAY\]** Inspeção ao vivo em 20/09/2026 confirmou os volumes, as cinco views, o dashboard e o contador de 21 automações.

# 10. Campos e dicionário de dados

| **Campo Monday**                    | **Tipo**       | **Origem**       | **Uso**                                           |
|-------------------------------------|----------------|------------------|---------------------------------------------------|
| **Equipamento**                     | Nome           | Manual           | Registro mestre                                   |
| **Status Negociação**               | Fórmula        | Derivado         | Atrasado, urgente, próximo, no prazo ou concluído |
| **F.Data Limite Negociação**        | Fórmula        | Derivado         | Prazo de negociação                               |
| **Status Necessidade Obra**         | Fórmula        | Derivado         | Risco de necessidade                              |
| **F.Limite Entrega Obra**           | Fórmula        | Derivado         | Data limite de chegada                            |
| **A.Status**                        | Status         | Automação/manual | Estado do processo                                |
| **0.Fornecedores**                  | Connect Boards | Relacionamento   | Fornecedor(es)                                    |
| **0.Origem**                        | Status         | Manual           | Origem da demanda                                 |
| **0.Startup/Grãos**                 | Data           | Manual           | Marco de startup                                  |
| **0.Disciplina**                    | Status/label   | Manual           | Roteamento técnico                                |
| **F.Data Limite para contrato/OC**  | Fórmula        | Derivado         | Prazo consolidado                                 |
| **0.Criticidade**                   | Prioridade     | Manual/derivado  | Curto, médio ou longo                             |
| **E.Data de Entrega contrato**      | Mirror         | Automático       | Entrega contratual espelhada                      |
| **0.Responsável**                   | Texto          | Manual           | Responsável operacional                           |
| **0.Área**                          | Texto          | Manual           | Área do equipamento                               |
| **Work Package**                    | Dropdown       | Manual           | Pacote de engenharia                              |
| **1.Equalização**                   | Checkbox       | Manual           | Marco da equalização                              |
| **2.Data da Negociação**            | Data           | Manual           | Marco de negociação                               |
| **3.Data de Abertura do Chamado**   | Data           | Manual           | Abertura jurídica                                 |
| **3.Chamado Jurídico**              | Texto          | Manual           | Número do chamado                                 |
| **3.Elab. Minuta**                  | Checkbox       | Manual           | Minuta elaborada                                  |
| **4.Minuta Aprovada**               | Checkbox       | Manual           | Minuta aprovada                                   |
| **5.Data Escrituração**             | Data           | Manual           | Escrituração do contrato                          |
| **5.Numero Contrato**               | Texto          | Manual           | Identificador contratual                          |
| **5.Data de Entrega pelo contrato** | Data           | Manual           | Compromisso de entrega                            |
| **6.Data de SC/OCI**                | Data           | Manual           | Data da solicitação                               |
| **6.Numero SC/OCI**                 | Texto          | Manual/bypass    | Identificador SC/OCI                              |
| **7.Data OC**                       | Data           | Manual           | Data da ordem                                     |
| **7.Numero OC**                     | Texto          | Manual           | Identificador da OC                               |
| **E.Lead Time de Fabricação**       | Mirror         | Automático       | Consolidação dos subitens                         |
| **E.Dias Antes do Startup**         | Mirror         | Automático       | Antecedência consolidada                          |
| **ESPELHO-FORMULA-FRETE**           | Mirror         | Automático       | Frete consolidado                                 |
| **Kickoff**                         | Data           | Manual           | Lembrete/notificação                              |
| **Leadtime Negociação**             | Fórmula        | Derivado         | Duração                                           |
| **Prazo Máximo Negociação**         | Fórmula        | Derivado         | Limite máximo                                     |
| **CAPEX Estimado**                  | Número         | Manual           | Orçamento                                         |

# 11. Subitens e componentes

| **Campo de subitem**               | **Conceito**                     | **Situação no Hub**                       |
|------------------------------------|----------------------------------|-------------------------------------------|
| **Subelemento**                    | Componente ou linha de aquisição | equipment_component.name                  |
| **TAG**                            | Identificação técnica            | equipment_component.tag                   |
| **Startup/Grãos**                  | Marco específico do componente   | Apenas equipment.startup_at; lacuna       |
| **Setor**                          | Setor operacional                | equipment_component.sector como texto     |
| **Lead Time de Fabricação**        | Prazo de fabricação              | lead_time_days                            |
| **Disponível Coleta**              | Data derivada                    | Ausente                                   |
| **Dias Antes do Startup**          | Antecedência                     | pre_start_days                            |
| **Data de Entrega pelo contrato**  | Entrega do componente            | contract_delivery_at                      |
| **Entrega planejada vs negociada** | Aderência                        | Ausente                                   |
| **Status da Data de Entrega**      | Risco                            | Ausente                                   |
| **Arquivos**                       | Documentos                       | Ausente                                   |
| **Frete em dias**                  | Prazo logístico                  | freight_days                              |
| **Fórmulas auxiliares e Item ID**  | Implementação do Monday          | Não migrar; substituir por cálculo e UUID |

**\[COMPARAÇÃO\]** O Hub modela bem o componente, mas ainda não o trata plenamente como unidade de aquisição; processos comerciais e jurídicos estão associados ao equipamento pai.

# 12. Workflow real observado no Monday

| **Etapa**                 | **Marco observado**             | **Exceções**                                               |
|---------------------------|---------------------------------|------------------------------------------------------------|
| **0 Nova demanda**        | Criação e classificação         | Automação inicial usa status Undefined antes de mover.     |
| **1 Negociação**          | Entrada/reinício                | Botão Reiniciar Negociação.                                |
| **2 Equalização**         | Checkbox 1.Equalização          | Avança quando a data de negociação ainda está vazia.       |
| **3 Abertura do chamado** | Data da negociação              | Chamado e data jurídica ainda vazios.                      |
| **4 Aprovação da minuta** | Chamado, abertura e elaboração  | Existe atalho 2 → 4 quando chamado e data são preenchidos. |
| **5 Escrituração**        | Minuta aprovada                 | Requisitos anteriores também verificados.                  |
| **6 SC ou OCI**           | Contrato e escrituração         | Sem tipo separado no Monday; número e data.                |
| **7 Aprovação da OC**     | SC/OCI preenchida               | Bypass manual de Suprimentos observado.                    |
| **8 Concluído**           | OC, entrega e marcos anteriores | Três automações alternativas de conclusão.                 |

**\[PRECISA VALIDAÇÃO\]** Standby, Cancelado e Não se Aplica aparecem no F2 e não estão confirmados como estados oficiais do C2.

# 13. Automações

| **Automação**                 | **Gatilho**               | **Ação**                   | **Finalidade**           |
|-------------------------------|---------------------------|----------------------------|--------------------------|
| **8 - OC B**                  | Número OC muda            | Concluir e mover           | Estado 7 → 8             |
| **4 - Minuta C**              | Elaboração muda           | Avançar e mover            | Estado 3 → 4             |
| **5 - Aprovação da Minuta A** | Minuta aprovada muda      | Avançar e mover            | Estado 4 → 5             |
| **8 - OC C**                  | Entrega contrato muda     | Concluir e mover           | Estado 7 → 8             |
| **4 - Minuta B**              | Abertura muda no status 2 | Pular para fase 4          | Atalho excepcional       |
| **FUP**                       | Status muda               | Notificar grupo            | Follow-up                |
| **7 - SC ou OCI A**           | Número SC/OCI muda        | Avançar e mover            | Estado 6 → 7             |
| **8 - OC A**                  | Data OC muda              | Concluir e mover           | Estado 7 → 8             |
| **3 - Chamado Jurídico A**    | Data negociação muda      | Avançar e mover            | Estado 2 → 3             |
| **Reiniciar Negociação**      | Botão                     | Mover para fase 1          | Reabertura               |
| **4 - Minuta A**              | Chamado muda              | Avançar e mover            | Estado 3 → 4             |
| **Clear Button - Auxiliar**   | Botão                     | Limpar coluna              | Ação auxiliar            |
| **2 - Equalização A**         | Equalização muda          | Avançar e mover            | Estado 1 → 2             |
| **7 - SC ou OCI B**           | Data SC/OCI muda          | Avançar e mover            | Estado 6 → 7             |
| **6 - Escrituração B**        | Número contrato muda      | Avançar e mover            | Estado 5 → 6             |
| **7 - Bypass Suprimentos A**  | Botão                     | Avançar e preencher SC/OCI | Bypass                   |
| **6 - Escrituração A**        | Data escrituração muda    | Avançar e mover            | Estado 5 → 6             |
| **Escalonamento**             | Coluna muda               | Criar item e conectar      | Board externo            |
| **Conclusão**                 | Status vira 8             | Mover para fase 8          | Sincronização redundante |
| **0 - Nova Demanda A**        | Item criado               | Inicializar e mover        | Entrada                  |
| **Pronto para uso**           | Kickoff chega             | Notificar inscritos        | Lembrete                 |

# 14. Fórmulas

| **Fórmula**                        | **Entradas aparentes**           | **Resultado**       | **Confirmação**      |
|------------------------------------|----------------------------------|---------------------|----------------------|
| **Status Negociação**              | datas, etapa e prazo             | 5 rótulos de status | REGRA NÃO CONFIRMADA |
| **Data Limite Negociação**         | startup, lead time, antecedência | data                | REGRA NÃO CONFIRMADA |
| **Prazo Máximo Negociação**        | criticidade e datas              | data                | REGRA NÃO CONFIRMADA |
| **Status Necessidade Obra**        | entrega e necessidade            | faixa de risco      | REGRA NÃO CONFIRMADA |
| **Limite Entrega em Obra**         | startup, antecedência e frete    | data                | REGRA NÃO CONFIRMADA |
| **Disponível Coleta**              | entrega/fabricação               | data                | REGRA NÃO CONFIRMADA |
| **Entrega planejada vs negociada** | planejada e contrato             | aderência           | REGRA NÃO CONFIRMADA |
| **Índices**                        | aderência e criticidade          | percentual/média    | REGRA NÃO CONFIRMADA |

A interface confirma os rótulos e exemplos, mas não expõe com segurança as expressões completas. O relatório não deduz fórmulas a partir dos nomes. A implementação deve esperar uma especificação de entradas, calendário, arredondamento, fuso horário, tratamento de nulos e exemplos de aceitação.

# 15. Views e filtros

| **View**                | **Configuração observada**                               | **Objetivo**         | **Implicação no Hub**                                 |
|-------------------------|----------------------------------------------------------|----------------------|-------------------------------------------------------|
| **Quadro principal**    | Grupos por fase                                          | Operação completa    | Lista única com agrupamento derivado.                 |
| **Engenharia MetalMec** | 10 de 41; 3 filtros; 5 ocultas; agrupada por responsável | Carteira técnica     | Filtros salvos por equipe e responsável.              |
| **Jurídico**            | 6 de 41; 2 filtros; 17 ocultas                           | Pendências jurídicas | Fila por requisitos, não só intervalo 3–5.            |
| **Suprimentos**         | 0 de 41; 2 filtros; 3 ordenações; 8 ocultas; agrupamento | Fila de compras      | Filtro atual precisa validação; não copiar cegamente. |
| **Gráfico**             | 12 widgets                                               | Gestão executiva     | Agregações com definição versionada.                  |

# 16. Dashboards

| **Indicador Monday**                   | **Resultado observado**          | **Hub atual**                | **Situação**                |
|----------------------------------------|----------------------------------|------------------------------|-----------------------------|
| **Quantidade por status**              | 31/6/3/1 nas fases ocupadas      | Distribuição 0–8             | **COMPLETO**                |
| **Prazos de negociação**               | 1 atrasado, 1 urgente, 1 próximo | Indisponível                 | **NÃO IMPLEMENTADO**        |
| **Status dos prazos**                  | 1/1/1/28/10                      | Indisponível                 | **NÃO IMPLEMENTADO**        |
| **Negociações concluídas**             | 0 de 163 aquisições              | negotiated_at / equipamentos | INCORRETO/PRECISA VALIDAÇÃO |
| **Contagem até startup**               | Widget existente                 | Próxima startup futura       | **PARCIAL**                 |
| **Emissões de OC**                     | 0 de 163                         | OCs com número               | **PARCIAL**                 |
| **Total emitido em OC**                | Widget existente                 | Soma amount                  | **PARCIAL**                 |
| **Total de aquisições**                | 163                              | Componentes 164              | INCORRETO/PRECISA VALIDAÇÃO |
| **Índices de aderência e criticidade** | 0/sem resultado                  | Ausentes                     | **NÃO IMPLEMENTADO**        |

# 17. Matriz de aderência Repositório × Monday

| **Funcionalidade Monday**     | **Existe no Hub** | **Estado**              | **Problema encontrado**       | **Ação necessária**                 |
|-------------------------------|-------------------|-------------------------|-------------------------------|-------------------------------------|
| **Filtro global Unidade**     | Sim               | **COMPLETO**            | Multiunidade centralizada     | Manter como fonte global            |
| **Filtro global Equipamento** | Sim               | **COMPLETO**            | Dependente da unidade         | Manter opcional                     |
| **Cadastro de equipamento**   | Sim               | **COMPLETO**            | Estruturado                   | Migrar e reconciliar                |
| **Subitens/componentes**      | Sim               | **PARCIAL**             | Processo ainda no pai         | Validar unidade de aquisição        |
| **Fornecedor conectado**      | Sim               | **COMPLETO**            | N:N melhor modelado           | Migrar vínculos                     |
| **Responsável**               | Sim               | **COMPLETO**            | FK melhor que texto           | Mapear nomes para usuários          |
| **Workflow 0–8**              | Sim               | **PARCIAL**             | Caminho feliz centralizado    | Cobrir exceções confirmadas         |
| **Atalho 2 → 4**              | Não               | **PRECISA CONFIRMAÇÃO** | Monday permite                | Decidir se é regra legítima         |
| **Reiniciar negociação**      | Sim               | **PARCIAL**             | Hub exige ADMIN e motivo      | Validar política                    |
| **Standby/Cancelado/N/A**     | Não               | **NÃO IMPLEMENTADO**    | Observado no F2               | Definir catálogo                    |
| **Negociação**                | Sim               | **PARCIAL**             | Sem prazo e status derivados  | Implementar após fórmula            |
| **Jurídico/contrato**         | Sim               | **PARCIAL**             | Sem arquivos/aprovação formal | Completar operação                  |
| **SC/OCI e OC**               | Sim               | **PARCIAL**             | Sem bypass/ERP                | Completar e integrar                |
| **FUP e kickoff**             | Não               | **NÃO IMPLEMENTADO**    | Automações reais              | Worker + notificação                |
| **Escalonamento**             | Não               | **NÃO IMPLEMENTADO**    | Cria item conectado           | Identificar destino/regra           |
| **Fórmulas de prazo**         | Não               | **NÃO IMPLEMENTADO**    | Essenciais ao dashboard       | Especificar e testar                |
| **Dashboard básico**          | Sim               | **PARCIAL**             | Contagens básicas             | Completar métricas                  |
| **Views salvas**              | Não               | **NÃO IMPLEMENTADO**    | Uso por equipe                | Saved views ou filas parametrizadas |
| **Kanban**                    | Não               | **NÃO IMPLEMENTADO**    | F2 utiliza                    | P2 após núcleo                      |
| **Anexos/comentários**        | Não               | **NÃO IMPLEMENTADO**    | Uso precisa confirmação       | P1 se operacionais                  |
| **Histórico/auditoria**       | Sim               | **COMPLETO**            | Melhor rastreabilidade        | Manter                              |
| **Exportação**                | Sim               | **PARCIAL**             | Client-side                   | Server-side para escala             |
| **Permissões por unidade**    | Sim               | **COMPLETO**            | Melhor que board privado      | Manter                              |
| **Permissões por área**       | Não               | **NÃO IMPLEMENTADO**    | Perfis reais não mapeados     | Segregar responsabilidades          |
| **Migração e reconciliação**  | Não               | **NÃO IMPLEMENTADO**    | Bloqueador do corte           | Criar pipeline idempotente          |

# 18. Comparação campo a campo

| **Campo Monday**              | **Campo Hub**             | **Tipo Monday** | **Tipo Hub**  | **Compatibilidade**   | **Ajuste**                               |
|-------------------------------|---------------------------|-----------------|---------------|-----------------------|------------------------------------------|
| **Equipamento**               | equipment.name            | Nome            | String        | **equivalente**       | Nenhum                                   |
| **A.Status**                  | equipment.current_stage   | Status          | Integer 0–8   | **melhor modelado**   | Adicionar estados especiais se aprovados |
| **0.Fornecedores**            | equipment_supplier        | Connect Boards  | N:N FK        | **melhor modelado**   | Migrar relacionamento                    |
| **0.Origem**                  | equipment.origin          | Status          | String        | parcialmente modelado | Validar catálogo                         |
| **0.Startup/Grãos**           | equipment.startup_at      | Date            | Date          | **equivalente**       | Nenhum                                   |
| **0.Disciplina**              | equipment.discipline_id   | Label           | FK            | **melhor modelado**   | Mapear opções                            |
| **0.Criticidade**             | equipment.criticality     | Priority        | String        | parcialmente modelado | Definir enum/regra                       |
| **0.Responsável**             | responsible_user_id       | Text            | FK User       | **melhor modelado**   | Tabela de correspondência                |
| **0.Área**                    | area_id                   | Text            | FK Area       | **melhor modelado**   | Normalizar valores                       |
| **Work Package**              | work_package_id           | Dropdown        | FK            | **melhor modelado**   | Normalizar por contexto                  |
| **1.Equalização**             | negotiation.equalized     | Checkbox        | Boolean       | **equivalente**       | Registrar ator/data se necessário        |
| **2.Data Negociação**         | negotiated_at             | Date            | Date          | **equivalente**       | Nenhum                                   |
| **3.Abertura Chamado**        | legal.opened_at           | Date            | Date          | **equivalente**       | Nenhum                                   |
| **3.Chamado Jurídico**        | legal.ticket_number       | Text            | String        | **equivalente**       | Nenhum                                   |
| **3.Elab. Minuta**            | legal.draft_prepared      | Checkbox        | Boolean       | **equivalente**       | Considerar completed_at/actor            |
| **4.Minuta Aprovada**         | legal.draft_approved      | Checkbox        | Boolean       | **equivalente**       | Considerar aprovação formal              |
| **5.Data Escrituração**       | contract.executed_at      | Date            | Date          | **equivalente**       | Nenhum                                   |
| **5.Numero Contrato**         | contract.contract_number  | Text            | String        | **equivalente**       | Validar cardinalidade                    |
| **5.Entrega contrato**        | contract.delivery_at      | Date/Mirror     | Date          | **melhor modelado**   | Validar pai vs componente                |
| **6.Data SC/OCI**             | request.requested_at      | Date            | Date          | **equivalente**       | Nenhum                                   |
| **6.Numero SC/OCI**           | request.request_number    | Text            | String        | **equivalente**       | Bypass pendente                          |
| **Tipo SC/OCI**               | request.kind              | Implícito       | Enum-like     | **melhor modelado**   | Confirmar regra                          |
| **7.Data OC**                 | order.ordered_at          | Date            | Date          | **equivalente**       | Nenhum                                   |
| **7.Numero OC**               | order.order_number        | Text            | String        | **equivalente**       | Validar cardinalidade                    |
| **Valor OC**                  | order.amount              | Number          | Numeric(18,2) | **melhor modelado**   | Definir moeda                            |
| **CAPEX Estimado**            | equipment.capex_estimated | Number          | Numeric(18,2) | **equivalente**       | Definir moeda/origem                     |
| **Lead Time Fabricação**      | component.lead_time_days  | Number/Mirror   | Integer       | parcialmente modelado | Definir agregação                        |
| **Dias antes Startup**        | component.pre_start_days  | Number/Mirror   | Integer       | parcialmente modelado | Definir agregação                        |
| **Frete**                     | component.freight_days    | Number/Mirror   | Integer       | parcialmente modelado | Definir agregação                        |
| **Kickoff**                   | —                         | Date            | —             | ausente               | Criar marco e notificação                |
| **Fórmulas de prazo**         | —                         | Formula         | —             | ausente               | Criar serviço de cálculo                 |
| **Arquivos**                  | —                         | Files           | —             | ausente               | Criar attachment se confirmado           |
| **Campos técnicos Mirror/ID** | JOIN/UUID                 | Mirror/Item ID  | Consulta/UUID | redundante no Hub     | Não migrar como dado editável            |

# 19. Comparação de workflows

| **Tema**              | **Monday**                         | **Hub atual**                      | **Conclusão**              |
|-----------------------|------------------------------------|------------------------------------|----------------------------|
| **Fonte de verdade**  | A.Status + grupo + automações      | current_stage + transition history | Hub é superior.            |
| **Avanço**            | Edição de marcos dispara automação | Comando explícito após salvar      | Hub é mais previsível.     |
| **Pulos**             | Atalho 2 → 4 observado             | Proibidos                          | PRECISA VALIDAÇÃO.         |
| **Reabertura**        | Botão para fase 1                  | ADMIN, motivo, \>=2 → 1            | PARCIAL; política diverge. |
| **Bypass**            | Suprimentos pode avançar           | Ausente                            | Bloqueador se legítimo.    |
| **Estados terminais** | Concluído; F2 também Cancelado/N/A | Apenas Concluído                   | Ausente.                   |
| **Standby**           | F2 possui                          | Ausente                            | Decisão humana.            |
| **Auditoria**         | Atividade do board                 | Transição + AuditLog               | Hub é superior.            |
| **Concorrência**      | Automação/eventual                 | Lock transacional                  | Hub é superior.            |

# 20. Comparação de automações

| **Automação Monday**                     | **Implementação Hub**     | **Situação**         | **Mudança necessária**                   |
|------------------------------------------|---------------------------|----------------------|------------------------------------------|
| **Avanços 1→2, 2→3, 3→4, 4→5, 5→6, 6→7** | workflow/stages.py        | **PARCIAL**          | Validar precondições exatas e atalho 2→4 |
| **Três conclusões 7→8**                  | Uma transição consolidada | **COMPLETO**         | Manter regra única transacional          |
| **Sincronizar status e grupo**           | Desnecessário             | NÃO APLICÁVEL        | Grupo vira consulta                      |
| **Nova demanda**                         | default current_stage=0   | **COMPLETO**         | Evitar estado Undefined                  |
| **Reiniciar negociação**                 | reopen para 1             | **PARCIAL**          | Validar papel e motivo                   |
| **Bypass Suprimentos**                   | Ausente                   | **NÃO IMPLEMENTADO** | Comando explícito auditável se aprovado  |
| **Clear Button**                         | Ausente                   | NÃO APLICÁVEL        | Preferir edição auditada                 |
| **FUP**                                  | Ausente                   | **NÃO IMPLEMENTADO** | Evento + job + canal                     |
| **Kickoff**                              | Ausente                   | **NÃO IMPLEMENTADO** | Agendamento idempotente                  |
| **Escalonamento**                        | Ausente                   | **NÃO IMPLEMENTADO** | Identificar destino e integrar           |

# 21. Implementações já corretas

| **Implementação**                      | **Evidência no código**           | **Equivalente Monday**      | **Aderência**          |
|----------------------------------------|-----------------------------------|-----------------------------|------------------------|
| **Contexto Unidade → Equipamento**     | stores/moduleContext.ts           | Boards/recortes por unidade | Alta                   |
| **Estado único + histórico**           | workflow service/models           | A.Status + grupos           | Alta e melhor modelado |
| **Fornecedores N:N**                   | supplier/equipment_supplier       | Connect Boards              | Alta                   |
| **Responsável estruturado**            | responsible_user_id               | Texto 0.Responsável         | Alta                   |
| **Catálogos normalizados**             | unit/area/discipline/work_package | Status/text/dropdown        | Alta                   |
| **Escopo por unidade**                 | scope.py + user_unit_access       | Board privado               | Alta                   |
| **Auditoria atômica**                  | AuditLog + WorkflowTransition     | Atividade do board          | Alta                   |
| **Tratamento de fórmula não definida** | deadlines.available=false         | Fórmulas frágeis            | Correto até validação  |

# 22. Implementações parcialmente corretas

| **Comportamento atual**          | **Processo real**                       | **Impacto**                             | **Recomendação**                          |
|----------------------------------|-----------------------------------------|-----------------------------------------|-------------------------------------------|
| **Filas por intervalo de etapa** | Views usam filtros complexos            | Itens podem entrar/sair incorretamente  | Filas baseadas em requisitos + saved view |
| **Processos 1:1**                | Cardinalidade não confirmada            | Não suporta recontratação/múltiplas OCs | Validar antes de migrar                   |
| **Reabertura ADMIN → etapa 1**   | Botão do Monday sem política exposta    | Divergência de autoridade               | Formalizar matriz                         |
| **Componentes técnicos**         | Subitem pode ser aquisição              | Processo pode estar no nível errado     | Definir aggregate root                    |
| **Dashboard por equipamentos**   | Monday usa 163 aquisições               | Denominadores divergentes               | Definir métrica                           |
| **Permissão ANALYST**            | Equipes têm responsabilidades distintas | Edição transversal                      | Permissões por área                       |

# 23. Implementações incorretas ou divergentes

| **Item**                   | **Hub atual**                | **Monday observado**                                           | **Correção**                                                       |
|----------------------------|------------------------------|----------------------------------------------------------------|--------------------------------------------------------------------|
| **2 → 3 obrigatório**      | Não permite 2 → 4            | Automação Minuta B pula para 4                                 | Confirmar regra; implementar transição nomeada ou rejeitar prática |
| **Fila Jurídico**          | Somente etapas 3–5           | Inclui condições OR por campos pendentes                       | Reformular critério funcional                                      |
| **Fila Suprimentos**       | Etapas 6–7                   | View usa exclusões, disciplina/responsável e hoje retorna zero | Definir carteira oficial                                           |
| **Negociações concluídas** | negotiated_at / equipamentos | 0 / 163 aquisições                                             | Alinhar unidade de contagem                                        |

# 24. Funcionalidades ausentes

| **Área**           | **Funcionalidades não encontradas**                                                                  |
|--------------------|------------------------------------------------------------------------------------------------------|
| **Banco**          | Estados especiais, anexos, comentários, notificações, saved views, outbox, mapeamento de migração.   |
| **Backend**        | Motor de fórmulas, jobs, bypass, escalonamento, importador, exportação server-side, integração ERP.  |
| **Frontend**       | Prazos/riscos, ações excepcionais, anexos/comentários, views salvas, Kanban, notificações do módulo. |
| **Workflow**       | Standby, cancelamento, não se aplica, transições excepcionais e reabertura parametrizada.            |
| **Relatórios**     | Índices, reconciliação, dashboards por disciplina/responsável, relatórios agendados.                 |
| **Infraestrutura** | Worker, agenda, object storage, outbox e observabilidade de jobs.                                    |

# 25. Gap Analysis

| **ID**      | **Área**        | **Problema**             | **Atual**         | **Esperado**             | **Solução**                          | **Prioridade** |
|-------------|-----------------|--------------------------|-------------------|--------------------------|--------------------------------------|----------------|
| **GAP-001** | Regras          | Fórmulas não confirmadas | Ausentes          | Cálculos auditáveis      | Workshop + especificação + testes    | **P0**         |
| **GAP-002** | Workflow        | Exceções divergentes     | Somente linear    | Política oficial         | State machine com comandos nomeados  | **P0**         |
| **GAP-003** | Banco           | Cardinalidade 1:1        | Provisória        | Suportar realidade       | Validar e migrar para 1:N se preciso | **P0**         |
| **GAP-004** | Migração        | Sem importador           | Ausente           | Carga idempotente        | Staging + mapping + reconciliação    | **P0**         |
| **GAP-005** | Permissões      | Sem segregação por área  | ANALYST amplo     | Least privilege          | Papéis/equipes por ação              | **P0**         |
| **GAP-006** | Métricas        | 163 vs 164               | Divergente        | Denominador oficial      | Definição + teste de reconciliação   | **P0**         |
| **GAP-007** | Backend         | Sem FUP/kickoff          | Ausente           | Notificações confiáveis  | Outbox + worker + canais             | **P1**         |
| **GAP-008** | Frontend        | Filas simplificadas      | Intervalos fixos  | Carteira real por equipe | Consultas parametrizadas             | **P1**         |
| **GAP-009** | Banco           | Sem documentos           | Ausente           | Arquivos com ACL         | attachment + object storage          | **P1**         |
| **GAP-010** | Backend         | Sem comentários          | Ausente           | Contexto operacional     | comment + mentions se confirmado     | **P1**         |
| **GAP-011** | Integrações     | Sem ERP/escalonamento    | Ausente           | Evitar duplicidade       | Adapter + outbox + idempotência      | **P1**         |
| **GAP-012** | Dashboard       | Indicadores incompletos  | Básicos           | Prazos e índices         | Agregações versionadas               | **P1**         |
| **GAP-013** | Testes          | Sem fixtures do Monday   | Testes sintéticos | Aceite com dados reais   | Dataset anonimizado + snapshots      | **P1**         |
| **GAP-014** | Infra           | Sem worker               | Ausente           | Jobs e retries           | Worker + scheduler + DLQ             | **P1**         |
| **GAP-015** | Frontend        | Sem saved views          | Ausente           | Filtros por equipe       | saved_view + UI                      | P2             |
| **GAP-016** | Frontend        | Sem Kanban               | Ausente           | Gestão visual            | Kanban somente via transição         | P2             |
| **GAP-017** | Exportação      | Client-side              | Limitada          | Escala                   | Job/exportação server-side           | P2             |
| **GAP-018** | Observabilidade | Sem métricas de jobs     | Ausente           | Operação segura          | Logs, métricas e alertas             | P2             |

# 26. Backlog técnico

| **ID**        | **Título**                            | **Área**   | **Dependência**   | **Módulos**                  | **Critérios de aceite**                                             | **Pri.** |
|---------------|---------------------------------------|------------|-------------------|------------------------------|---------------------------------------------------------------------|----------|
| **DB-001**    | Evoluir modelo de processo            | Banco      | FUN-004           | models/process.py; migration | Cardinalidade aprovada; migration reversível; constraints e índices | **P0**   |
| **BE-001**    | Motor de cálculo de prazos            | Backend    | FUN-001           | modules/deadlines            | Resultados e motivos de não cálculo; testes de exemplos oficiais    | **P0**   |
| **BE-002**    | Política de transições excepcionais   | Backend    | FUN-003           | workflow/stages.py           | Bypass/atalho/reabertura nomeados, autorizados e auditados          | **P0**   |
| **SEC-001**   | Permissões por área e ação            | Segurança  | FUN-005           | permissions.py; scope.py     | Engenharia, Jurídico e Suprimentos limitados às próprias ações      | **P0**   |
| **MIG-001**   | Importador Monday idempotente         | Migração   | FUN-010           | scripts/import_monday        | Dry-run; mapping; upsert; relatório de erros; sem duplicação        | **P0**   |
| **MIG-002**   | Reconciliação C2/F2                   | Migração   | MIG-001           | scripts/reconcile            | Contagens, campos, fases e métricas comparadas automaticamente      | **P0**   |
| **QA-001**    | Testes de aceitação do workflow       | Testes     | FUN-003           | backend/tests/acceptance     | Caminho feliz, exceções, concorrência e negações cobertos           | **P0**   |
| **DB-002**    | Attachment e metadados                | Banco      | FUN-009           | models/attachment.py         | ACL, hash, versão, uploader, equipamento/componente                 | **P1**   |
| **INFRA-001** | Object storage                        | Infra      | DB-002            | config + adapter             | Upload/download autorizados; antivírus/política definidos           | **P1**   |
| **DB-003**    | Notificação e outbox                  | Banco      | FUN-007           | models/notification.py       | Evento transacional, status, tentativas e idempotência              | **P1**   |
| **INFRA-002** | Worker e scheduler                    | Infra      | DB-003            | worker                       | FUP/kickoff com retry e observabilidade                             | **P1**   |
| **BE-003**    | Serviço de notificações               | Backend    | INFRA-002         | modules/notifications        | Canais configuráveis; preferências; auditoria                       | **P1**   |
| **BE-004**    | Queries reais das filas               | Backend    | FUN-005/FUN-008   | modules/queues               | Critérios documentados e testados por equipe                        | **P1**   |
| **FE-001**    | Prazos e risco no detalhe             | Frontend   | BE-001            | equipamentos/\[id\].vue      | Exibir cálculo, entradas, data-base e motivo quando indisponível    | **P1**   |
| **FE-002**    | Ações excepcionais do workflow        | Frontend   | BE-002            | workflow components          | Confirmação, justificativa, permissão e erro claro                  | **P1**   |
| **FE-003**    | Documentos por equipamento/componente | Frontend   | DB-002/INFRA-001  | components/attachments       | Upload, lista, download e remoção autorizada                        | **P1**   |
| **BE-005**    | Dashboards oficiais                   | Backend    | FUN-008/BE-001    | modules/dashboard            | Métricas versionadas e reconciliadas                                | **P1**   |
| **FE-004**    | Dashboard completo                    | Frontend   | BE-005            | pages/dashboard              | Prazos, índices e drill-down por filtro global                      | **P1**   |
| **INT-001**   | Adapter ERP/escalonamento             | Integração | FUN-011           | modules/integrations         | Idempotência, correlação, retry e reconciliação                     | P2       |
| **BE-006**    | Saved views                           | Backend    | FUN-005           | models/saved_view            | Filtros validados, pessoais/equipe, sem SQL arbitrário              | P2       |
| **FE-005**    | Editor de views e agrupamentos        | Frontend   | BE-006            | components/views             | Salvar, aplicar, compartilhar e restaurar padrão                    | P2       |
| **FE-006**    | Kanban seguro                         | Frontend   | BE-002            | pages/equipamentos/kanban    | Arraste chama transição; nunca atualiza estágio diretamente         | P2       |
| **BE-007**    | Exportação server-side                | Backend    | MIG-002           | modules/exports              | Mesmo recorte da tela; job para grande volume; trilha de auditoria  | P2       |
| **OPS-001**   | Observabilidade de domínio            | Operações  | INFRA-002/INT-001 | logging/metrics              | Métricas de transição, jobs, retries e falhas                       | P2       |

# 27. Backlog funcional

| **ID**      | **Decisão**                                 | **Responsável sugerido** | **Critério de aceite**                                                        | **Pri.** |
|-------------|---------------------------------------------|--------------------------|-------------------------------------------------------------------------------|----------|
| **FUN-001** | Formalizar fórmulas                         | Planejamento             | Exemplos de entrada/saída, nulos, calendário, fuso e arredondamento aprovados | **P0**   |
| **FUN-002** | Definir equipamento, componente e aquisição | Negócio                  | Unidade de contagem e de processo documentada; 163 vs 164 resolvido           | **P0**   |
| **FUN-003** | Aprovar catálogo de estados e transições    | Todas as áreas           | Standby/cancelamento/N-A/bypass/reabertura e autoridades definidos            | **P0**   |
| **FUN-004** | Aprovar cardinalidades                      | Jurídico/Suprimentos     | Múltiplos fornecedores, contratos, SCs e OCs decididos                        | **P0**   |
| **FUN-005** | Matriz RACI e permissões                    | Gestão                   | Quem lê, edita, aprova, reabre e cancela por unidade/área                     | **P0**   |
| **FUN-010** | Mapeamento de migração C2/F2                | Dados                    | Cada coluna classificada: migrar, transformar, derivar ou descartar           | **P0**   |
| **FUN-012** | Critérios de corte                          | Gestão                   | Reconciliação, período paralelo, rollback e aceite definidos                  | **P0**   |
| **FUN-006** | Processo de fornecedores                    | Suprimentos              | Principal, concorrente, contratado e troca de fornecedor definidos            | **P1**   |
| **FUN-007** | Política de notificações                    | Todas as áreas           | Eventos, destinatários, canal, frequência e escalonamento definidos           | **P1**   |
| **FUN-008** | Dicionário oficial de indicadores           | Gestão                   | Fonte, filtro, fórmula, denominador e dono de cada KPI                        | **P1**   |
| **FUN-009** | Uso de anexos e comentários                 | Operação                 | Tipos documentais, retenção, acesso e obrigatoriedade definidos               | **P1**   |
| **FUN-011** | Origem oficial de SC/OCI/OC/CAPEX           | Suprimentos/Financeiro   | Sistema mestre, moeda, integração e reconciliação definidos                   | P2       |

# 28. Prioridades P0 P1 P2 P3

| **Prioridade** | **Objetivo**                               | **Itens**                                                                                                                    |
|----------------|--------------------------------------------|------------------------------------------------------------------------------------------------------------------------------|
| **P0**         | Sem isso o Monday não pode ser substituído | Regras e fórmulas, estados/transições, cardinalidades, permissões, métrica de aquisição, importação, reconciliação e aceite. |
| **P1**         | Obrigatório para operação real             | Notificações, filas equivalentes, dashboards oficiais, documentos se usados, testes de aceitação e infraestrutura de jobs.   |
| **P2**         | Importante após o núcleo                   | Saved views, Kanban, integração ERP, exportação server-side e observabilidade avançada.                                      |
| **P3**         | Melhoria                                   | Risco preditivo, simulação de impacto, portal de fornecedor e recomendações baseadas em histórico.                           |

# 29. Pontos que exigem decisão humana

1.  Definição oficial de aquisição e explicação da divergência entre 163 e 164.

2.  Expressões completas das fórmulas e exemplos de aceite.

3.  Legitimidade do atalho Equalização → Aprovação da Minuta.

4.  Política de Standby, Cancelado, Não se Aplica, bypass e reabertura.

5.  Nível correto do processo: equipamento pai, componente ou ambos.

6.  Cardinalidade de fornecedores, contratos, SCs/OCIs e OCs.

7.  Matriz de responsabilidades e segregação entre Engenharia, Jurídico, Suprimentos, Gestor e Consulta.

8.  Uso real e retenção de anexos, comentários e documentos jurídicos.

9.  Destino e finalidade da automação Escalonamento.

10. Canais de FUP e kickoff: Teams, e-mail, alerta interno ou combinação.

11. Origem oficial de CAPEX, valores de OC, moeda e conversão.

12. Quais diferenças do F2 são regra válida e quais são legado.

# 30. Arquitetura final recomendada

| **Componente**              | **Responsabilidade alvo**                                                                              |
|-----------------------------|--------------------------------------------------------------------------------------------------------|
| **Nuxt 4/Vue 3**            | Interface orientada a operação; filtros globais; listas, detalhe, filas, dashboard e ações explícitas. |
| **FastAPI Domain Services** | Fonte única de regras, permissões, transições, fórmulas e invariantes.                                 |
| **PostgreSQL**              | Dados normalizados, histórico, auditoria, views salvas, outbox e staging de migração.                  |
| **Worker/Scheduler**        | FUP, kickoff, alertas, exportações e integrações com retry/idempotência.                               |
| **Object Storage**          | Anexos com hash, metadados, retenção e autorização.                                                    |
| **SSO corporativo**         | Usuários, equipes e papéis; sem responsáveis em texto.                                                 |
| **Adapters**                | ERP, contratos e outros sistemas sem acoplar o domínio.                                                |
| **Observabilidade**         | Correlação entre comando, transição, notificação e integração.                                         |

Fluxo alvo: Monday atual → necessidades reais → modelo de domínio → PostgreSQL → FastAPI → Nuxt/Vue. Grupos, Mirrors e automações não são copiados como entidades; são traduzidos em estado, relações, cálculos, consultas e eventos de domínio.

Princípio de centralização: uma única base multiunidade. Unit é filtro global obrigatório no contexto operacional; Equipment é o segundo filtro, dependente da unidade e opcional. ProjectContext representa LEM C2, LEM F2 e futuros contextos sem criar módulos, bancos ou schemas separados.

# 31. Roadmap até dezembro

| **Etapa**                        | **Janela recomendada** | **Entregas e dependências**                                                                   |
|----------------------------------|------------------------|-----------------------------------------------------------------------------------------------|
| **1 Correções estruturais**      | 21/09 a 02/10          | Workshops P0; unidade de aquisição; fórmulas; transições; cardinalidades; RACI.               |
| **2 Funcionalidades essenciais** | 05/10 a 23/10          | Schema aprovado, motor de fórmulas, workflow excepcional, permissões e testes.                |
| **3 Fluxos por área**            | 26/10 a 06/11          | Filas reais, documentos essenciais, fornecedores e ações por Engenharia/Jurídico/Suprimentos. |
| **4 Dashboards e notificações**  | 09/11 a 20/11          | KPIs reconciliados, FUP/kickoff, worker, dashboards e observabilidade.                        |
| **5 Migração**                   | 23/11 a 04/12          | Importador, dry-runs C2/F2, correção de mapeamento e reconciliação automatizada.              |
| **6 Homologação**                | 07/12 a 11/12          | UAT por área, segurança, desempenho, restauração e critérios de corte.                        |
| **7 Substituição**               | 14/12 a 18/12          | Operação paralela curta, delta final, aceite, congelamento do Monday e plano de rollback.     |
| **Reserva**                      | 21/12 a 23/12          | Correções críticas sem ampliar escopo.                                                        |

**\[INFERÊNCIA\]** As janelas são uma sequência de dependências funcionais, não estimativas baseadas em quantidade de arquivos. O corte em dezembro depende de decisões P0 concluídas até o início de outubro.

# 32. Critério de substituição do Monday

| **Capacidade**  | **Estado**  | **Bloqueador**                                 |
|-----------------|-------------|------------------------------------------------|
| **Cadastro**    | **PRONTO**  | Migração e reconciliação                       |
| **Workflow**    | **PARCIAL** | Exceções, estados especiais e política oficial |
| **Negociação**  | **PARCIAL** | Fórmulas, FUP e unidade de aquisição           |
| **Jurídico**    | **PARCIAL** | Atalho, documentos e responsabilidades         |
| **Suprimentos** | **PARCIAL** | Bypass, cardinalidades e integração            |
| **Dashboard**   | **PARCIAL** | KPIs oficiais e 163 vs 164                     |
| **Histórico**   | **PRONTO**  | Validar retenção                               |
| **Permissões**  | **PARCIAL** | Matriz por área/equipe                         |
| **Migração**    | **AUSENTE** | Importador, mapping, dry-run e delta final     |

**O Hub já consegue substituir o Monday?** Não. A base técnica é boa e reduz retrabalho, mas o corte hoje eliminaria fórmulas e alertas operacionais, não cobriria exceções confirmadas, manteria ambiguidade na unidade de aquisição e não teria um caminho seguro de migração.

Bloqueadores restantes: FUN-001 a FUN-005, FUN-010, FUN-012, BE-001, BE-002, SEC-001, MIG-001, MIG-002 e QA-001.

# 33. Próximos passos recomendados

13. Reunir Engenharia, Jurídico, Suprimentos, Planejamento e TI para fechar as decisões P0 em workshops curtos e orientados a exemplos.

14. Transformar cada fórmula em especificação testável antes de implementar qualquer cálculo.

15. Resolver primeiro a unidade de aquisição e as cardinalidades; elas condicionam banco, endpoints, telas, migração e dashboard.

16. Aprovar a state machine completa e manter o backend como única fonte de mudança de estado.

17. Criar o importador e a reconciliação cedo, usando uma amostra real do C2; não deixar migração para o fim.

18. Homologar por área com cenários reais e somente então ativar operação paralela e corte.

# Apêndice A. Fontes e evidências

| **Origem**            | **Evidência utilizada**                                                                                   |
|-----------------------|-----------------------------------------------------------------------------------------------------------|
| **REPOSITÓRIO**       | GitHub main, commit 67701b5; leitura de código, migrations, testes e documentação.                        |
| **MONDAY**            | Inspeção somente leitura do C2, views, dashboard e painel de 21 automações; comparação contextual com F2. |
| **COMPARAÇÃO**        | Mapeamento campo, workflow e automação entre os dois ambientes.                                           |
| **INFERÊNCIA**        | Recomendação arquitetural derivada das evidências, sempre sinalizada.                                     |
| **PRECISA VALIDAÇÃO** | Regra não confirmada por código ou interface segura do Monday.                                            |

Limitações de leitura: as expressões integrais das fórmulas do Monday não ficaram disponíveis de forma segura; configurações de permissão por usuário e conteúdo de boards externos da automação Escalonamento não foram abertos. Nenhuma regra foi inventada para preencher essas lacunas.
