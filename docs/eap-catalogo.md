# Catálogo EAP canônico

Catálogo corporativo da EAP (`eap_node`), extraído **somente** da Árvore de
Localização oficial. A LGE e o Monday não participam deste catálogo.

## Fluxo

```
Árvore oficial (XLSX, somente leitura, fora do Git)
  → extração em desenvolvimento: python -m app.modules.eap_catalog extract <xlsx>
  → backend/app/data/eap_catalog.json   (versionado; o app nunca abre o XLSX)
  → validação: python -m app.modules.eap_catalog validate
  → carga idempotente: python -m app.modules.eap_catalog seed --dry-run | --apply
  → eap_node
```

| Item | Valor |
|---|---|
| Fonte | `INPASA-DO-PRO-1700-001-07 - ÁRVORE DE LOCALIZAÇÃO - POR RESPONSÁVEL 2.xlsx`, aba `Table 2` |
| SHA-256 da fonte | `aafd38fb034d987534473cf8c82f062cc0ea1fa2059a5e81071dff20c746bd5d` |
| SHA-256 do catálogo | `d070bdde2ac74dd99a3cffa5e49375910279675e325340f587ea9d5bfd5660f7` |
| Linhas EAP (códigos `X…`) | 144 |
| Cabeçalhos de ilha | 8 |
| Linhas de responsabilidade ignoradas | 34 (linhas 154–187) |
| Códigos EAP distintos | 141 |
| Nós carregáveis | 134: 7 ISLAND, 20 PROCESS, 107 AREA |
| `EAP_REVIEW_REQUIRED` | 15 (não carregados) |

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
| 00 | PROCESS | Geral INPASA AGROINDUSTRIAL / Layout Geral / ADM 3D | `DUPLICATE_CODE_DIFFERENT_NAMES` | O código aparece em 3 linhas com descrições diferentes. | 3, 4, 5 | 'Geral INPASA AGROINDUSTRIAL' (linha 3); 'Layout Geral' (linha 4); 'ADM 3D' (linha 5) |
| 21 | PROCESS | Sistema de Geração de Ar Comprimido | `MALFORMED_PREFIX_MARKER` | Marcador de prefixo 'XX' em vez de 'X' ('XX21'). | 152 | '21' lido com o marcador corrigido para 'X'; posição na Árvore: bloco da ilha F |
| 00.0 | AREA | Projetos executivos civis industriais | `PARENT_REVIEW_REQUIRED` | O pai (00) está em revisão. | 14 | Carregar após resolver 00 |
| 00.A | AREA | Pipe Rack | `PARENT_REVIEW_REQUIRED` | O pai (00) está em revisão. | 6 | Carregar após resolver 00 |
| 00.B | AREA | Terraplenagem (camada vegetal, tratamento de sub-leito, compactação de aterro) | `PARENT_REVIEW_REQUIRED` | O pai (00) está em revisão. | 7 | Carregar após resolver 00 |
| 00.C | AREA | Drenagem (boca de lobo, poço de visita, caixa de coleta, tubo, meio fio) | `PARENT_REVIEW_REQUIRED` | O pai (00) está em revisão. | 8 | Carregar após resolver 00 |
| 00.D | AREA | Pavimentação (cascalho, tratamento de sub-base e base, imprimação, CBUQ) | `PARENT_REVIEW_REQUIRED` | O pai (00) está em revisão. | 9 | Carregar após resolver 00 |
| 00.E | AREA | Hangar (aeroporto) | `PARENT_REVIEW_REQUIRED` | O pai (00) está em revisão. | 10 | Carregar após resolver 00 |
| 00.H | AREA | Reservatório de detenção de água pluvial (dissipador) | `PARENT_REVIEW_REQUIRED` | O pai (00) está em revisão. | 11 | Carregar após resolver 00 |
| 00.I | AREA | Trevo de acesso | `PARENT_REVIEW_REQUIRED` | O pai (00) está em revisão. | 12 | Carregar após resolver 00 |
| 00.J | AREA | Projeto de canteiros | `PARENT_REVIEW_REQUIRED` | O pai (00) está em revisão. | 13 | Carregar após resolver 00 |
| 02.G | AREA | Fermentação-Executivo Civil | `POSITION_CONTRADICTS_CODE` | O código indica o PROCESS 02, mas a linha está no bloco do PROCESS 06. | 32 | pai 02 (pelo código); pai 06 (pela posição; o código seria 06.G) |
| 15.B | AREA | Balanças rodoviária / Balanças rodoviária - executivo civil | `DUPLICATE_CODE_DIFFERENT_NAMES` | O código aparece em 2 linhas com descrições diferentes. | 75, 76 | 'Balanças rodoviária' (linha 75); 'Balanças rodoviária - executivo civil' (linha 76) |
| 21.A | AREA | Geração e Distribuição de Ar Comprimido | `MALFORMED_PREFIX_MARKER` | Marcador de prefixo 'XX' em vez de 'X' ('XX21.A'). | 153 | '21.A' lido com o marcador corrigido para 'X'; posição na Árvore: bloco da ilha F |

**Como resolver.** Corrigir a Árvore (ou registrar a decisão), rodar `extract`
de novo e conferir o diff do JSON. Depois rodar `seed`: os nós resolvidos
entram como `created`, e os já carregados continuam `unchanged`.

**Observação.** O código de ilha usa a letra da própria Árvore, a fonte
oficial. As siglas da LGE (ETN, DGO, UTI…) não foram usadas.
