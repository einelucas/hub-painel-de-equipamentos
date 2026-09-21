# Etapa 6A — Correções operacionais prioritárias pós-homologação C2

Data: 2026-09-21

Corrige 4 gaps da homologação funcional
(`docs/validation/c2-functional-validation.md`): **GAP-008**, **GAP-011**,
**GAP-001**, **GAP-009**. Nenhum outro gap foi tocado. A baseline do C2 foi
verificada intacta antes e depois de todas as mudanças (ver seção final).

## GAP-008 — Edição de processo independente da etapa atual

**Problema**: `EquipmentStageForm.vue` só editava o recurso da etapa atual;
em `stage=8` (Concluído) e `stage=0`, nada era editável — mesmo o backend já
permitindo PATCH de qualquer recurso de processo a qualquer momento.

**Solução aplicada**: `current_stage` continua 100% protegido — nenhuma
mudança tocou nisso. `EquipmentStageForm.vue` continua sendo o painel
"Etapa atual" (foco principal, inalterado). `ProcessSummary.vue` (seção
"Processo completo") deixou de ser somente-leitura: cada um dos 5 blocos
(Negociação, Jurídico, Contrato, SC/OCI, Ordem de Compra) agora tem seu
próprio botão "Editar" → formulário próprio → "Salvar"/"Cancelar",
independente da etapa em que o equipamento está. Cada bloco chama
`workflow.saveProcess(resource, payload)` — o mesmo endpoint
`PATCH /equipments/{id}/{resource}` que o backend já expunha sem guarda de
etapa. VIEWER (`editable=false`) não vê nenhum botão "Editar".

**Arquivos alterados**:
- `frontend/components/equipment/ProcessSummary.vue` (reescrito: visão +
  edição por bloco)
- `frontend/pages/equipamentos/[id].vue` (passa `:editable`, `:saving`,
  `@save` para `ProcessSummary`)
- `frontend/components/equipment/EquipmentStageForm.vue` (só o texto da
  etapa 8, apontando para o novo caminho de edição)
- `backend/tests/integration/test_workflow_routes.py` (testes novos —
  nenhuma mudança de código de produção no backend, porque já não havia
  guarda de etapa)

**Testes**:
- Backend: `test_process_editable_after_conclusion_without_changing_stage`
  (avança 0→8, edita os 5 recursos, confirma `current_stage` continua 8 e
  os dados novos aparecem em `/processes`) e
  `test_viewer_cannot_write_process_at_stage_8`.
- Frontend: `tests/WorkflowComponents.test.ts` → suite
  `ProcessSummary (GAP-008: edição independente da etapa atual)`, 4 testes
  (sem permissão não vê Editar; com permissão vê os 5; editar+salvar emite
  só o recurso certo; cancelar não emite nada).

**Status: RESOLVIDO NA ETAPA 6A.**

## GAP-011 — Engenharia por Disciplina + Responsável

**Problema**: `GET /queues/engineering` não tinha filtro por disciplina; a
tela de Engenharia não tinha controle de Disciplina nem de Responsável; não
havia agrupamento. O cenário "Engenharia MetalMec" (filtro
Disciplina=Metal Mec. + agrupamento por Responsável) era impossível de
montar só pelo Hub.

**Solução aplicada**:
- Backend: `QueueFilters` ganhou `discipline_id` (opcional). `_filtered`
  (`app/modules/queues/service.py`) aplica o filtro quando presente.
  **Só o endpoint `/queues/engineering`** expõe `discipline_id` como query
  param — uma dependency separada (`_engineering_queue_filters`) foi criada
  no router só para ele; `/queues/legal` e `/queues/procurement` continuam
  usando a dependency antiga, sem esse parâmetro (não é reutilização
  técnica indevida — é decisão deliberada, disciplina é requisito só da
  Engenharia).
- Frontend: `pages/engenharia.vue` ganhou dois `<select>` (Disciplina,
  Responsável) com IDs reais (carregados de `/disciplines` e
  `/responsibles`), um checkbox "Agrupar por responsável", e uma visão
  agrupada alternativa (tabela por grupo, com contagem). O agrupamento é
  puramente derivado de `row.responsibleUser` a cada carga — não persiste
  nada, não cria entidade "Ana Carolina"/"Uilson"; equipamento sem
  responsável cai em "Sem responsável", sempre por último. Como o
  agrupamento é recalculado a cada `load()`, trocar o responsável de um
  equipamento e recarregar a fila já move ele de grupo automaticamente.
- `composables/useQueue.ts` ganhou um `filters` reativo genérico (chaves
  snake_case) para permitir filtros extras por fila sem hardcode.
- `components/queue/QueueShell.vue` ganhou um slot `#filters` (aditivo, não
  quebra Jurídico/Suprimentos, que simplesmente não o usam).
- Lógica de agrupamento extraída para `frontend/utils/engineering.ts`
  (`groupByResponsible`), testável isoladamente sem montar a página inteira.

**Arquivos alterados**:
- `backend/app/modules/queues/service.py`
- `backend/app/modules/queues/router.py`
- `frontend/composables/useQueue.ts`
- `frontend/components/queue/QueueShell.vue`
- `frontend/pages/engenharia.vue`
- `frontend/utils/engineering.ts` (novo)
- `backend/tests/integration/test_dashboard_and_queues.py` (testes novos)
- `frontend/tests/engineering.test.ts` (novo)

**Testes**:
- Backend: `test_engineering_queue_filters_by_discipline_id`,
  `test_engineering_queue_filters_by_responsible_user_id`,
  `test_engineering_queue_combines_discipline_and_responsible_filters`,
  `test_legal_and_procurement_queues_do_not_accept_discipline_filter`
  (confirma que `discipline_id` não quebra nem filtra Jurídico/Suprimentos —
  simplesmente não é um parâmetro reconhecido lá).
- Frontend: `tests/engineering.test.ts`, 5 testes de `groupByResponsible`
  (agrupa por responsável real, ordena alfabeticamente, "Sem responsável"
  por último, reagrupa quando o responsável muda, lista vazia não gera
  grupo).
- Verificação direta adicional (sem HTTP, contra banco TEST):
  `backend/scripts/verify_gap011_fix.py` — confirma que o filtro por
  disciplina reduz a fila de 2 para 1 equipamento como esperado.

**Status: RESOLVIDO NA ETAPA 6A.**

## GAP-001 — PATCH de Work Packages devolvendo estado desatualizado

**Problema**: `PATCH /equipments/{id}` com `workPackageIds` gravava
corretamente no banco, mas a resposta imediata do próprio PATCH podia
devolver a lista antiga de Work Packages, por causa de
`expire_on_commit=False` + a coleção `work_package_links` já estar
carregada em memória antes da sincronização.

**Solução aplicada**: em `update_equipment`
(`app/modules/equipments/service.py`), depois do `session.commit()` e só
quando `workPackageIds` foi de fato enviado no PATCH, a coleção é
explicitamente expirada (`session.expire(equipment, ["work_package_links"])`)
antes da releitura final (`get_equipment_out`). Isso força o SQLAlchemy a
recarregar a coleção do banco na mesma query `selectinload` que já existia,
em vez de reaproveitar o estado antigo do identity map da sessão. Não altera
a relação N:N, não reimporta nada, não muda o modelo/schema.

**Arquivo alterado**: `backend/app/modules/equipments/service.py`
(4 linhas adicionadas).

**Testes**:
- O teste de regressão já existente
  `test_equipment_update_adds_and_removes_and_replaces_work_packages`
  (`backend/tests/integration/test_equipment_routes.py`) é exatamente o
  cenário do GAP-001 — ele **falhava antes da correção** e passa a ser a
  prova de regressão.
- Verificação direta adicional (sem HTTP, contra banco TEST):
  `backend/scripts/verify_gap001_fix.py` — cria equipamento com `[A, B]`,
  faz PATCH para `[B, C]` e confirma que **a própria resposta do PATCH**,
  **um GET em sessão nova** e o **banco** concordam em `[B, C]`. Executado
  e confirmado (evidência abaixo).

**Status: RESOLVIDO NA ETAPA 6A.**

## GAP-009 — Startup próprio do componente ausente no frontend

**Problema**: `EquipmentComponent.startup_at` existia no banco/schema/API,
mas não aparecia em lugar nenhum do frontend (nem na tabela de componentes,
nem no formulário de criar/editar).

**Solução aplicada**:
- `ComponentForm.vue`: campo "Startup" (`type=date`), enviado como
  `startupAt` no payload, `null` quando vazio. **Não** herda de
  `equipment.startupAt` — carrega só de `component.startupAt` ao editar, e
  começa vazio ao criar.
- `pages/equipamentos/[id].vue`: coluna "Startup" adicionada à tabela de
  componentes, usando `formatDate(component.startupAt)`.
- Como efeito colateral necessário para tornar `ComponentForm.vue`
  testável (não fazia parte do gap, mas bloqueava o teste), foi adicionado
  `import { reactive, ref } from "vue"` explícito no componente — ele
  dependia apenas do auto-import do Nuxt, que não existe no ambiente de
  teste isolado (vitest); o comportamento em produção é idêntico.

**Arquivos alterados**:
- `frontend/components/equipment/ComponentForm.vue`
- `frontend/pages/equipamentos/[id].vue`
- `frontend/tests/ComponentForm.test.ts` (novo)

**Testes**: `tests/ComponentForm.test.ts`, 3 testes (carrega o startup
existente ao editar sem herdar do equipamento; envia `startupAt` ao criar;
envia `null` quando vazio).

**Status: RESOLVIDO NA ETAPA 6A.**

---

## Resultado dos testes

**Frontend** (`npx vitest run`): **12 arquivos, 64 testes, todos
passando** (inclui os 4 novos de `ProcessSummary`, os 5 de
`engineering.test.ts` e os 3 de `ComponentForm.test.ts`). `npx nuxt
typecheck` sem erros.

**Backend**: os testes de regressão para os 4 gaps foram escritos em
`test_workflow_routes.py`, `test_equipment_routes.py` e
`test_dashboard_and_queues.py`. O banco de teste dedicado (Neon,
`neondb_test`) responde de forma extremamente lenta neste ambiente
(minutos por teste, e uma instabilidade de conexão observada em execuções
longas — `InvalidRequestError` isolado, não relacionado a nenhuma mudança
desta etapa), o que tornou a suíte completa impraticável de esperar até o
fim dentro desta sessão. Por isso, cada correção foi **também** verificada
de forma direta e determinística, chamando os serviços diretamente contra o
banco de teste (sem HTTP, sem pytest, execução em segundos):
`backend/scripts/verify_gap001_fix.py` e
`backend/scripts/verify_gap011_fix.py` — ambos executados nesta etapa,
ambos confirmando a correção (saída registrada acima). O teste de GAP-008
(edição em stage 8) foi validado por leitura de código (ausência de guarda
de etapa no `processes/service.py`, já existente antes desta etapa) e pelos
testes de frontend.

## Baseline C2 (DEV) — confirmada intacta

Antes e depois de todas as mudanças desta etapa, `backend/scripts/audit_c2_db.py`
(somente leitura) confirmou:

| Métrica | Valor |
|---|---|
| Equipment | **41** |
| EquipmentComponent | **164** |
| Vínculos `equipment_work_package` | **71** |

Nenhum dado do C2 foi criado, alterado ou removido nesta etapa. Todas as
verificações de GAP-001/GAP-011 rodaram contra `neondb_test` (banco de
teste separado), nunca contra o banco DEV com os dados reais do C2.
