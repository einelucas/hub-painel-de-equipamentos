# MIG-001 — Fundação do importador Monday

## Escopo desta etapa

Esta etapa prepara uma migração futura, mas **não realiza o corte do Monday**. Os XLSX em
`references/monday_exports/` são dados reais imutáveis usados somente como referência e fixtures de
validação. O importador não altera esses arquivos, não os empacota como dados de produção e não cria
`Equipment`, `EquipmentComponent` ou processos definitivos.

Não foi criado endpoint nem frontend de upload. O único ponto executável é um CLI interno de dry-run;
a gravação intermediária existe como serviço de backend e permanece fora da API pública.

## Arquitetura

O pacote `backend/app/modules/monday_import/` separa as responsabilidades:

- `xlsx.py`: leitura segura e somente leitura do contêiner XLSX, com limites de entradas, tamanho,
  linhas e colunas;
- `parser.py`: máquina de estados semântica que reconhece board, fase, cabeçalhos, equipamento e
  subitem sem depender de número fixo de linha;
- `normalization.py`: datas, checkbox, números, texto, multi-valor e IDs externos;
- `mappings.py`: aliases de colunas e estratégia de identidade;
- `calculations.py`: apenas relações matemáticas confirmadas pelos 164 subitens;
- `dry_run.py`: consolidação de snapshots, lacunas de mapeamento e relatório sem banco;
- `reconciliation.py`: contagens origem/destino e invariantes C2;
- `service.py`: staging transacional e idempotente, sem aplicar dados ao domínio;
- `cli.py`: interface administrativa de dry-run e JSON.

O leitor suporta strings diretas, `inlineStr`, `sharedStrings`, números, booleanos e valor cacheado de
fórmulas. Também lê o epoch 1900/1904 declarado no workbook. XML malformado, ZIP inválido, referência
insegura e planilha excessiva falham de forma explícita.

## Formato real do XLSX

O arquivo não é uma tabela plana. Cada fase possui esta sequência, que pode reaparecer no mesmo
workbook:

```text
Equipamentos - LEM C2
Fase N - nome
<cabeçalho principal>
<equipamento>
Subitems | Name | ... | ID do elemento
<subitem>
<subitem>
<próximo equipamento>
...
<linha-resumo do Monday>
```

O parser localiza semanticamente `Name`, `Subelementos`, `A.Status`, `Subitems` e outros aliases.
Cabeçalhos podem mudar de linha, grupos podem ser repetidos, células podem estar vazias e colunas
desconhecidas são preservadas no payload bruto e listadas no relatório. Linhas-resumo (`null`, `0/31`
etc.) não viram entidades.

Os quatro exports atuais são snapshots sobrepostos. A consolidação usa a identidade externa do
subitem e a chave provisória do equipamento; o último snapshot recebido prevalece no dry-run. Nos
arquivos de referência isso elimina 108 repetições e resulta em 41 equipamentos/164 subitens.

## Normalização

- Datas conhecidas aceitam `YYYY/MM/DD`, `YYYY-MM-DD`, `DD/MM/YYYY` e serial Excel, por exemplo
  `46687`. Serial nunca é interpretado como data fora de campos declarados como data.
- Checkbox aceita `v`, `true`, `TRUE`, `1`, `sim`, `yes`, `x`, `checked`, `✓` e `✔`; representações
  negativas também são reconhecidas. Vazio permanece `null` no staging para distinguir ausência de
  `false` explícito.
- Work Package vira uma lista intermediária, por exemplo
  `["CAL012", "CIV014", "CIV015", "CIV012"]`; o texto original continua no JSON bruto.
- IDs numéricos são convertidos para string sem `.0`; não são tratados como datas.
- Valores inválidos produzem `ImportIssue` com arquivo/batch, linha, campo e valor bruto.

Nenhum normalizador é aplicado indiscriminadamente: a seleção é feita pelo conceito mapeado da coluna.

## Staging, rastreabilidade e idempotência

A migration `0005_monday_import_foundation` cria:

- `monday_import_batch`: contexto, arquivo, SHA-256, board, sheet, versão do parser, status e resumo;
- `monday_import_record`: equipamento/subitem, pai, fase, linha, chave de origem, JSON bruto, JSON
  normalizado e ponte opcional para o registro final;
- `monday_import_issue`: severidade, código, linha, campo, valor bruto e mensagem;
- `external_mapping`: identidade de origem genérica ligada a um registro final do Hub.

A unicidade `(project_context_id, source_system, file_sha256)` torna o recebimento do mesmo arquivo
idempotente inclusive sob concorrência (`ON CONFLICT DO NOTHING`). Uma segunda chamada recupera o
batch existente e não duplica linhas. A tabela de records não impõe unicidade por external ID para não
descartar dado bruto inconsistente; duplicidade vira issue e toda linha continua auditável.

`status=STAGED` significa apenas que raw/normalizado foram preservados. A passagem para `APPLIED`, o
upsert das entidades finais e o preenchimento de `final_entity_*` ficam para a próxima etapa, depois da
validação humana dos mapeamentos.

## Estratégia de identidade externa

- Subitem: `source_system=monday`, `source_entity_type=component` e `external_id=ID do elemento`.
- Equipamento: como o Item ID pai não está claro no XLSX, usa provisoriamente
  `project_context + normalized-name:<nome normalizado>`.
- A limitação da chave por nome é deliberadamente visível em `identity_strategy`; colisões são issues.
- Quando o Monday Item ID pai estiver disponível, uma nova identidade pode ser registrada em
  `external_mapping` sem adicionar colunas Monday a cada tabela de domínio.

Renomear um equipamento na origem pode parecer um item novo enquanto só existir a chave provisória.
Nenhum merge automático por similaridade é feito.

## Dry-run

Na raiz de `backend/`:

```powershell
.venv\Scripts\python.exe -m app.modules.monday_import ..\references\monday_exports
.venv\Scripts\python.exe -m app.modules.monday_import ..\references\monday_exports --json
.venv\Scripts\python.exe -m app.modules.monday_import ..\references\monday_exports --json-out monday-report.json
```

Diretórios e múltiplos arquivos são aceitos. O relatório informa arquivos, boards, totais, fases,
campos desconhecidos, datas inválidas, responsáveis/áreas/Work Packages sem mapeamento, duplicidades,
warnings, errors e reconciliação C2. `--json-out` é a única escrita do dry-run e ocorre apenas no caminho
explicitamente fornecido; não há sessão de banco.

Sem um `MappingCatalog` fornecido pela futura camada administrativa, os valores encontrados são
listados como “sem mapeamento”; isso não significa que devam ser criados automaticamente.

## Reconciliação

Os invariantes implementados são:

| Escopo | Equipamentos | Subitens |
|---|---:|---:|
| Total | 41 | 164 |
| Fase 0 | 31 | 55 |
| Fase 4 | 6 | 8 |
| Fase 6 | 3 | 77 |
| Fase 8 | 1 | 24 |

`reconcile_counts` aceita duas estruturas independentes. Hoje o destino esperado pode ser a baseline C2;
na próxima etapa a mesma interface deverá receber contagens consultadas do Hub e depois ampliar a
comparação para responsável, área, disciplina, Work Package, fornecedor, contrato, SC/OCI, OC, prazo e
dashboard.

## Regras de cálculo confirmadas por evidência

Para cada componente, a cadeia abaixo coincidiu nos 164/164 casos:

```text
delivery_deadline        = startup_at - pre_start_days
collection_available_at = delivery_deadline - freight_days
contract_or_po_deadline  = collection_available_at - lead_time_days
negotiation_deadline     = contract_or_po_deadline - 21 dias
```

Nos dois subitens em que frete está vazio, o resultado observado equivale a zero dia. Essa política é
um parâmetro explícito (`blank_freight_days_default=0`) e pode ser desabilitada, sem ficar embutida como
suposição invisível.

As funções são puras. O cálculo de dias restantes exige `reference_date` explícita e nunca usa a data
atual do servidor implicitamente.

Para os 41/41 equipamentos, os mirrors observados correspondem a:

- `MAX(component.lead_time_days)`;
- `MAX(component.pre_start_days)`;
- `MAX(component.freight_days)`;
- `MIN(component.delivery_deadline)`;
- `MIN(component.contract_or_po_deadline)`;
- `MIN(component.negotiation_deadline)`.

A abordagem escolhida é calcular em serviço/API (ou SQL agregado no futuro), sem persistir mirrors.

Status com data de negociação preenchida retorna `CONCLUIDO`; prazo negativo retorna `ATRASADO`.
Valores positivos retornam `PENDENTE_THRESHOLDS`, pois 10→URGENTE, 25/30→PRÓXIMO e 40→NO PRAZO não
definem as fronteiras exatas. A margem `delivery_deadline - contract_delivery_at` positiva pode produzir
o candidato `ATENDE`; zero/negativo permanece `PENDENTE_VALIDACAO`.

## Equipment × Component × Acquisition

O modelo atual é preservado:

```text
ProjectContext
└── Equipment
    ├── EquipmentComponent
    ├── Negotiation
    ├── LegalProcess
    ├── Contract
    ├── PurchaseRequest
    ├── PurchaseOrder
    └── WorkflowTransition
```

`EquipmentComponent` representa hoje o subitem técnico exportado pelo Monday. Isso não comprova que o
componente seja a unidade de aquisição. Duas alternativas continuam abertas:

```text
Equipment ── Component
          └─ AcquisitionProcess
```

ou

```text
Equipment ── Component ── Acquisition
```

A migration desta etapa adiciona somente staging/mapeamento e não muda as cardinalidades 1:1 atuais dos
processos.

## DECISÕES AINDA PENDENTES

- aggregate root da aquisição: equipamento, componente ou uma nova `Acquisition`;
- cardinalidades de contratos, SCs/OCIs, OCs, fornecedores e processos;
- obtenção e estabilidade do Monday Item ID do equipamento pai;
- thresholds exatos de URGENTE, PRÓXIMO e NO PRAZO;
- razão funcional de o dashboard mostrar 163 aquisições para 164 subitens;
- estados Standby, Cancelado e Não se Aplica;
- bypass de Suprimentos;
- política oficial de reabertura;
- atalho 2→4 e demais exceções do workflow;
- departamento/permissões definitivos;
- fórmula definitiva de criticidade e demais indicadores;
- cardinalidade de Work Package, pois a origem traz múltiplos códigos e o modelo atual tem uma FK;
- local definitivo do startup específico de subitem observado no XLSX;
- comportamento de aderência quando a margem de entrega é zero ou negativa.

## Riscos conhecidos e próxima etapa

- nome normalizado não é identidade estável do equipamento;
- mudanças futuras de headers podem exigir novo alias, embora o valor bruto seja preservado;
- arquivos sobrepostos precisam de política temporal explícita antes do apply final;
- staging contém dados reais e deve seguir a política de acesso/retensão do ambiente;
- arquivos/anexos do Monday não são baixados;
- raw JSON preserva o conteúdo das células, mas não pretende reproduzir layout visual, estilo ou fórmulas
  de apresentação.

A próxima etapa deve validar as decisões pendentes, carregar catálogos/mapeamentos aprovados, definir a
política de conflito/renome, implementar o apply transacional em amostra controlada, reconciliar origem
versus Hub campo a campo e só então planejar o corte.
