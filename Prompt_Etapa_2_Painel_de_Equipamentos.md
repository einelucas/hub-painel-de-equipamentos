# Painel de Equipamentos — Prompt para a primeira etapa funcional

## 1. Leitura do estado atual

O repositório base já está corretamente limpo para iniciar o domínio do **Painel de Equipamentos**.

### O que já existe

- **Frontend:** Nuxt 4 + Vue 3 + TypeScript + Pinia + Tailwind.
- **Backend:** FastAPI + Python + SQLAlchemy assíncrono + Pydantic.
- **Banco:** PostgreSQL + Alembic.
- **Autenticação:** OIDC/Keycloak, com bypass controlado para desenvolvimento.
- **Base compartilhada:** usuários, auditoria, health checks, shell visual do Hub, componentes UI e charts reutilizáveis.
- **Página principal atual:** apenas placeholder de “Painel de Equipamentos em desenvolvimento”.
- **Banco atual:** ainda não possui tabelas do domínio de equipamentos.
- **Navegação:** `TabsNav.vue` está propositalmente vazia; não deve ser transformada em uma cópia das views do Monday.

### Direção funcional adotada

O novo Hub **não deve copiar a estrutura visual do Monday**. O Monday será tratado apenas como fonte de requisitos do processo. O domínio deve ser centralizado e normalizado, com dados estruturados de unidade, contexto de projeto, equipamento, componentes e histórico.

Os dois filtros principais da experiência devem ser:

1. **Unidade** — filtro global do módulo.
2. **Equipamento** — filtro dependente da unidade selecionada.

O conceito interno de `project_context` deve existir no banco para representar contextos como **LEM C2 / LEM F2**, mas não precisa virar um terceiro filtro principal nesta primeira entrega. Ele deve ser usado internamente para evitar que cada board do Monday vire um schema/tela diferente no Hub.

---

## 2. Objetivo da primeira etapa

Transformar a base atual em uma **primeira fatia vertical realmente funcional**, sem tentar implementar todo o Monday de uma vez.

Ao final desta etapa deve ser possível:

- carregar unidades pela API;
- selecionar uma unidade no frontend;
- carregar os equipamentos daquela unidade;
- selecionar um equipamento específico ou visualizar todos da unidade;
- cadastrar e editar equipamentos básicos;
- cadastrar e consultar componentes/subitens;
- visualizar uma tabela operacional com os equipamentos;
- abrir o detalhe de um equipamento;
- visualizar contagens básicas consistentes;
- manter o estágio atual do equipamento de forma estruturada;
- registrar histórico/auditoria das alterações importantes;
- executar toda a aplicação com testes, migrations e documentação atualizados.

Esta etapa deve criar a fundação para negociação, jurídico, contrato, SC/OCI, OC, prazos e dashboards avançados, mas **não deve implementar regras ainda não confirmadas**.

---

## 3. Escopo técnico recomendado para a Etapa 1

### 3.1 Banco e domínio

Criar uma nova migration Alembic, sem alterar a migration compartilhada `0001_shared_base`.

Criar inicialmente as seguintes entidades:

#### `unit`

- `id`
- `code`
- `name`
- `active`
- timestamps

#### `project_context`

Representa um contexto de projeto/processo dentro da unidade, por exemplo LEM C2 ou LEM F2.

- `id`
- `unit_id`
- `code`
- `name`
- `active`
- timestamps

Relação: `unit 1:N project_context`.

#### `area`

- `id`
- `unit_id`
- `name`
- `active`

#### `discipline`

- `id`
- `code`
- `name`
- `active`

#### `work_package`

- `id`
- `project_context_id`
- `code`
- `name`
- `active`

#### `equipment`

Campos mínimos:

- `id`
- `project_context_id`
- `name`
- `origin` nullable
- `startup_at` nullable
- `discipline_id` nullable
- `area_id` nullable
- `work_package_id` nullable
- `responsible_user_id` nullable
- `criticality` nullable
- `current_stage` obrigatório, iniciando em `0`
- `capex_estimated` nullable
- `created_at`
- `updated_at`

Não armazenar “grupo do Monday”. O único estado operacional é `current_stage`.

#### `equipment_component`

Campos mínimos:

- `id`
- `equipment_id`
- `name`
- `tag` nullable
- `sector` nullable ou FK futura, sem bloquear esta etapa
- `lead_time_days` nullable
- `pre_start_days` nullable
- `contract_delivery_at` nullable
- `freight_days` nullable
- timestamps

#### `workflow_transition`

Criar desde agora a estrutura de histórico do workflow:

- `id`
- `equipment_id`
- `from_stage`
- `to_stage`
- `reason` nullable
- `actor_id`
- `occurred_at`

Nesta etapa, estruturar a máquina de estados para os estágios 0 a 8, mas não inventar pré-condições de negócio que ainda precisam ser confirmadas. O mecanismo de transição deve ser centralizado em service/backend e preparado para receber validadores depois.

### 3.2 Catálogo de estágios

Usar os estágios documentados:

- 0 — Nova demanda
- 1 — Negociação
- 2 — Equalização
- 3 — Abertura do chamado
- 4 — Aprovação da minuta
- 5 — Escrituração do contrato
- 6 — SC ou OCI
- 7 — Aprovação da OC
- 8 — Concluído

`Standby`, `Cancelado` e `Não se Aplica` devem ficar documentados como pendentes de definição e **não devem ser assumidos como parte do fluxo principal nesta etapa**.

### 3.3 Permissões

Não redesenhar toda a matriz de perfis agora.

Aproveitar os perfis existentes:

- `VIEWER`: leitura de equipamentos;
- `ANALYST`: leitura + criação/edição do domínio operacional;
- `ADMIN`: acesso total + administração/auditoria.

Adicionar permissões específicas, por exemplo:

- `equipments:read`
- `equipments:write`
- `catalogs:read`
- `catalogs:manage`

Preservar as permissões já existentes de usuários e auditoria.

### 3.4 API inicial

Criar módulos FastAPI separados e coerentes com a arquitetura atual.

Endpoints mínimos:

#### Unidades/contextos

- `GET /api/v1/units`
- `GET /api/v1/units/{unit_id}/project-contexts`

#### Catálogos

- `GET /api/v1/areas?unit_id=`
- `GET /api/v1/disciplines`
- `GET /api/v1/work-packages?project_context_id=`

CRUD administrativo completo pode ser adiado se não for necessário para a primeira tela.

#### Equipamentos

- `GET /api/v1/equipments`
- `POST /api/v1/equipments`
- `GET /api/v1/equipments/{equipment_id}`
- `PATCH /api/v1/equipments/{equipment_id}`

A listagem deve aceitar desde o início:

- `unit_id`
- `project_context_id` opcional
- `equipment_id` opcional
- `search` opcional
- `stage` opcional
- paginação
- ordenação segura

A filtragem deve ocorrer no backend; não buscar tudo para filtrar somente no navegador.

#### Componentes

- `GET /api/v1/equipments/{equipment_id}/components`
- `POST /api/v1/equipments/{equipment_id}/components`
- `PATCH /api/v1/components/{component_id}`

#### Resumo do painel

Criar somente métricas que não dependem das fórmulas ainda não confirmadas:

- `GET /api/v1/dashboard/summary?unit_id=&equipment_id=`

Retornar inicialmente:

- total de equipamentos;
- total de componentes;
- equipamentos em andamento (`current_stage < 8`);
- equipamentos concluídos (`current_stage = 8`);
- distribuição por estágio.

**Não usar ainda o indicador “Total de Aquisições” como equivalente a subitens**, porque a auditoria identificou divergência entre 163 e 164.

### 3.5 Frontend — primeira tela operacional

Transformar `frontend/pages/dashboard/index.vue` no primeiro painel funcional, preservando a identidade visual já existente.

Não recriar as views do Monday como abas.

Estrutura sugerida:

1. título atual do módulo;
2. barra de filtros globais;
3. cards de resumo;
4. distribuição simples por estágio, usando componente de chart existente se fizer sentido;
5. tabela de equipamentos;
6. estados de loading, erro e vazio.

#### Filtro global 1 — Unidade

- carregar via API;
- se o usuário tiver uma única unidade disponível, pré-selecioná-la;
- se houver mais de uma, permitir “Todas as unidades” somente quando isso fizer sentido para a permissão atual;
- mudança de unidade deve limpar um equipamento incompatível anteriormente selecionado.

#### Filtro global 2 — Equipamento

- dependente da unidade;
- opção inicial “Todos os equipamentos”;
- deve mostrar somente equipamentos compatíveis com a unidade selecionada;
- se “Todas as unidades” estiver selecionado, deixar apenas “Todos os equipamentos” nesta primeira versão para evitar dropdown enorme/ambíguo;
- busca textual da tabela continua disponível separadamente.

Manter os filtros sincronizados com query string quando possível, por exemplo:

- `?unit=<id>`
- `?equipment=<id>`

Isso permite compartilhar/recarregar a mesma visão sem perder o contexto.

### 3.6 Tabela principal

Colunas iniciais recomendadas:

- Equipamento
- Contexto
- Área
- Disciplina
- Responsável
- Etapa atual
- Startup
- Criticidade
- Componentes
- Ação “Ver detalhes”

Não exibir campos Monday com nomes técnicos como `FÓRMULA-NÃO MEXER`, mirrors ou colunas auxiliares.

### 3.7 Detalhe do equipamento

Criar uma rota de detalhe, preferencialmente:

- `/equipamentos/[id]`

ou manter o padrão de rotas existente se houver motivo técnico claro.

A primeira versão deve mostrar:

- dados mestres;
- unidade/contexto;
- área, disciplina e work package;
- responsável;
- estágio atual;
- startup e criticidade;
- CAPEX estimado, se informado;
- lista de componentes/subitens;
- histórico básico das alterações/transições.

Não implementar ainda as telas completas de negociação, jurídico, contrato, SC/OCI e OC.

---

## 4. Regras importantes de arquitetura

- Não criar uma tabela ou tela diferente para cada board do Monday.
- Não persistir mirrors/lookups que possam ser calculados por JOIN/consulta.
- Não duplicar estado em `grupo + status`; usar somente `current_stage`.
- Não colocar regra de transição relevante no frontend.
- Toda mudança de estágio deve passar por um service/backend centralizado.
- Alterações importantes devem gerar auditoria.
- Campos derivados ainda sem fórmula oficial devem permanecer ausentes ou retornar estado “não calculável”; nunca inventar fórmula.
- Não inventar equipamentos, fornecedores, valores, prazos ou dados reais para preencher a interface.
- Fixtures de teste/dev são permitidas somente isoladas e claramente identificadas como fictícias.
- Preservar o header, identidade visual, componentes compartilhados e charts já existentes.
- Não remover ou quebrar autenticação, usuários, auditoria e health checks.
- Novas tabelas devem vir em migration separada e reversível.
- Não alterar a migration `0001_shared_base`.

---

## 5. Itens que NÃO devem entrar nesta etapa

Deixar explicitamente para fases seguintes:

- equivalência completa das 21 automações do Monday;
- regras finais de negociação/equalização/jurídico;
- fórmulas de prazo e risco ainda não confirmadas;
- índices de aderência, criticidade e índice geral;
- FUP e notificações de kickoff;
- fornecedores completos e processo competitivo, salvo se necessário para preparar somente o schema;
- contratos, SC/OCI e OCs completos;
- arquivos e comentários;
- Kanban;
- exportações avançadas;
- integração ERP;
- migração integral do C2/F2;
- estados especiais Standby/Cancelado/Não se Aplica até validação;
- qualquer tentativa de reproduzir visualmente o Monday.

---

## 6. Testes obrigatórios

### Backend

Criar testes cobrindo pelo menos:

- criação e listagem de unidade/contexto;
- criação de equipamento com `current_stage = 0`;
- filtro de equipamentos por unidade;
- filtro por equipamento específico;
- busca textual;
- paginação;
- criação/listagem de componente;
- equipamento não pode apontar para área de outra unidade;
- equipamento não pode apontar para work package de outro contexto;
- permissões de leitura/escrita;
- auditoria em criação/edição;
- histórico de transição quando o estágio for alterado pelo service apropriado.

### Frontend

Cobrir pelo menos:

- carregamento do filtro de unidade;
- carregamento dependente do filtro de equipamento;
- troca de unidade limpando equipamento incompatível;
- loading;
- erro da API;
- empty state;
- renderização da tabela;
- filtro por unidade/equipamento refletido nas requisições.

### Validações finais

Executar e corrigir até passar:

```bash
# frontend
pnpm lint
pnpm typecheck
pnpm test
pnpm build

# backend
python -m ruff check app tests scripts
python -m mypy app
python -m pytest
```

Não mascarar testes com `skip` sem justificativa documentada.

---

## 7. Documentação obrigatória da implementação

Ao concluir o trabalho, criar:

`docs/etapa-01-primeiro-fluxo.md`

Esse arquivo deve registrar:

- objetivo da etapa;
- decisões arquiteturais tomadas;
- schema criado;
- migration criada;
- endpoints implementados;
- comportamento dos filtros Unidade + Equipamento;
- páginas/componentes criados;
- permissões adicionadas;
- testes criados;
- comandos para executar localmente;
- limitações atuais;
- decisões ainda pendentes;
- lista clara do que ficou para a Etapa 2.

Também atualizar, sem apagar o histórico válido:

- `README.md`
- `docs/README.md`
- `docs/arquitetura.md`
- `docs/banco-de-dados.md`
- `docs/api.md`
- `docs/modulos.md`

A documentação deve refletir o código final, e não apenas a intenção inicial.

---

# PROMPT PRONTO PARA O AGENTE DE CÓDIGO

Copie o bloco abaixo para o Codex/Claude/agente que terá acesso ao repositório.

```text
Você vai implementar a PRIMEIRA ETAPA FUNCIONAL do projeto “Painel de Equipamentos”.

IMPORTANTE: antes de alterar qualquer arquivo, leia todo o repositório, principalmente:
- README.md
- docs/*
- backend/app/core/*
- backend/app/models/*
- backend/app/modules/*
- backend/alembic/*
- frontend/pages/*
- frontend/components/*
- frontend/composables/*
- frontend/stores/*

Também considere como fonte funcional a especificação do Painel de Equipamentos fornecida junto ao projeto.

CONTEXTO DO PROJETO
O repositório atual é uma base limpa do Hub de Automação. Ele já possui Nuxt 4 + Vue 3 + TypeScript + Pinia + Tailwind no frontend e FastAPI + SQLAlchemy assíncrono + PostgreSQL + Alembic no backend. Também já existem autenticação OIDC/Keycloak, usuários, auditoria, health checks, componentes visuais e charts reutilizáveis.

O domínio de equipamentos ainda não foi implementado. A página /dashboard ainda é um placeholder.

REGRA CENTRAL
NÃO faça uma cópia da estrutura do Monday.com. O Monday é apenas fonte de requisitos. O Hub deve centralizar e normalizar os dados.

O processo deve ser modelado em domínio estruturado, e não em boards/grupos/colunas duplicadas.

DECISÃO DE UX JÁ DEFINIDA
A experiência terá dois filtros principais e globais:
1. Unidade
2. Equipamento

O filtro de Equipamento deve depender da Unidade.
Ao trocar a Unidade, qualquer equipamento incompatível selecionado anteriormente deve ser limpo.

O conceito project_context deve existir no backend para representar contextos como LEM C2 / LEM F2, mas NÃO precisa virar um terceiro filtro principal nesta primeira entrega.

OBJETIVO DESTA ETAPA
Transformar a base atual em uma primeira fatia vertical funcional, com banco + API + frontend integrados.

Ao final deve ser possível:
- listar unidades;
- filtrar por unidade;
- listar equipamentos da unidade;
- filtrar por equipamento;
- cadastrar/editar equipamento básico;
- cadastrar/consultar componentes;
- exibir cards básicos consistentes;
- exibir tabela operacional;
- abrir detalhe do equipamento;
- manter estágio atual estruturado;
- registrar auditoria/histórico;
- executar migrations e testes com sucesso.

1. BANCO E MODELS
Crie uma NOVA migration Alembic. Não altere 0001_shared_base.

Implemente models para:
- unit
- project_context
- area
- discipline
- work_package
- equipment
- equipment_component
- workflow_transition

Relações principais:
Unit 1:N ProjectContext
ProjectContext 1:N Equipment
Equipment 1:N EquipmentComponent
Equipment N:1 Area
Equipment N:1 Discipline
Equipment N:1 WorkPackage
Equipment N:1 User responsável (nullable)
Equipment 1:N WorkflowTransition

Campos mínimos de equipment:
- id
- project_context_id
- name
- origin nullable
- startup_at nullable
- discipline_id nullable
- area_id nullable
- work_package_id nullable
- responsible_user_id nullable
- criticality nullable
- current_stage obrigatório, default 0
- capex_estimated nullable
- created_at
- updated_at

Campos mínimos de equipment_component:
- id
- equipment_id
- name
- tag nullable
- sector nullable nesta etapa
- lead_time_days nullable
- pre_start_days nullable
- contract_delivery_at nullable
- freight_days nullable
- created_at
- updated_at

Campos mínimos de workflow_transition:
- id
- equipment_id
- from_stage
- to_stage
- reason nullable
- actor_id
- occurred_at

Não crie uma coluna de “grupo Monday”. current_stage é a única fonte de verdade do estágio.

Catálogo de estágios principal:
0 Nova demanda
1 Negociação
2 Equalização
3 Abertura do chamado
4 Aprovação da minuta
5 Escrituração do contrato
6 SC ou OCI
7 Aprovação da OC
8 Concluído

Standby, Cancelado e Não se Aplica ainda estão pendentes de validação. Não os incorpore ao fluxo principal como decisão definitiva.

Estruture a state machine no backend, mas NÃO invente pré-condições de negócio ainda não confirmadas. Centralize qualquer alteração de estágio em um service específico e registre workflow_transition + auditoria.

2. PERMISSÕES
Preserve VIEWER, ANALYST e ADMIN nesta etapa.

Adicione permissões de domínio, por exemplo:
- equipments:read
- equipments:write
- catalogs:read
- catalogs:manage

Sugestão:
VIEWER = leitura
ANALYST = leitura + escrita operacional
ADMIN = todas as permissões + administração/auditoria

Não quebre as permissões atuais de users/audit.

3. API
Crie módulos FastAPI separados, mantendo o padrão atual de router/service/schemas.

Endpoints mínimos:
GET /api/v1/units
GET /api/v1/units/{unit_id}/project-contexts
GET /api/v1/areas?unit_id=
GET /api/v1/disciplines
GET /api/v1/work-packages?project_context_id=

GET /api/v1/equipments
POST /api/v1/equipments
GET /api/v1/equipments/{equipment_id}
PATCH /api/v1/equipments/{equipment_id}

GET /api/v1/equipments/{equipment_id}/components
POST /api/v1/equipments/{equipment_id}/components
PATCH /api/v1/components/{component_id}

GET /api/v1/dashboard/summary?unit_id=&equipment_id=

A listagem de equipamentos deve suportar no backend:
- unit_id
- project_context_id opcional
- equipment_id opcional
- search opcional
- stage opcional
- paginação
- ordenação segura

Não carregue todos os registros para filtrar somente no frontend.

O summary inicial deve retornar apenas métricas seguras:
- total de equipamentos
- total de componentes
- equipamentos em andamento (stage < 8)
- equipamentos concluídos (stage = 8)
- distribuição por estágio

NÃO implemente “Total de Aquisições” usando subitens como verdade, porque a especificação identificou divergência 163 x 164 e essa regra ainda precisa ser validada.

4. FRONTEND
Transforme frontend/pages/dashboard/index.vue em uma tela funcional, mantendo a identidade atual do Hub.

NÃO transforme TabsNav em uma cópia das views do Monday.

Estrutura da tela:
- título atual
- barra de filtros globais
- cards de resumo
- distribuição por estágio, usando chart já existente se adequado
- tabela de equipamentos
- loading/error/empty states

FILTRO 1 — UNIDADE
- carregar pela API
- filtrar todo o conteúdo do painel
- ao trocar unidade, limpar equipamento incompatível

FILTRO 2 — EQUIPAMENTO
- dependente da unidade
- opção “Todos os equipamentos”
- listar apenas equipamentos da unidade selecionada
- se estiver em “Todas as unidades”, nesta primeira versão deixe somente “Todos os equipamentos” para evitar ambiguidade

Sincronize os filtros com query string, preferencialmente:
?unit=<id>&equipment=<id>

Tabela inicial:
- Equipamento
- Contexto
- Área
- Disciplina
- Responsável
- Etapa atual
- Startup
- Criticidade
- Componentes
- ação Ver detalhes

Crie também a rota de detalhe /equipamentos/[id] (ou justifique outro padrão coerente com o projeto).

Detalhe inicial:
- dados mestres
- unidade/contexto
- área
- disciplina
- work package
- responsável
- estágio
- startup
- criticidade
- CAPEX estimado se houver
- componentes
- histórico básico

Não implemente nesta etapa as telas completas de negociação, jurídico, contrato, SC/OCI ou OC.

5. DADOS DE DESENVOLVIMENTO
Não invente dados reais do processo.

Se precisar de seed para desenvolvimento, crie script separado e idempotente, claramente identificado como DEV. Pode cadastrar apenas contextos mínimos conhecidos, como uma unidade LEM e um contexto LEM C2, sem inventar a lista de 41 equipamentos.

Fixtures fictícias podem existir apenas em testes.

6. REGRAS DE QUALIDADE
- preserve autenticação, usuários, auditoria e health checks;
- preserve a identidade visual existente;
- reutilize componentes UI/charts existentes antes de criar duplicatas;
- não persista mirrors/lookups desnecessários;
- não invente fórmulas;
- não coloque regra crítica de negócio no frontend;
- valide relações cruzadas (ex.: área deve pertencer à unidade compatível; work package ao contexto correto);
- use transações para operações que alterem equipamento + histórico/auditoria;
- evite N+1 na listagem;
- implemente paginação desde o início;
- mantenha typing estrito no frontend;
- mantenha schemas Pydantic explícitos no backend.

7. NÃO IMPLEMENTAR AGORA
- 21 automações completas do Monday
- fórmulas finais de prazo/risco
- índices de aderência/criticidade/geral
- notificações/FUP/kickoff
- Kanban
- comentários/arquivos
- exportações avançadas
- ERP
- migração integral do C2/F2
- regras definitivas dos estados especiais
- cópia visual do Monday

8. TESTES
Backend mínimo:
- unit/context CRUD ou leitura conforme implementação
- criação de equipment com stage 0
- filtro por unit_id
- filtro por equipment_id
- search
- paginação
- component create/list
- validação de área de outra unidade
- validação de work package de outro contexto
- permissões
- auditoria
- workflow_transition quando houver mudança de estágio pelo service

Frontend mínimo:
- carregar unidades
- equipamento dependente de unidade
- reset do equipamento ao trocar unidade
- loading
- error
- empty state
- tabela
- parâmetros enviados corretamente à API

Antes de concluir execute:
Frontend:
pnpm lint
pnpm typecheck
pnpm test
pnpm build

Backend:
python -m ruff check app tests scripts
python -m mypy app
python -m pytest

Corrija os erros. Não use skip para esconder falhas sem documentar motivo real.

9. DOCUMENTAÇÃO OBRIGATÓRIA
Crie ao final:
docs/etapa-01-primeiro-fluxo.md

Registre nele:
- o que foi implementado
- decisões arquiteturais
- schema e migration
- endpoints
- filtros Unidade + Equipamento
- páginas/componentes
- permissões
- testes
- comandos para execução
- limitações
- pendências
- escopo proposto para Etapa 2

Atualize também, sem apagar histórico válido:
README.md
docs/README.md
docs/arquitetura.md
docs/banco-de-dados.md
docs/api.md
docs/modulos.md

10. ENTREGA FINAL DO AGENTE
No final, responda com:
1. resumo do que foi implementado;
2. lista dos arquivos principais criados/alterados;
3. migration criada;
4. endpoints disponíveis;
5. testes executados e resultado;
6. decisões/assunções feitas;
7. pendências que exigem validação do negócio;
8. próximos passos recomendados para Etapa 2.

Não faça commits nem push sem autorização explícita.
```

---

## 8. Resultado esperado antes de avançar para a Etapa 2

A Etapa 1 está concluída quando o projeto deixar de ser apenas um shell e passar a ter uma cadeia funcional completa:

**PostgreSQL → FastAPI → filtros globais → tabela de equipamentos → detalhe → componentes → auditoria**, com testes e documentação.

A próxima etapa poderá então implementar o workflow de aquisição em profundidade: negociação, equalização, jurídico, contrato, SC/OCI, OC, prazos e regras equivalentes às automações do Monday, já sobre uma base estável e centralizada.
