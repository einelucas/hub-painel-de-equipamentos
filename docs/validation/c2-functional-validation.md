# Homologação Funcional Pós-Migração C2

Auditoria somente-leitura do estado real do Hub após a migração do C2 (LEM),
usando os 41 equipamentos/164 componentes já importados como dado de
referência. Nenhum dado do C2 foi alterado, criado ou apagado durante esta
auditoria; nenhuma correção foi aplicada. Evidências novas produzidas nesta
etapa (somente leitura) ficam em `docs/validation/`.

> **Atualização — Etapa 6A (2026-09-21)**: GAP-008, GAP-011, GAP-001 e
> GAP-009 foram corrigidos. Detalhes, arquivos alterados e evidência de
> teste em [`etapa-06a-operational-fixes.md`](etapa-06a-operational-fixes.md).
> O texto original da auditoria abaixo foi mantido intacto (histórico); a
> tabela consolidada no fim deste arquivo marca esses 4 gaps como
> `RESOLVIDO NA ETAPA 6A`.
>
> **Atualização — Etapa 6B (2026-09-21)**: GAP-013 implementado (fórmulas de
> prazo, arquitetura única em `app/domain/equipment_calculations.py`,
> consumida pelo importador E pela API viva; 0 MISMATCH contra os 164
> componentes/41 equipamentos reais do C2). GAP-014 continua
> **intencionalmente pendente** (thresholds de Status Negociação não
> confirmados) — não implementado, conforme instruído. UI-001 (largura do
> módulo) registrada como melhoria estrutural concluída. Detalhes em
> [`etapa-06b-formulas-layout.md`](etapa-06b-formulas-layout.md).
>
> **Atualização — Etapa 6C (2026-09-21)**: GAP-014 **implementado** — fórmula
> oficial de Status Negociação recebida e codificada em
> `calculate_negotiation_status` (mesmo domínio da 6B), com precedência
> testada (23 testes unitários) e **41/41 MATCH exato** contra o "Status
> Negociação" real observado no Monday para os 41 equipamentos do C2. Bug
> global de datas DATE-ONLY (exibição um dia antes por timezone) também
> corrigido nesta etapa — afetava todas as datas já em produção, não só as
> fórmulas da 6B. Detalhes em
> [`etapa-06c-dates-negotiation-status.md`](etapa-06c-dates-negotiation-status.md).
>
> **Atualização — Etapa 6C.1 (2026-09-21)**: GAP-015 **implementado** —
> fórmula oficial de "Status Necessidade da Obra" codificada em
> `calculate_work_need_status` (mesmo domínio de 6B/6C), reutilizada pelo
> detalhe do equipamento e pelo card "Situação de prazos" do Dashboard, que
> deixa de ser `available=false` hardcoded e passa a mostrar a distribuição
> real do recorte. **41/41 MATCH exato** contra o Status Necessidade da
> Obra real observado no Monday. Detalhes em
> [`etapa-06c1-work-need-dashboard.md`](etapa-06c1-work-need-dashboard.md).
>
> **Atualização — Etapa 6D (2026-09-22)**: completude operacional e
> auditoria — GAP-002 (sub-processos migrados agora aparecem no Histórico,
> resolvido por relacionamento via `equipment_audit_conditions`, sem
> reescrever dado nem reexecutar migração), GAP-003 (título amigável
> "Importado do Monday"), GAP-010 (filtros `area_id`/`work_package_id` em
> `/equipments`, EXISTS sem duplicar linha), GAP-012a/b (coluna Responsável
> em Jurídico/Suprimentos, Entrega contratual em Jurídico), GAP-016
> (`auth.can()` do frontend passa a usar só `user.permissions` do backend,
> matriz local removida) e GAP-019 (filtros de Equipamento/Usuário/período
> na Auditoria, mesma lógica do GAP-002). Todos confirmados contra os 41
> equipamentos reais do C2. Detalhes em
> [`etapa-06d-operational-completeness.md`](etapa-06d-operational-completeness.md).

Critério usado em cada item: **"Se o Monday fosse desligado hoje, o usuário
conseguiria executar esta parte do processo somente pelo Hub?"**

## Baseline (confirmada intacta ao final desta auditoria)

| Métrica | Valor |
|---|---|
| Equipment (C2) | **41** |
| EquipmentComponent (C2) | **164** |
| Vínculos `equipment_work_package` (C2) | **71** |
| Fase 0 | 31 equipamentos / 55 componentes |
| Fase 4 | 6 / 8 |
| Fase 6 | 3 / 77 |
| Fase 8 | 1 / 24 |
| Reconcile (apply anterior) | 0 MISMATCH |
| Equipamentos com múltiplos Work Packages | 15 (ex.: "Bomba SUMP" → CAL012, CIV012, CIV014, CIV015) |
| Equipamentos sem nenhum Work Package | 17 (todos sem `work_package_codes` na origem — confirmado, não é perda) |
| `equipment.area_id` / `discipline_id` / `responsible_user_id` nulos | 0 / 0 / 0 |
| Fornecedores vinculados ao C2 | 0 (esperado — Connect Boards não migrado) |

Reconfirmado via `backend/scripts/audit_c2_db.py` (script novo, somente
leitura) ao final da auditoria: os três números acima (41/164/71) **não
mudaram**.

---

## 1. Equipment

Amostra de 1 equipamento por fase (dados reais, IDs em
`docs/validation/audit_db_result.json`):

| Fase | Equipamento | WP links | Negotiation | Legal | Contract | PR | PO |
|---|---|---|---|---|---|---|---|
| 0 | Analisador de gás da Caldeira | 0 | — | — | — | — | — |
| 4 | Conjunto Turbo-Gerador | 0 | ✔ | ✔ | — | — | — |
| 6 | Equipamentos da Biomassa (...) | 6 | ✔ | ✔ | ✔ | — | — |
| 8 | Caldeira de Biomassa | 10 | ✔ | ✔ | ✔ | ✔ (kind=NULL) | ✔ |

Todos os campos pedidos (nome, unidade, contexto, área, disciplina,
responsável, origem, startup, criticidade, CAPEX, Work Packages, etapa,
`componentsCount`, `createdAt`/`updatedAt`) existem no modelo, são retornados
pela API (`EquipmentOut`) e são exibidos no resumo do detalhe
(`pages/equipamentos/[id].vue:102-111`). `EquipmentUpdateIn` representa o
valor atual corretamente ao abrir Editar (formulário populado a partir do
objeto `Equipment` recebido).

**GAP-001 — BUG — P1 — bloqueia parcialmente a confiança na resposta da
edição de Work Packages.**
Ao fazer `PATCH /equipments/{id}` alterando `workPackageIds`, a resposta
imediata do próprio PATCH pode devolver a lista **antiga** de Work Packages
(pré-edição), mesmo com a gravação correta no banco. Causa raiz: a sessão do
SQLAlchemy tem `expire_on_commit=False`
(`app/core/database.py:55`); `update_equipment` já havia carregado
`equipment.work_package_links` via `selectinload` **antes** de sincronizar os
vínculos; a sincronização (`_sync_work_packages`,
`app/modules/equipments/service.py:167-181`) insere/apaga linhas de
`EquipmentWorkPackage` diretamente por `session.add`/`session.delete`, sem
atualizar a coleção Python já carregada no objeto `equipment`; a releitura
final (`get_equipment_out(session, equipment.id)`) reaproveita o mesmo objeto
do identity map da sessão, que o SQLAlchemy não recarrega automaticamente
para uma relação já populada. **Confirmado empiricamente**: o teste novo
`test_equipment_update_adds_and_removes_and_replaces_work_packages`
(`backend/tests/integration/test_equipment_routes.py`) falhou exatamente
nesse ponto ao rodar contra um banco de teste real.
Impacto real hoje é **contido**: a única tela que edita equipamento
(`pages/equipamentos/[id].vue`) ignora o corpo do PATCH e sempre recarrega
via `GET` (`equipmentSaved` → `loadEquipment()`), então o usuário não vê o
dado errado na prática — mas qualquer novo consumidor da API (relatório,
integração, tela futura que confie no retorno do PATCH) vai receber dado
desatualizado. Não afeta o banco, não afeta GETs subsequentes em uma sessão
nova.
Recomendação técnica: `await session.refresh(equipment,
attribute_names=["work_package_links"])` (ou `populate_existing=True` na
releitura) antes do `get_equipment_out` final em `update_equipment`.

---

## 2. Responsáveis

| Nome | Ativo | Vínculo Unit LEM | Equipamentos apontando pra ele |
|---|---|---|---|
| Ediel | ✔ | ✔ | 21 |
| Uilson | ✔ | ✔ | 9 |
| Ana Carolina | ✔ | ✔ | 8 |
| Samuel | ✔ | ✔ | 3 |

- Aparecem no seletor de responsável (`GET /responsibles?unit_id=...`) — **OK**.
- `responsible_user_id` de cada um dos 41 equipamentos aponta para o `User`
  correto (soma 21+9+8+3 = 41) — **OK**.
- Filtro por responsável em `/equipamentos` é server-side, real
  (`_apply_filters`, `app/modules/equipments/service.py:179-180`) — **OK**.
- Edição de responsável: `EquipmentUpdateIn.responsible_user_id`, validado
  contra unidade do contexto — **OK**.
- **GAP-011 (ver seção 12)**: filtro por responsável nas *filas*
  operacionais (Engenharia/Jurídico/Suprimentos) existe no backend
  (`QueueFilters.responsible_user_id`) mas **não tem controle de UI** em
  nenhuma das três telas — usuário não consegue filtrar a fila por
  responsável hoje, só a listagem geral de Equipamentos.
- Regra "RESPONSÁVEL ≠ PERMISSÃO" confirmada no código: nenhuma rota checa
  `responsible_user_id == actor.id` para autorizar edição; a autorização é
  só por `Role`/`Permission` — **OK**, consistente com o que foi pedido.

---

## 3. Work Packages

Cobertura ampla, resultado quase todo **OK** — única mancha é o GAP-001 (seção 1).

| Cenário | Status | Evidência |
|---|---|---|
| Leitura de 0 Work Packages | OK | 17 equipamentos reais do C2, `workPackages: []`, resumo mostra "—" |
| Leitura de 1 | OK | equipamentos com `wp_link_count == 1` |
| Leitura de vários | OK | 15 equipamentos com 2+ (ex. "Bomba SUMP": CAL012, CIV012, CIV014, CIV015) |
| Resumo mostra todos | OK | `pages/equipamentos/[id].vue` — chips por `code` |
| Editar mostra todos selecionados | OK | `EquipmentForm.vue` carrega de `equipment.workPackages.map(id)`, nunca de `workPackage` singular |
| Criação com múltiplos | OK | teste `test_equipment_create_with_multiple_work_packages` passou |
| Adição/remoção de vínculo | **Ver GAP-001** | lógica de sync correta no banco; resposta imediata do PATCH pode estar desatualizada |
| Lista vazia válida | OK | `test_equipment_create_with_zero_work_packages` / `..._empty_list_removes_all...` |
| PATCH sem `workPackageIds` preserva vínculos | **Validado por leitura de código, não por execução nesta sessão** — ver nota abaixo | `work_package_ids_provided = "work_package_ids" in changes`; se ausente, `_sync_work_packages` nunca é chamada |
| Validação de ProjectContext | OK | `_validate_work_packages` rejeita WP de outro contexto (teste passou) |
| WorkPackage inativo | OK | `test_equipment_create_rejects_inactive_work_package` passou |
| WorkPackage inexistente | OK | `test_equipment_create_rejects_unknown_work_package` passou |
| Duplicidade de ID | OK | rejeitado no schema (`work_package_ids_no_duplicates`), teste passou |
| Auditoria da alteração | OK (por design) | `AuditLog.previousData/newData["work_package_ids"]`, listas ordenadas deterministicamente |

**Nota sobre execução de testes nesta etapa**: o banco de teste dedicado
(Neon, banco separado `neondb_test`) responde de forma extremamente lenta
neste ambiente (~2 a 3 minutos por teste de integração via rede), o que
tornou inviável reexecutar a suíte inteira dentro desta sessão. A bateria
completa de criação (`0/1/N`, duplicado, inexistente, inativo, contexto
errado) **foi executada e passou**. O teste que exercita
adicionar+remover+substituir vínculos **falhou** e revelou o GAP-001. O teste
que verifica "PATCH sem `workPackageIds` preserva vínculos" não chegou a
rodar nesta sessão (a suíte para no primeiro erro); a leitura do código
mostra que ele deveria passar (a sincronização só é chamada quando a chave
está presente no payload), mas isso continua sem confirmação empírica nesta
etapa — reclassificado como **REGRA VALIDADA POR CÓDIGO, PENDENTE DE
CONFIRMAÇÃO POR TESTE**.

---

## 4. Componentes / Subitens

164 componentes reais auditados por amostragem + schema completo.

| Campo | Banco | API | Frontend (listagem) | Frontend (form) |
|---|---|---|---|---|
| Nome | OK | OK | OK | OK |
| TAG | OK | OK | OK | OK |
| Setor | OK | OK | OK | OK |
| Lead time fabricação | OK | OK | OK | OK |
| Dias antes do startup | OK | OK | OK | OK |
| Data entrega contratual | OK | OK | OK | OK |
| Frete (dias) | OK | OK | OK | OK |
| **Startup próprio do componente** | OK | OK | **AUSENTE** | **AUSENTE** |

**GAP-009 — INCOMPLETO — P1.**
`EquipmentComponent.startup_at` existe no modelo
(`app/models/equipment.py:218`), é aceito em `ComponentCreateIn`/
`ComponentUpdateIn` e devolvido em `ComponentOut.startup_at`
(`app/modules/equipments/schemas.py`). **Confirmado nos dados reais**: pelo
menos um componente do C2 tem `startup_at` divergente do
`equipment.startup_at` do seu equipamento-pai (ex.: componente em
2027-06-05, equipamento-pai em 2027-10-27) — exatamente o comportamento
documentado como esperado ("Data limite de entrega em obra" depende do
startup do subitem, não do equipamento). Porém:
- a tabela de componentes no detalhe do equipamento
  (`pages/equipamentos/[id].vue:167`) não tem coluna para esse campo;
- `ComponentForm.vue` (criar/editar) não tem nenhum input para ele.
Resultado: o dado existe e é correto no banco/API, mas é **invisível e
não-editável** no Hub hoje. Qualquer novo componente cadastrado
manualmente pelo Hub (pós-cutover) não poderá ter esse startup próprio
definido pela UI.

---

## 5. Negociação / 6. Jurídico / 7. Contrato / 8. Suprimentos

Testado com as 4 amostras (Fase 0/4/6/8). `ProcessSummary.vue` (resumo
somente-leitura) e `EquipmentStageForm.vue` (edição da etapa atual) cobrem
**100% dos campos** do domínio (`Negotiation`, `LegalProcess`, `Contract`,
`PurchaseRequest` incl. `kind`, `PurchaseOrder` incl. `amount`) — **OK**
estruturalmente.

Comportamento quando não existe o registro (ex. Fase 0 sem `Negotiation`):
API devolve objeto com `id: null` e campos `null`/`false`
(`NegotiationOut`/etc.), frontend mostra "—"/checkbox desmarcado — **OK**.

**Pendência conhecida, conforme instruído — NÃO CORRIGIR:**
"Caldeira de Biomassa" (Fase 8) tem `PurchaseRequest` real
(`request_number=2643239`, `requested_at=2026-06-26`) com **`kind = NULL`**
(SC/OCI não identificável na origem). O warning
`PURCHASE_REQUEST_KIND_UNRESOLVED` do apply continua preservado. O campo
`kind` é editável via `EquipmentStageForm` (select "Não informado"/SC/OCI) —
classificado como **DADO NÃO EXISTENTE NA ORIGEM**, decisão humana
pendente, não é bug.

**GAP-008 — BUG/INCOMPLETO — P0 — bloqueia corrigir exatamente essa pendência pela UI.**
`EquipmentStageForm.vue` só renderiza o formulário do recurso que corresponde
à **etapa atual** do equipamento (`resourceForStage(stage)`,
`utils/workflow.ts:32-34`; mapa fixo etapa→recurso). Quando `stage === 8`
(Concluído) — caso exato da Caldeira de Biomassa — o componente renderiza
apenas um texto estático "Processo concluído. Os dados permanecem
disponíveis para consulta..." (`EquipmentStageForm.vue:94-96`), sem nenhum
formulário editável. O mesmo vale para `stage === 0`. **O backend não tem
essa restrição** — `app/modules/processes/service.py` não checa
`current_stage` em nenhum PATCH de processo, só a permissão
`process:write`. Ou seja: hoje, a única forma de corrigir o `kind` da
Caldeira de Biomassa (ou qualquer outro dado de processo de um equipamento
já concluído) é chamar a API diretamente — **não é possível pela interface**.
Isso afeta todo equipamento que chegue à etapa 8, o que vai se tornar cada
vez mais comum. Resposta ao critério da auditoria: **NÃO**, o usuário não
consegue resolver essa pendência real só pelo Hub hoje.

---

## 9. Workflow 0 → 8

Os 4 equipamentos-amostra (fases 0/4/6/8) aparecem corretamente na API e no
frontend com o `current_stage` correto — **OK**. `by_stage` do banco bate
exatamente com a baseline (31/6/3/1).

Regras de transição hoje implementadas (`app/modules/workflow/stages.py`,
`service.py`):

| Regra | Status | Evidência |
|---|---|---|
| Fluxo normal (avançar +1) | OK | `_classify`, só aceita `target == current+1` |
| Requisitos por etapa (0→1 ... 7→8) | OK | `TRANSITION_REQUIREMENTS`; 7→8 **revalida todos os requisitos de 0 a 7** |
| **Shortcut 2→4** | **NÃO IMPLEMENTADO** | qualquer `target != current+1` (exceto reabertura) gera erro "Não é possível pular etapas" |
| **Reabertura de negociação** | Implementado, mas **genérico** | sempre volta para etapa 1, sem regra fina sobre o que acontece com dados de etapas já preenchidas; exige `WORKFLOW_REOPEN` (só ADMIN) + motivo obrigatório |
| **Bypass de suprimentos** | **NÃO IMPLEMENTADO** | nenhuma menção no código |
| **Mais de uma forma de concluir (7→8)** | **NÃO IMPLEMENTADO** | só existe o avanço normal revalidando tudo |

**GAP-004 — SUBSTITUÍDO NA ETAPA 7.1.** Shortcut 2→4 do Monday não existe
no Hub — e a decisão de negócio confirmada foi que ele nunca vai existir
como salto automático. Em vez disso, casos de fornecedor pré-definido
usam dispensa (`RequirementWaiver`) dos grupos de negociação, com avanço
manual fase por fase preservado. Ver
[`etapa-07-1-requirement-waivers.md`](etapa-07-1-requirement-waivers.md).

**GAP-005 — SUBSTITUÍDO NA ETAPA 7.1.** Bypass de suprimentos do Monday
não existe no Hub — substituído por dispensa dos grupos `CONTRACT`/
`PURCHASE_REQUEST` para casos de importação, sempre com avanço manual.
Ver [`etapa-07-1-requirement-waivers.md`](etapa-07-1-requirement-waivers.md).

**GAP-006 — REGRA AINDA NÃO VALIDADA — P2.**
Reabertura sempre volta para etapa 1 e não distingue "reabrir negociação"
(efeito local) de um reset mais amplo. Precisa confirmar com negócio se isso
é suficiente.

**Migração e histórico**: confirmado (código + banco) que `current_stage`
dos 10 equipamentos importados em etapa >0 foi setado diretamente pelo
`apply.py`, **sem** criar `WorkflowTransition` fictício — isso é
**intencional e documentado no próprio código**
(`monday_import/apply.py:1-7`) e está alinhado à instrução explícita de não
fabricar histórico de workflow para a migração. `workflow_transitions_c2 =
0` confirmado no banco. Ver GAP-002 (seção 18) para o efeito colateral na
aba Histórico.

---

## 10. Fórmulas e campos derivados

**Não implementadas, conforme instruído nesta etapa — apenas auditoria.**

**GAP-013 — RESOLVIDO NA ETAPA 6B (FUN-001).**
As fórmulas de prazo (4 de componente + agregados MAX/MIN de equipamento)
foram implementadas em `app/domain/equipment_calculations.py` (nova
implementação única, também usada pelo importador via reexportação em
`monday_import/calculations.py`), expostas em
`EquipmentOut.calculated`/`ComponentOut.calculated`, calculadas on-the-fly
a cada leitura (nunca persistidas), e confirmadas com 0 MISMATCH contra os
164 componentes/41 equipamentos reais do C2. Ver
[`etapa-06b-formulas-layout.md`](etapa-06b-formulas-layout.md) para
arquitetura, contrato da API e evidência completa. Texto original abaixo
preservado como histórico da auditoria.

<details>
<summary>Texto original da auditoria (histórico, pré-Etapa 6B)</summary>

As 12 fórmulas/agregações confirmadas nos XLSX (4 de componente + várias de
equipamento, incluindo `E.Lead Time`, `E.Dias Antes Startup`, `Frete` (MAX),
`F.Limite Entrega Obra`/`F.Data Limite contrato-OC`/`F.Data Limite
Negociação` (MIN)) **não existem em nenhum lugar da aplicação viva**.
`backend/app/modules/monday_import/calculations.py` implementa exatamente
essas fórmulas, mas **só é usado dentro do importador** (para validar a
migração/reconciliação 164/164 e 41/41) — confirmado por grep: zero
referências a `lead_time_days`/`freight_days`/`pre_start_days`/
`negotiation_deadline`/`delivery_deadline` em `app/modules/equipments`,
`app/modules/processes` ou `app/modules/dashboard`. Os campos-base
(`lead_time_days`, `pre_start_days`, `freight_days`, `contract_delivery_at`)
existem e são editáveis "crus", mas nenhum prazo derivado (data limite de
entrega em obra, disponibilidade para coleta, data limite para contrato/OC,
data limite de negociação, prazo de negociação) é calculado ou exibido em
lugar nenhum do Hub hoje.

</details>

**GAP-014 — REGRA CONFIRMADA / IMPLEMENTADA NA ETAPA 6C.** Fórmula oficial
recebida (precedência: A.Status especial > `negotiatedAt` > deadline ausente
> tabela de dias) implementada em `calculate_negotiation_status`, exposta em
`EquipmentOut.calculated.negotiationStatus`. 23 testes unitários cobrindo a
tabela completa e a precedência; **41/41 MATCH** contra o Status Negociação
real observado no Monday para os equipamentos do C2. Os estados especiais
(CANCELADO/Em Saneamento/Não se Aplica) ficam suportados na função de
domínio mas sem modelagem no Hub ainda — nenhum equipamento real os usa
hoje. Ver [`etapa-06c-dates-negotiation-status.md`](etapa-06c-dates-negotiation-status.md).

Registrado para **FUN-001** (backlog de fórmulas), conforme pedido.

---

## 11. Listagem de equipamentos

`/equipamentos` — total C2 = 41 confirmado; busca, unidade, contexto (via
seletor de unidade → contexto), etapa, disciplina, responsável, paginação e
ordenação (`sortBy`) — todos **server-side reais**, sem hardcode de nome
(`app/modules/equipments/service.py:_apply_filters`,
`pages/equipamentos/index.vue`). Exportação percorre as páginas reais via
API (`exportAll`, teto de segurança 20 páginas). Permissão por unidade
respeitada (`allowed_unit_ids`/`restrict_to_units`). — **OK** no geral.

**GAP-010 — RESOLVIDO NA ETAPA 6D.** `GET /equipments` ganhou `area_id`
(`Equipment.area_id == area_id`) e `work_package_id` (EXISTS sobre a
relação N:N `equipment_work_package` — nunca o `workPackage` singular
legado; confirmado sem duplicar linha nem contagem, inclusive para
equipamentos com vários Work Packages). Filtros expostos em
`pages/equipamentos/index.vue` (Área respeita Unidade; Work Package
respeita os ProjectContext da Unidade). `EquipmentTable.vue` ganhou coluna
"Pacotes de trabalho" (chips compactos, máx. 3 + "+N"); a exportação ganhou
a coluna "Pacotes de Trabalho" e já respeita os novos filtros (usa
`currentQuery`, compartilhada com a listagem).

---

## 12. Engenharia

**GAP-011 — NÃO IMPLEMENTADO — P0 — bloqueia um fluxo operacional nomeado explicitamente pelo negócio.**
O cenário de referência dado ("Engenharia MetalMec": filtro
`Disciplina = Metal Mec.` + agrupamento por Responsável) **não é
reproduzível hoje**, nem pela UI nem pela API:
- `GET /queues/engineering` (`app/modules/queues/router.py:_queue_filters`)
  aceita `unit_id, equipment_id, stage, search, responsible_user_id, page,
  pageSize` — **não existe parâmetro de filtro por disciplina** em nenhuma
  das 3 filas.
- A tela `pages/engenharia.vue` não tem **nenhum** controle de filtro por
  Disciplina nem por Responsável — só busca textual e os filtros globais de
  Unidade/Equipamento (via `ModuleFilters`). A coluna "Disciplina" e a
  coluna "Responsável" existem só como exibição.
- Não existe nenhum endpoint ou UI de agrupamento/agregação (ex.: contagem
  por responsável) em nenhuma fila.
Resposta ao critério da auditoria: **NÃO**, "Engenharia MetalMec" não pode
ser montada só pelo Hub hoje — o usuário precisaria continuar usando o
Monday (ou um filtro manual fora do sistema) para esse recorte específico.
Confirma-se também que Ana Carolina/Uilson são `User`s reais com
`responsible_user_id`, não grupos persistidos — **OK**, consistente com a
regra confirmada; o problema é puramente a ausência do filtro/agrupamento.

Demais itens da tela (colunas, Work Packages múltiplos exibidos
corretamente como "Pacotes", componentes via link de detalhe,
comportamento ao trocar responsável) — **OK**.

---

## 13. Jurídico — view operacional

Critério de entrada (etapas 3-5), colunas (chamado, abertura, minuta
elaborada/aprovada, contrato), filtros (busca + Unidade/Equipamento
globais, server-side), link para detalhe — **OK** estruturalmente.

**GAP-012a — RESOLVIDO NA ETAPA 6D.** `pages/juridico.vue` ganhou as
colunas "Responsável" (`LegalRow.responsibleUser`) e "Entrega contratual"
(`LegalRow.deliveryAt`) — ambas já vinham prontas da API, só não eram
exibidas. Nenhuma regra nova.

Filtro por Disciplina não se aplica aqui (Jurídico não é segmentado por
disciplina) — **OK**, não é gap.

---

## 14. Suprimentos — view operacional

Critério de entrada (etapas 6-7), colunas (tipo SC/OCI, número/data SC-OCI,
número/data OC, valor, fornecedor principal) — **OK**, campos batendo 1:1
com `ProcurementRow`. Botão exclusivo "Administração" (fornecedores) — **OK**.

**GAP-012b — RESOLVIDO NA ETAPA 6D.** `pages/suprimentos.vue` ganhou a
coluna "Responsável" (`ProcurementRow.responsibleUser`). Critérios da fila
inalterados.

Nenhum campo do Monday relativo a suprimentos ficou de fora do schema —
todos os campos mapeados como MIGRAR nessa área existem.

---

## 15. Dashboard

Todos os totais exibidos vêm prontos do backend (`/dashboard/summary`);
nenhum somatório de negócio é refeito no cliente — só reagregações de
apresentação (donut de 3 baldes a partir de `workflow[]`, percentual de
negociação a partir de `open`/`completed` já oficiais). Comparação com
consulta direta ao banco: `totals.equipments = 41`,
`totals.components = 164` batem exatamente com a baseline. Filtro por
Unidade/Equipamento — **OK**, server-side.

**GAP-015 — REGRA CONFIRMADA / IMPLEMENTADA NA ETAPA 6C.1.** Fórmula oficial
de "Status Necessidade da Obra" recebida e codificada em
`calculate_work_need_status` (mesmo domínio das etapas 6B/6C), reutilizada
tanto pelo detalhe do equipamento (`EquipmentOut.calculated.workNeedStatus`)
quanto pelo card "Situação de prazos" do Dashboard
(`DeadlinesSummaryOut`) — nenhum threshold duplicado entre as duas telas.
`deadlines.available` passa a ser `true` com a distribuição real do
recorte; **41/41 MATCH exato** contra o "Status Necessidade da Obra" real
observado no Monday para os 41 equipamentos do C2. Ver
[`etapa-06c1-work-need-dashboard.md`](etapa-06c1-work-need-dashboard.md).

**Confirmado, conforme instruído**: não existe nenhuma lógica de "163 vs
164" em lugar nenhum do dashboard/domínio — a divergência conhecida
Monday=163 aquisições vs Hub=164 componentes **não foi mascarada nem
forçada**; o Hub simplesmente conta `EquipmentComponent` real (164), sem
tentar reproduzir o número do Monday.

---

## 16. Filas e outras views

Cobertas nas seções 12/13/14 (Engenharia/Jurídico/Suprimentos) — são as
únicas 3 filas operacionais existentes hoje, todas usando o mesmo padrão de
componente (`QueueShell`) e o mesmo composable (`useQueue`). Nenhuma view
nova foi criada nesta auditoria, conforme instruído.

---

## 17. Permissões

Matriz atual (idêntica nos dois lados, backend fonte de verdade):

| Permission | VIEWER | ANALYST | ADMIN |
|---|:---:|:---:|:---:|
| equipments:read / catalogs:read / workflow:read / suppliers:read | ✔ | ✔ | ✔ |
| equipments:write / process:write / workflow:transition / suppliers:write | ✗ | ✔ | ✔ |
| users:manage / audit:read / catalogs:manage / workflow:reopen | ✗ | ✗ | ✔ |

VIEWER: leitura/filtros/detalhe, sem escrita — **OK** (backend `_READ` só,
frontend some com botões de escrita). ANALYST: criação/edição/processo/
transição/fornecedores — **OK**. ADMIN: tudo + catálogos/usuários/
reabertura/auditoria — **OK**.

**GAP-016 — RESOLVIDO NA ETAPA 6D.** `stores/auth.ts` não replica mais a
matriz — `can(permission)` agora delega a `hasPermission(user, permission)`
(`utils/permissions.ts`), que só olha `user.permissions` (o array que
`/auth/me` já devolve). Zero matriz local; `permissions` ausente nega tudo
em vez de assumir acesso. 5 testes novos (`tests/permissions.test.ts`)
comprovam VIEWER/ANALYST/ADMIN continuam exatamente com o mesmo
comportamento — construindo o usuário só a partir do array de permissões,
nunca do papel.

**GAP-018 — INCOMPLETO — P3.** Itens de menu (exceto Auditoria) não são
filtrados por permissão — aparecem para qualquer usuário autenticado; o
bloqueio real (`allowed`/"Sem permissão") só acontece dentro da página.
Não é falha de segurança (a API sempre revalida), só inconsistência de UX.

**GAP-017 — NÃO IMPLEMENTADO — P2 (registrar para matriz fina futura).**
Confirmado: nenhuma permissão por departamento (Engenharia/Jurídico/
Suprimentos/Gestão) existe em nenhum dos dois lados — as 3 filas usam
exatamente a mesma permissão `equipments:read`.

Também notado: `workflow:transition` e `workflow:reopen` **nunca são
consultados via `auth.can()` no frontend** — os botões de avançar/reabrir
dependem só do `canExecute` que o backend já calcula em
`available-transitions`. Isso é uma escolha de design razoável (fonte única
de verdade no backend), não um gap — registrado só como observação.

---

## 18. Histórico e Auditoria

`WorkflowTransition` (só transições reais 0-8, geradas pelo endpoint de
transição) é conceitualmente diferente de `AuditLog` (qualquer alteração de
dado) — confirmado que o backend **não confunde os dois**: nenhuma
transição fictícia foi fabricada pela migração (ver seção 9).

O endpoint `GET /equipments/{id}/history` (usado pela aba "Histórico" do
detalhe) já mescla `WorkflowTransition` + `AuditLog` filtrado por
`entityId == equipment_id` OU `metadata.equipmentId == equipment_id` — e
esse segundo caminho **é usado de propósito** pelas edições normais de
processo (`app/modules/processes/service.py:115`: `metadata={"equipmentId":
equipment_id}`).

**GAP-002 — RESOLVIDO NA ETAPA 6D.** Nem migração reexecutada nem dado
histórico reescrito — o histórico passou a resolver por relacionamento:
`app/shared/audit.py:equipment_audit_conditions` monta, além dos dois
critérios já existentes (`entityId == equipment_id` /
`metadata.equipmentId == equipment_id`), condições para os
`EquipmentComponent` e sub-entidades 1:1 (`Negotiation`/`LegalProcess`/
`Contract`/`PurchaseRequest`/`PurchaseOrder`) reais daquele equipamento
(FK, não suposição). Confirmado rodando o endpoint real para "Caldeira de
Biomassa": a timeline foi de **1 item** (só a criação do `Equipment`) para
**30 itens** — todos os `AuditLog` de migração dos seus componentes e
sub-processos.

**GAP-003 — RESOLVIDO NA ETAPA 6D.** `_AUDIT_TITLES["migration.import"] =
"Importado do Monday"` — só tradução de apresentação, `action` continua
`"migration.import"` no banco.

**GAP-019 — RESOLVIDO NA ETAPA 6D.** `GET /auditoria` ganhou
`equipment_id` (mesma `equipment_audit_conditions` do GAP-002 — nunca uma
segunda lógica), `user_id`, `date_from` e `date_to`. `AuditViewer.vue`
ganhou os 4 filtros correspondentes (Equipamento/Usuário como `<select>`
com IDs reais, período como `<input type="date">`) — sem busca avançada,
sem query builder. Confirmado: filtrar Auditoria por "Caldeira de Biomassa"
devolve os mesmos 30 itens que a aba Histórico do próprio equipamento.

**GAP-020 — REGRA AINDA NÃO VALIDADA — P3.** Auditoria e Histórico
continuam sendo duas telas/fontes totalmente separadas, sem rótulo
específico para registros de migração. Confirmar se esse design é aceitável
a longo prazo ou se deveria haver uma visão unificada.

---

## 19. Fornecedores

Cadastro mestre (`Supplier`), vínculo N:N (`EquipmentSupplier`), fornecedor
principal (`is_primary`, exclusividade **garantida no banco** por índice
único parcial), edição, desativação (nunca exclusão física, `ondelete=
RESTRICT` no vínculo) — **CRUD completo e OK** nos dois lados (2 telas:
`/fornecedores` para cadastro mestre, aba "Fornecedores" no detalhe do
equipamento para o vínculo N:N). Permissões `suppliers:read`/
`suppliers:write` aplicadas de forma consistente.

Confirmado, conforme instruído: **0 fornecedores vinculados** aos 41
equipamentos do C2 — **não é erro de migração**, é esperado, porque no
Monday esse campo usa Connect Boards, que os XLSX canônicos não carregam.

Pequenos detalhes sem gap formal (não bloqueiam nada): `EquipmentSuppliers.vue`
não pede confirmação antes de desvincular (diferente de `SupplierAdmin.vue`,
que pede `confirm()` antes de desativar); não há edição de `role` de um
vínculo já criado (só criar/marcar principal/remover).

---

## 20. Funcionalidades ausentes (apenas registro, não implementar)

Confirmado por busca no código inteiro — nenhuma das funcionalidades abaixo
tem qualquer implementação, apenas vestígios pontuais onde fazia sentido:

| Item | Situação encontrada |
|---|---|
| Anexos | Não migrados por decisão explícita do importador (`ATTACHMENT_MIGRATION_PENDING`, `monday_import/plan.py:844-845`); nenhuma tela de anexos existe |
| Comentários | Ausente, nenhum vestígio |
| Notificações | **GAP-021** — botão "Notificações" existe no cabeçalho (`AppHeader.vue`) mas é puramente decorativo (sem handler, sem contador) |
| E-mail / FUP | Ausente |
| Kickoff | Campo mapeado do Monday (`kickoff_at`) fica só no staging bruto; nunca vira campo de domínio — classificado desde o mapeamento original como `PENDENTE` |
| Kanban | Ausente |
| Saved views | Ausente |
| Integrações ERP | Ausente |
| Escalonamento para outros boards | Ausente |
| Fórmulas | Ver seção 10 (GAP-013) |
| Regras especiais de workflow | Ver seção 9 (GAP-004/005/006) |
| Permissões departamentais | Ver seção 17 (GAP-017) |

**GAP-021 — NÃO IMPLEMENTADO — P3 — apenas registrar.**

---

## Conclusão

A migração do C2 e a correção de Work Packages N:N estão **estruturalmente
sólidas**: 0 MISMATCH, 71/71 vínculos corretos, CRUD de Work Package
completo e coberto por teste automatizado (exceto a ressalva pontual do
GAP-001), dados de Equipment/Componente/Processo íntegros e rastreáveis até
a origem. Os gaps encontrados nesta etapa são majoritariamente de
**completude de interface** (dado existe e está correto no backend, mas
falta tela/filtro/campo) e de **regras de negócio do Monday ainda não
portadas** (shortcuts de workflow, fórmulas) — não há indício de corrupção,
duplicação ou perda de dado migrado.

Os dois gaps mais sérios para um corte real eram GAP-008 (processo de
equipamento concluído não editável pela UI) e GAP-011 (Engenharia por
Disciplina + Responsável impossível de montar) — **ambos resolvidos na
Etapa 6A**, junto com GAP-001 e GAP-009. Ver
[`etapa-06a-operational-fixes.md`](etapa-06a-operational-fixes.md).

---

## Tabela consolidada

| ID | Área | Gap | Status | Prioridade | Bloqueia substituição do Monday? |
|---|---|---|---|---|---|
| GAP-001 | Work Packages / API | PATCH de equipamento pode devolver `workPackages` desatualizado na resposta imediata (banco correto) | **RESOLVIDO NA ETAPA 6A** | P1 | Não (impacto contido hoje) |
| GAP-002 | Histórico/Auditoria | Sub-processos criados pela migração não aparecem na aba Histórico do equipamento | **RESOLVIDO NA ETAPA 6D** | ~~P2~~ | Não |
| GAP-003 | Histórico/Auditoria | Título cru "migration.import" na timeline | **RESOLVIDO NA ETAPA 6D** | ~~P3~~ | Não |
| GAP-004 | Workflow | Shortcut 2→4 não implementado | **SUBSTITUÍDO NA ETAPA 7.1** — negócio decidiu não ter salto automático nenhum; casos de fornecedor pré-definido usam dispensa (`RequirementWaiver`) do grupo `NEGOTIATION_EQUALIZATION`/`COMMERCIAL_NEGOTIATION`, com motivo `FIXED_SUPPLIER` (avanço manual, fase por fase) | ~~P1/P2~~ | Não |
| GAP-005 | Workflow | Bypass de suprimentos não implementado | **SUBSTITUÍDO NA ETAPA 7.1** — casos de importação usam dispensa dos grupos `CONTRACT`/`PURCHASE_REQUEST` (motivo `IMPORTATION`), chegando à fase 7 sem contrato/SC-OCI obrigatórios, sempre manual | ~~P2~~ | Não |
| GAP-006 | Workflow | Reabertura genérica (sempre → etapa 1) | **RESOLVIDO NA ETAPA 7** — `ReopenRequest`: escolhe qualquer fase anterior, exige aprovação por permissão superior, equipamento só muda de fase após aprovação | ~~P2~~ | Não |
| GAP-007 | Workflow | Só uma forma de concluir 7→8 | **RESOLVIDO NA ETAPA 7** — regra explícita: fornecedor + ao menos 1 OC + Valor Total do Projeto, sem reexecutar requisitos de fases anteriores | ~~P3~~ | Não |
| GAP-008 | Processo / UI | Dado de processo de equipamento concluído (etapa 8) não é editável pela UI | **RESOLVIDO NA ETAPA 6A** | ~~P0~~ | ~~Sim~~ |
| GAP-009 | Componentes | Startup do componente ausente no frontend (listagem e formulário) | **RESOLVIDO NA ETAPA 6A** | P1 | Parcial |
| GAP-010 | Listagem | Sem filtro de Área/Work Package e sem coluna de WP na listagem/exportação | **RESOLVIDO NA ETAPA 6D** | ~~P2~~ | Não |
| GAP-011 | Engenharia | Filtro por Disciplina + agrupamento por Responsável impossível hoje | **RESOLVIDO NA ETAPA 6A** | ~~P0~~ | ~~Sim~~ |
| GAP-012a/b | Jurídico/Suprimentos | Coluna Responsável não exibida nas filas | **RESOLVIDO NA ETAPA 6D** | ~~P2~~ | Não |
| GAP-013 | Fórmulas | Nenhuma fórmula/derivado implementado na aplicação viva | **RESOLVIDO NA ETAPA 6B** | ~~P1~~ | ~~Parcial~~ |
| GAP-014 | Fórmulas | Status Negociação sem threshold (correto, registrar) | **REGRA CONFIRMADA / IMPLEMENTADA — ETAPA 6C** | ~~P2~~ | Não |
| GAP-015 | Dashboard | Indicador de prazos hardcoded como indisponível | **REGRA CONFIRMADA / IMPLEMENTADA — ETAPA 6C.1** | ~~P2~~ | Não |
| GAP-016 | Permissões | Frontend usa matriz local hardcoded em vez do array do backend | **RESOLVIDO NA ETAPA 6D** | ~~P2~~ | Não |
| GAP-017 | Permissões | Sem permissão departamental (esperado, registrar) | NÃO IMPLEMENTADO | P2 | Não |
| GAP-018 | Permissões | Menu não filtra por permissão de leitura | INCOMPLETO | P3 | Não |
| GAP-019 | Auditoria | Tela de Auditoria sem filtro por equipamento/usuário/data | **RESOLVIDO NA ETAPA 6D** | ~~P2~~ | Não |
| GAP-020 | Auditoria | Auditoria e Histórico continuam separados, sem rótulo de migração | REGRA AINDA NÃO VALIDADA | P3 | Não |
| GAP-021 | Geral | Botão de notificações decorativo | NÃO IMPLEMENTADO | P3 | Não |
| UI-001 | Layout | Largura útil do módulo (1320px → 1680px) | **MELHORIA ESTRUTURAL CONCLUÍDA — ETAPA 6B** | — | Não (não era gap, era melhoria de UX) |

### Por prioridade

- **P0 (0, era 2)**: GAP-008 e GAP-011 resolvidos na Etapa 6A.
- **P1 (0, era 4)**: GAP-004 substituído na Etapa 7 (GAP-001/GAP-009 resolvidos na Etapa 6A; GAP-013 resolvido na Etapa 6B)
- **P2 (1, era 11)**: GAP-017 (GAP-005/GAP-006 resolvidos/substituídos na Etapa 7; GAP-014 resolvido na Etapa 6C; GAP-015 resolvido na Etapa 6C.1; GAP-002/GAP-010/GAP-012a/GAP-012b/GAP-016/GAP-019 resolvidos na Etapa 6D)
- **P3 (3, era 5)**: GAP-018, GAP-020, GAP-021 (GAP-003 resolvido na Etapa 6D; GAP-007 resolvido na Etapa 7)

---

## Próximas etapas propostas (só backlog — aguardando aprovação, nada implementado)

Ordem sugerida, baseada só nos gaps acima.

**Feito na Etapa 6A**: ~~GAP-008~~, ~~GAP-011~~, ~~GAP-001~~, ~~GAP-009~~ —
ver [`etapa-06a-operational-fixes.md`](etapa-06a-operational-fixes.md).

**Feito na Etapa 6B**: ~~GAP-013~~ (fórmulas de prazo) e ~~UI-001~~ (largura
do módulo) — ver [`etapa-06b-formulas-layout.md`](etapa-06b-formulas-layout.md).

**Feito na Etapa 6C**: ~~GAP-014~~ (Status Negociação) e o bug global de
datas DATE-ONLY — ver [`etapa-06c-dates-negotiation-status.md`](etapa-06c-dates-negotiation-status.md).

**Feito na Etapa 6C.1**: ~~GAP-015~~ (Status Necessidade da Obra + card
"Situação de prazos" do Dashboard) — ver
[`etapa-06c1-work-need-dashboard.md`](etapa-06c1-work-need-dashboard.md).

**Feito na Etapa 6D**: ~~GAP-002~~, ~~GAP-003~~, ~~GAP-010~~, ~~GAP-012a~~,
~~GAP-012b~~, ~~GAP-016~~, ~~GAP-019~~ (completude operacional e auditoria)
— ver
[`etapa-06d-operational-completeness.md`](etapa-06d-operational-completeness.md).

**Feito na Etapa 7**: ~~GAP-006~~ (reabertura com aprovação), ~~GAP-007~~
(regra explícita de conclusão 7→8) — mais contratos/SC-OCI/OC 1:N,
fornecedor único, Standby/Cancelado/Em Saneamento, comentários,
Kickoff/FUP e Kanban (não eram GAPs catalogados aqui, vieram direto da
especificação da etapa) — ver
[`etapa-07-operational-business-rules.md`](etapa-07-operational-business-rules.md).

**Feito na Etapa 7.1**: ~~GAP-004~~, ~~GAP-005~~ — o mecanismo de exceções
de fluxo rígidas (`FIXED_SUPPLIER`/`IMPORTATION`, Etapa 7B) foi substituído
por dispensa flexível por grupo de requisitos (`RequirementWaiver`, motivo
+ justificativa auditáveis, sem tabela rígida tipo→requisitos) — ver
[`etapa-07-1-requirement-waivers.md`](etapa-07-1-requirement-waivers.md).

Próximos, em ordem sugerida:

1. Demais P2/P3 (GAP-017, GAP-018, GAP-020, GAP-021) — dependem de decisão de negócio (permissão departamental) ou são baixo impacto (menu, notificações, rótulo de migração).
2. Hierarquia corporativa real (Microsoft/Automação) para `workflow:reopen_approve` e para os destinatários de Kickoff/FUP — pendência registrada na Etapa 7, não um GAP novo.
