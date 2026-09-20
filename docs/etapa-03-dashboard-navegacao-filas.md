# Etapa 03 — Dashboard Geral, navegação e filas operacionais

**Data da implementação:** 2026-09-20

## Objetivo

Transformar a base das Etapas 1 e 2 em uma experiência operacional navegável: navbar funcional, Dashboard Geral como primeiro menu, filtros globais de Unidade e Equipamento compartilhados entre telas, e filas por área (Engenharia, Jurídico e Suprimentos). Nenhuma métrica sem definição de negócio foi criada.

## Decisões arquiteturais

- O contexto global (Unidade + Equipamento) vive em um store Pinia (`stores/moduleContext.ts`), compartilhado por todas as telas do módulo. Trocar a unidade descarta o equipamento incompatível em um único lugar.
- A navegação é orientada por **Unidade → Equipamentos → Processo**. `project_context` continua interno e não vira menu; os boards C2/F2 não viraram telas.
- As filas são recortes explícitos do mesmo workflow 0–8, declarados em `QUEUE_STAGES`. Não há filtro oculto herdado do Monday.
- A pendência mostrada nas filas vem de `requirements_for()` — a mesma fonte do endpoint de transições da Etapa 2 —, então fila e detalhe nunca divergem.
- Agregações acontecem no banco. O frontend não carrega equipamentos para contar.
- A lógica pura do dashboard e da navbar ficou em `utils/` (testável sem montar componente), seguindo o padrão adotado nas etapas anteriores.

## Migrations

Nenhuma. A etapa não alterou o schema — só leitura e agregação sobre as tabelas das Etapas 1 e 2.

## Endpoints

### Alterado — `GET /api/v1/dashboard/summary`

Resposta consolidada (uma chamada por recorte), com `unit_id` e `equipment_id` opcionais:

```json
{
  "context": { "unitId": "...", "equipmentId": null },
  "totals": {
    "equipments": 3, "components": 0, "inProgress": 3, "completed": 0,
    "purchaseOrders": 1, "purchaseOrderAmount": "97500.00", "capexEstimated": "125000.00"
  },
  "workflow": [{ "stage": 0, "name": "Nova demanda", "count": 1 }],
  "negotiation": { "open": 1, "completed": 2, "inNegotiation": 0 },
  "deadlines": { "available": false, "reason": "..." },
  "startup": { "nextAt": "2026-10-04", "daysRemaining": 15, "equipmentId": "...", "equipmentName": "..." }
}
```

O formato plano da Etapa 1 (`totalEquipments`, `stageDistribution`…) foi substituído — não mantivemos campos duplicados. O único consumidor era o painel, atualizado nesta etapa.

### Novos — filas

- `GET /api/v1/queues/engineering`
- `GET /api/v1/queues/legal`
- `GET /api/v1/queues/procurement`

Filtros: `unit_id`, `equipment_id`, `stage`, `search`, `page`, `pageSize`. Permissão `equipments:read`. Cada linha traz o equipamento, os dados da área e `pending` com o que falta para a próxima etapa.

### Alterado — `GET /api/v1/equipments`

Novos filtros `discipline_id` e `responsible_user_id`, somados aos já existentes.

## Navbar

`components/TabsNav.vue` deixou de ser um contêiner vazio. Itens, em ordem, com ícones `lucide-vue-next` importados individualmente:

| Ordem | Item | Rota | Ícone | Visibilidade |
| --- | --- | --- | --- | --- |
| 1 | Dashboard | `/dashboard` | `LayoutDashboard` | sempre |
| 2 | Equipamentos | `/equipamentos` | `Boxes` | sempre |
| 3 | Engenharia | `/engenharia` | `Wrench` | sempre |
| 4 | Jurídico | `/juridico` | `Scale` | sempre |
| 5 | Suprimentos | `/suprimentos` | `ShoppingCart` | sempre |
| 6 | Auditoria | `/dashboard/auditoria` | `History` | só com `audit:read` |

A navbar segue o padrão dos demais módulos do Hub: **apenas o ícone**, com o nome aparecendo em um balão abaixo no hover e no foco de teclado. O rótulo continua acessível por `aria-label` em cada item, então leitores de tela anunciam o nome mesmo sem texto visível.

O balão precisa ultrapassar a borda do card, por isso a barra **não** usa `overflow`: qualquer valor diferente de `visible` recortaria o balão e criaria rolagem. Só com ícones, os seis itens cabem mesmo em telas estreitas.

O item ativo é resolvido por **prefixo mais específico** (`utils/navigation.ts`): `/equipamentos/{id}` mantém Equipamentos ativo e `/dashboard/auditoria` ativa Auditoria, não Dashboard. A navbar preserva a altura e o estilo anteriores, com hover e `:focus-visible`.

## Filtros globais

- As unidades vêm de `GET /units`, já restrito ao que o usuário pode ver.
- Unidade única é pré-selecionada; com várias, existe "Todas as unidades".
- O filtro de Equipamento só lista equipamentos da unidade selecionada e sempre oferece "Todos os equipamentos".
- Trocar a unidade limpa o equipamento incompatível (`setUnit` zera a seleção e recarrega as opções).
- Sem unidade selecionada, o filtro de equipamento fica desabilitado e os números consolidam as unidades disponíveis.
- Os filtros são sincronizados com a query string (`?unit=<id>&equipment=<id>`) em Dashboard e Equipamentos, permitindo compartilhar a mesma visão. As filas leem a query string na entrada.
- Sempre são usados IDs estáveis, nunca códigos ou nomes.

## Métricas implementadas

| Card | Definição exata |
| --- | --- |
| Equipamentos | contagem de equipamentos no recorte |
| Componentes | contagem de `equipment_component` dos equipamentos do recorte |
| Em andamento | equipamentos com `current_stage < 8` |
| Concluídos | equipamentos com `current_stage = 8` |
| Valor emitido em OC | soma de `purchase_order.amount` das OCs com `order_number` preenchido |
| CAPEX estimado | soma de `equipment.capex_estimated` informado |

Gráficos:

- **Distribuição por etapa** (`BarChart`): contagem por estágio 0–8, agregada no banco.
- **Situação geral** (`DonutChart`): agrupa as mesmas contagens em Nova demanda (0), Em processo (1–7) e Concluído (8). Nenhum estado novo foi inventado.
- **Negociação**: concluídas = `negotiation.negotiated_at` preenchido; em aberto = restante do recorte; em negociação/equalização = equipamentos nos estágios 1 e 2. A barra de progresso é `concluídas / total` e some quando não há base para calcular.
- **Próxima startup**: menor `startup_at` **maior ou igual a hoje** (UTC), empate resolvido pelo nome do equipamento. Datas passadas são ignoradas porque a startup já ocorreu.

## Métricas propositalmente não implementadas

- **Situação de prazos** — o backend devolve `deadlines.available: false` com o motivo, e a interface mostra "Indicador aguardando definição da regra de prazo." As fórmulas de `ATRASADO`, `URGENTE`, `PRÓXIMO` e `NO PRAZO` não foram formalizadas e não foram deduzidas do Monday.
- **"Total de Aquisições"** — não existe no painel. A auditoria apontou divergência entre 163 e 164, então usamos os rótulos inequívocos **Equipamentos** e **Componentes**.
- Índices de aderência, criticidade e índice geral: sem fórmula validada.
- Valor médio por OC: não incluído por não ter definição de negócio pedida.

## Critérios das filas

| Fila | Rota | Etapas | Colunas principais |
| --- | --- | --- | --- |
| Engenharia | `/engenharia` | 0 a 2 | disciplina, área, work package, responsável, startup |
| Jurídico | `/juridico` | 3 a 5 | chamado, abertura, minuta elaborada/aprovada, contrato, escrituração |
| Suprimentos | `/suprimentos` | 6 e 7 | tipo SC/OCI, número e data da solicitação, número/data/valor da OC |

O critério aparece em texto na própria tela, além de estar em `QUEUE_STAGES`. Todas trazem a coluna **Pendência** com o que falta para a próxima etapa e o link "Ver detalhes". Fornecedor não é exibido: a estrutura não existe e nenhum dado foi inventado.

## Páginas e componentes

Criados:

- `pages/equipamentos/index.vue` — listagem com busca, filtros de etapa e disciplina, paginação server-side.
- `pages/engenharia.vue`, `pages/juridico.vue`, `pages/suprimentos.vue`.
- `components/ModuleFilters.vue` — barra de filtros globais reutilizada por todas as telas.
- `components/queue/QueueShell.vue` — estados (carregando, erro, vazio, sem permissão) e paginação das filas.
- `components/queue/PendingBadge.vue` — pendências da próxima etapa.
- `stores/moduleContext.ts`, `composables/useQueue.ts`, `utils/navigation.ts`, `utils/dashboard.ts`.

Alterados:

- `components/TabsNav.vue` — navbar funcional.
- `pages/dashboard/index.vue` — reescrito como Dashboard Geral (a tabela de equipamentos migrou para `/equipamentos`).
- `types/equipment.ts`, `types/api.ts`, `stores/auth.ts`, `utils/format.ts` (novo `formatCurrency`, que eliminou a duplicação de formatação de moeda em três arquivos).

Removido:

- `composables/useEquipmentDashboard.ts` — substituído pelo store global; ficaria sem uso.

Backend: `app/modules/queues/` (novo) e `app/modules/dashboard/` (reescrito).

## Estados de interface

Todas as telas novas têm carregando, erro com "Tentar novamente", vazio sem dados falsos, e **sem permissão** quando falta `equipments:read`. Os filtros têm `label` associado; a navbar tem `aria-current` e foco visível.

## Testes

Backend — `tests/integration/test_dashboard_and_queues.py` (13 testes):

- totais e distribuição por etapa com as 9 etapas na ordem do catálogo;
- filtro por unidade e por equipamento;
- métricas de OC e de negociação;
- prazos retornando não calculável;
- próxima startup ignorando datas passadas;
- summary exigindo autenticação;
- separação das três filas pelos intervalos documentados;
- pendência correta na fila de Engenharia;
- dados de processo nas filas Jurídica e de Suprimentos;
- filtro por unidade e paginação nas filas;
- filas exigindo autenticação;
- filtro por disciplina em `/equipments`.

Frontend — `tests/navigation.test.ts` (9) e `tests/dashboard.test.ts` (8): ordem e ícones únicos dos menus, visibilidade da Auditoria por permissão, rota ativa por prefixo mais específico, pontos do gráfico, agrupamento do donut, progresso de negociação e rótulos de startup.

`tests/integration/test_equipment_routes.py` foi ajustado para o novo formato do summary.

## Validação executada

| Check | Resultado |
| --- | --- |
| `ruff check app tests scripts` | ✅ |
| `mypy app` | ✅ 57 arquivos |
| `pytest` | ✅ (ver seção abaixo) |
| `pnpm lint` | ✅ |
| `pnpm typecheck` | ✅ |
| `pnpm test` | ✅ 39 testes |
| `pnpm build` | ✅ |

Validação visual real no navegador (Edge headless via CDP, backend + banco reais): navbar com os 6 itens e item ativo correto, Dashboard Geral com os 6 cards, gráfico de etapas, donut, negociação, aviso de prazo não calculável e próxima startup; `/equipamentos` com filtros e tabela; `/suprimentos` exibindo SC/OCI, OC, valor e a pendência "Informe a data de entrega prevista no contrato". Os dados de demonstração usados foram removidos do banco de desenvolvimento ao final.

## Pendências conhecidas

Dependem de definição de negócio e ficaram fora desta etapa:

- fórmulas oficiais de prazo (e, por consequência, o bloco "Situação de prazos");
- definição de "Total de Aquisições";
- índices de aderência, criticidade e índice geral;
- cadastro de fornecedores e processo competitivo;
- FUP, notificações e kickoff;
- Kanban, comentários, anexos e exportações avançadas;
- integração ERP e migração integral de C2/F2;
- estados `Standby`, `Cancelado` e `Não se Aplica`;
- matriz fina de permissões por Engenharia/Jurídico/Suprimentos (hoje todas as filas usam `equipments:read`);
- filtro por responsável na tela de Equipamentos: o backend já aceita `responsible_user_id`, mas falta um catálogo de responsáveis para alimentar o seletor.

## Correção incidental

Durante a etapa foi corrigido um bug pré-existente em `app/core/errors.py`: o handler de validação passava `exc.errors()` direto ao `JSONResponse`, e como o Pydantic embute o `ValueError` original em `ctx.error`, qualquer validador que levantasse `ValueError` puro devolvia **500** em vez de 422. Agora passa por `jsonable_encoder`.
