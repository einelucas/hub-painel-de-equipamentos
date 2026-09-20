# Etapa 04 — consolidação operacional

**Data da implementação:** 2026-09-20

## Objetivo

Consolidar o MVP antes de fórmulas e integrações: autorização real por unidade, responsáveis utilizáveis, fornecedores N:N, manutenção administrativa dos catálogos, exportação ligada a um fluxo real e remoção de controles mortos.

## Auditoria de lacunas herdadas

Confirmado no código antes de implementar:

| Lacuna | Evidência encontrada | Situação |
| --- | --- | --- |
| Filtro de Unidade não era autorização | `catalogs.list_units()` retornava todas as unidades ativas; `User` não tinha vínculo com unidade | Corrigida |
| Responsável sem seletor | `Equipment.responsible_user_id` e o filtro `responsible_user_id` já existiam, mas `EquipmentForm.vue` não oferecia o campo | Corrigida |
| Sem fornecedores | Não existiam `supplier` nem `equipment_supplier` | Corrigida |
| Controles mortos no header | `AppHeader.vue` tinha busca, sino e exportação sem nenhum handler | Corrigida |
| Exportação desconectada | `useExport.ts` e as libs `xlsx`/`jspdf` existiam, sem nenhum consumidor | Corrigida |
| Catálogos sem manutenção | Só havia `GET`/`POST`; sem edição nem desativação | Corrigida |

Lacuna adicional encontrada e corrigida no caminho: o `DELETE` do vínculo de fornecedor precisou de `response_model=None` — com `-> None`, o FastAPI infere `NoneType` (truthy) e recusa o status 204.

## Divergências entre o prompt e a regra de compatibilidade do Hub

A regra final obrigatória do prompt contradiz as seções 5 e 6. Seguindo o desempate que ela mesma define ("prefira a integração contextual"), e com confirmação explícita do usuário:

- **Busca (seção 6):** não foi criada busca de equipamentos no header. A barra do header pertence ao Hub (busca de módulos/aplicações) e ficou **desabilitada com tooltip**. A busca de equipamentos já existia e permanece nas telas do módulo (`/equipamentos` e as três filas), toda server-side. Nenhum endpoint `/search` foi criado.
- **Configurações (seção 5):** não foi criada a tela `/configuracoes`. A administração virou **ação contextual condicionada a ADMIN**: a API de manutenção dos catálogos e de acessos por unidade está completa e auditada, e a UI administrativa dedicada ficou como pendência consciente (ver Pendências).

## Migration

`0004_access_and_suppliers.py`, sucessora de `0003_acquisition_process`. Sobe e desce sem resíduo (verificado com `upgrade`/`downgrade`/`upgrade` e `check_schema_drift.py`).

| Tabela | Campos | Restrições |
| --- | --- | --- |
| `user_unit_access` | `user_id`, `unit_id`, `created_at` | UNIQUE (`user_id`, `unit_id`) |
| `supplier` | `legal_name`, `trade_name`, `tax_id`, `active`, timestamps | UNIQUE parcial em `tax_id` **quando informado** |
| `equipment_supplier` | `equipment_id`, `supplier_id`, `role`, `is_primary`, `created_at` | UNIQUE (`equipment_id`, `supplier_id`) e UNIQUE parcial em `equipment_id` **onde `is_primary`** |

O índice parcial garante **no banco** que existe no máximo um fornecedor principal por equipamento — não depende da aplicação.

### Backfill

Até aqui todo usuário enxergava todas as unidades. Para não remover acesso de quem já usa o sistema, a migration vincula os VIEWER/ANALYST **existentes** a todas as unidades **existentes naquele momento**. ADMIN não recebe vínculo (é global por perfil) e usuários criados depois exigem atribuição explícita.

## Autorização por unidade

`app/core/scope.py` centraliza a regra. O perfil define **o que**; o vínculo define **onde**.

| Perfil | Escopo |
| --- | --- |
| ADMIN | todas as unidades ativas, por perfil |
| ANALYST | apenas as unidades atribuídas |
| VIEWER | apenas as unidades atribuídas |

Funções: `allowed_unit_ids` (`None` = todas), `assert_unit_allowed`, `assert_context_allowed`, `assert_equipment_allowed`, `restrict_to_units` e `user_can_access_unit`.

Aplicado em `/units`, contextos, áreas, work packages, `/equipments` (lista e detalhe), componentes, processos, workflow/transições, histórico, dashboard, filas e fornecedores vinculados ao equipamento. Disciplinas continuam globais por não pertencerem a uma unidade.

**Conhecer o UUID não dá acesso.** Um equipamento de unidade não autorizada responde **404** com mensagem única ("Recurso não encontrado ou fora das unidades autorizadas"), que não revela se o recurso existe em outra unidade. Um usuário sem nenhuma unidade vê listas vazias, não erro.

Administração (ADMIN, auditada em `user.units_changed`):

- `GET /api/v1/usuarios/{user_id}/units`
- `PUT /api/v1/usuarios/{user_id}/units`

O `PUT` substitui todos os vínculos e recusa atribuição individual a ADMIN, que é global por perfil.

## Responsáveis

`GET /api/v1/responsibles?unit_id=` — leitura própria do formulário, sem reaproveitar o endpoint administrativo `/usuarios`. Retorna apenas usuários **ativos** com acesso à unidade, mais os ADMIN (globais por perfil), ordenados por nome.

No backend, `responsible_user_id` incompatível com a unidade do equipamento é recusado com **422**. No `EquipmentForm.vue` há seletor com "Não atribuído", que preserva o valor na edição e limpa automaticamente um responsável sem acesso à unidade. Em `/equipamentos` há filtro por responsável, server-side. As filas também aceitam `responsible_user_id`.

## Fornecedores

- `GET|POST /api/v1/suppliers` (`?search=`, `?includeInactive=`)
- `GET|PATCH /api/v1/suppliers/{id}`
- `GET|POST /api/v1/equipments/{id}/suppliers`
- `PATCH|DELETE /api/v1/equipments/{id}/suppliers/{supplier_id}`

Permissões novas: `suppliers:read` (VIEWER+) e `suppliers:write` (ANALYST+).

Regras: `tax_id` duplicado só é bloqueado quando informado; fornecedor inativo não pode ser vinculado; promover um fornecedor a principal rebaixa o anterior na mesma transação; o `DELETE` remove **apenas o vínculo** — o cadastro mestre é desativado, nunca apagado. `role` é texto livre, porque o catálogo oficial de papéis não foi validado.

Frontend: aba **Fornecedores** no detalhe do equipamento (vincular, desvincular, definir principal, conforme permissão), coluna **Fornecedor principal** na fila de Suprimentos (`—` quando não houver, sem bloquear o workflow) e página `/fornecedores` para o cadastro mestre.

## Catálogos administráveis

`PATCH` em `/units/{id}`, `/project-contexts/{id}`, `/areas/{id}`, `/disciplines/{id}` e `/work-packages/{id}` — nome, código (onde existe) e `active`. Exige `catalogs:manage` (ADMIN), recusa duplicidade de código/nome no mesmo escopo e gera auditoria `catalog.update`. **Não há hard delete**: desativar é o caminho, porque os registros são referenciados por equipamentos.

## Controles do header

Seguindo a regra de compatibilidade, o header é infraestrutura do Hub e nenhum controle ficou clicável sem função:

| Controle | Estado |
| --- | --- |
| Busca | desabilitada, com tooltip apontando a busca da tela Equipamentos |
| Sino | desabilitado, "Notificações em breve" |
| Exportação | desabilitada, com tooltip apontando o botão Exportar da tela Equipamentos |

**Notificações:** nenhuma regra automática foi inventada. Destinatário, canal, antecedência e repetição de FUP/kickoff continuam indefinidos, então o sino permanece desabilitado até a etapa específica.

## Exportação

O botão **Exportar** vive em `/equipamentos`, junto dos filtros que ele respeita: unidade, equipamento, etapa, disciplina, responsável e busca. Não exporta apenas a página visível — pagina o recorte inteiro no servidor (100 por vez) e monta um `.xlsx` com `useExport()`. Há um teto de 20 páginas (2.000 linhas) para não puxar volume ilimitado para o navegador; acima disso, a saída deve migrar para CSV server-side na Etapa 5.

## Arquivos principais

**Backend (novos):** `app/core/scope.py`, `app/models/access.py`, `app/models/supplier.py`, `app/modules/access/*`, `app/modules/suppliers/*`, `alembic/versions/0004_access_and_suppliers.py`, `tests/helpers.py`, `tests/integration/test_access_and_suppliers.py`.

**Backend (alterados):** `app/core/permissions.py`, `app/models/equipment.py`, `app/models/__init__.py`, `app/api/v1/router.py` e os módulos `catalogs`, `equipments`, `processes`, `workflow`, `dashboard`, `queues` (escopo + responsável + fornecedor principal).

**Frontend (novos):** `components/equipment/EquipmentSuppliers.vue`, `pages/fornecedores.vue`, `tests/EquipmentSuppliers.test.ts`.

**Frontend (alterados):** `components/AppHeader.vue`, `components/equipment/EquipmentForm.vue`, `pages/equipamentos/index.vue`, `pages/equipamentos/[id].vue`, `pages/suprimentos.vue`, `stores/auth.ts`, `types/api.ts`, `types/equipment.ts`.

## Testes

Backend — `tests/integration/test_access_and_suppliers.py`: ADMIN vê todas as unidades e ANALYST só as atribuídas; equipamento de outra unidade bloqueado por UUID em sete rotas de leitura e nas de escrita/transição; listagem, dashboard e filas respeitando o escopo; usuário sem unidade vendo listas vazias; endpoints de acesso restritos a ADMIN e auditados; ADMIN global recusando vínculo individual; responsáveis filtrados por unidade e rejeição de responsável sem acesso; filtro por responsável; CRUD de fornecedor com `tax_id` duplicado, desativação sem hard delete e auditoria; VIEWER sem escrita; fornecedor principal único; desvínculo preservando o mestre; fornecedor principal na fila de Suprimentos; `PATCH` de catálogo com desativação, permissão, auditoria e código duplicado.

As suítes das Etapas 1–3 foram mantidas verdes com `tests/helpers.py::grant_unit`, que concede a unidade recém-criada aos perfis operacionais — necessário porque, a partir desta etapa, o acesso é explícito.

Frontend — `tests/EquipmentSuppliers.test.ts`: listagem dos vínculos, destaque do principal, promoção a principal, ocultação das ações sem `suppliers:write` e estado vazio.

## Decisões provisórias

- Todas as filas usam `equipments:read`; não há matriz fina por departamento.
- `role` do fornecedor é texto livre até o catálogo oficial ser validado.
- Backfill dá acesso amplo aos usuários que já existiam — é a leitura conservadora de "não quebrar quem já usa", mas deve ser revisada com a lista real de pessoas por unidade.
- Teto de 2.000 linhas na exportação client-side.

## Pendências para a Etapa 5

- **UI administrativa**: a API de catálogos e de acessos por unidade está pronta e auditada, mas não há tela. Definir se ela entra como ação contextual nas telas atuais ou como área dedicada — hoje só é operável via API.
- Matriz fina de permissões por Engenharia/Jurídico/Suprimentos.
- Exportação server-side (CSV) para volumes acima do teto atual.
- Busca do Hub no header, quando o Hub assumir esse componente.
- Notificações (FUP/kickoff) após definição de destinatário, canal, antecedência e repetição.
- Itens que seguem fora de escopo: Standby/Cancelado/Não se Aplica, múltiplos contratos/SCs/OCs, fórmulas de prazo e índices, "Total de Aquisições", ERP, migração C2/F2, comentários, anexos e Kanban.
