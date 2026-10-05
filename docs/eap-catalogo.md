# Catálogo EAP canônico

Catálogo corporativo da EAP (`eap_node`), extraído **somente** da Árvore de
Localização oficial. A LGE e o Monday não participam deste catálogo.

## Fluxo

```
Árvore oficial (XLSX, somente leitura, fora do Git)
  → extração em desenvolvimento: python -m app.modules.eap_catalog extract <xlsx>
     (+ decisões aprovadas: eap_catalog_resolutions.json — privado)
  → eap_catalog.json   (PRIVADO, fora do Git; o app nunca abre o XLSX)
  → validação: python -m app.modules.eap_catalog validate
  → carga idempotente: python -m app.modules.eap_catalog seed --dry-run | --apply
  → eap_node
```

### Arquivos privados (REPO-SEC-01B)

A EAP corporativa **não é versionada**. `eap_catalog.json`,
`eap_catalog_resolutions.json` e `eap_aliases.json` ficam fora do Git, por padrão em
`backend/app/data/` (ignorado), ou no caminho indicado por:

| Variável | Arquivo |
|---|---|
| `EAP_CATALOG_PATH` | catálogo |
| `EAP_RESOLUTIONS_PATH` | decisões de extração |
| `EAP_ALIASES_PATH` | aliases e valores não vinculáveis da reconciliação |

A API HTTP não depende desses arquivos. As CLIs de catálogo e reconciliação falham
com mensagem clara se eles não existirem. Os testes usam apenas a fixture sintética
em `backend/tests/fixtures/eap/`.

| Item | Valor |
|---|---|
| Fonte | `<Árvore de Localização oficial — arquivo privado>`, aba `Table 2` |
| SHA-256 da fonte | `aafd38fb034d987534473cf8c82f062cc0ea1fa2059a5e81071dff20c746bd5d` |
| SHA-256 do catálogo | `ab1d0d8bd178c56feacbb22bc7b2bcff556839dde7d312f5d9f7b63c7597746e` (P0.4: `53ff2d19…`; antes da decisão 00: `d070bdde…`) |
| Linhas EAP (códigos `X…`) | 144 |
| Cabeçalhos de ilha | 8 |
| Linhas de responsabilidade ignoradas | 34 (linhas 154–187) |
| Códigos EAP distintos | 141 |
| Nós carregáveis | 148: 7 ISLAND, 22 PROCESS, 119 AREA (P0.4: 144 = 7/21/116; antes da decisão 00: 134 = 7/20/107) |
| `EAP_REVIEW_REQUIRED` | **0** (P0.4: 5; antes da decisão 00: 15) |

## Regras de extração

- `X<letra> <nome>` sem SETOR abre um bloco de **ISLAND**. O código é a letra da
  Árvore (`B`, `C`, `D`, `E`, `F`, `H`, `I`).
- `X<NN>` é **PROCESS** e `X<NN>.<sub>` é **AREA**. O `X` é o marcador do
  prefixo do projeto e não faz parte da identidade (`X01.A` → `01.A`).
- O pai de um PROCESS é a ilha do bloco em que ele está. O pai de uma AREA é o
  PROCESS indicado pelo próprio código.
- Linhas sem código `X…` (Materiais, Eng. Administrativa, Fluxogramas etc.) são
  atribuições de responsabilidade e não viram nó. A coluna RESPONSÁVEL não é
  carregada.
- Nomes: o texto da Árvore, só com espaços normalizados (incluindo `[SE-xx]`).
- Um PROCESS sem AREA é válido (ex.: `16`). Equipamento pode apontar para
  PROCESS ou AREA, nunca ISLAND (regra inalterada).

## Decisão de domínio: família 00 = Áreas gerais (2026-10-02)

A Árvore traz o código `X00` em **três linhas** (2–5, bloco `X GERAL`):
"Geral INPASA AGROINDUSTRIAL", "Layout Geral" e "ADM 3D". Na primeira extração
isso foi tratado como `DUPLICATE_CODE_DIFFERENT_NAMES`, o que levou `00` e as
nove áreas `00.*` para revisão.

**Decisão aprovada:** `00` representa a família/processo de **Áreas gerais**. As
três linhas são descrições/atribuições do mesmo agrupamento no documento
"por responsável", não três EAPs.

| Item | Valor |
|---|---|
| Nó | `00` — PROCESS **raiz** (`parent = NULL`), nome canônico **"Geral"** |
| Nomes da fonte (preservados em `source_names` no catálogo) | Geral INPASA AGROINDUSTRIAL; Layout Geral; ADM 3D |
| Áreas liberadas (AREA, pai `00`, nome oficial da Árvore) | `00.0`, `00.A`, `00.B`, `00.C`, `00.D`, `00.E`, `00.H`, `00.I`, `00.J` |
| Cabeçalho `X GERAL` | **Sem ISLAND**. Na P0.4 ficou em revisão; na P0.4.1 foi reconhecido como título visual (ver abaixo) |

- "Geral" é decisão de domínio, não uma linha literal da Árvore.
- A decisão está em `eap_catalog_resolutions.json` (privado) e vale só
  para `00`. A extração só a aplica se a Árvore trouxer exatamente esses três
  nomes; se a fonte mudar, a extração falha em vez de aplicar a decisão antiga.
- Essa resolução vale só para `00`. O outro código duplicado (`15.B`) foi
  resolvido depois, por decisão própria (P0.4.1, abaixo).

## EAP canônica, sem prefixo (P1.3.1)

- **Decisão vigente:** o Hub usa **somente `EapNode.code`** ("03", "04.A",
  "23.I") para identidade e exibição. Não existe composição "prefixo + EAP" —
  nem da unidade, nem da obra, nem da fase. A decisão anterior (prefixo do
  projeto em `ProjectContext.eap_prefix` + `build_full_eap_code()`) foi
  **revogada**: a função e o código de issue `EAP_PREFIX_MISMATCH` foram removidos.
- `ProjectContext.eap_prefix` é **LEGADO**: a coluna continua no banco (sem
  migration) só por compatibilidade de schema, mas a API não a expõe nem a
  grava (`eapPrefix` enviado por cliente antigo é ignorado) e a interface não
  pede prefixo ao criar/editar uma obra.
- Valores do Monday trazem um prefixo **contextual** da planilha ("2303 - …",
  "2104.A …", "2323.I …"). `extract_eap_codes()` (`app/domain/eap.py`) remove
  esse prefixo pelo formato reconhecido (2+ dígitos antes dos 2 dígitos do
  processo): `2303` → `03`, `2104.A` e `2404.A` → `04.A`, `2323.I` → `23.I`,
  `2300.` → `00`. Nada de `codigo[2:]` cego.
- Um valor pode citar **várias EAPs** ("2309 X / 2319 Y" → `09`, `19`): todas
  são detectadas e nenhuma é escolhida. O equipamento tem um único
  `eap_node_id`; um vínculo N:N é decisão de domínio futura.
- Valores **sem código** ("Diversos", "Pré-Obra", "Outros/Diversos") não viram EAP.
- O importador valida o código contra `EapNode` ativo (PROCESS/AREA). Sem EAP
  única e cadastrada, o equipamento fica com `eap_node_id = NULL` e a issue
  explícita (`MULTIPLE_EAP_CANDIDATES`, `NO_EAP`, `EAP_NOT_FOUND`); o valor
  bruto continua no staging. O usuário pode escolher uma EAP no mapeamento
  (`eapNodes`). Nunca há correspondência por nome.
- `Area`/`area_id` é legado: não é mais destino da localização em importações
  novas; equipamentos existentes não têm `area_id` alterado.

## Carga (`seed`)

- Cria só códigos inexistentes, pais antes de filhos. Cada criação gera um
  AuditLog `eap_catalog.create` com o SHA-256 do catálogo.
- Código existente com mesmo nível, nome e pai → `unchanged`. Qualquer
  divergência → `conflicts`, **sem sobrescrever**.
- Itens `review_required` nunca são inseridos. Nada é excluído; nós do banco
  fora do catálogo são só reportados (`extra_in_database`).
- Não toca em `project_eap`, `equipment` nem `project_context`.
- `--apply` exige `--confirm` e `--expect-database <nome>` e só roda com
  `APP_ENV` em `test` ou `development`. `--env-file` é carregado antes de abrir
  qualquer conexão.

```
python -m app.modules.eap_catalog seed --apply --confirm --expect-database neondb_test --env-file .env.test
```

## Correções aprovadas da Árvore oficial (P0.4.1, 2026-10-03)

Depois da P0.4 restavam 5 itens em `EAP_REVIEW_REQUIRED`. Eles vinham de uma leitura
**literal** da planilha. O responsável pelo projeto esclareceu que são erros de digitação
ou estrutura visual da fonte. As decisões estão em
`eap_catalog_resolutions.json` (privado) e não alteram o XLSX.

| Fonte (linha) | Canônico | Tipo de decisão | Motivo aprovado |
|---|---|---|---|
| `XX21` — Área EAP Sintética 123 (152) | `21` (PROCESS) | `source_corrections` | Erro de digitação: `XX21` é `X21` |
| `XX21.A` — Área EAP Sintética 80 (153) | `21.A` (AREA, pai `21`) | `source_corrections` | Erro de digitação: `XX21.A` é `X21.A` |
| `X02.G` — Área EAP Sintética 71 (32) | `06.G` (AREA, pai `06`) | `source_corrections` | Erro de digitação: o item pertence à família X06; `02.G` não existe |
| `X15.B` repetido (75: "Área EAP Sintética 15"; 76: "Área EAP Sintética 15 - executivo civil") | um único `15.B` "Área EAP Sintética 15" (AREA, pai `15`) | `resolutions` | Duplicidade consolidada; os dois textos ficam em `source_names` |
| `X GERAL` (2) | nenhum nó | `ignored_headers` | Título visual do bloco; não é ISLAND, nem nó, nem pendência |

- Cada correção vale só para o texto exato da célula e só se o SETOR da linha for o
  registrado. Se a fonte mudar, a extração falha. Não existe heurística genérica.
- O valor original fica no nó: `source_corrections` (fonte → canônico → motivo) para
  `21`, `21.A` e `06.G`, e `source_names` para `15.B`.
- `21` segue a regra geral de posição: fica sob a ilha do bloco em que aparece na
  Árvore, que é **F (Área EAP Sintética 1)**, porque as linhas `XX21` vêm logo depois do bloco `XF`.
- Resultado: catálogo com **148 nós** (7 ISLAND, 22 PROCESS, 119 AREA) e **0**
  `EAP_REVIEW_REQUIRED`. Aplicado no `neondb_test`: 4 nós criados (`21`, `21.A`, `06.G`,
  `15.B`) e 144 inalterados. Os vínculos EAP do LEM/C2 não mudaram.

### Histórico de `EAP_REVIEW_REQUIRED`

| Momento | Pendências | O que mudou |
|---|---|---|
| P0.1 (extração literal) | 15 | GERAL sem código, `00` (3 descrições) e suas 9 áreas, `21`, `21.A`, `02.G`, `15.B` |
| P0.4 (decisão da família 00) | 5 | Saíram `00` e `00.0`…`00.J` |
| P0.4.1 (correções aprovadas) | 0 | Saíram GERAL (título visual), `21`, `21.A`, `02.G` (→ `06.G`) e `15.B` |

**Novas pendências.** Se a Árvore mudar e a extração encontrar um caso ambíguo, ele
volta para `review_required` com as alternativas encontradas. Para resolver: registrar
a decisão aprovada no arquivo de resoluções, rodar `extract`, conferir o diff do JSON e
rodar `seed`.

**Observação.** O código de ilha usa a letra da própria Árvore, a fonte
oficial. As siglas da LGE (ETN, DGO, UTI…) não foram usadas.
