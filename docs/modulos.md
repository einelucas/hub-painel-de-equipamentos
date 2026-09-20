# Módulos

## Base compartilhada

O backend compartilhado possui:

- `audit`: consulta da trilha de atividades;
- `users`: administração de usuários e perfis.

O frontend possui o shell visual do Hub, autenticação, componentes genéricos de UI e charts reutilizáveis.

## Painel de Equipamentos

O domínio possui oito módulos:

- `catalogs`: unidades, contextos, áreas, disciplinas e pacotes de trabalho;
- `equipments`: listagem, criação, edição e componentes;
- `dashboard`: métricas agregadas seguras e distribuição por etapa;
- `processes`: dados de negociação, jurídico, contrato, SC/OCI e OC, 1:1 com o equipamento;
- `workflow`: máquina de estados 0–8, requisitos por transição, reabertura e histórico consolidado;
- `queues`: filas operacionais de Engenharia, Jurídico e Suprimentos, como recortes explícitos do workflow;
- `access`: responsáveis atribuíveis e administração das unidades de cada usuário;
- `suppliers`: cadastro mestre de fornecedores e vínculo N:N com equipamentos.

`workflow` é o único caminho que altera `equipment.current_stage`; o `PATCH` de equipamento rejeita esse campo.

`app/core/scope.py` é o ponto único da autorização por unidade: o perfil define o que o usuário faz, o vínculo `user_unit_access` define onde. Todo módulo que toca dados de unidade passa por ele.

No frontend, a navbar do módulo dá acesso a `/dashboard` (visão consolidada), `/equipamentos` (listagem), `/engenharia`, `/juridico` e `/suprimentos` (filas por área) e `/dashboard/auditoria`. O detalhe `/equipamentos/[id]` é a tela de operação do processo, com stepper 0–8, formulário da etapa atual, painel de requisitos da próxima etapa e histórico. Unidade e Equipamento são filtros globais compartilhados por todas essas telas. A administração é **contextual**: a aba Equipamentos tem um painel de catálogos e de acesso por unidade (`catalogs:manage` / `users:manage`) e a aba Suprimentos tem o cadastro mestre de fornecedores (`suppliers:write`). Não existe rota `/configuracoes` nem item de Configurações na navbar. `/fornecedores` permanece como tela auxiliar de Suprimentos.

O header é do Hub corporativo: busca, sino e exportação pertencem a ele e o Painel não acopla funções próprias a esses controles. As regras finais de prazo e os estados especiais continuam fora do escopo — ver `etapa-02-workflow-aquisicao.md`.
