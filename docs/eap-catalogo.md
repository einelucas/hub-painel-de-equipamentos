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
| SHA-256 do catálogo | `53ff2d19d615a6339874f9b394ac13c49d32f81506a54d27bd2c2a3f94e1e11d` (antes da decisão 00: `d070bdde…`) |
| Linhas EAP (códigos `X…`) | 144 |
| Cabeçalhos de ilha | 8 |
| Linhas de responsabilidade ignoradas | 34 (linhas 154–187) |
| Códigos EAP distintos | 141 |
| Nós carregáveis | 144: 7 ISLAND, 21 PROCESS, 116 AREA (antes da decisão 00: 134 = 7/20/107) |
| `EAP_REVIEW_REQUIRED` | 5 (não carregados; antes da decisão 00: 15) |

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
| Cabeçalho `X GERAL` | Continua **sem ISLAND** (a Árvore não dá código); fica em revisão |

- "Geral" é decisão de domínio, não uma linha literal da Árvore.
- A decisão está em `backend/app/data/eap_catalog_resolutions.json` e vale só
  para `00`. A extração só a aplica se a Árvore trouxer exatamente esses três
  nomes; se a fonte mudar, a extração falha em vez de aplicar a decisão antiga.
- Nenhum outro código duplicado é resolvido por essa regra: `15.B` continua em
  revisão.

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

## EAP_REVIEW_REQUIRED

Nós que a Árvore não permite representar de forma inequívoca. Nenhuma
alternativa foi escolhida; cada um depende de decisão do dono da Árvore.

| Código | Nível | Descrição encontrada | Motivo | Detalhe | Linhas | Alternativas encontradas |
|---|---|---|---|---|---|---|
| — (ilha) | ISLAND | GERAL | `ISLAND_CODE_MISSING` | Cabeçalho de ilha sem letra na Árvore: não há código oficial para o nó. | 2 | Definir o código oficial desta ilha (a Árvore não traz letra para o bloco). |
| 21 | PROCESS | Sistema de Geração de Ar Comprimido | `MALFORMED_PREFIX_MARKER` | Marcador de prefixo 'XX' em vez de 'X' ('XX21'). | 152 | '21' lido com o marcador corrigido para 'X'; posição na Árvore: bloco da ilha F |
| 02.G | AREA | Fermentação-Executivo Civil | `POSITION_CONTRADICTS_CODE` | O código indica o PROCESS 02, mas a linha está no bloco do PROCESS 06. | 32 | pai 02 (pelo código); pai 06 (pela posição; o código seria 06.G) |
| 15.B | AREA | Balanças rodoviária / Balanças rodoviária - executivo civil | `DUPLICATE_CODE_DIFFERENT_NAMES` | O código aparece em 2 linhas com descrições diferentes. | 75, 76 | 'Balanças rodoviária' (linha 75); 'Balanças rodoviária - executivo civil' (linha 76) |
| 21.A | AREA | Geração e Distribuição de Ar Comprimido | `MALFORMED_PREFIX_MARKER` | Marcador de prefixo 'XX' em vez de 'X' ('XX21.A'). | 153 | '21.A' lido com o marcador corrigido para 'X'; posição na Árvore: bloco da ilha F |

Saíram da revisão pela decisão da família 00: `00`, `00.0`, `00.A`, `00.B`,
`00.C`, `00.D`, `00.E`, `00.H`, `00.I` e `00.J`.

**Como resolver.** Corrigir a Árvore (ou registrar a decisão), rodar `extract`
de novo e conferir o diff do JSON. Depois rodar `seed`: os nós resolvidos
entram como `created`, e os já carregados continuam `unchanged`.

**Observação.** O código de ilha usa a letra da própria Árvore, a fonte
oficial. As siglas da LGE (ETN, DGO, UTI…) não foram usadas.
