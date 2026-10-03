# Catálogo EAP canônico

Catálogo corporativo da EAP (`eap_node`), extraído **somente** da Árvore de
Localização oficial. A LGE e o Monday não participam deste catálogo.

## Fluxo

```
Árvore oficial (XLSX, somente leitura, fora do Git)
  → extração em desenvolvimento: python -m app.modules.eap_catalog extract <xlsx>
     (+ decisões aprovadas: backend/app/data/eap_catalog_resolutions.json)
  → backend/app/data/eap_catalog.json   (versionado; o app nunca abre o XLSX)
  → validação: python -m app.modules.eap_catalog validate
  → carga idempotente: python -m app.modules.eap_catalog seed --dry-run | --apply
  → eap_node
```

| Item | Valor |
|---|---|
| Fonte | `INPASA-DO-PRO-1700-001-07 - ÁRVORE DE LOCALIZAÇÃO - POR RESPONSÁVEL 2.xlsx`, aba `Table 2` |
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
  prefixo do projeto e não faz parte da identidade (`X01.A` → `01.A`). O
  prefixo exibido vem de `ProjectContext.eap_prefix`.
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
- A decisão está em `backend/app/data/eap_catalog_resolutions.json` e vale só
  para `00`. A extração só a aplica se a Árvore trouxer exatamente esses três
  nomes; se a fonte mudar, a extração falha em vez de aplicar a decisão antiga.
- Essa resolução vale só para `00`. O outro código duplicado (`15.B`) foi
  resolvido depois, por decisão própria (P0.4.1, abaixo).

## Prefixo EAP do projeto

- O prefixo pertence ao **projeto/fase** (`ProjectContext.eap_prefix`), não à
  unidade nem ao catálogo. A árvore EAP é corporativa e única. O prefixo é
  o que diferencia o código exibido em cada obra.
- É **informado manualmente** por quem tem `catalogs:manage`, em
  *Administração · Equipamentos → Catálogos → Contextos de projeto* (campo
  "Prefixo EAP"), ou via `PATCH /project-contexts/{id}` com `{"eapPrefix": "23"}`.
- **Não é sequencial nem calculado.** Rondonópolis F1 = `23` e F2 = `24` não
  implica F3 = `25`. Projetos diferentes podem usar o mesmo prefixo (sem
  unicidade).
- Só dígitos, guardado como texto: `"03"` continua `"03"`. **Pode ser NULL**
  ("Não definido"). `{"eapPrefix": null}` limpa o valor; string vazia é
  rejeitada. Sem prefixo, o sistema funciona normalmente; só não é possível
  compor o código completo.
- **Código completo é derivado, nunca persistido:** `eap_prefix + EapNode.code`
  (`23` + `01.A` → `2301.A`), via `build_full_eap_code()` em
  `app/domain/eap.py`.
- Cada alteração gera um AuditLog `catalog.update` (entidade `ProjectContext`,
  `entityId` = id do contexto), com o valor anterior e o novo, o usuário e a
  data.

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
`backend/app/data/eap_catalog_resolutions.json` e não alteram o XLSX.

| Fonte (linha) | Canônico | Tipo de decisão | Motivo aprovado |
|---|---|---|---|
| `XX21` — Sistema de Geração de Ar Comprimido (152) | `21` (PROCESS) | `source_corrections` | Erro de digitação: `XX21` é `X21` |
| `XX21.A` — Geração e Distribuição de Ar Comprimido (153) | `21.A` (AREA, pai `21`) | `source_corrections` | Erro de digitação: `XX21.A` é `X21.A` |
| `X02.G` — Fermentação-Executivo Civil (32) | `06.G` (AREA, pai `06`) | `source_corrections` | Erro de digitação: o item pertence à família X06; `02.G` não existe |
| `X15.B` repetido (75: "Balanças rodoviária"; 76: "Balanças rodoviária - executivo civil") | um único `15.B` "Balanças rodoviária" (AREA, pai `15`) | `resolutions` | Duplicidade consolidada; os dois textos ficam em `source_names` |
| `X GERAL` (2) | nenhum nó | `ignored_headers` | Título visual do bloco; não é ISLAND, nem nó, nem pendência |

- Cada correção vale só para o texto exato da célula e só se o SETOR da linha for o
  registrado. Se a fonte mudar, a extração falha. Não existe heurística genérica.
- O valor original fica no nó: `source_corrections` (fonte → canônico → motivo) para
  `21`, `21.A` e `06.G`, e `source_names` para `15.B`.
- `21` segue a regra geral de posição: fica sob a ilha do bloco em que aparece na
  Árvore, que é **F (Administração)**, porque as linhas `XX21` vêm logo depois do bloco `XF`.
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
