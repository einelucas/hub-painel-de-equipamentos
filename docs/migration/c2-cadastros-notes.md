# Cadastros C2 — notas da migração (DEV)

Registro das decisões fechadas para os cadastros pendentes do C2, aplicadas via
`backend/scripts/seed_c2_catalog.py` e resumidas em `c2-seed-ids.json`.

## Área

`"2104.A Casa de Força"` e `"Casa de Força"` são a mesma área operacional.
Foi criada uma única `Area` ("Casa de Força"); os dois valores de origem
apontam para o mesmo `area_id` em `c2-mapping.json`. Nenhuma segunda Area foi
criada.

## Responsáveis — e-mails provisórios

Os 4 responsáveis foram criados como `User` reais (role `ANALYST`,
`authProvider=KEYCLOAK`, `externalUserId=NULL`, seguindo o mesmo caminho do
cadastro administrativo padrão em `app/modules/users/service.py`) com e-mails
**provisórios**:

| Nome | E-mail provisório |
|---|---|
| Ediel | ediel@inpasa.com.br |
| Uilson | uilson@inpasa.com.br |
| Ana Carolina | ana.carolina@inpasa.com.br |
| Samuel | samuel@inpasa.com.br |

**Ação futura:** quando os e-mails corporativos oficiais forem definidos,
atualizar apenas `User.email` (via `PATCH` de usuário ou update direto). O
`User.id` não muda, então nenhuma relação com `Equipment.responsible_user_id`
(nem com `c2-mapping.json`) precisa ser refeita.

## Acesso e permissões

Os 4 usuários estão `active=true` e vinculados à `Unit` LEM via
`UserUnitAccess`, o que os torna elegíveis no seletor de responsável
(`GET /access/units/{unit_id}/responsibles`). Perfil usado: `ANALYST`
(permite `equipments:write`), por decisão explícita — **não** é uma regra de
autorização "responsável = only editor"; qualquer ANALYST/ADMIN com acesso à
unidade continua podendo editar. O refinamento de permissões por
Engenharia/Jurídico/Suprimentos fica para FUN-005/SEC-001.

## Disciplinas — códigos gerados

A origem Monday só traz o nome de exibição da disciplina, sem código. Foram
gerados códigos técnicos (únicos, exigidos pelo schema) na criação:

| Nome (origem) | `Discipline.code` |
|---|---|
| E&I | `EI` |
| Metal Mec. | `METAL_MEC` |
| Automação | `AUTOMACAO` |

## Work Packages — nome provisório

A origem Monday só traz o código do Work Package (ex.: `CAL001`), sem nome de
exibição separado. `WorkPackage.name` foi preenchido com o próprio código
como valor provisório (`name = code`) para os 24 registros. Ação futura:
substituir por um nome descritivo quando houver um catálogo oficial de Work
Packages — a troca de `name` não afeta o mapping (chave é o `code`/`id`) nem
as relações N:N `equipment_work_package`.

## IDs criados

Ver `c2-seed-ids.json` (mesma pasta) para o dump completo de IDs, e
`c2-mapping.json` para o mapping final usado pelo `plan`.
