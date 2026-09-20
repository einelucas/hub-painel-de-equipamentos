# Painel de Equipamentos

*Auditoria funcional do Monday.com e especificação inicial para o Hub de Automação*

| **Ambiente principal**   | Equipamentos - LEM C2                                                                |
|--------------------------|--------------------------------------------------------------------------------------|
| **Ambiente comparativo** | Equipamentos LEM F2                                                                  |
| **Workspace**            | 08\. Luis Eduardo Magalhães                                                          |
| **Data da auditoria**    | 20/09/2026                                                                           |
| **Modo de trabalho**     | Somente leitura; nenhuma alteração intencional em dados, automações ou configurações |

**Fonte observada:** [<u>Monday - Equipamentos LEM C2</u>](https://inpasa-team.monday.com/boards/18418526304/views/265049299)

*Documento preparado para servir de base funcional e técnica ao desenvolvimento em Nuxt 4, Vue 3, TypeScript, FastAPI, Python e PostgreSQL.*

# 1. Resumo executivo

O processo observado não é apenas um cadastro de equipamentos. Ele é um fluxo de aquisição e acompanhamento que começa na nova demanda, passa por negociação, equalização, tramitação jurídica, contratação, solicitação de compra, emissão da ordem de compra e conclusão. O Monday combina o registro mestre do equipamento, componentes/subitens, prazos calculados, relacionamentos com fornecedores, filtros por equipe, dashboards e 21 automações que mantêm o status e o grupo sincronizados.

**Conclusão principal:** O Hub deve substituir o modelo de quadro por um domínio estruturado: Equipamento + Componente + Processo de Aquisição + Marcos + Workflow + Histórico. Replicar somente a grade visual deixaria as regras críticas espalhadas e manteria as inconsistências atuais.

- Board C2 confirmado com 41 equipamentos distribuídos em quatro fases ocupadas e 164 subitens informados pelos grupos.

- O dashboard informa 163 aquisições, um registro a menos que a soma dos subitens; a regra desse indicador precisa ser validada.

- Existem 21 automações ativas, majoritariamente responsáveis por validar marcos, atualizar A.Status e mover o item para o grupo correspondente.

- O board F2, usado como comparação, contém 77 equipamentos, 540 subitens, 19 automações e uma view Kanban; ele evidencia redundâncias e campos antigos/duplicados.

- O campo 0.Responsável é texto, não People; isso dificulta identidade, permissões e notificações confiáveis.

- O relacionamento 0.Fornecedores é Connect Boards, mas a maioria dos exemplos do C2 aparece como N/D; no F2 o fornecedor é texto, revelando modelos inconsistentes entre boards.

- Várias fórmulas retornam 'failed to calculate: no value' quando marcos estão vazios. No Hub, campos derivados devem aceitar estado incompleto sem erro de interface.

# 2. Escopo e método da auditoria

- Inspeção do workspace, boards visíveis relacionados, views, grupos, colunas, exemplos, filtros, ordenações, agrupamentos, dashboard e automações.

- Leitura de tipos técnicos das colunas quando expostos pela interface: status, data, fórmula, lookup/mirror, Connect Boards, texto, dropdown, checkbox, número, arquivo e ID.

- Comparação do board principal C2 com o board F2 para identificar padrões, exceções, volume e redundâncias.

- Nenhuma criação, edição, exclusão, movimentação, envio de comentário, execução manual de automação ou mudança de configuração foi realizada.

# 3. Estrutura atual do Monday

| **Nível**         | **Nome**                                                         | **Tipo**         | **Finalidade observada**                                                                     |
|-------------------|------------------------------------------------------------------|------------------|----------------------------------------------------------------------------------------------|
| Workspace         | 08\. Luis Eduardo Magalhães                                      | Área de trabalho | Concentra planejamento, aquisições, equipamentos e contratos da unidade.                     |
| Pasta/agrupador   | 3 - Planejamento Engenharia & Aquisições                         | Agrupador        | Contém boards de equipamentos C2 e F2.                                                       |
| Board principal   | Equipamentos - LEM C2                                            | Board privado    | Controla 41 equipamentos e 164 subitens ao longo do fluxo de aquisição.                      |
| Board comparativo | Equipamentos LEM F2                                              | Board privado    | Processo semelhante, com 77 equipamentos, 540 subitens e Kanban.                             |
| Pasta/agrupador   | 5 - Contratos                                                    | Agrupador        | Agrupa conteúdo contratual da unidade; não foi confirmado como relacionamento técnico do C2. |
| Board visível     | Contratos Luis Eduardo Magalhães                                 | Board            | Provável cadastro/controle de contratos; dependência direta não confirmada.                  |
| Boards visíveis   | Histograma de Obra; Previsão da Obra - Sábado, Domingo e Feriado | Boards           | Contexto de planejamento; relação direta com equipamentos não confirmada.                    |

# 4. Boards e visualizações

| **Board / view**                                        | **Estrutura**                               | **Volume / filtros**                                                          | **Papel no processo**                                                      |
|---------------------------------------------------------|---------------------------------------------|-------------------------------------------------------------------------------|----------------------------------------------------------------------------|
| C2 - Quadro principal                                   | Tabela, grupos por fase                     | 41 equipamentos; 164 subitens                                                 | Fonte operacional completa.                                                |
| C2 - Engenharia MetalMec                                | Tabela filtrada, agrupada por 0.Responsável | 10 de 41; 3 filtros; 5 colunas ocultas; 1 agrupamento                         | Fila de engenharia por responsável e disciplina.                           |
| C2 - Jurídico                                           | Tabela filtrada                             | 6 de 41; 2 filtros; 17 colunas ocultas                                        | Pendências jurídicas/contratuais entre abertura de chamado e escrituração. |
| C2 - Suprimentos                                        | Tabela filtrada, agrupada e ordenada        | 0 de 41; 2 filtros; 3 ordenações; 8 colunas ocultas; agrupada por responsável | Fila de Suprimentos atualmente sem resultado.                              |
| C2 - Gráfico                                            | Dashboard                                   | 12 widgets visíveis                                                           | Indicadores de prazos, status, negociação, OC, CAPEX e índices.            |
| F2 - Quadro principal                                   | Tabela, grupos por fase                     | 77 equipamentos; 540 subitens                                                 | Referência mais madura e populada.                                         |
| F2 - Kanban                                             | Kanban por A.Status                         | Filtro ativo; 36 em Nova demanda e 12 em Não se Aplica no recorte visível     | Gestão visual por estado; expõe estados adicionais.                        |
| F2 - Engenharia MetalMec / Jurídico / Status Negociação | Views filtradas                             | Não detalhadas integralmente                                                  | Variações por função e acompanhamento de prazo.                            |

# 5. Grupos, volumes e estados

| **Grupo C2**                      | **Equipamentos** | **Subitens** | **Interpretação**                                          |
|-----------------------------------|------------------|--------------|------------------------------------------------------------|
| Fase 0 - Nova Demanda             | 31               | 55           | Entrada, classificação técnica e preparação.               |
| Fase 1 - Negociação               | 0                | \-           | Negociação iniciada.                                       |
| Fase 2 - Equalização              | 0                | \-           | Equalização técnica/comercial.                             |
| Fase 3 - Abertura do Chamado      | 0                | \-           | Acionamento jurídico.                                      |
| Fase 4 - Aprovação da Minuta      | 6                | 8            | Análise e aprovação de minuta.                             |
| Fase 5 - Escrituração do Contrato | 0                | \-           | Formalização contratual.                                   |
| Fase 6 - SC ou OCI                | 3                | 77           | Solicitação de compra/OCI.                                 |
| Fase 7 - Aprovação da OC          | 0                | \-           | Emissão/aprovação da ordem de compra.                      |
| Fase 8 - Concluído                | 1                | 24           | Aquisição concluída.                                       |
| Total observado                   | 41               | 164          | Dashboard apresenta 163 aquisições; divergência a validar. |

# 6. Dicionário de dados - Equipamento

| **Board** | **Campo**                       | **Tipo**       | **Exemplo**                                         | **Regra/origem**                   | **Dependência**                           | **Uso**                                   |
|-----------|---------------------------------|----------------|-----------------------------------------------------|------------------------------------|-------------------------------------------|-------------------------------------------|
| C2        | Equipamento                     | Nome           | Visores de nível                                    | Manual                             | Registro mestre                           | Identificação do pacote/equipamento       |
| C2        | Status Negociação               | Fórmula        | NO PRAZO / ATRASADO / URGENTE / PRÓXIMO / CONCLUÍDO | Calculado                          | Datas e marcos                            | Sinalização automática de prazo           |
| C2        | F.Data Limite Negociação        | Fórmula        | Data ou vazio                                       | Calculado                          | Startup/lead time                         | Prazo-limite da negociação                |
| C2        | Status Necessidade Obra         | Fórmula        | PRAZO SEGURO / \<30 DIAS                            | Calculado                          | Entrega e necessidade                     | Risco da necessidade em obra              |
| C2        | F.Limite Entrega Obra           | Fórmula        | Data ou vazio                                       | Calculado                          | Startup/lead time/frete                   | Data-limite para chegada em obra          |
| C2        | A.Status                        | Status         | 0.Nova demanda                                      | Automação + eventual ajuste manual | Grupos e marcos                           | Estado canônico do workflow               |
| C2        | 0.Fornecedores                  | Connect Boards | N/D                                                 | Relacionamento                     | Board conectado não exposto com segurança | Fornecedor(es) relacionados               |
| C2        | 0.Origem                        | Status         | A definir                                           | Manual                             | Cadastro                                  | Origem da demanda/aquisição               |
| C2        | 0.Startup/Grãos                 | Data           | 27/10/2027                                          | Manual                             | Planejamento                              | Marco de startup                          |
| C2        | 0.Disciplina                    | Etiqueta/label | E&I; Automação; Metal Mec.                          | Manual                             | Catálogo de disciplinas                   | Roteamento por área técnica               |
| C2        | F.Data Limite para contrato/OC  | Fórmula        | Data ou vazio                                       | Calculado                          | Marcos do processo                        | Prazo consolidado do contrato/OC          |
| C2        | 0.Criticidade                   | Prioridade     | Curto \<90; Médio 90~180; Longo \>180               | Manual/derivado a confirmar        | Prazos                                    | Classificação temporal de criticidade     |
| C2        | E.Data de Entrega contrato      | Lookup/Mirror  | Data espelhada                                      | Automático                         | Campo relacionado                         | Disponibiliza entrega contratual          |
| C2        | 0.Responsável                   | Texto          | Ediel; Uilson                                       | Manual                             | Sem vínculo de identidade                 | Responsável operacional                   |
| C2        | 0.Área                          | Texto          | Caldeira; Geral                                     | Manual                             | Cadastro livre                            | Área/setor do equipamento                 |
| C2        | Work Package                    | Dropdown       | EIA001; CIV001; MEC001                              | Manual                             | Pacotes de trabalho                       | Vinculação ao pacote de engenharia        |
| C2        | 1.Equalização                   | Checkbox       | Marcado/desmarcado                                  | Manual                             | Workflow                                  | Marco de equalização                      |
| C2        | 2.Data da Negociação            | Data           | Data ou vazio                                       | Manual                             | Workflow                                  | Conclusão/início registrado da negociação |
| C2        | 3.Data de Abertura do Chamado   | Data           | Data ou vazio                                       | Manual                             | Jurídico                                  | Abertura do chamado jurídico              |
| C2        | 3.Chamado Jurídico              | Texto          | Número/referência                                   | Manual                             | Jurídico                                  | Identificador do chamado                  |
| C2        | 3.Elab. Minuta                  | Checkbox       | Marcado/desmarcado                                  | Manual                             | Jurídico                                  | Minuta elaborada                          |
| C2        | 4.Minuta Aprovada               | Checkbox       | Marcado/desmarcado                                  | Manual                             | Jurídico                                  | Minuta aprovada                           |
| C2        | 5.Data Escrituração             | Data           | Data ou vazio                                       | Manual                             | Contrato                                  | Data de escrituração                      |
| C2        | 5.Numero Contrato               | Texto          | Número                                              | Manual                             | Contrato                                  | Identificação contratual                  |
| C2        | 5.Data de Entrega pelo contrato | Data           | Data ou vazio                                       | Manual                             | Contrato                                  | Compromisso de entrega                    |
| C2        | 6.Data de SC/OCI                | Data           | Data ou vazio                                       | Manual                             | Suprimentos                               | Data da solicitação/OCI                   |
| C2        | 6.Numero SC/OCI                 | Texto          | Número                                              | Manual ou automação de bypass      | Suprimentos                               | Identificador SC/OCI                      |
| C2        | 7.Data OC                       | Data           | Data ou vazio                                       | Manual                             | Suprimentos                               | Data da ordem de compra                   |
| C2        | 7.Numero OC                     | Texto          | Número                                              | Manual                             | Suprimentos                               | Identificador da OC                       |
| C2        | E.Lead Time de Fabricação       | Lookup/Mirror  | 145                                                 | Automático                         | Subitens/relacionamento                   | Prazo espelhado de fabricação             |
| C2        | Espelho/Fórmula2                | Lookup/Mirror  | Vazio                                               | Automático                         | Campo relacionado                         | Campo técnico auxiliar                    |
| C2        | E.Dias Antes do Startup         | Lookup/Mirror  | Vazio                                               | Automático                         | Subitens/planejamento                     | Antecedência consolidada                  |
| C2        | ESPELHO-FORMULA-FRETE           | Lookup/Mirror  | 5                                                   | Automático                         | Subitens                                  | Frete consolidado                         |
| C2        | Kickoff                         | Data           | Data ou vazio                                       | Manual                             | Notificação                               | Dispara aviso aos inscritos               |
| C2        | Leadtime Negociação             | Fórmula        | 0 ou vazio                                          | Calculado                          | Datas de negociação                       | Duração da negociação                     |
| C2        | Prazo Máximo Negociação         | Fórmula        | Data ou vazio                                       | Calculado                          | Criticidade/prazos                        | Limite máximo de negociação               |
| C2        | CAPEX Estimado                  | Número         | Valor monetário                                     | Manual                             | Financeiro                                | Orçamento estimado                        |

# 7. Dicionário de dados - Subitem / componente

| **Campo**                      | **Tipo** | **Exemplo**               | **Origem**       | **Uso**                                                       |
|--------------------------------|----------|---------------------------|------------------|---------------------------------------------------------------|
| Subelemento                    | Nome     | Válvula elétrica Caldeira | Manual           | Identifica componente/linha de aquisição.                     |
| TAG                            | Texto    | Vazio no exemplo          | Manual           | Identificação técnica do componente.                          |
| 0.Startup/Grãos                | Data     | 27/10/2027                | Manual/replicado | Marco de startup do componente.                               |
| Data Limite de Entrega em Obra | Fórmula  | Vazio                     | Calculado        | Limite de entrega do componente.                              |
| Setor                          | Dropdown | CALDEIRA                  | Manual           | Setor/área funcional.                                         |
| Prazo Neg                      | Fórmula  | Vazio                     | Calculado        | Prazo de negociação.                                          |
| Lead Time de Fabricação        | Número   | 160                       | Manual           | Tempo do fornecedor/fabricação.                               |
| Disponivel Coleta              | Fórmula  | Vazio                     | Calculado        | Previsão de disponibilidade para coleta.                      |
| 0.Dias Antes do Startup        | Número   | 140                       | Manual           | Antecedência necessária.                                      |
| Data de Entrega pelo contrato  | Data     | Vazio                     | Manual           | Compromisso contratual do componente.                         |
| Entrega planejada vs negociada | Fórmula  | Vazio                     | Calculado        | Comparação de aderência.                                      |
| Status da Data de Entrega      | Fórmula  | Vazio                     | Calculado        | Sinal de risco de entrega.                                    |
| Arquivos                       | Arquivo  | Vazio                     | Manual           | Documentos do componente.                                     |
| Frete (Dias)                   | Número   | 10                        | Manual           | Prazo logístico.                                              |
| FÓRMULA-NÃO MEXER              | Fórmula  | Vazio                     | Calculado        | Campo auxiliar técnico; não deve virar campo editável no Hub. |
| F.Data Limite Negociação_calc  | Fórmula  | Vazio                     | Calculado        | Cálculo auxiliar de prazo.                                    |
| ID do elemento                 | Item ID  | Sem valor exibido         | Automático       | Identificador técnico do Monday.                              |

# 8. Relacionamentos identificados

| **Origem**             | **Relacionamento** | **Destino / cardinalidade**                 | **Evidência**                                      | **Proposta no Hub**                        |
|------------------------|--------------------|---------------------------------------------|----------------------------------------------------|--------------------------------------------|
| Projeto/unidade        | contém             | Muitos equipamentos                         | Boards C2 e F2 dentro de LEM                       | project_context 1:N equipment              |
| Equipamento            | possui             | Muitos componentes/subitens                 | 164 subitens no C2; 540 no F2                      | equipment 1:N equipment_component          |
| Equipamento            | relaciona          | Um ou mais fornecedores                     | 0.Fornecedores é Connect Boards                    | equipment_supplier N:N supplier            |
| Equipamento            | pertence           | Área, disciplina e work package             | Campos 0.Área, 0.Disciplina, Work Package          | FKs estruturadas                           |
| Equipamento            | é conduzido por    | Responsável                                 | 0.Responsável em texto e views agrupadas           | FK para user; histórico de atribuição      |
| Equipamento            | executa            | Uma instância de workflow                   | A.Status + grupos 0 a 8                            | workflow_instance + transition_history     |
| Equipamento            | possui             | Negociação, jurídico, contrato, SC/OCI e OC | Marcos numerados 1 a 7                             | Entidades/processos separados, 1:1 inicial |
| Componente             | produz             | Prazos e indicadores consolidados           | Lookup/Mirror no equipamento                       | Agregações SQL/API sem duplicação          |
| Equipamento/componente | possui             | Arquivos, comentários e histórico           | Arquivo em subitem; conversa/atividade disponíveis | attachment, comment e audit_event          |

# 9. Fluxo operacional e status

| **Etapa** | **Status**               | **Atividade**                                                                            | **Critério principal observado**                           |
|-----------|--------------------------|------------------------------------------------------------------------------------------|------------------------------------------------------------|
| 0         | Nova demanda             | Criar demanda; classificar origem, startup, disciplina, criticidade, área e work package | Cadastro mínimo                                            |
| 1         | Negociação               | Iniciar negociação                                                                       | Ação/botão de reinício ou entrada do fluxo                 |
| 2         | Equalização              | Registrar equalização                                                                    | 1.Equalização alterado; data da negociação ainda vazia     |
| 3         | Abertura do chamado      | Registrar negociação e iniciar jurídico                                                  | 2.Data da Negociação preenchida; chamado/data ainda vazios |
| 4         | Aprovação da minuta      | Concluir abertura do chamado e elaborar minuta                                           | Combina data, número do chamado e elaboração               |
| 5         | Escrituração do contrato | Aprovar minuta e formalizar contrato                                                     | 4.Minuta Aprovada e marcos jurídicos preenchidos           |
| 6         | SC ou OCI                | Registrar escrituração/número do contrato e solicitar compra                             | Data/número do contrato e requisitos jurídicos             |
| 7         | Aprovação da OC          | Registrar SC/OCI e emitir OC                                                             | Data e número de SC/OCI                                    |
| 8         | Concluído                | Registrar OC e entrega contratual; concluir                                              | OC, contrato e marcos anteriores preenchidos               |

Estados adicionais confirmados no Kanban do board F2: 9.Standby, CANCELADO e Não se Aplica. A adoção desses estados no C2 precisa ser decidida explicitamente.

# 10. Automações existentes

| **Descrição**             | **Gatilho**                  | **Condição**                                                | **Ação**                                       | **Objetivo**                     |
|---------------------------|------------------------------|-------------------------------------------------------------|------------------------------------------------|----------------------------------|
| 8 - OC B                  | 7.Numero OC muda             | Status=7 e marcos anteriores preenchidos                    | Status=8; mover para Fase 8                    | Concluir por número da OC        |
| 4 - Minuta C              | 3.Elab. Minuta muda          | Status=3; negociação, abertura e chamado preenchidos        | Status=4; mover para Fase 4                    | Avançar jurídico                 |
| 5 - Aprovação da Minuta A | 4.Minuta Aprovada muda       | Status=4; minuta e marcos anteriores preenchidos            | Status=5; mover para Fase 5                    | Avançar para contrato            |
| 8 - OC C                  | 5.Data de Entrega muda       | Status=7; contrato, SC/OCI e OC completos                   | Status=8; mover para Fase 8                    | Concluir por entrega contratual  |
| 4 - Minuta B              | 3.Data de Abertura muda      | Status=2; chamado e data preenchidos                        | Status=4; mover para Fase 4                    | Atalho condicionado para minuta  |
| FUP                       | Status muda                  | Qualquer valor configurado                                  | Notificar grupo fixo de pessoas                | Follow-up operacional            |
| 7 - SC ou OCI A           | 6.Numero SC/OCI muda         | Status=6; data SC/OCI preenchida                            | Status=7; mover para Fase 7                    | Avançar para OC                  |
| 8 - OC A                  | 7.Data OC muda               | Status=7; número OC, contrato e marcos completos            | Status=8; mover para Fase 8                    | Concluir por data da OC          |
| 3 - Chamado Jurídico A    | 2.Data da Negociação muda    | Status=2; data e chamado jurídico vazios                    | Status=3; mover para Fase 3                    | Abrir etapa jurídica             |
| Reiniciar Negociação      | Botão clicado                | Sem condição adicional visível                              | Mover para Fase 1; Status=1                    | Reabrir fluxo                    |
| 4 - Minuta A              | 3.Chamado Jurídico muda      | Data abertura preenchida; Status=3; negociação preenchida   | Status=4; mover para Fase 4                    | Avançar por chamado              |
| Clear Button - Auxiliar   | Botão clicado                | Não exposta                                                 | Limpar coluna                                  | Ação auxiliar                    |
| 2 - Equalização A         | 1.Equalização muda           | Status=1; data negociação vazia                             | Status=2; mover para Fase 2                    | Avançar equalização              |
| 7 - SC ou OCI B           | 6.Data de SC/OCI muda        | Status=6; número SC/OCI preenchido                          | Status=7; mover para Fase 7                    | Avançar por data da SC           |
| 6 - Escrituração B        | 5.Numero Contrato muda       | Data escrituração preenchida; Status=5; abertura preenchida | Status=6; mover para Fase 6                    | Avançar por número do contrato   |
| 7 - Bypass Suprimentos A  | Botão clicado                | Status=6; contrato completo                                 | Status=7; mover; IA escreve em 6.Numero SC/OCI | Bypass manual de Suprimentos     |
| 6 - Escrituração A        | 5.Data Escrituração muda     | Número contrato preenchido; Status=5; minuta elaborada      | Status=6; mover para Fase 6                    | Avançar por data de escrituração |
| Escalonamento             | Coluna muda e não está vazia | Campo/board não expostos                                    | Criar item em outro board e conectar           | Escalonar para board dependente  |
| Concluisão                | A.Status muda para 8         | Status=8                                                    | Mover para Fase 8                              | Sincronizar grupo e status       |
| 0 - Nova Demanda A        | Item criado                  | Novo item                                                   | A.Status=Undefined; mover para Fase 0          | Inicializar demanda              |
| Pronto para uso           | Kickoff chega                | Data atingida                                               | Notificar inscritos do item                    | Lembrete de kickoff              |

<table>
<colgroup>
<col style="width: 100%" />
</colgroup>
<thead>
<tr class="header">
<th><strong>Implicação técnica<br />
</strong>As automações devem virar regras transacionais no backend. Uma única operação de transição deve validar pré-condições, atualizar o estágio, registrar histórico e publicar notificações. Isso elimina duplicações como as três rotas para concluir e as múltiplas rotas para avançar entre fases.</th>
</tr>
</thead>
<tbody>
</tbody>
</table>

# 11. Filtros, agrupamentos e modo de trabalho

| **View**            | **Filtros confirmados**                                                                                                            | **Agrupamento / ordenação**                                                           | **Leitura operacional**                                       |
|---------------------|------------------------------------------------------------------------------------------------------------------------------------|---------------------------------------------------------------------------------------|---------------------------------------------------------------|
| Engenharia MetalMec | A.Status em 4 valores; 0.Disciplina em 2 valores incluindo Metal Mec.; Status Negociação não está em 2 valores incluindo CONCLUÍDO | Agrupado por 0.Responsável; A-Z                                                       | Carteira técnica ativa por responsável; 10 de 41 itens.       |
| Jurídico            | A.Status em 3 valores a partir de 3.Abertura do chamado; e grupo OR com data/chamado/minuta/contrato/entrega pendentes             | Sem agrupamento salvo visível                                                         | Fila de pendências jurídicas e contratuais; 6 itens.          |
| Suprimentos         | A.Status não é 8.Concluído + 1 valor; e (Disciplina=Suprimentos OU Responsável em valor não exibido)                               | Agrupado por 0.Responsável A-Z; ordenado por A.Status, Disciplina e Status Negociação | Fila atualmente vazia; requer revisão de filtros e cadastros. |
| Quadro principal    | Sem filtros salvos visíveis                                                                                                        | Grupos por etapa                                                                      | Visão operacional completa.                                   |

# 12. Dashboards e indicadores

| **Widget**                                  | **Tipo**                    | **Resultado observado**                                     | **Finalidade**               |
|---------------------------------------------|-----------------------------|-------------------------------------------------------------|------------------------------|
| Prazo de negociação vencido ou próximo      | Barra por Status Negociação | ATRASADO=1; URGENTE=1; PRÓXIMO=1                            | Priorização de prazo         |
| Quantidade por status                       | Contagem por A.Status       | Nova demanda=31; Aprovação da Minuta=6; SC=3; Concluído=1   | Distribuição do pipeline     |
| Status dos prazos de negociação             | Pizza por fórmula de prazo  | ATRASADO=1; URGENTE=1; PRÓXIMO=1; NO PRAZO=28; CONCLUÍDO=10 | Saúde dos prazos             |
| Status de Conclusão de Negociações - Fase 1 | Gauge                       | 0 concluídas / 163 aquisições                               | Acompanhamento de negociação |
| Contagem regressiva para Startup Fase 1     | Contador                    | Valor não exposto no recorte acessível                      | Ritmo até startup            |
| Emissões de Ordem de Compra                 | Gauge                       | 0 emitidas / 163 OCs                                        | Acompanhamento de OC         |
| Total Emitido (R\$) em OC's Atual           | Valor                       | Valor não exposto                                           | Financeiro                   |
| Total de Aquisições                         | Valor                       | Widget visível; valor não exposto separadamente             | Volume                       |
| Índice Geral de Aquisição por Disciplina    | Gráfico                     | Nenhum resultado                                            | Comparativo por disciplina   |
| Índice de Aderência Médio                   | Média                       | 0                                                           | Aderência de entrega         |
| Índice de Criticidade Médio                 | Média                       | 0                                                           | Criticidade                  |
| Índice Geral Aquisição Médio                | Média                       | 0                                                           | Índice consolidado           |

# 13. Funcionalidades e criticidade

| **Funcionalidade**                      | **Classificação**    | **Justificativa**                                                                                             |
|-----------------------------------------|----------------------|---------------------------------------------------------------------------------------------------------------|
| Cadastro de equipamento e subitem       | Essencial            | Base do processo e volume operacional.                                                                        |
| Workflow 0-8 com validações             | Essencial            | Substitui grupos, status e automações de avanço.                                                              |
| Busca, filtros, ordenação e agrupamento | Essencial            | Usados nas views de equipe.                                                                                   |
| Prazos e fórmulas                       | Essencial            | Alimentam alertas e dashboard.                                                                                |
| Responsável e filas por equipe          | Essencial            | Engenharia e Suprimentos trabalham por responsável.                                                           |
| Fornecedor e relacionamento             | Essencial            | Connect Boards existente; normalização necessária.                                                            |
| Notificações de FUP e kickoff           | Essencial            | Automação explícita e acompanhamento diário.                                                                  |
| Dashboard operacional                   | Essencial            | Visão executiva do pipeline e riscos.                                                                         |
| Histórico/auditoria                     | Essencial            | Substitui atividade do board e dá rastreabilidade.                                                            |
| Arquivos                                | Importante           | Campo presente no subitem; uso real precisa ser confirmado.                                                   |
| Comentários/conversas                   | Importante           | Controles disponíveis; frequência não confirmada.                                                             |
| Kanban                                  | Importante           | Usado no F2; ausente no C2.                                                                                   |
| Exportação                              | Importante           | Disponível no dashboard/board.                                                                                |
| Filtros salvos por função               | Importante           | Engenharia, Jurídico e Suprimentos têm views específicas.                                                     |
| IA para preencher SC/OCI                | Redundante/arriscado | Pode produzir identificador não determinístico; deve ser removido ou substituído por valor técnico explícito. |
| Botões auxiliares de limpar/reiniciar   | Auxiliar             | Devem virar ações controladas com confirmação e auditoria.                                                    |

# 14. Perfis e permissões propostos

| **Perfil**              | **Permissões sugeridas**                                                                                         |
|-------------------------|------------------------------------------------------------------------------------------------------------------|
| Administrador           | Configura catálogos, workflow, permissões e integrações; acessa auditoria completa.                              |
| Planejamento/Engenharia | Cria demanda, classifica equipamento, mantém área, disciplina, work package, criticidade, startup e equalização. |
| Jurídico                | Mantém chamado, minuta, aprovação e dados de contrato; consulta contexto técnico.                                |
| Suprimentos             | Mantém SC/OCI, OC, fornecedores, custos e prazos de aquisição.                                                   |
| Gestor                  | Consulta todas as unidades, dashboards, exceções e aprovações definidas.                                         |
| Consulta                | Somente leitura, exportação conforme política e sem ações de transição.                                          |

Evidência disponível: ambos os boards são privados; o C2 mostra 27 convidados e o F2 mostra 12. A granularidade real de permissões por usuário não ficou exposta na navegação de leitura.

# 15. Redundâncias, inconsistências e limitações

| **Prioridade** | **Achado**                                               | **Impacto**                                                     | **Tratamento proposto**                                               |
|----------------|----------------------------------------------------------|-----------------------------------------------------------------|-----------------------------------------------------------------------|
| Alta           | A.Status e grupo representam a mesma etapa               | Risco de divergência se automação falhar                        | Um único estado no banco; views agrupam por ele.                      |
| Alta           | 21 automações duplicam validações                        | Manutenção difícil e resultados inconsistentes                  | State machine transacional no FastAPI.                                |
| Alta           | Bypass de Suprimentos usa IA para escrever número SC/OCI | Dado não determinístico em campo identificador                  | Exigir justificativa e valor técnico; não gerar identificador por IA. |
| Alta           | Dashboard 163 vs soma de 164 subitens                    | Indicador possivelmente exclui um registro sem transparência    | Definir métrica e teste automatizado.                                 |
| Média          | 0.Responsável é texto                                    | Nomes inconsistentes; notificações frágeis                      | FK para usuário/equipe corporativa.                                   |
| Média          | Fornecedor é relacionamento no C2 e texto no F2          | Modelo divergente entre boards                                  | Cadastro único de fornecedores + relação N:N.                         |
| Média          | Fórmulas mostram erro quando faltam dados                | Ruído e baixa confiança                                         | Retornar estado 'não calculável' com motivo.                          |
| Média          | Campos auxiliares com nomes técnicos                     | FÓRMULA-NÃO MEXER, Espelho/Fórmula2                             | Ocultar implementação e expor conceitos de negócio.                   |
| Média          | Campos antigos/duplicados no F2                          | z.0.Área (texto antigo); z.F.Limite Entrega Obra (duplicada)    | Migração com mapeamento e descarte controlado após validação.         |
| Média          | Suprimentos retorna zero itens                           | View pode estar desatualizada ou sem cadastros compatíveis      | Validar filtros e responsabilidades.                                  |
| Baixa          | Estados adicionais somente no F2                         | Standby, Cancelado e Não se Aplica não aparecem no fluxo C2     | Unificar catálogo ou parametrizar por projeto.                        |
| Baixa          | Automação inicial usa status Undefined                   | Contrasta com grupo Fase 0 e dados exibidos como 0.Nova demanda | Inicializar diretamente no estado correto.                            |

# 16. Arquitetura proposta para o Hub

## 16.1 Visão de componentes

| **Camada**      | **Tecnologia**                           | **Responsabilidade**                                                                      |
|-----------------|------------------------------------------|-------------------------------------------------------------------------------------------|
| Frontend        | Nuxt 4 + Vue 3 + TypeScript              | Listas, detalhe, workflow, formulários, dashboards, filtros salvos e gestão por perfil.   |
| API             | FastAPI + Python                         | Regras de domínio, state machine, validações, cálculo de prazos, autorização e auditoria. |
| Persistência    | PostgreSQL                               | Dados normalizados, histórico de transições, anexos e índices para busca/filtros.         |
| Jobs            | Worker/agenda                            | Notificações de kickoff, prazos, reprocessamento de cálculos e integrações.               |
| Identidade      | SSO corporativo                          | Usuários, equipes e papéis; mapear identidade real em vez de texto.                       |
| Arquivos        | Object storage + metadados no PostgreSQL | Documentos de equipamentos/componentes com controle de acesso.                            |
| Observabilidade | Logs estruturados + métricas             | Transições, falhas de notificação, cálculos e integrações.                                |

## 16.2 Princípios de domínio

- Separar dado mestre (equipamento/componente) do processo de aquisição (negociação, jurídico, contrato, SC e OC).

- Centralizar transições no backend; o frontend solicita a transição e recebe pré-condições faltantes.

- Calcular prazos no backend a partir de dados primários, mantendo explicação do cálculo e data de referência.

- Registrar toda mudança relevante em audit_event, inclusive valor anterior, novo valor, usuário, origem e correlação.

- Tratar views como consultas salvas, não como cópias de dados.

- Parametrizar estados e regras por contexto de projeto quando C2 e F2 realmente divergirem.

# 17. Modelo conceitual do banco

| **Entidade**        | **Campos principais**                                                                                                                      | **Finalidade**                               |
|---------------------|--------------------------------------------------------------------------------------------------------------------------------------------|----------------------------------------------|
| project_context     | id, unit_id, code, name, active                                                                                                            | Contexto C2/F2 da unidade.                   |
| unit                | id, code, name                                                                                                                             | Unidade corporativa.                         |
| area                | id, unit_id, name                                                                                                                          | Área/setor estruturado.                      |
| discipline          | id, code, name                                                                                                                             | E&I, Automação, Metal Mec., Suprimentos etc. |
| work_package        | id, project_context_id, code, name                                                                                                         | Pacote de engenharia.                        |
| equipment           | id, project_context_id, name, origin, startup_at, discipline_id, area_id, responsible_user_id, criticality, current_stage, capex_estimated | Registro mestre.                             |
| equipment_component | id, equipment_id, name, tag, sector_id, lead_time_days, pre_start_days, contract_delivery_at, freight_days                                 | Subitem/componente.                          |
| supplier            | id, legal_name, trade_name, tax_id, active                                                                                                 | Cadastro único.                              |
| equipment_supplier  | equipment_id, supplier_id, role, is_primary                                                                                                | Relacionamento N:N.                          |
| negotiation         | id, equipment_id, equalized, negotiated_at, max_deadline_at                                                                                | Etapa comercial/técnica.                     |
| legal_process       | id, equipment_id, opened_at, ticket_number, draft_prepared, draft_approved                                                                 | Etapa jurídica.                              |
| contract            | id, equipment_id, contract_number, executed_at, delivery_at                                                                                | Contrato.                                    |
| purchase_request    | id, equipment_id, kind, request_number, requested_at                                                                                       | SC ou OCI.                                   |
| purchase_order      | id, equipment_id, order_number, ordered_at, amount                                                                                         | Ordem de compra.                             |
| workflow_transition | id, equipment_id, from_stage, to_stage, reason, actor_id, occurred_at                                                                      | Histórico imutável de transições.            |
| attachment          | id, equipment_id, component_id, storage_key, filename, mime_type, uploaded_by                                                              | Arquivos.                                    |
| comment             | id, equipment_id, component_id, author_id, body, created_at                                                                                | Conversas, se confirmadas para o MVP.        |
| notification        | id, user_id, type, payload, status, scheduled_at, sent_at                                                                                  | FUP, kickoff e alertas.                      |
| saved_view          | id, owner_scope, name, filters_json, sort_json, group_by                                                                                   | Views por equipe/usuário.                    |
| audit_event         | id, entity_type, entity_id, action, before_json, after_json, actor_id, created_at                                                          | Auditoria técnica e funcional.               |

## 17.1 Relações principais

- Unit 1:N ProjectContext 1:N Equipment 1:N EquipmentComponent.

- Equipment N:N Supplier por EquipmentSupplier.

- Equipment N:1 Area, Discipline, WorkPackage e User responsável.

- Equipment 1:1 inicial com Negotiation, LegalProcess, Contract, PurchaseRequest e PurchaseOrder; permitir 1:N se o processo real admitir múltiplos documentos.

- Equipment 1:N WorkflowTransition, Attachment, Comment, Notification e AuditEvent.

# 18. Backend - módulos e endpoints REST

| **Módulo**   | **Endpoints**                                                                          | **Objetivo**                                         |
|--------------|----------------------------------------------------------------------------------------|------------------------------------------------------|
| Catálogos    | GET/POST/PATCH /units, /areas, /disciplines, /work-packages, /suppliers                | Cadastros estruturados e permissões administrativas. |
| Equipamentos | GET /equipments; POST /equipments; GET/PATCH /equipments/{id}                          | Listagem, criação, detalhe e atualização.            |
| Componentes  | GET/POST /equipments/{id}/components; PATCH /components/{id}                           | Subitens técnicos.                                   |
| Fornecedores | GET/POST/DELETE /equipments/{id}/suppliers                                             | Relacionamento de fornecedores.                      |
| Workflow     | GET /equipments/{id}/available-transitions; POST /equipments/{id}/transitions          | Validação e avanço/reabertura do processo.           |
| Negociação   | GET/PATCH /equipments/{id}/negotiation                                                 | Equalização, datas e prazos.                         |
| Jurídico     | GET/PATCH /equipments/{id}/legal                                                       | Chamado e minuta.                                    |
| Contrato     | GET/PATCH /equipments/{id}/contract                                                    | Escrituração, número e entrega.                      |
| Suprimentos  | GET/PATCH /equipments/{id}/purchase-request; GET/PATCH /equipments/{id}/purchase-order | SC/OCI e OC.                                         |
| Arquivos     | GET/POST /equipments/{id}/attachments; DELETE /attachments/{id}                        | Documentos com autorização.                          |
| Histórico    | GET /equipments/{id}/history; GET /audit-events                                        | Rastreabilidade.                                     |
| Views        | GET/POST/PATCH /saved-views                                                            | Filtros, ordenação e agrupamento.                    |
| Dashboards   | GET /dashboard/summary; /status; /deadlines; /procurement; /indices                    | Widgets calculados por API.                          |
| Notificações | GET /notifications; PATCH /notifications/{id}/read                                     | Alertas e caixa de entrada.                          |
| Exportação   | POST /exports/equipments                                                               | CSV/XLSX conforme filtros e permissão.               |

# 19. Frontend - telas sugeridas

| **Rota**                         | **Conteúdo**                                                                   |
|----------------------------------|--------------------------------------------------------------------------------|
| /equipamentos                    | Tabela principal com filtros, busca, ordenação, agrupamento e seleção de view. |
| /equipamentos/kanban             | Kanban por estágio; movimento permitido apenas via transição validada.         |
| /equipamentos/\[id\]             | Resumo do equipamento, dados mestres, prazos e ações disponíveis.              |
| /equipamentos/\[id\]/componentes | Subitens, tags, lead times, frete, entrega e arquivos.                         |
| /equipamentos/\[id\]/historico   | Timeline de mudanças, transições, notificações e comentários.                  |
| /negociacoes                     | Fila de negociação/equalização e alertas de prazo.                             |
| /juridico                        | Fila equivalente à view Jurídico, com pendências explícitas.                   |
| /suprimentos                     | Fila SC/OCI/OC, fornecedor, CAPEX e emissão.                                   |
| /dashboard                       | Status, prazos, negociações, OCs, valores e índices.                           |
| /fornecedores                    | Cadastro e vínculo com equipamentos.                                           |
| /relatorios                      | Exportações e consultas salvas.                                                |
| /configuracoes/catalogos         | Áreas, disciplinas, work packages, criticidades e estados.                     |
| /configuracoes/workflow          | Regras de transição e notificações, apenas administradores.                    |

# 20. Matriz Monday → Hub

| **Monday atual**         | **Função**                    | **Hub proposto**                       | **Observação**                           |
|--------------------------|-------------------------------|----------------------------------------|------------------------------------------|
| Board C2/F2              | Contexto do projeto           | project_context + unit                 | Evita duplicar schema por board.         |
| Item                     | Equipamento/pacote            | equipment                              | Registro mestre.                         |
| Subitem                  | Componente/linha de aquisição | equipment_component                    | Estrutura 1:N.                           |
| Grupo                    | Etapa visual                  | current_stage + consulta agrupada      | Grupo deixa de armazenar estado.         |
| A.Status                 | Workflow                      | Enum/configuração + transition_history | Estado único e auditável.                |
| Connect Boards           | Fornecedor relacionado        | FK/tabela associativa                  | Relacionamento nativo.                   |
| Mirror/Lookup            | Dado agregado                 | JOIN/consulta/API                      | Sem duplicação persistida desnecessária. |
| Fórmula                  | Prazo/indicador               | Serviço de cálculo testado             | Explicação e tratamento de ausência.     |
| People/texto responsável | Responsável                   | user_id/team_id                        | Identidade corporativa.                  |
| Status/label/dropdown    | Catálogo                      | FK/enum parametrizável                 | Validação central.                       |
| Checkbox                 | Marco concluído               | Boolean + completed_at/actor           | Mais rastreável que boolean isolado.     |
| Automações               | Regra de negócio              | State machine + domain events          | Transação única.                         |
| View filtrada            | Fila por função               | saved_view + endpoints filtrados       | Reutilizável e segura.                   |
| Dashboard                | Indicador                     | Agregação SQL/API                      | Métrica documentada.                     |
| Updates/conversa         | Comentário                    | comment + notification                 | Se confirmado no escopo.                 |
| Atividade do board       | Histórico                     | audit_event + workflow_transition      | Rastreabilidade completa.                |
| Files                    | Anexo                         | Object storage + attachment            | Permissão e versionamento.               |
| Botão                    | Ação contextual               | Comando REST com confirmação           | Sem coluna auxiliar.                     |

# 21. Classificação do escopo

## 21.1 MVP - obrigatório para substituir o Monday

- Autenticação corporativa, perfis e autorização por unidade/contexto.

- Cadastro de equipamentos e componentes/subitens.

- Catálogos de unidade, área, disciplina, work package, criticidade e fornecedor.

- Workflow 0-8 com pré-condições equivalentes às automações e ações de reabertura controlada.

- Dados de negociação, jurídico, contrato, SC/OCI e OC.

- Cálculos de prazo, status de negociação e necessidade em obra.

- Busca, filtros, ordenação, agrupamento e views de Engenharia, Jurídico e Suprimentos.

- Responsáveis vinculados a usuários/equipes; notificações de FUP e kickoff.

- Dashboard mínimo: quantidade por status, prazos, negociação, OC e totais consistentes.

- Histórico de transições e auditoria de alterações.

- Migração inicial do C2 e teste de reconciliação com contagens e indicadores.

## 21.2 Segunda fase

- Kanban completo, filtros pessoais e views compartilhadas.

- Arquivos e comentários, caso o uso diário seja confirmado.

- Exportações avançadas, relatórios agendados e dashboards por disciplina/responsável.

- Integração com board/processo de contratos e com cadastros corporativos.

- Migração do F2 e unificação parametrizada de estados especiais.

- Gestão administrativa de regras de workflow sem deploy.

## 21.3 Melhorias futuras

- Previsão de risco baseada no histórico de lead time, sem substituir decisões humanas.

- Alertas preditivos de atraso e simulação de impacto no startup.

- Portal controlado para fornecedores atualizarem marcos de fabricação/entrega.

- Integração com ERP para SC, OCI, contrato e OC, eliminando digitação duplicada.

- Indicadores de qualidade de dados e reconciliação automática.

# 22. Pontos a confirmar com os usuários do processo

1.  Qual é a definição oficial de equipamento, subitem e aquisição? O dashboard deve contar pais, subitens ou outra unidade?

2.  Por que o dashboard mostra 163 aquisições enquanto os grupos somam 164 subitens?

3.  Quais são as fórmulas exatas de Status Negociação, F.Data Limite Negociação, Status Necessidade Obra, F.Limite Entrega Obra, aderência, criticidade e índice geral?

4.  Qual board é o destino de 0.Fornecedores e da automação Escalonamento?

5.  Os fornecedores devem ser múltiplos por equipamento? Existe fornecedor principal, concorrente e contratado?

6.  0.Responsável deve virar usuário corporativo, equipe, função ou combinação dos três?

7.  Quais quatro estados estão incluídos na view Engenharia e quais dois valores são excluídos de Status Negociação?

8.  Na view Suprimentos, qual é o segundo status excluído e qual valor de responsável compõe o filtro OR?

9.  Os estados Standby, Cancelado e Não se Aplica do F2 também devem existir no C2/Hub?

10. O bypass de Suprimentos ainda é necessário? Qual valor legítimo deve preencher SC/OCI quando aplicado?

11. Há múltiplos contratos, SCs ou OCs por equipamento? Se sim, os relacionamentos devem ser 1:N desde o MVP.

12. Comentários, arquivos e atividade são usados no dia a dia ou apenas estão disponíveis?

13. Quais notificações precisam ser e-mail, Teams, alerta interno ou somente fila no sistema?

14. Quem pode reabrir, cancelar, colocar em standby ou corrigir marcos após avanço de fase?

15. Qual é a origem do CAPEX estimado e do valor emitido em OC? Há moeda e conversão cambial?

16. O Work Package vem de um cadastro corporativo e deve ser integrado a outro sistema?

17. Quais dados do F2 são referência válida e quais campos antigos/duplicados podem ser ignorados na migração?

18. Quais regras de retenção e acesso se aplicam a contratos e anexos jurídicos?

# 23. Recomendação de execução

19. Realizar workshop curto com Engenharia, Jurídico e Suprimentos para fechar as perguntas da seção anterior.

20. Formalizar as fórmulas e o catálogo de estados em testes de aceitação antes de construir telas.

21. Construir primeiro o modelo de dados e a state machine; depois lista/detalhe e views operacionais.

22. Migrar uma amostra do C2 e comparar automaticamente 41 equipamentos, 164 subitens, fases e prazos.

23. Publicar o MVP em paralelo somente para validação; cortar o Monday após reconciliação e aceite dos usuários.

<table>
<colgroup>
<col style="width: 100%" />
</colgroup>
<thead>
<tr class="header">
<th><strong>Critério de substituição<br />
</strong>O Hub estará pronto para substituir o Monday quando conseguir reproduzir o ciclo 0-8, impedir transições inválidas, manter os marcos e relacionamentos, entregar as filas das três áreas, reconciliar os indicadores e preservar histórico/auditoria.</th>
</tr>
</thead>
<tbody>
</tbody>
</table>
