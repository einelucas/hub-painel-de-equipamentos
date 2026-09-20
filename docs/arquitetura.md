# Arquitetura

O Painel de Equipamentos utiliza duas aplicações independentes no mesmo repositório.

## Frontend

O frontend é Nuxt 4 + Vue 3 + TypeScript, com Pinia e Tailwind CSS. A identidade do Hub fica concentrada no layout, `AppHeader`, `TabsNav`, tokens visuais e assets em `public/brand`.

O contexto global do módulo (Unidade + Equipamento) fica no store Pinia `moduleContext`, compartilhado por dashboard, listagem e filas; `components/ModuleFilters.vue` é a barra única desses filtros e a query string mantém a visão compartilhável. A navbar (`TabsNav`) resolve o item ativo por prefixo mais específico em `utils/navigation.ts`.

O detalhe também é a tela de operação do processo de aquisição: `useEquipmentWorkflow` coordena os dados dos processos, as transições disponíveis e o histórico, e `utils/workflow.ts` concentra a lógica pura (mapa etapa → formulário, estados do stepper). Nenhuma regra de transição vive no frontend — a habilitação do avanço vem de `available-transitions`.

Os componentes genéricos de UI e os charts permanecem reutilizáveis.

## Backend

O backend é FastAPI com SQLAlchemy assíncrono. A composição das rotas acontece em `app/api/v1/router.py`.

A base preserva autenticação, usuários, auditoria e health checks. O domínio foi separado em `catalogs`, `equipments`, `dashboard`, `processes`, `workflow`, `queues`, `access` e `suppliers`, cada um com router, service e schemas explícitos.

A autorização por unidade é centralizada em `app/core/scope.py` e aplicada em todos os módulos que leem ou escrevem dados de uma unidade. Conhecer o UUID de um equipamento não dá acesso a ele: fora do escopo a resposta é 404, com mensagem que não revela a existência do recurso.

`dashboard` agrega tudo no banco em uma resposta consolidada e `queues` recorta o workflow por área, reaproveitando os requisitos de transição do módulo `workflow` para nunca divergir do detalhe.

`workflow` concentra a máquina de estados: `stages.py` declara as pré-condições de cada transição e `service.py` as executa sob transação, com o equipamento bloqueado e revalidação do estágio antes do commit. É o único componente autorizado a alterar `equipment.current_stage`.

## Persistência

O schema compartilhado continua na migration `0001_shared_base`. A migration `0002_equipment_domain` adiciona o domínio normalizado e reversível, `0003_acquisition_process` acrescenta as entidades do processo de aquisição e `0004_access_and_suppliers` adiciona acesso por unidade e fornecedores. Estado de workflow é mantido apenas em `equipment.current_stage`; transições são históricas e imutáveis.
