# Etapa 6D — Completude Operacional e Auditoria

Data: 2026-09-22

Corrige apenas gaps técnicos já confirmados que não dependem de nova
decisão de negócio: GAP-002, GAP-003, GAP-010, GAP-012a/b, GAP-016,
GAP-019. Nenhum workflow especial, notificação, anexo ou outra
funcionalidade fora dessa lista foi implementado nesta etapa.

Baseline DEV confirmada intacta no início e no fim da etapa:
41 Equipment / 164 EquipmentComponent / 71 EquipmentWorkPackage.

---

## 1. GAP-002 — Histórico dos registros migrados

### Causa

`GET /equipments/{id}/history` (`app/modules/workflow/service.py::history`)
filtrava `AuditLog` só por `entityId == equipment_id` OU
`metadata.equipmentId == equipment_id`. O segundo caminho é o usado pelas
edições em tempo real (`processes/service.py::update_process` grava
`metadata={"equipmentId": equipment_id}`), mas os `AuditLog` gravados pela
migração (MIG-001.1, `monday_import/apply.py`) para as sub-entidades
(`EquipmentComponent`, `Negotiation`, `LegalProcess`, `Contract`,
`PurchaseRequest`, `PurchaseOrder`) têm `entityId` = ID da própria
sub-entidade e `metadata` sem a chave `equipmentId`
(`_plan_metadata` só grava `sourceSystem/migrationRunId/batchIds/
sourceKey/identityStrategy`). Resultado: esses registros nunca apareciam
na aba Histórico do equipamento.

### Solução (por relacionamento, sem reescrever nada)

Não fabricamos `WorkflowTransition`, não reexecutamos a migração e não
alteramos nenhum `AuditLog` histórico. Em vez disso, o histórico passou a
localizar também os `AuditLog` cujo `entityId` corresponde às sub-entidades
reais daquele equipamento (FK real, não suposição):

`app/shared/audit.py::equipment_audit_conditions(session, equipment_id)`
devolve a lista de condições OR:
- `AuditLog.entityId == equipment_id`
- `AuditLog.metadata_["equipmentId"].astext == equipment_id`
- `AuditLog.entity == "EquipmentComponent" AND AuditLog.entityId IN (component_ids do equipamento)`
- para cada sub-entidade 1:1 (`Negotiation`/`LegalProcess`/`Contract`/
  `PurchaseRequest`/`PurchaseOrder`): `AuditLog.entity == model.__name__ AND
  AuditLog.entityId == <id da linha 1:1 daquele equipamento>`

Essa função é usada tanto por `workflow/service.py::history` (GAP-002)
quanto por `audit/service.py::list_audit_logs` (GAP-019) — nenhuma lógica
duplicada entre as duas telas.

### Evidência (DEV, somente leitura, "Caldeira de Biomassa")

```
Antes:  1 item  (só a criação do Equipment)
Depois: 30 itens (componentes + Negotiation + LegalProcess + Contract +
                  PurchaseRequest + PurchaseOrder, todos migration.import)
```

### Testes

`tests/integration/test_workflow_routes.py::test_history_surfaces_migration_style_subentity_audits`
(novo): cria um equipamento real via API, insere `AuditLog` no formato
exato da migração (entityId da sub-entidade, sem `metadata.equipmentId`)
para as 6 sub-entidades, confirma que as 6 aparecem no histórico com o
título amigável certo, e confirma que **nenhuma `WorkflowTransition`** foi
criada (contagem real no banco = 0).

---

## 2. GAP-003 — Título amigável da migração

`_AUDIT_TITLES["migration.import"] = "Importado do Monday"` em
`workflow/service.py`. Só tradução de apresentação — `action` continua
`"migration.import"` no banco, nada foi reescrito. Coberto pelo mesmo
teste do GAP-002 (`assert item["title"] == "Importado do Monday"`).

---

## 3. GAP-010 — Filtros de Área e Work Package

### Backend

`GET /equipments` ganhou `area_id` e `work_package_id`
(`app/modules/equipments/service.py::_apply_filters`):

- `area_id`: `Equipment.area_id == area_id` — direto.
- `work_package_id`: **EXISTS** sobre a relação N:N oficial
  (`equipment_work_package`), nunca o `work_package_id` singular legado:
  ```python
  stmt.where(
      select(EquipmentWorkPackage.id)
      .where(
          EquipmentWorkPackage.equipment_id == Equipment.id,
          EquipmentWorkPackage.work_package_id == work_package_id,
      )
      .exists()
  )
  ```
  EXISTS em vez de JOIN — um equipamento com vários Work Packages nunca
  duplica linha na listagem nem na contagem/paginação.

### Evidência (DEV, somente leitura)

- "Bomba SUMP" (equipamento real com 4 Work Packages) filtrado por
  qualquer um dos 4 aparece **exatamente uma vez** em cada filtro,
  `pagination.total` bate com `items.length`.
- Filtro por Área (`Caldeira`, 36 equipamentos reais) devolve só
  equipamentos daquela área.

### Testes

`tests/integration/test_equipment_routes.py`: `test_equipment_filters_by_area_id`,
`test_equipment_filters_by_work_package_id`,
`test_equipment_with_multiple_work_packages_appears_once_and_count_matches`
(cria equipamento com 2 WPs, filtra por cada um, confirma 1 resultado e
`total == 1` nos dois casos), `test_equipment_filters_combine_area_and_work_package`.

### Frontend

`pages/equipamentos/index.vue`: novos filtros "Área" (respeita a Unidade,
via `GET /areas?unit_id=`) e "Pacote de trabalho" (respeita o(s)
ProjectContext(s) da Unidade — a API exige `project_context_id`; busca os
contexts da unidade via `GET /units/{id}/project-contexts` e agrega os
Work Packages de todos eles). Seleção que deixa de existir ao trocar de
unidade é limpa automaticamente; uma que continua válida (ex.: após editar
catálogos) permanece. IDs reais em todo lugar, nenhum nome hardcoded.

`components/equipment/EquipmentTable.vue`: nova coluna "Pacotes de
trabalho" com chips compactos (`equipment.workPackages`, máx. 3 visíveis +
"+N" para o excedente) — nunca aumenta a altura da linha mesmo para
equipamentos com muitos WPs (ex.: "Caldeira de Biomassa" tem 10).

### Exportação

`exportAll()` já reaproveitava `currentQuery()` — passou a incluir
`area_id`/`work_package_id` automaticamente (mesma função usada pela
listagem, sem duplicar regra). Nova coluna "Pacotes de Trabalho" no Excel,
formatada como `CAL012, CIV012, CIV014` a partir de `equipment.workPackages`
(nunca o `workPackage` singular legado).

### Testes (frontend)

`tests/EquipmentTable.test.ts`: novo teste confirma chips compactos com
"+N" para 4 Work Packages (mostra os 3 primeiros + "+1", nunca o 4º
completo).

---

## 4. GAP-012a — Jurídico (Responsável + Entrega contratual)

`pages/juridico.vue` ganhou as colunas "Responsável"
(`LegalRow.responsibleUser`) e "Entrega contratual" (`LegalRow.deliveryAt`)
— ambas já vinham prontas da API (`app/modules/queues/schemas.py`,
`queues/service.py:282`), só não eram renderizadas. Nenhuma regra nova.

## 5. GAP-012b — Suprimentos (Responsável)

`pages/suprimentos.vue` ganhou a coluna "Responsável"
(`ProcurementRow.responsibleUser`). Critérios da fila (etapas 6-7)
inalterados. Filtros específicos do Monday que ainda dependem de
confirmação do negócio **não foram implementados**, conforme instruído.

Evidência ao vivo (Playwright, DEV): Jurídico mostra "Ediel" na coluna
Responsável para "Conjunto Turbo-Gerador"; Suprimentos mostra "Uilson" para
"ESTRUTURAS METÁLICAS CALDEIRA".

---

## 6. GAP-016 — Permissões no frontend

### Antes

`frontend/stores/auth.ts` tinha uma matriz `MATRIX: Record<Role,
Permission[]>` local que replicava manualmente `app/core/permissions.py`.
`/auth/me` já devolvia `permissions` (campo existia no tipo `CurrentUser`),
mas nada no frontend o consumia.

### Depois

`can(permission)` delega a `hasPermission(user, permission)`
(`utils/permissions.ts`, nova função pura): `Boolean(user?.permissions?.includes(permission))`.
Zero matriz local — `permissions` ausente (usuário nulo, sessão antiga sem
o campo) nega o acesso em vez de assumir uma permissão que o backend não
confirmou. Backend continua a única autoridade: qualquer permissão nova
(ex.: departamental, se vier a existir) aparece automaticamente no
frontend assim que `/auth/me` passar a devolvê-la — sem replicar nada.

Nenhuma matriz departamental nova foi criada, conforme instruído.

### Testes

`tests/permissions.test.ts` (5 testes, novo): VIEWER só tem as 4
permissões de leitura; ANALYST tem leitura+escrita mas não administração;
ADMIN tem tudo; usuário nulo nega tudo; `permissions` ausente nega tudo
(nunca assume acesso). Todos constroem o usuário só a partir do array de
permissões devolvido pela API — nunca do papel — provando que a fonte de
verdade é mesmo o backend.

Evidência ao vivo: `GET /auth/me` com `dev-viewer` devolve exatamente
`["catalogs:read","equipments:read","suppliers:read","workflow:read"]`.

---

## 7. GAP-019 — Filtros da Auditoria

### Backend

`GET /auditoria` ganhou `equipment_id`, `user_id`, `date_from`, `date_to`
(`app/modules/audit/service.py::list_audit_logs`). `equipment_id` reutiliza
**a mesma** `equipment_audit_conditions` do GAP-002 — nenhuma segunda
lógica de "o que pertence a este equipamento". `date_from`/`date_to`
comparam contra `AuditLog.createdAt` (naive UTC, mesmo padrão já usado no
resto do schema) com `datetime.combine(data, time.min/max)`. Paginação,
filtros existentes (`entity`/`action`), ordenação por data
(`createdAt.desc()`) e a permissão `AUDIT_READ` (ADMIN-only) continuam
exatamente como estavam.

### Frontend

`AuditViewer.vue` ganhou 4 filtros: "Equipamento" e "Usuário" como
`<select>` nativo com IDs reais (populados de `GET /equipments` e `GET
/usuarios`, sem nome hardcoded), "De"/"Até" como `<input type="date">`.
Sem busca avançada nem query builder, conforme instruído.

### Evidência (DEV, somente leitura)

Filtrar `/auditoria?equipment_id=<Caldeira de Biomassa>` devolve os
**mesmos 30 itens** que a aba Histórico do próprio equipamento (GAP-002) —
confirma que as duas telas usam a mesma fonte de verdade.

### Testes

`tests/integration/test_audit_routes.py`:
`test_audit_filters_by_equipment_id_includes_sub_entities` (confirma que
inclui sub-entidades e não vaza auditoria de outro equipamento),
`test_audit_filters_by_user_id`, `test_audit_filters_by_date_range`,
`test_audit_combines_equipment_and_action_filters`.

---

## 8. Não implementado nesta etapa (por instrução explícita)

Shortcut 2→4 (GAP-004), bypass de Suprimentos (GAP-005), nova regra de
reabertura (GAP-006), novas formas de conclusão (GAP-007), estados
Standby/Cancelado/Não se Aplica, permissões departamentais (GAP-017),
notificações, e-mail/FUP, anexos, comentários, Kanban, Saved Views, ERP,
alteração da cardinalidade Contract/SC/OC, migração de fornecedores do
Monday — nenhum destes foi tocado.

---

## Baseline DEV — confirmada intacta

```
Equipment: 41
EquipmentComponent: 164
equipment_work_package: 71
```

Nenhum dado do C2 foi criado, alterado ou removido nesta etapa. Todas as
verificações contra dados reais (GAP-002, GAP-010, GAP-012a/b, GAP-016,
GAP-019) são somente leitura contra DEV.
