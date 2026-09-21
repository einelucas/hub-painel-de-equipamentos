# Etapa 6C — Consistência de Datas + Status de Negociação (GAP-014)

Data: 2026-09-21

## 1. Bug global de datas DATE-ONLY

### Causa

`frontend/utils/format.ts#formatDate("2027-10-26")` fazia `new Date("2027-10-26")`.
O JavaScript interpreta uma string `YYYY-MM-DD` como **meia-noite UTC**.
Ao formatar esse `Date` de volta com `Intl.DateTimeFormat`, o resultado é
convertido para o **fuso local do navegador** — se esse fuso está atrás de
UTC (ex.: Brasil, UTC-3), meia-noite UTC de dia 26 cai às 21h do dia 25 no
horário local, e a tela mostra `25/10/2027`. Confirmado em produção nesta
sessão: API devolvia `startupAt: "2027-10-27"`, a tela da Caldeira de
Biomassa mostrava `26/10/2027`.

Esse bug só existe para strings **DATE-ONLY** (sem hora). Timestamps
completos (`"2026-09-21T14:30:00.000Z"`) não têm esse problema — a
conversão de fuso é exatamente o comportamento certo para eles, porque
representam um instante real que faz sentido reapresentar no fuso de quem
está olhando.

### Solução

`frontend/utils/format.ts` ganhou duas funções, substituindo `formatDate`:

- **`formatDateOnly(value)`** — nunca deixa o `Date` nascer via parsing de
  string. Extrai ano/mês/dia da string com regex e constrói
  `new Date(ano, mês - 1, dia)`, que o JS sempre interpreta no fuso
  **local** — não há conversão de fuso para dar errado, porque não há
  conversão nenhuma. O dia formatado é sempre exatamente o dia recebido,
  em qualquer fuso.
- **`formatDateTime(value)`** — o comportamento antigo (`new Date(string)` +
  `Intl.DateTimeFormat` com `dateStyle`+`timeStyle`), mantido porque é
  correto para timestamps reais.

Nenhuma fórmula da Etapa 6B foi tocada — o bug era só na camada de
apresentação (frontend), nunca no cálculo em si (as fórmulas trabalham com
objetos `date` do Python, nunca com string formatada).

### Campos corrigidos (todos os usos de `formatDate` foram revisados e substituídos)

**DATE-ONLY → `formatDateOnly`**: `equipment.startupAt`,
`component.startupAt`, `negotiation.negotiatedAt`, `legal.openedAt`,
`contract.executedAt`, `contract.deliveryAt`, `purchaseRequest.requestedAt`,
`purchaseOrder.orderedAt`, `component.contractDeliveryAt`, e todos os 4
prazos calculados na Etapa 6B (`deliveryDeadline`, `availableForCollection`,
`contractOrderDeadline`, `negotiationDeadline`, no nível de componente e de
equipamento).

**DATETIME → `formatDateTime`**: `AuditLog.createdAt` (`AuditViewer.vue`),
`HistoryEntry.occurredAt` (aba Histórico do equipamento).

Nenhum outro uso de `new Date(...)`, `Date.parse`, `toLocaleDateString` ou
`toLocaleString` foi encontrado no frontend (grep completo) além dos já
citados e de um `new Date().toISOString().slice(0, 10)` só para nomear o
arquivo de exportação — sem risco de timezone (é só "hoje", não vem da API).

### Arquivos alterados

`utils/format.ts` e os 9 arquivos que chamavam `formatDate`:
`components/admin/AuditViewer.vue`, `components/equipment/EquipmentTable.vue`,
`components/equipment/ProcessSummary.vue`, `pages/dashboard/index.vue`,
`pages/engenharia.vue`, `pages/equipamentos/index.vue`,
`pages/equipamentos/[id].vue`, `pages/juridico.vue`, `pages/suprimentos.vue`.

### Testes

`tests/format.test.ts`, 9 testes novos: preserva o dia exato (regressão do
bug relatado, `"2027-10-26"` → `"26/10/2027"`), início/fim de mês e ano,
29/02 em ano bissexto, string com hora/timezone anexada (ainda extrai só o
dia certo), valores vazios, valor inválido, e `formatDateTime` com
timestamp completo.

### Evidência ao vivo

Playwright contra DEV, "Caldeira de Biomassa" real: `startupAt` da API é
`"2027-10-27"` — antes desta etapa a tela mostrava `26/10/2027`, depois
mostra `27/10/2027`. `deliveryDeadline` calculado é `"2026-10-19"` — antes
mostrava `18/10/2026`, depois mostra `19/10/2026`.

---

## 2. GAP-014 — Status Negociação

### Fórmula oficial recebida (implementada exatamente como especificada)

Precedência (nunca reordenada):

1. `operational_status` ∈ {CANCELADO, ⚠️Em Saneamento, Não se Aplica} → `NOT_APPLICABLE`
2. `negotiated_at` preenchido → `COMPLETED`
3. `negotiation_deadline` ausente → `None`
4. Tabela de dias restantes (`negotiation_deadline - reference_date`):

| Dias | Resultado |
|---|---|
| `< 0` | `OVERDUE` (Atrasado) |
| `0` | `DUE_TODAY` (Vence hoje) |
| `1`–`7` | `CRITICAL` (Crítico) |
| `8`–`15` | `URGENT` (Urgente) |
| `16`–`30` | `UPCOMING` (Próximo) |
| `> 30` | `ON_TRACK` (No prazo) |

### Implementação

`app/domain/equipment_calculations.py` (mesmo módulo único da Etapa 6B):
`NegotiationStatus` (enum `str`) + `calculate_negotiation_status(*, negotiation_deadline, negotiated_at, reference_date, operational_status=None)`.
A função antiga `negotiation_status(...)` (placeholder "PENDENTE_THRESHOLDS"
da Etapa 6B, nunca ligada a nenhum endpoint) foi **substituída** por esta —
não ficaram duas funções de status conflitantes no domínio.

Exposta em `EquipmentOut.calculated.negotiationStatus` (enum de string
estável: `NOT_APPLICABLE`/`COMPLETED`/`OVERDUE`/`DUE_TODAY`/`CRITICAL`/
`URGENT`/`UPCOMING`/`ON_TRACK` — nunca os rótulos/emoji do Monday, ex.:
`"✅NO PRAZO✅"`). Calculado a partir do agregado de equipamento
(`min(component.negotiationDeadline)`, já existente desde a 6B) e de
`Equipment.negotiation.negotiated_at` (carregado via novo `joinedload` em
`_base_load_options`). Não é exposto a nível de componente — "status" é um
conceito do processo de negociação do equipamento (1:1 com `Negotiation`),
não do componente individual.

`operational_status` não é passado em lugar nenhum da chamada real
(`service.py`) — ver seção "Pendência de modelagem" abaixo.

### Proteção

`negotiationStatus`/`negotiation_status` adicionado ao conjunto de campos
calculados rejeitados em `EquipmentCreateIn`/`EquipmentUpdateIn` (422 se
enviado).

### Frontend

`utils/negotiationStatus.ts`: só apresentação (rótulo em português + classe
CSS por valor de enum), **nenhum threshold é recalculado no Vue** — a
função só faz um `Record<NegotiationStatus, string>` lookup do que a API já
decidiu. Badge novo em "Prazos e planejamento" (`pages/equipamentos/[id].vue`),
ao lado do prazo de negociação.

### Arquivos alterados

- `app/domain/equipment_calculations.py` (enum + função nova, função antiga removida)
- `app/modules/monday_import/calculations.py` (shim atualizado)
- `app/modules/equipments/schemas.py` (campo novo + proteção)
- `app/modules/equipments/service.py` (`joinedload(Equipment.negotiation)`, cálculo)
- `tests/unit/test_negotiation_status.py` (novo, 23 testes)
- `tests/unit/test_monday_import_calculations.py` (teste antigo adaptado à nova assinatura)
- `tests/integration/test_negotiation_status_routes.py` (novo)
- `scripts/verify_gap014_c2_regression.py`, `scripts/inspect_negotiation_status_observed.py` (novos, verificação direta)
- `frontend/types/equipment.ts` (`NegotiationStatus`, campo em `EquipmentCalculated`)
- `frontend/utils/negotiationStatus.ts` (novo)
- `frontend/pages/equipamentos/[id].vue` (badge)
- `frontend/tests/negotiationStatus.test.ts` (novo)

### Testes unitários (23/23 passando)

Tabela oficial completa (`-1`→ATRASADO, `0`→VENCE HOJE, `1` e `7`→CRÍTICO,
`8` e `15`→URGENTE, `16` e `30`→PRÓXIMO, `31`→NO PRAZO); atraso extremo
(-67 dias) continua ATRASADO; `negotiated_at` preenchido → CONCLUÍDO mesmo
com deadline atrasado ou ausente; deadline ausente e não negociado → `None`;
os 3 valores especiais de A.Status (`CANCELADO`, `⚠️Em Saneamento` com e sem
emoji, `Não se Aplica` com e sem acento) → `NOT_APPLICABLE`; precedência
explícita (status especial vence `negotiated_at`, que vence a tabela de
dias, que só é usada quando as duas primeiras não se aplicam); um A.Status
qualquer fora do conjunto especial não vira `NOT_APPLICABLE` por engano;
`operational_status=None` (caso real do C2 hoje) não é tratado como
especial.

### Regressão C2 (41 equipamentos reais, DEV, somente leitura)

Comparação entre o status calculado agora e o "Status Negociação" que o
Monday tinha registrado no momento da migração
(`negotiation_status_observed`, staged em `monday_import_record` desde a
MIG-001.1 — não foi tocado, só lido).

Valores reais observados nos 41 equipamentos (com emoji, como vieram do
Monday): `✅NO PRAZO✅` (27×), `🎯CONCLUÍDO🎯` (10×), `👀PRÓXIMO👀` (2×),
`💥ATRASADO💥` (1×), `❗URGENTE❗` (1×). Nenhum CANCELADO/Em Saneamento/Não se
Aplica presente nos dados reais.

```
Equipamentos com negotiation_status_observed no staging: 41/41
Sem valor observado: 0
Não reconhecidos após normalização: []

MATCH exato (mesmo enum, hoje == data da exportação em efeito): 41
Divergência esperada por passagem de tempo: 0
MISMATCH real (precedência ou classificação incompatível): 0 []

GAP-014: nenhum MISMATCH real.
```

**41/41 MATCH.** Nota metodológica importante: o valor observado é um
retrato do dia em que o Monday foi exportado; o valor calculado usa a data
de hoje. Para os estados que dependem de "quantos dias faltam"
(NO_PRAZO/PRÓXIMO/URGENTE/CRÍTICO/VENCE HOJE), uma divergência frente ao
snapshot antigo seria **esperada e aceitável** à medida que o tempo passa —
não teria sido tratada como bug. Não foi necessário invocar essa tolerância
porque todos os 41 já bateram exatamente; nenhuma fórmula foi ajustada para
"fazer bater".

### Pendência de modelagem: CANCELADO / Em Saneamento / Não se Aplica

O Hub não tem hoje nenhum campo equivalente ao `A.Status` do Monday.
`current_stage` (0–8) é uma state machine de **etapa do processo**, não um
status operacional do equipamento — não foi (e não deve ser, por instrução
explícita desta etapa) transformado em novas etapas nem sobrecarregado para
representar CANCELADO/Em Saneamento/Não se Aplica.

`calculate_negotiation_status` já suporta o parâmetro `operational_status`
completo e testado (prioridade 1 da fórmula), mas **nenhum equipamento real
do C2 usa esse caminho hoje** — os 41 equipamentos importados não têm
nenhum estado especial (confirmado na regressão acima). O parâmetro fica
pronto para quando o negócio decidir como/onde modelar esse campo (ex.: novo
enum em `Equipment`, ou tabela própria) — decisão de modelagem que não foi
tomada nesta etapa, por instrução explícita ("não inventar modelagem").

---

## Baseline DEV — confirmada intacta

```
Equipment: 41
EquipmentComponent: 164
equipment_work_package: 71
```

Nenhum dado do C2 foi criado, alterado ou removido nesta etapa. As
verificações de GAP-014 (`verify_gap014_c2_regression.py`,
`inspect_negotiation_status_observed.py`) são somente leitura contra DEV.
