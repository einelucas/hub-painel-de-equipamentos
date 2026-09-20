# Etapa 04.1 — administração contextual e preservação do Hub

**Data da implementação:** 2026-09-20

## Objetivo

Fechar pendências de interface deixadas pela Etapa 4 sem redesenhar o sistema: administração contextual dentro das abas onde o dado é usado, visível apenas a quem tem permissão, e restauração integral do shell corporativo do Hub.

## Estado encontrado antes da implementação

- A API administrativa da Etapa 4 (PATCH de catálogos, `GET|PUT /usuarios/{id}/units`, CRUD de fornecedores) estava completa, testada e auditada, **mas sem nenhuma interface** — só era operável via API.
- O `AppHeader.vue` tinha sido alterado pela Etapa 4: busca, sino e exportação ficaram `disabled`, com tooltips reescritos.
- `/fornecedores` existia como tela independente, sem ponto de entrada a partir da operação.

## Alterações da Etapa 4 no header: revertidas

Todas. O `AppHeader.vue` foi restaurado byte a byte para a versão da baseline aprovada (commit `69be6d6`), usando `git checkout` do próprio arquivo.

| Controle | Etapa 4 tinha feito | Estado agora |
| --- | --- | --- |
| Busca | `disabled`, placeholder "Busca do Hub em breve", tooltip novo | Restaurado: campo ativo, `placeholder="Buscar"` |
| Sino | `disabled`, "Notificações em breve" | Restaurado: botão ativo, `title="Notificações do Hub"` |
| Exportação | `disabled`, tooltip apontando a tela Equipamentos | Restaurado: botão ativo |

O raciocínio da Etapa 4 (não deixar controle clicável sem ação) estava certo para componentes do módulo, mas **errado para o shell corporativo**: desabilitar controles do Hub redefine o contrato visual/funcional dele. Serviços corporativos que dependem do ambiente de produção mantêm a estrutura preparada, sem implementação local.

## Como o header corporativo foi preservado

- Nenhuma busca do Painel foi acoplada ao campo do header. A busca de equipamentos continua nas telas do módulo (`/equipamentos` e as três filas), toda server-side.
- Nenhum controle foi removido, desabilitado ou simplificado.
- Há teste de regressão automatizado (`tests/AppHeader.test.ts`) que falha se alguém desabilitar um controle, remover um dos elementos previstos ou acoplar busca de equipamentos ao campo do Hub.

## Abas que receberam Administração

### Equipamentos — `catalogs:manage` ou `users:manage`

Botão **Administração** (ícone `SlidersHorizontal`) na barra de filtros, ao lado de Exportar. Abre um painel com duas seções:

1. **Catálogos** — Unidades, Contextos de projeto, Áreas, Disciplinas e Work packages. Cada um lista, cria, edita e ativa/desativa. Catálogos dependentes avisam o que falta selecionar (unidade no filtro global, contexto no seletor do painel) em vez de listar vazio sem explicação.
2. **Acesso às unidades** — seleciona usuário, mostra as unidades atuais, marca/desmarca e salva. Usuário ADMIN exibe aviso de que enxerga tudo por perfil e não recebe vínculo individual, espelhando a regra do backend.

Após qualquer alteração, a tela recarrega disciplinas, responsáveis, opções de equipamento e a listagem — a mudança reflete sem sair da aba.

### Suprimentos — `suppliers:write`

Botão **Administração** na barra de filtros, abrindo o cadastro mestre de fornecedores: buscar, mostrar inativos, criar, editar e ativar/desativar. Traz link **"Ver todos os fornecedores"** para `/fornecedores`, que passou a ser tela auxiliar de Suprimentos em vez de ponto solto.

## Abas que não receberam Administração, e por quê

| Aba | Motivo |
| --- | --- |
| **Engenharia** | Área, Disciplina e Work Package já são administrados no painel de Equipamentos. Criar um segundo painel só duplicaria componente e ponto de entrada para os mesmos dados. |
| **Jurídico** | Chamado, minuta, contrato e datas são **dados do processo**, não catálogo. Continuam sendo editados pelo fluxo do equipamento. Nenhuma entidade de catálogo real foi encontrada que justificasse um painel — e nenhum catálogo foi inventado. |
| **Dashboard** | Visão gerencial. Manutenção de dado não se mistura com acompanhamento. |
| **Auditoria** | Rastreabilidade, não administração. |

## Permissões usadas

| Ação | Permissão |
| --- | --- |
| Botão Administração em Equipamentos | `catalogs:manage` **ou** `users:manage` |
| Seção Catálogos | `catalogs:manage` |
| Seção Acesso às unidades | `users:manage` |
| Botão Administração em Suprimentos | `suppliers:write` |

Nenhuma verificação usa `role === "ADMIN"`: a UI consulta as permissões existentes. O backend continua sendo a fonte de verdade — esconder o botão não afrouxa nenhum endpoint.

Verificado no navegador: ANALYST **não** vê Administração em Equipamentos (não tem `catalogs:manage`), mas **vê** em Suprimentos (tem `suppliers:write`); VIEWER não vê em nenhuma das duas. É gating por permissão, não por perfil.

## Componentes criados

| Componente | Papel |
| --- | --- |
| `components/admin/AdminPanel.vue` | Casca do painel: abas, layout e estados. Esconde a barra de abas quando há só uma seção. |
| `components/admin/CatalogAdmin.vue` | CRUD genérico de catálogo, reutilizado pelas cinco entidades — só mudam rota e campos. |
| `components/admin/UnitAccessAdmin.vue` | Acesso por unidade sobre os endpoints existentes. |
| `components/admin/EquipmentAdmin.vue` | Compõe catálogos + acessos para a aba Equipamentos. |
| `components/admin/SupplierAdmin.vue` | Cadastro mestre de fornecedores para a aba Suprimentos. |

`AppModal` do Hub foi reaproveitado como contêiner; nenhum CSS global foi alterado. O painel respeita a largura de 680px do `.modal-card` existente.

## Endpoints reaproveitados

Nenhum endpoint novo foi criado. Tudo usa a API da Etapa 4:

- `GET|POST /units`, `/units/{id}/project-contexts`, `/areas`, `/disciplines`, `/work-packages`
- `PATCH /units/{id}`, `/project-contexts/{id}`, `/areas/{id}`, `/disciplines/{id}`, `/work-packages/{id}`
- `GET|PUT /usuarios/{user_id}/units` e `GET /usuarios`
- `GET|POST /suppliers` e `GET|PATCH /suppliers/{id}`

## Fluxos

**Catálogos:** abrir Administração → escolher o catálogo → criar/editar/desativar. Catálogos por unidade usam a unidade do filtro global; work packages pedem o contexto dentro do painel. Desativar pede confirmação (o item some dos formulários); reativar não pede. **Não há exclusão física** em lugar nenhum.

**Acesso por unidade:** escolher usuário → ver unidades atuais → marcar/desmarcar → salvar. ADMIN é bloqueado com explicação, como no backend.

**Fornecedores:** buscar/criar/editar/ativar/desativar no painel. O vínculo fornecedor ↔ equipamento continua no detalhe do equipamento, intocado.

## Auditoria

Nenhuma auditoria nova foi criada — o frontend só consome endpoints já auditados na Etapa 4: `catalog.create`, `catalog.update`, `user.units_changed`, `supplier.create` e `supplier.update` (inclusive quando a mudança é só `active`). Não há evento duplicado.

## Testes

Frontend (52 no total, todos verdes):

- `tests/AppHeader.test.ts` (novo, 4): controles corporativos presentes, nenhum `disabled`, nenhuma busca do Painel acoplada ao campo do Hub, Registro de Atividades oculto para não-ADMIN.
- `tests/CatalogAdmin.test.ts` (novo, 5): listagem com situação, edição pelo endpoint existente, desativação com confirmação e sem opção de excluir, reativação sem confirmação, aviso quando falta o pai.
- Suítes das Etapas 1–4 mantidas sem alteração.

Backend: nenhum teste novo — nenhuma regra ou endpoint precisou mudar. As suítes anteriores seguem válidas.

Validação no navegador (Edge headless via CDP, backend + banco reais): painel de catálogos com dados reais, aba de acessos listando usuários, painel de fornecedores, e o gating de permissão descrito acima. Os dados de demonstração foram removidos do banco ao final.

## Resultados

| Check | Resultado |
| --- | --- |
| `pnpm lint` | ✅ |
| `pnpm typecheck` | ✅ |
| `pnpm test` | ✅ 52 testes |
| `pnpm build` | ✅ |
| `ruff` / `mypy` | ✅ (sem alteração no backend) |

## Pendências conhecidas

- Formato definitivo (modal x drawer), posição do botão e agrupamento dos catálogos seguem provisórios, conforme combinado — a implementação é reversível e de baixo acoplamento.
- `/fornecedores` continua existindo como tela auxiliar; se o painel contextual bastar, ela pode ser removida depois.
- Atalho administrativo em Engenharia não foi criado; se a operação pedir, basta reusar `CatalogAdmin` com as três entidades.
- Matriz fina de permissões por departamento continua pendente da Etapa 4.
- Exportação server-side (CSV) para volumes acima do teto atual.

## Preparação para Super Auditoria 4.5

Recursos já disponíveis no Hub que devem ser comparados com o Monday:

| Recurso | Onde está |
| --- | --- |
| Equipamento | `/equipamentos`, detalhe `/equipamentos/{id}` |
| Componentes | aba Componentes do detalhe |
| Workflow 0–8 | stepper e painel de requisitos no detalhe; regras em `app/modules/workflow` |
| Negociação | aba Processo (etapas 1–2) |
| Jurídico | aba Processo (etapas 3–4) e fila `/juridico` |
| Contrato | aba Processo (etapa 5) |
| SC/OCI | aba Processo (etapa 6) e fila `/suprimentos` |
| OC | aba Processo (etapa 7), com valor no dashboard |
| Responsáveis | seletor no formulário e filtro em `/equipamentos` |
| Fornecedores | aba Fornecedores do detalhe, painel de Suprimentos e `/fornecedores` |
| Unidade e filtros | filtros globais Unidade → Equipamento em todas as telas |
| Engenharia / Jurídico / Suprimentos | filas por recorte de etapa (0–2, 3–5, 6–7) |
| Dashboard | totais, distribuição 0–8, situação geral, negociação, próxima startup |
| Histórico | `GET /equipments/{id}/history`, aba Histórico |
| Auditoria | `audit_event` e `/dashboard/auditoria` |
| Permissões | `app/core/permissions.py` + escopo por unidade em `app/core/scope.py` |
| Catálogos | unidades, contextos, áreas, disciplinas, work packages |
| Administração contextual | painéis de Equipamentos e Suprimentos |
| Exportações | `.xlsx` da listagem de equipamentos, respeitando os filtros |

**Ainda não implementado**, e que a auditoria deve tratar como lacuna conhecida: fórmulas de prazo e os indicadores derivados (ATRASADO/URGENTE/PRÓXIMO/NO PRAZO), "Total de Aquisições", índices de aderência/criticidade/geral, FUP e kickoff, notificações, Kanban, comentários, anexos, integração ERP, migração C2/F2, estados Standby/Cancelado/Não se Aplica, múltiplos contratos/SCs/OCs por equipamento e processo competitivo entre fornecedores.
