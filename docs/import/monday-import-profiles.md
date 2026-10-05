# Monday Import Profiles (P1.1)

## Propósito

O importador Monday (`backend/app/modules/monday_import/`) lê a exportação hierárquica XLSX de um board, grava o staging e depois planeja, aplica e reconcilia com o Hub. O que muda de um board para outro está num **ImportProfile**, que é um arquivo JSON declarativo:

- nomes das colunas;
- título do board e títulos de grupo;
- rótulos de status;
- identidade dos itens.

```
novo board → novo profile (JSON) → mesmo parser → stage → plan → apply → reconcile
```

Um board novo **não** pede parser novo, módulo novo, tabela nova nem código condicional por board. Também não existe código executável dentro do profile: o schema é Pydantic com `extra="forbid"` e aceita só strings, números e listas. Não há `eval`, regex fornecida pelo arquivo nem plugin.

## Separação de responsabilidades

| Camada | Responsável por | Onde |
|---|---|---|
| **ImportProfile** | Estrutura e semântica da ORIGEM: cabeçalho → conceito canônico, status → estágio, identidade, campos ignorados | `profiles/*.json`, validado por `profile.py` |
| **Conceitos canônicos** | Nomes e tipos que o pipeline entende (`startup_at`, `responsible_name`, `current_stage`…) | `mappings.py` (código) |
| **Normalização** | Datas, inteiros, booleanos, decimais, listas — igual para todo profile | `normalization.py`, `parser.py` |
| **MappingFile** | Valor da origem → entidade existente no Hub (usuário, área, disciplina, Work Package) | `mapping_file.py` (JSON com IDs, fora do profile) |

O profile **nunca** contém UUID de ProjectContext, de usuário ou de catálogo.

## Schema (resumo)

```jsonc
{
  "profile_id": "synthetic-asset-board-b",   // [a-z0-9._-], 3–64
  "version": 1,
  "source_system": "monday",
  "description": "…",
  "board": { "title_prefixes": ["Quadro Sintético de Ativos"], "title_required": true },
  "groups": {
    "stage_prefixes": ["Etapa"],              // reconhece "Etapa 2 - …" como grupo
    "other_titles": [],
    "not_applicable_titles": ["Fora do Escopo"],
    "stage_fallback_from_group": false        // ver "Status"
  },
  "equipment": {
    "header_signature": ["name", "current_stage", "area_name"],
    "required": ["name", "current_stage", "area_name"],
    "aliases": { "name": ["Asset"], "external_id": ["Asset Code"], "current_stage": ["Phase"],
                 "area_name": ["Sector"], "responsible_name": ["Responsible Person"] },
    "ignored_headers": [],
    "external_id_concept": "external_id"
  },
  "component": {
    "header_markers": ["Sub-assets"],
    "header_signature": ["name"],
    "required": ["name"],
    "aliases": { "subitems_marker": ["Sub-assets"], "name": ["Part"], "external_id": ["Part Code"] },
    "ignored_headers": [],
    "external_id_concept": "external_id"
  },
  "status": {
    "values": { "P0 Intake": 0, "P2 Sourcing": 2, "P5 Signed": 5, "Fora do Escopo": "NOT_APPLICABLE" },
    "stage_number_in_text": false
  },
  "expected_counts": null                      // opcional: { equipments, components, groups }
}
```

O validador recusa:
- conceito canônico desconhecido;
- cabeçalho mapeado para dois conceitos;
- coluna ignorada e mapeada ao mesmo tempo;
- `required` ou `header_signature` sem alias;
- `name` ausente;
- estágio fora de 0..8;
- rótulo de status vazio ou repetido;
- campos extras.

A identidade do profile (`profileId`, `version` e o `sha256` do conteúdo canônico) acompanha o parse, o dry-run e o batch.

## Cabeçalhos

- **Cabeçalho principal:** é a linha que contém um alias para **cada** conceito de `equipment.header_signature`.
- **Cabeçalho de subitens:** a primeira célula está em `component.header_markers` e a linha cumpre `component.header_signature`.
- **Comparação:** sem acento, caixa ou pontuação. "Área" e "AREA" são equivalentes.
- **Linhas de subitem:** dentro do bloco, a coluna do marcador fica vazia. Essa é uma propriedade do formato Monday, não de um board.

## Conceitos canônicos

São definidos em `mappings.EQUIPMENT_CONCEPTS` e `COMPONENT_CONCEPTS`.

| Conceitos | Uso |
|---|---|
| `name`, `external_id`, `current_stage` | Identidade e workflow |
| `startup_at`, `area_name`, `responsible_name`, `discipline_name`, `work_package_codes` | Dados do equipamento |
| `contract_number`, `purchase_request_number`, `purchase_order_number` | Processo de aquisição |
| `lead_time_days`, `freight_days`, `pre_start_days` | Prazos dos componentes |

A semântica de tipo (data, inteiro, booleano…) é do código e vale para qualquer profile.

## Identidade

| Item | Com ID estável (`external_id_concept` preenchido na linha) | Sem ID |
|---|---|---|
| Equipment | `monday-item-id:<id>`; estratégia `monday-item-id-v1` | `normalized-name:<nome>` + aviso `fragile_equipment_identity`; estratégia `normalized-name-v1` |
| Component | `monday-item-id:<id>` | `missing-external-id:<hash>` determinístico + aviso `missing_component_external_id`; o plan **bloqueia** esse componente (regra existente) |

Os IDs repetidos no arquivo geram erro. Nunca há merge aproximado: dois itens só são o mesmo quando têm o mesmo ID ou, no fallback, o mesmo nome normalizado. Mesmo assim, o plan bloqueia o caso `PARENT_IDENTITY_CONFLICT`. O `ExternalMapping` registra a estratégia usada.

## Status

O conceito `current_stage` (por exemplo, a coluna "Phase") é a **fonte** do estágio. A tradução segue esta ordem:

1. Rótulo exato em `status.values`: estágio 0..8 ou `NOT_APPLICABLE`.
2. Se `stage_number_in_text` estiver ligado: número isolado no texto ("3.Contrato" vira 3).
3. Caso contrário: valor **desconhecido**. O texto fica no `raw`, o parse marca `current_stage_unrecognized` e emite o aviso `unknown_status_value`, e o plan bloqueia com `UNKNOWN_STAGE_VALUE`. Nunca vira estágio 0.

O **grupo** é contexto estrutural. Ele só serve de fallback quando o status está **vazio** e `groups.stage_fallback_from_group = true`. Nunca sobrescreve um status explícito: se os dois divergirem, o plan registra `STAGE_CONFLICT`. Boards novos devem manter `false`.

## Campos ignorados e desconhecidos

- **`ignored_headers`:** coluna conhecida e deliberadamente não usada. Fica no `raw` e não aparece como desconhecida.
- **Coluna fora de `aliases` e de `ignored_headers`:** é **UNKNOWN**. Aparece em `unknown_fields` no dry-run e fica no `raw`.
- **Coluna de `required` ausente:** gera o erro `missing_required_column`. Coluna opcional ausente não gera aviso.

## Mapeamento de catálogos

O MappingFile resolve os valores observados para IDs existentes, separado por seção:

| Seção do MappingFile | Conceito canônico |
|---|---|
| `responsibles` | `responsible_name` |
| `areas` | `area_name` |
| `disciplines` | `discipline_name` |
| `workPackages` | `work_package_codes` |

A validação continua a mesma: existência, ativo, unidade ou contexto, e acesso. O profile só decide **qual coluna** da origem alimenta cada conceito.

## Contagens esperadas

São opcionais e vêm de `expected_counts` no profile ou de `--expected-counts arquivo.json` no dry-run. Sem elas, o dry-run não marca divergência. Quando não se declaram grupos, só os totais são comparados. Não existem contagens fixas de nenhuma obra no código.

## Rastreabilidade (sem migration)

O `stage` registra `import_profiles` no `summary` (JSON) do batch, com `parser_version = monday-xlsx-v3`. O `plan`, o `apply` e o `reconcile` leem o normalizado já persistido e não pedem profile. Restage do mesmo arquivo (mesmo SHA-256) no mesmo contexto com **outro** profile é recusado (`StagedWithDifferentProfileError`). Batches anteriores à P1.1 são tratados como lidos pelo profile histórico.

## Profile histórico

`profiles/monday-equipamentos-legacy.json` reproduz o layout antigo do board "Equipamentos" (variações C2/F2). Ele contém **somente nomes de colunas e rótulos estruturais**, nenhum valor de registro. É o padrão quando nenhum `--profile` é informado, o que mantém o comportamento anterior.

## Como criar um profile para um board novo (exemplo sintético)

1. **Exporte** o board no Monday (XLSX hierárquico). Guarde o arquivo **fora do Git** (`.gitignore` já cobre `*.xlsx`).
2. **Crie** `meu-board.json` a partir de um profile sintético:
   - em `aliases`, aponte cada coluna do board para um conceito canônico;
   - liste em `ignored_headers` as colunas que não interessam;
   - traduza os rótulos de status em `status.values`;
   - preencha `external_id_concept` se o board tiver ID do item.
3. **Dry-run** (sem banco):
   ```
   python -m app.modules.monday_import dry-run export.xlsx --profile meu-board.json
   ```
4. **Corrija** a partir do relatório:
   - `unknown_fields`: mapear ou ignorar;
   - `unknown_status_value`: incluir o rótulo em `status.values`;
   - `missing_required_column`;
   - `fragile_equipment_identity`: incluir ID do item, se o board tiver;
   - responsáveis, áreas e Work Packages sem mapeamento: completar o **MappingFile**.
5. **Stage:**
   ```
   python -m app.modules.monday_import stage export.xlsx --project-context-id <ctx> --profile meu-board.json
   ```
6. **Plan:**
   ```
   python -m app.modules.monday_import plan --project-context-id <ctx> --batch <id> --mapping-file mapping.json
   ```
   Revise BLOCKED e os avisos.
7. **Apply:**
   ```
   python -m app.modules.monday_import apply … --plan-hash <hash> --actor-id <user> --confirm
   ```
   Só em ambiente autorizado pela salvaguarda.
8. **Reconcile:**
   ```
   python -m app.modules.monday_import reconcile --project-context-id <ctx> --mapping-file mapping.json
   ```

Os exemplos completos estão em `backend/tests/fixtures/monday/profiles/` (layouts A e B, totalmente sintéticos). Os testes de `test_monday_import_profiles.py` e `test_monday_import_profile_pipeline.py` provam que os dois layouts produzem os mesmos conceitos canônicos pelo mesmo pipeline.

## Fora do escopo da P1.1

- Cadastro de ProjectContext (P1.2).
- Upload e UI.
- ProjectEap.
- Fornecedores.
- Representação de `NOT_APPLICABLE` no domínio: o plan continua bloqueando `STAGE_NOT_APPLICABLE`.
