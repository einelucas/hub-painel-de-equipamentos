# Funcionalidades e fluxos operacionais

Este documento descreve as capacidades identificadas no frontend, nos controllers e services do backend. A disponibilidade efetiva depende do perfil do usuário, do contexto selecionado, dos dados importados e da configuração do ambiente.

## Navegação e contexto

A navegação principal definida em `frontend/utils/navigation.ts` contém Dashboard, Equipamentos, Engenharia, Jurídico, Suprimentos, Fornecedores e Kanban (os dois últimos com checagem de permissões na navegação). Há rotas adicionais para auditoria, administração, notificações, usuários e detalhes.

O store `moduleContext` centraliza a seleção de **Unidade → Projeto/Contexto → Equipamento**, propaga filtros à API e evita manter um equipamento incompatível ao trocar de unidade/contexto. A autorização no backend sempre prevalece sobre o filtro visual.

## Dashboard e indicadores

O painel agrega quantidades por etapa e dados de acompanhamento de aquisição, negociação, criticidade e prazos. Existem cards e gráficos reutilizáveis em `frontend/components/dashboard/` e `frontend/components/charts/`, com agregações no domínio `backend/app/modules/dashboard/`.

Valores de fórmulas dependem de marcos preenchidos e das regras confirmadas. Ausência de dados deve ser tratada como estado incompleto, não convertida em um resultado presumido.

## Equipamentos e componentes

- Listagem paginada, busca e filtros por unidade/contexto/equipamento.
- Cadastro, edição, detalhes e componentes técnicos (subitens).
- Área/EAP, disciplina, criticidade, responsável, work packages e marcos de projeto.
- Abas de visão geral, processos, prazos, histórico, comentários, documentos e dados vinculados.
- Associação ao contexto operacional; validações de domínio e escopo no backend.

A equipe pode usar `frontend/components/equipment/` como referência dos componentes padronizados, sem copiar formulários para novas páginas.

## Processo de aquisição

~~~text
Demanda → Negociação → Equalização → Jurídico/Minuta
        → Contrato → SC/OCI → OC → Concluído
~~~

- **Negociação:** equalização e data de negociação.
- **Jurídico:** abertura de chamado, número de referência, elaboração e aprovação de minuta.
- **Contratos:** múltiplos contratos por equipamento, números, escrituração e anexos; janela contratual do equipamento tratada separadamente.
- **SC/OCI:** múltiplas solicitações por equipamento.
- **OC:** múltiplas ordens por equipamento, com números, datas e valores.
- **Workflow:** transições uma fase por vez, com pré-requisitos e registro auditável.

O avanço de etapa é decidido pelo backend. `RequirementWaiver` documenta dispensas justificadas por **grupo de requisito**, sem permitir pular fases; a conclusão mantém grupos obrigatórios. Reaberturas seguem solicitação e aprovação. Estados `ACTIVE`, `STANDBY`, `CANCELLED` e `IN_SANITATION` não são fases do workflow.

Consulte [domínio e EAP](dominio-eap.md) para regras exatas.

## Filas operacionais e Kanban

Engenharia, Jurídico e Suprimentos usam filtros e tabelas orientados ao trabalho de cada equipe. O Kanban apresenta o estágio operacional do processo em outra visualização. Não se devem confundir visualizações filtradas com modelos de dados diferentes.

## Fornecedores e cadastros

Há cadastro corporativo de fornecedores, importação/reconciliação, aliases e vínculos com equipamentos. A **regra atual de negócio** admite no máximo um fornecedor por equipamento, mesmo que versões antigas de documentos falem em N:N sem restrição. Troca de fornecedor exige substituição explícita.

Catálogos disponíveis incluem unidades, contextos, áreas, disciplinas, pacotes de trabalho, criticidade e EAP. Módulos administrativos permitem gerenciar dados sujeitos às permissões, sem apagamento físico indiscriminado.

## Administração, usuários e auditoria

- Gerenciamento de usuários, perfis e acessos por unidade.
- Telas administrativas contextuais e trilhas de auditoria.
- Logs/históricos de alterações e transições.
- Consulta de dados limitada por permissões e escopo.

A rota temporária de usuários presente no frontend deve ser avaliada para homologação; sua existência não dispensa a revisão da política corporativa de identidade.

## Importação Monday

A interface administrativa permite selecionar `ImportProfile`, enviar XLSX, acompanhar análise de lote/staging, preparar plano e executar apply confirmado com acompanhamento de job. O motor também possui CLI administrativa.

**Upload não equivale a importação final.** A criação ou atualização de equipamento ocorre somente no apply controlado, após validação dos mapeamentos. Consulte [importação](importacao-monday.md).

## Notificações

Regras e destinatários são configurados no backend e persistidos em banco. O centro administrativo permite editar modelos HTML, pré-visualizar, enviar testes e consultar entregas. Há diferentes modos de execução e provedores; a entrega real depende de configuração autorizada.

Consulte [notificações](notificacoes.md) e [ambientes](ambientes-deploy.md).

## Limitações que exigem confirmação

Não presumir: CI verde no último push, schema atualizado em todos os bancos, provedor de e-mail pronto para uso real, disponibilidade de EAP corporativa em cada ambiente, importação de todas as obras ou homologação de produção. Esses itens dependem de verificação específica, e não apenas da existência de telas, serviços ou migrations.
