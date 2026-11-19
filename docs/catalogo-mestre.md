# Catálogo Mestre — áreas, equipamentos e componentes

O Catálogo Mestre é a biblioteca **global** usada para compor novas obras no Painel de Equipamentos. Ele não é uma segunda tabela de equipamentos da obra e não substitui a hierarquia EAP.

## Modelo de dados

- `MasterArea`: nome, normalização, estado ativo/inativo e marcador estrutural para a categoria virtual **Sem área definida**.
- `MasterEquipment`: modelo de equipamento, nome normalizado, flags de revisão e ativação.
- `MasterEquipmentArea`: associação N:N entre modelos e áreas do catálogo.
- `MasterComponentOption`: opções de componentes por modelo, com indicadores de revisão de quantidade/nome.
- `MasterProjectCreation`: idempotência das solicitações de criação de obra a partir do catálogo.

A EAP (`EapNode`) é uma classificação corporativa separada. Não associe automaticamente áreas do Catálogo Mestre a nós EAP apenas pela semelhança textual.

## Interface e permissões

A administração é acessada em `/administracao/catalogo-mestre` (`frontend/pages/administracao/catalogo-mestre.vue`, protegido pelo middleware `catalog-manager`). A interface oferece pesquisa, filtro por área, cadastro/renomeação, ativação, vínculos de área, opções de componentes e importação de seed.

- Leitura da API: `catalogs:read`.
- Escrita e importação: `catalogs:manage`.
- Criação de obra pelo catálogo: também requer `equipments:write` e autorização na unidade de destino.

## Seed JSON e manutenção

`POST /api/v1/master-catalog/seed?dry_run=true` **valida e simula** a importação sem gravar; `dry_run=false` tenta inserir novos registros preservando os já existentes. Conflitos de identidade/nome são recusados. Não utilize o seed para sobrescrever alterações administrativas feitas depois da primeira carga.

A API permite incluir áreas, equipamentos e componentes, associar áreas e alterar ativação/nome. Exclusões físicas obedecem às validações de vínculo; a categoria virtual não pode ser excluída.

## Criação de obra

`POST /api/v1/master-catalog/projects` recebe a unidade, os dados do contexto e seleções de equipamentos com os componentes escolhidos. O backend cria `ProjectContext`, `Equipment` e `EquipmentComponent` **próprios da nova obra** numa transação e usa `request_id` para evitar duplicidade por repetição da mesma requisição.

**Consequência importante:** editar ou desativar um modelo no catálogo não modifica equipamentos já cadastrados em obras. O mesmo vale para equipamentos anteriores à introdução do Catálogo Mestre; a manutenção e a classificação desses registros precisam ser tratadas explicitamente no fluxo operacional.

## Arquivos de referência

- `backend/app/models/master_catalog.py`
- `backend/app/modules/master_catalog/{controllers,schemas,services}.py`
- `frontend/components/master-catalog/`
- `frontend/pages/administracao/catalogo-mestre.vue`
- Migration base: `backend/alembic/versions/0027_master_equipment_catalog.py`

Consulte [API](api.md), [Domínio e EAP](dominio-eap.md) e [Funcionalidades](funcionalidades.md).
