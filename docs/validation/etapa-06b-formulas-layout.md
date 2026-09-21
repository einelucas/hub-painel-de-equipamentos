# Etapa 6B — Layout estrutural + Fórmulas e Prazos (FUN-001)

Data: 2026-09-21

## UI-001 — Largura útil do módulo

**Componente/regra alterada**: uma única regra CSS, compartilhada por todas
as páginas — `.app-toolbar-shell, .nuxt-app-main` em
`frontend/assets/css/vue.css`. `.nuxt-app-main` é o `<main>` de
`layouts/default.vue` (envolve o conteúdo de toda página via `ModuleWorkspace`);
`.app-toolbar-shell` é o mesmo wrapper usado por `TabsNav.vue`. Não havia
nenhuma largura fixa por página — todas herdam dessa única regra, então a
alteração foi centralizada por natureza (nenhuma página foi editada para
isso).

| | Antes | Depois |
|---|---|---|
| Largura | `min(calc(100% - 40px), 1320px)` | `min(calc(100% - 48px), 1680px)` |
| Breakpoint ≤900px | `min(calc(100% - 28px), 1320px)` | `min(calc(100% - 28px), 1680px)` |
| Breakpoint ≤480px (novo) | — | `min(calc(100% - 20px), 1680px)` |

Header (`AppHeader.vue`) e identidade visual não foram tocados — o cabeçalho
já era full-bleed (sem `max-width`), então continua igual; só o conteúdo
abaixo dele (nav de abas + páginas) ficou mais largo.

**Telas verificadas** (Playwright, 1920×1080, dados reais do C2 em DEV):
Dashboard, Equipamentos (listagem), detalhe de equipamento, Engenharia,
Jurídico, Fornecedores — todas centralizadas, sem redesenho, mesma
identidade visual, só com mais espaço horizontal para as tabelas. Auditoria
usa o mesmo layout compartilhado (não verificada individualmente, mas não
há CSS próprio de largura nela).

**Responsividade**: testado em 400px de largura (engenharia e dashboard) —
`document.documentElement.scrollWidth === clientWidth` (sem scroll
horizontal na página). Tabelas mantêm `overflow-x: auto` interno já
existente (`.table-wrap`), não foi necessário mexer em min-width de coluna
nenhuma — não havia nenhuma largura fixa em pixel nas tabelas.

---

## FUN-001 — Fórmulas e prazos

### Arquitetura

**Antes**: `backend/app/modules/monday_import/calculations.py` continha a
única implementação das fórmulas, mas só era consumida pelos próprios
testes do importador (`test_monday_import_calculations.py`,
`test_monday_import_reconciliation.py`) — nunca chamada por `apply.py`,
`plan.py`, nem por nenhum módulo da aplicação viva.

**Depois**: lógica movida para `backend/app/domain/equipment_calculations.py`
(pacote novo, `app/domain/`, sem dependência de banco/HTTP — só dataclasses
e funções puras). `monday_import/calculations.py` virou um shim de
reexportação (`from app.domain.equipment_calculations import ...`), para
não quebrar nenhum import/teste existente do importador. A API viva
(`app/modules/equipments/service.py`) importa diretamente do domínio.
**Uma implementação só**, os dois lados a compartilham.

### Decisão de persistência

**On-the-fly, nunca persistido.** Cada campo derivado é recalculado a cada
leitura (`GET`), a partir dos campos-base já no banco
(`startup_at`, `pre_start_days`, `freight_days`, `lead_time_days`,
`contract_delivery_at` do componente). Motivo: os campos-base mudam com
alguma frequência (edição manual do componente) e o volume é pequeno (164
componentes hoje, mesmo em escala futura seria uma soma/min/max sobre uma
lista curta por equipamento) — cachear ou persistir criaria uma segunda
fonte de verdade que precisaria de invalidação toda vez que um componente
mudasse, sem nenhum ganho de performance mensurável neste volume. Se o
volume crescer ordens de grandeza no futuro, materializar os agregados do
equipamento (não os do componente, que já são baratos) é a extensão natural
— não implementado agora porque não há necessidade real hoje.

A única exceção dinâmica de verdade é `negotiationDaysRemaining`
(dias restantes até a data limite de negociação): depende de "hoje". Nunca
lido do relógio dentro da função pura (`days_until` exige `reference_date`
explícito) — a data de referência (`datetime.now(UTC).date()`) é resolvida
uma vez por chamada de serviço, no mesmo padrão já usado em
`dashboard/service.py` (`_next_startup`).

### Fórmulas implementadas

**Componente** (`ComponentCalculatedOut`, depende só do startup PRÓPRIO do
componente — nunca herda `equipment.startupAt`):

| Campo API | Fórmula | Regra de NULL |
|---|---|---|
| `deliveryDeadline` | `startup_at - pre_start_days` | `null` se `startup_at` ou `pre_start_days` faltar |
| `availableForCollection` | `deliveryDeadline - freight_days` | `null` se `deliveryDeadline` faltar. `freight_days` em branco = **0 dias** — comportamento já confirmado empiricamente durante a migração (não é regra nova; ver docstring de `equipment_calculations.py`) |
| `contractOrderDeadline` | `availableForCollection - lead_time_days` | `null` se `availableForCollection` ou `lead_time_days` faltar |
| `negotiationDeadline` | `contractOrderDeadline - 21 dias corridos` | `null` se `contractOrderDeadline` faltar |
| `negotiationDaysRemaining` | `negotiationDeadline - hoje (UTC)` | `null` se `negotiationDeadline` faltar. Dinâmico, nunca persistido |
| `deliveryMarginDays` | `deliveryDeadline - contract_delivery_at` | `null` se `deliveryDeadline` ou `contract_delivery_at` faltar |

**Equipment** (`EquipmentCalculatedOut`, agregado dos componentes):

| Campo API | Fórmula |
|---|---|
| `maxLeadTimeDays` | `MAX(component.lead_time_days)` |
| `maxPreStartDays` | `MAX(component.pre_start_days)` |
| `maxFreightDays` | `MAX(component.freight_days)` |
| `deliveryDeadline` | `MIN(component.deliveryDeadline)` |
| `contractOrderDeadline` | `MIN(component.contractOrderDeadline)` |
| `negotiationDeadline` | `MIN(component.negotiationDeadline)` |
| `negotiationDaysRemaining` | `negotiationDeadline - hoje (UTC)` |

Equipamento sem componentes, ou sem nenhum componente com o dado
preenchido, devolve `null` em todo agregado correspondente — nunca 0 nem
data arbitrária (`aggregate_component_deadlines`, testado).

### Não implementado nesta etapa (por instrução explícita)

- **`negotiationStatus`** (URGENTE/PRÓXIMO/NO PRAZO/ATRASADO/CONCLUÍDO):
  a função `negotiation_status()` continua existindo e testada no domínio
  (só o caso `CONCLUIDO` quando há `negotiated_at`, e `ATRASADO` quando
  `days_remaining < 0`, são tratados como confirmados), mas **não está
  ligada a nenhum endpoint/schema**. GAP-014 continua registrado e
  pendente — os limiares exatos de URGENTE/PRÓXIMO/NO PRAZO não foram
  formalmente confirmados.
- **Classificação categórica de aderência de entrega**
  (`delivery_adherence_candidate`, ATENDE/PENDENTE_VALIDACAO): função
  mantida e testada no domínio, mas também não exposta pela API nesta
  etapa — só o número (`deliveryMarginDays`) é exposto, conforme instruído
  ("a fórmula numérica/diferença... pode ser exposta. Não inventar
  threshold de status.").

### Proteção contra escrita manual

`EquipmentCreateIn`/`EquipmentUpdateIn`/`ComponentCreateIn`/`ComponentUpdateIn`
ganharam um `model_validator(mode="before")` que rejeita (422) qualquer
payload contendo os nomes dos campos calculados (camelCase ou snake_case),
tanto no create quanto no update. Testado em
`test_calculated_fields_cannot_be_set_directly`.

### Arquivos alterados

**Backend**
- `app/domain/__init__.py`, `app/domain/equipment_calculations.py` (novos — lógica movida)
- `app/modules/monday_import/calculations.py` (virou shim de reexportação)
- `app/modules/equipments/schemas.py` (`ComponentCalculatedOut`, `EquipmentCalculatedOut`, proteção)
- `app/modules/equipments/service.py` (`_base_load_options` carrega `components`; `component_out`, `_component_calculated_out`, `_equipment_calculated_out`, `_reference_date`)
- `app/modules/equipments/router.py` (usa `service.component_out` em vez de `ComponentOut.model_validate`)
- `tests/unit/test_equipment_calculations.py` (novo, 16 testes)
- `tests/integration/test_equipment_calculations_routes.py` (novo)
- `scripts/verify_fun001_fix.py`, `scripts/verify_fun001_c2_regression.py` (novos, verificação direta)

**Frontend**
- `assets/css/vue.css` (UI-001)
- `types/equipment.ts` (`EquipmentCalculated`, `ComponentCalculated`)
- `pages/equipamentos/[id].vue` (seção "Prazos e planejamento"; tabela de componentes com toggle "Prazos calculados" por linha)
- `tests/EquipmentTable.test.ts`, `tests/ComponentForm.test.ts` (fixtures atualizadas com `calculated`)

### Contrato da API (novo)

`GET /equipments/{id}`, `GET /equipments`, `GET /equipments/{id}/components`,
`POST .../components`, `PATCH /components/{id}` agora incluem:

```jsonc
// Equipment.calculated
{
  "maxLeadTimeDays": 150,
  "maxPreStartDays": 373,
  "maxFreightDays": 10,
  "deliveryDeadline": "2026-10-19",
  "contractOrderDeadline": "2026-08-03",
  "negotiationDeadline": "2026-07-13",
  "negotiationDaysRemaining": -70
}
// EquipmentComponent.calculated
{
  "deliveryDeadline": "2026-11-09",
  "availableForCollection": "2026-10-30",
  "contractOrderDeadline": "2026-08-28",
  "negotiationDeadline": "2026-08-07",
  "negotiationDaysRemaining": -45,
  "deliveryMarginDays": null
}
```

Nomenclatura deliberadamente sem prefixos herdados do Monday (`F.`, `E.`,
`ESPELHO`, `FÓRMULA-NÃO-MEXER`) — nomes de domínio em `camelCase` puro.

### Frontend

- **Equipamento → "Prazos e planejamento"** (nova seção, sempre visível no
  topo do detalhe, abaixo do Resumo): Lead time máximo, Dias antes do
  startup (máx.), Frete máximo, Limite entrega em obra, Limite contrato/OC,
  Limite negociação (com "X dias restantes"/"X dias em atraso" quando
  aplicável). Somente leitura.
- **Componentes → tabela**: mantida como estava (Startup, Lead time,
  Pré-start, Entrega contratual, Frete já existiam) **+ botão "Prazos
  calculados" por linha**, que expande uma linha com Limite entrega em
  obra, Disponível coleta, Limite contrato/OC, Limite negociação — evita
  transformar a tabela numa grade de 12+ colunas, conforme pedido.
- Nada é editável nos campos derivados — só os campos-base (via "Editar" do
  componente), e os derivados já aparecem atualizados na resposta do
  próprio PATCH (sem precisar recarregar a página), porque `component_out`
  monta o `calculated` a partir do objeto já atualizado em memória.

### Testes

**Unitários** (`tests/unit/test_equipment_calculations.py`, 16 testes, 0.14s,
todos passando): todos os inputs presentes; cada input-base `None`
isoladamente (startup, pré-start, lead time — cada um interrompe a cadeia
no ponto certo); frete em branco (comportamento confirmado = 0, e modo
estrito com `blank_freight_days_default=None`); valores zero (não tratados
como ausentes); virada de mês; virada de ano; ano bissexto (29/02/2028);
equipamento sem componentes (todos os agregados `None`); equipamento com
componentes parcialmente preenchidos (ignora os que faltam dado); MAX;
MIN; recálculo após "edição" (mesma função, novo valor-base).

**Integração** (`tests/integration/test_equipment_calculations_routes.py`,
novo): equipamento sem componentes → `calculated` todo `null`; componente
calculado corretamente e independente do `startupAt` do equipamento;
agregados MAX/MIN corretos com 2 componentes; recálculo refletido na
resposta do PATCH; proteção contra payload forjando campo calculado (422);
`negotiationDaysRemaining` dinâmico (positivo para startup futuro).

**Regressão C2** (`scripts/verify_fun001_c2_regression.py`, somente
leitura, roda direto contra o banco DEV): recalcula os prazos de cada um
dos 164 componentes reais e os agregados dos 41 equipamentos reais via
`app.domain.equipment_calculations`, e compara contra o que
`component_out`/`get_equipment_out` (a mesma função da API) devolveram.

```
Componentes comparados: 164 (esperado 164)
Componentes MATCH: 164
Componentes MISMATCH: 0 []

Equipamentos comparados: 41 (esperado 41)
Equipamentos MATCH: 41
Equipamentos MISMATCH: 0 []

FUN-001: 0 MISMATCH em 164 componentes e 41 equipamentos reais do C2.
```

Evidência adicional ao vivo (Playwright, dados reais, "Caldeira de
Biomassa"): seção "Prazos e planejamento" mostrou `Limite negociação:
12/07/2026 (70 dias em atraso)`, e o toggle "Prazos calculados" de um
componente mostrou `Limite entrega em obra: 08/11/2026`, `Disponível
coleta: 29/10/2026`, `Limite contrato/OC: 27/08/2026`, `Limite negociação:
06/08/2026` — batendo com a mesma API testada acima.

### Achado colateral (não corrigido, fora de escopo)

`frontend/utils/format.ts#formatDate` faz `new Date(string)` em datas
`YYYY-MM-DD`, que o JS interpreta como meia-noite UTC; ao formatar de volta
no fuso local do navegador, isso pode exibir o dia anterior (observado:
API devolveu `"2026-10-19"`, tela mostrou `18/10/2026`, dependendo do fuso
do navegador). **Isto é pré-existente e afeta TODAS as datas já exibidas no
Hub hoje** (startup, entrega contratual, etc.) — não foi introduzido por
esta etapa, e corrigi-lo está fora do escopo de UI-001/FUN-001 (mexeria em
uma função usada por praticamente toda a aplicação). Registrado aqui para
priorização futura.

---

## Baseline DEV — confirmada intacta

Antes, durante e depois de todas as mudanças desta etapa:

```
Equipment: 41
EquipmentComponent: 164
equipment_work_package: 71
```

Nenhum dado do C2 foi criado, alterado ou removido. As verificações de
FUN-001 que gravam dados (`verify_fun001_fix.py`) rodaram contra
`neondb_test` (banco de teste separado); a regressão contra o C2
(`verify_fun001_c2_regression.py`) é somente leitura contra DEV.
