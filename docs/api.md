# API

Prefixo: `/api/v1`.

## Saúde

- `GET /health/live`: indica que o processo está ativo.
- `GET /health/ready`: verifica a conectividade com o banco.

## Autenticação

- `GET /auth/me`: retorna o usuário autenticado e suas permissões.

## Usuários

Rotas administrativas:

- `GET /usuarios`
- `POST /usuarios`
- `PATCH /usuarios/{user_id}`

## Auditoria

- `GET /auditoria`: lista eventos registrados, com paginação e filtros opcionais por entidade e ação.

A documentação interativa completa é gerada pelo FastAPI em `/docs`.

## Catálogos de equipamentos

- `GET /units`
- `GET /units/{unit_id}/project-contexts`
- `GET /areas?unit_id=`
- `GET /disciplines`
- `GET /work-packages?project_context_id=`

ADMIN também pode criar esses catálogos pelos respectivos endpoints `POST`.

## Equipamentos e componentes

- `GET /equipments`: filtros `unit_id`, `project_context_id`, `equipment_id`, `search`, `stage`, `discipline_id`, `responsible_user_id`, paginação e ordenação segura.
- `POST /equipments`
- `GET /equipments/{equipment_id}`
- `PATCH /equipments/{equipment_id}`
- `GET /equipments/{equipment_id}/components`
- `POST /equipments/{equipment_id}/components`
- `PATCH /components/{component_id}`

O `PATCH` de equipamento **não** aceita `currentStage`: a etapa só muda pelo endpoint de transições e a tentativa retorna 422 com a orientação correta.

## Processo de aquisição

Leitura com `equipments:read`, escrita com `process:write`. Um processo ainda não iniciado é devolvido com `id: null` e valores padrão, sem gravar nada.

- `GET /equipments/{equipment_id}/processes`: os cinco processos em uma chamada
- `GET | PATCH /equipments/{equipment_id}/negotiation`
- `GET | PATCH /equipments/{equipment_id}/legal`
- `GET | PATCH /equipments/{equipment_id}/contract`
- `GET | PATCH /equipments/{equipment_id}/purchase-request`
- `GET | PATCH /equipments/{equipment_id}/purchase-order`

## Workflow 0–8

- `GET /equipments/{equipment_id}/available-transitions` (`workflow:read`): etapa atual e, para cada transição possível, `canExecute` e os requisitos com `code`, `field`, `message` e `satisfied`.
- `POST /equipments/{equipment_id}/transitions` (`workflow:transition`): corpo `{ "targetStage": <int>, "reason": <string|null> }`. O backend valida as pré-condições — 422 para requisito pendente ou pulo de etapa, 409 quando a etapa já foi alterada por outro usuário. A reabertura (`targetStage: 1` a partir da etapa 2 ou superior) exige `reason` e `workflow:reopen`.
- `GET /equipments/{equipment_id}/history` (`workflow:read`): transições e alterações de dados do processo em uma lista única, da mais recente para a mais antiga.

## Resumo do painel

- `GET /dashboard/summary?unit_id=&equipment_id=`: resposta consolidada com `context`, `totals` (equipamentos, componentes, em andamento, concluídos, OCs e valor emitido, CAPEX), `workflow` (distribuição pelas etapas 0–8), `negotiation`, `deadlines` e `startup`.

`deadlines.available` é sempre `false` enquanto as regras oficiais de prazo não forem formalizadas — o campo `reason` explica o motivo e nenhum prazo é estimado.

## Filas operacionais

Recortes do workflow por área, com `equipments:read`. Todas aceitam `unit_id`, `equipment_id`, `stage`, `search`, `page` e `pageSize`, e devolvem `pending` com o que falta para a próxima etapa.

- `GET /queues/engineering`: etapas 0 a 2
- `GET /queues/legal`: etapas 3 a 5
- `GET /queues/procurement`: etapas 6 e 7
