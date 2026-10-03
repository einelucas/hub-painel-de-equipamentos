# Reconciliação EAP — LEM C2 (dry run)

> Relatório READ-ONLY gerado por `python -m app.modules.eap_reconciliation analyze`.
> Nenhum vínculo foi gravado. MATCH é candidato a vínculo futuro, não decisão aplicada.

## Fontes

- Catálogo EAP: `INPASA-DO-PRO-1700-001-07 - ÁRVORE DE LOCALIZAÇÃO - POR RESPONSÁVEL 2.xlsx` (catálogo SHA-256 `53ff2d19d615a6339874f9b394ac13c49d32f81506a54d27bd2c2a3f94e1e11d`)
- Alias EAP aprovado (`app/data/eap_aliases.json`): `Drenagem` → `00.C` — Na Árvore, 00.C é 'Drenagem (boca de lobo, poço de visita, caixa de coleta, tubo, meio fio)'; 'Drenagem' no Monday designa explicitamente esse nó.
- Export Monday: `Equipamentos_LEM_C2_ fase-0.xlsx` — 31 equipamentos, 55 subitens (SHA-256 `3217056aef05de39…`)
- Export Monday: `Equipamentos_LEM_C2_1789930920.xlsx` — 10 equipamentos, 109 subitens (SHA-256 `21e0c8e80dbcd763…`)
- Exports auxiliares conferidos (não somados): `Equipamentos_LEM_C2_1789930895.xlsx`, `Equipamentos_LEM_C2_1789930910.xlsx` — 9 equipamentos, todos contidos nos canônicos: sim; mesma área: sim
- Campo de EAP: `0.Área` → `normalized.area_name` do importador Monday (mesmo valor usado no apply).
- Identidade: `source_key` do importador (= `external_mapping.external_id`).

## Resumo

| Métrica | Valor |
|---|---|
| `total_equipment` | 41 |
| `matched_code_and_name` | 1 |
| `matched_code` | 0 |
| `matched_unique_name` | 38 |
| `matched_approved_alias` | 1 |
| `review_name_mismatch` | 0 |
| `review_catalog` | 0 |
| `review_multiple_eap` | 0 |
| `unresolved_unknown_code` | 0 |
| `unresolved_generic` | 1 |
| `unresolved_ambiguous_name` | 0 |
| `auto_match_safe_total` | 40 |

**Matches seguros (`auto_match_safe_total`): 40 de 41.** REVIEW não conta como match.

## Prefixos observados

O prefixo esperado do projeto é desconhecido (não configurado), então não há `EAP_PREFIX_MISMATCH`: o prefixo encontrado é só evidência (`OBSERVED_EAP_PREFIX`).

| Prefixo | Ocorrências | Equipamentos |
|---|---|---|
| `21` | 1 | Ponte rolante 25 ton |

Consistente em todo o projeto: sim. Evidência apenas — não autoriza gravar `ProjectContext.eap_prefix`.

## Matches seguros (40)

| Equipamento | Valor Monday | Prefixo observado | EAP oficial | Nome oficial | Status |
|---|---|---|---|---|---|
| Analisador de gás da Caldeira | Caldeira | — | 01.A | Caldeira | MATCH_UNIQUE_NAME |
| Bomba SUMP | Caldeira | — | 01.A | Caldeira | MATCH_UNIQUE_NAME |
| Bomba SUMP - Drenagem | Drenagem | — | 00.C | Drenagem (boca de lobo, poço de visita, caixa de coleta, tubo, meio fio) | MATCH_APPROVED_ALIAS |
| Caldeira de Biomassa | Caldeira | — | 01.A | Caldeira | MATCH_UNIQUE_NAME |
| Conjunto Turbo-Gerador | Caldeira | — | 01.A | Caldeira | MATCH_UNIQUE_NAME |
| Cubículos | Caldeira | — | 01.A | Caldeira | MATCH_UNIQUE_NAME |
| Eletrocentro SE12 | Caldeira | — | 01.A | Caldeira | MATCH_UNIQUE_NAME |
| Eletrocentros - Casa de Químicos | Caldeira | — | 01.A | Caldeira | MATCH_UNIQUE_NAME |
| Equipamentos da Biomassa: Linha de Alternativos | Caldeira | — | 01.A | Caldeira | MATCH_UNIQUE_NAME |
| Equipamentos da Biomassa: tremonhas, transportadores, peneiras, dutos, plataformas, torres, separadores e sistemas de nebulização. | Caldeira | — | 01.A | Caldeira | MATCH_UNIQUE_NAME |
| Estrutura Metálica - Pipe Rack | Pipe Rack | — | 00.A | Pipe Rack | MATCH_UNIQUE_NAME |
| ESTRUTURAS METÁLICAS CALDEIRA | Caldeira | — | 01.A | Caldeira | MATCH_UNIQUE_NAME |
| Gerador a Diesel | Caldeira | — | 01.A | Caldeira | MATCH_UNIQUE_NAME |
| Lubrificação Forçada - Unidade de Lubrificação | Caldeira | — | 01.A | Caldeira | MATCH_UNIQUE_NAME |
| Manômetros e Termômetros | Caldeira | — | 01.A | Caldeira | MATCH_UNIQUE_NAME |
| Moto Bombas | Caldeira | — | 01.A | Caldeira | MATCH_UNIQUE_NAME |
| Motores Da Caldeira | Caldeira | — | 01.A | Caldeira | MATCH_UNIQUE_NAME |
| Painéis de PLC | Caldeira | — | 01.A | Caldeira | MATCH_UNIQUE_NAME |
| Painéis QDCA/QNBS | Caldeira | — | 01.A | Caldeira | MATCH_UNIQUE_NAME |
| Painel de Acionamento (Cilindros) das Grelhas | Caldeira | — | 01.A | Caldeira | MATCH_UNIQUE_NAME |
| Ponte rolante 25 ton | 2104.A Casa de Força | 21 | 04.A | Casa de força | MATCH_CODE_AND_NAME |
| Projetores, Iluminação Industrial E Iluminação Perimetral | Caldeira | — | 01.A | Caldeira | MATCH_UNIQUE_NAME |
| Remotas | Caldeira | — | 01.A | Caldeira | MATCH_UNIQUE_NAME |
| Retificadores | Caldeira | — | 01.A | Caldeira | MATCH_UNIQUE_NAME |
| Sensores Eletrônicos De Alarme E Nível Por Eletrodo (Nível Cald.) | Caldeira | — | 01.A | Caldeira | MATCH_UNIQUE_NAME |
| Servidor(Desktop e Tablets) | Caldeira | — | 01.A | Caldeira | MATCH_UNIQUE_NAME |
| Sistema de Requeima de Cinzas | Caldeira | — | 01.A | Caldeira | MATCH_UNIQUE_NAME |
| Sopradores de Fuligem | Caldeira | — | 01.A | Caldeira | MATCH_UNIQUE_NAME |
| Suporte de mola - Modelo Carga Variável | Casa de Força | — | 04.A | Casa de força | MATCH_UNIQUE_NAME |
| Transformadores | Caldeira | — | 01.A | Caldeira | MATCH_UNIQUE_NAME |
| Transmissores | Caldeira | — | 01.A | Caldeira | MATCH_UNIQUE_NAME |
| Transportadores de Cinza | Caldeira | — | 01.A | Caldeira | MATCH_UNIQUE_NAME |
| Tubulação de alta pressão - P22 TG até caldeira | Caldeira | — | 01.A | Caldeira | MATCH_UNIQUE_NAME |
| Válvula elétrica Caldeira | Caldeira | — | 01.A | Caldeira | MATCH_UNIQUE_NAME |
| Válvulas De Alívio/Segurança (Alta Pressão) Caldeira | Caldeira | — | 01.A | Caldeira | MATCH_UNIQUE_NAME |
| Válvulas De Alívio/Segurança (Baixa Pressão) Caldeira | Caldeira | — | 01.A | Caldeira | MATCH_UNIQUE_NAME |
| Válvulas de Controle On-Off Desuper e Dumper | Caldeira | — | 01.A | Caldeira | MATCH_UNIQUE_NAME |
| Válvulas Manuais (Alta Pressão) | Caldeira | — | 01.A | Caldeira | MATCH_UNIQUE_NAME |
| Ventiladores centrífugos - Conjuntos | Caldeira | — | 01.A | Caldeira | MATCH_UNIQUE_NAME |
| Visores de nível | Caldeira | — | 01.A | Caldeira | MATCH_UNIQUE_NAME |

## Revisão humana necessária (0)

Nenhum.

## Não resolvidos (1)

| Equipamento | Valor bruto | Status | Motivo |
|---|---|---|---|
| LM - Isolamento térmico | Geral | UNRESOLVED_GENERIC_VALUE | Valor genérico aprovado como não vinculável: 'Geral' sozinho não identifica qual área geral (00.*) é a do equipamento; não vincula ao PROCESS 00 nem a ilha (GERAL não tem código e equipamento nunca aponta para ISLAND). Permanece sem EAP até haver valor específico. |

## Múltiplas EAP

Nenhum equipamento com mais de uma EAP. Para este projeto, o `equipment.eap_node_id` singular é suficiente.

## EAPs candidatas a ProjectEap (não gravadas)

Somente códigos de matches seguros: `00.A`, `00.C`, `01.A`, `04.A`.

## Comparação com o banco (somente leitura)

- Banco: `neondb` (alembic `0009_requirement_waivers`); contextos: LEM/C2
- Equipment no banco: 41; com mapping Monday: 41
- Export ↔ banco pela identidade externa: 41 encontrados
- Export sem Equipment: 0 
- Equipment sem fonte no export: 0 
- Equipment sem mapping: 0; identidades duplicadas: 0

Área legada (`equipment.area_id`) × EAP reconciliada (não sincronizado):

| Comparação | Equipamentos |
|---|---|
| `DIFFERENT_NAME` | 1 |
| `NO_EAP_MATCH` | 1 |
| `SAME_NAME` | 39 |

Diferenças de nome (área legada × EAP oficial):

- Bomba SUMP - Drenagem: área `Drenagem` × EAP `00.C Drenagem (boca de lobo, poço de visita, caixa de coleta, tubo, meio fio)`

<!-- HISTÓRICO: mantido manualmente; preservado ao regenerar este relatório -->

## Histórico da reconciliação e aplicação (LEM C2)

### 1. Primeira reconciliação — antes da decisão do bloco 00 (commit `adbf30f`)

Catálogo com 134 nós; `00` e todas as áreas `00.*` estavam em `EAP_REVIEW_REQUIRED`
(código `X00` aparece na Árvore com três descrições).

| Resultado | Quantidade |
|---|---|
| Total | 41 |
| Seguros | 38 |
| `REVIEW_EAP_CATALOG` | 1 — Estrutura Metálica - Pipe Rack (`Pipe Rack` → `00.A`, dependente do bloco 00) |
| Não resolvidos | 2 — Bomba SUMP - Drenagem (`Drenagem`) e LM - Isolamento térmico (`Geral`) |

### 2. Decisão de domínio posterior: família 00 = Áreas gerais

A interpretação do bloco 00 **não estava na Árvore**: foi uma decisão de domínio tomada depois
da primeira reconciliação (ver `docs/eap-catalogo.md`).

- `00` passa a ser PROCESS raiz "Geral" (nomes da fonte preservados: Geral INPASA AGROINDUSTRIAL,
  Layout Geral, ADM 3D); `00.0`…`00.J` viram AREA filhas. Catálogo: 144 nós (7/21/116);
  `EAP_REVIEW_REQUIRED` cai de 15 para 5. Decisão em `backend/app/data/eap_catalog_resolutions.json`.
- Alias aprovado `Drenagem` → `00.C` (status `MATCH_APPROVED_ALIAS`), em `backend/app/data/eap_aliases.json`.
- `Geral` registrado como valor **não vinculável** no mesmo arquivo. Sem isso, a primeira regeneração
  deu 41 seguros, porque "Geral" passou a casar por nome exato com o PROCESS `00`; a decisão de
  domínio é que "Geral" sozinho não identifica a área geral do equipamento.

### 3. Reconciliação após a decisão (artefato versionado deste relatório)

| Resultado | Quantidade |
|---|---|
| Total | 41 |
| Seguros | 40 (38 nome único, 1 código + nome, 1 alias aprovado) |
| Revisão | 0 |
| Não resolvidos | 1 — LM - Isolamento térmico (`Geral`) |

- Pipe Rack → `00.A` (`MATCH_UNIQUE_NAME`); Drenagem → `00.C` (`MATCH_APPROVED_ALIAS`); Geral → sem vínculo.
- Os 36 equipamentos com Área = "Caldeira" no Monday continuam em `01.A`: a EAP vem do campo Área do
  Monday, nunca do nome do equipamento.

### 4. Aplicação no `neondb_test` (2026-10-02)

Pré-condição: o C2 foi recarregado no `neondb_test` pelo importador Monday, após a correção do commit
`9b5e3af` (41 Equipment, 164 componentes, 231 auditorias `migration.import`). Catálogo com 144 nós.

Comando: `python -m app.modules.eap_reconciliation apply` lendo este JSON versionado (SHA-256
`83b1354d727ad9c1…`); a reconciliação não é recalculada no apply.

| Etapa | planned/updated | unchanged | skipped_unresolved | skipped_review | conflicts |
|---|---|---|---|---|---|
| Dry-run | 40 | 0 | 1 | 0 | 0 |
| Apply (transação única) | 40 | 0 | 1 | 0 | 0 |
| Dry-run de idempotência | 0 | 40 | 1 | 0 | 0 |

O dry-run não escreveu nada (0 vínculos e 0 auditorias depois dele).

**Resultado físico (consulta direta ao banco):**

| EAP | Equipamentos |
|---|---|
| `00.A` Pipe Rack | 1 |
| `00.C` Drenagem | 1 |
| `01.A` Caldeira | 36 |
| `04.A` Casa de força | 2 |
| **Total vinculado** | **40** (todos AREA) |
| Sem EAP (`NULL`) | 1 — LM - Isolamento térmico |

- 40 auditorias `eap_reconciliation.apply` (uma por vínculo criado; nenhuma para o não resolvido),
  com `eap_node_id` anterior (NULL) e novo, código EAP, status da reconciliação, SHA do artefato, ator e data.
  O dry-run de idempotência não criou auditoria nova (continuam 40).
- 0 vínculos a ISLAND, a nó em revisão ou a nó inexistente.
- `area_id` legado: 0 alterações (comparado com o retrato tirado antes do apply).
- `project_eap` = 0 (candidatos apenas: `00.A`, `00.C`, `01.A`, `04.A`).
- `ProjectContext.eap_prefix` do C2 = NULL; o prefixo observado `21` continua só como evidência.
- DEV (`neondb`, `0009_requirement_waivers`): somente leitura; nada aplicado.
