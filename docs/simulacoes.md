# Simulador de Startup — cenários de prazos

A rota `/simulacoes` permite testar e comparar cronogramas de negociação, contrato/OC e entrega sem modificar o planejamento ou os equipamentos operacionais do Hub.

## Escopo independente

O simulador usa `SimulationUnit → SimulationProject → StartupScenario → StartupScenarioEquipment`. Suas unidades e obras **não são** os cadastros `Unit`/`ProjectContext` da operação. Cenários guardam seus próprios snapshots e datas, mesmo quando existem referências legadas opcionais a equipamento.

- Selecionar/criar unidade e obra do simulador.
- Criar cenário manual com nome e data de startup; a relação de equipamentos pode começar **vazia**.
- Adicionar, remover ou editar livremente equipamentos do cenário. Campos: **nome, origem, disciplina, fornecedor, área, responsável**, data individual de startup e dias de suprimentos, jurídico, fabricação e antecedência de entrega.
- Salvar, duplicar ou excluir cenário, conforme autorização.
- Comparar dois cenários nos indicadores, gráfico e tabelas de datas mensais; escolher a métrica de negociação, contrato/OC ou entrega.
- Importar cenários de uma planilha XLSX e exportar resultados de comparação para Excel.

A página distingue alterações ainda não salvas da versão persistida e solicita confirmação ao trocar de cenário ou escopo com edição pendente.

## Cálculos

Os prazos são calculados **retroativamente** a partir da data individual do equipamento (quando informada) ou da data de startup do cenário:

```text
Limite de entrega   = Data de startup - Dias de antecedência da entrega
Limite de contrato  = Limite de entrega - Dias de fabricação
Limite de negociação= Limite de contrato - Dias de jurídico
```

O campo de dias de suprimentos é premissa editável, mas **não é subtraído** nessas três datas, de acordo com a regra implementada em `frontend/utils/startupSimulation.ts`. Quando uma data ou prazo necessário estiver ausente, o resultado correspondente é indefinido; não preencher com zeros presumidos. O modelo limita prazos inteiros a 0–36.500 dias.

## Integração e segurança

- API: `/api/v1/startup-simulation-units`, `/startup-simulation-projects` e `/startup-scenarios`.
- Leitura exige `equipments:read`; criação, edição, clonagem e exclusão exigem `equipments:write`.
- Importação/exportação XLSX e comparação são iniciadas no frontend com `frontend/utils/startupWorkbook.ts`, `startupExport.ts` e `startupSimulation.ts`.
- O backend persiste cenários no domínio `backend/app/modules/startup_simulations/`; **não** aplica resultados às transições de aquisição.

## Verificação

Testar cenários vazios, inclusão dinâmica de equipamentos, premissas nulas, datas-limite, importação/exportação, troca de escopo com edição pendente, autorização e comparação A/B. Referências: `frontend/tests/StartupSimulation.test.ts`, `frontend/tests/StartupComparison.test.ts` e `backend/tests/unit/test_startup_simulations.py`.

Consulte [API](api.md), [Funcionalidades](funcionalidades.md) e [Testes](testes.md).
