# Reconciliação EAP — LEM C2 (dry run)

> Relatório READ-ONLY gerado por `python -m app.modules.eap_reconciliation analyze`.
> Nenhum vínculo foi gravado. MATCH é candidato a vínculo futuro, não decisão aplicada.

## Fontes

- Catálogo EAP: `INPASA-DO-PRO-1700-001-07 - ÁRVORE DE LOCALIZAÇÃO - POR RESPONSÁVEL 2.xlsx` (catálogo SHA-256 `d070bdde2ac74dd99a3cffa5e49375910279675e325340f587ea9d5bfd5660f7`)
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
| `matched_unique_name` | 37 |
| `review_name_mismatch` | 0 |
| `review_catalog` | 1 |
| `review_multiple_eap` | 0 |
| `unresolved_unknown_code` | 0 |
| `unresolved_generic` | 2 |
| `unresolved_ambiguous_name` | 0 |
| `auto_match_safe_total` | 38 |

**Matches seguros (`auto_match_safe_total`): 38 de 41.** REVIEW não conta como match.

## Prefixos observados

O prefixo esperado do projeto é desconhecido (não configurado), então não há `EAP_PREFIX_MISMATCH`: o prefixo encontrado é só evidência (`OBSERVED_EAP_PREFIX`).

| Prefixo | Ocorrências | Equipamentos |
|---|---|---|
| `21` | 1 | Ponte rolante 25 ton |

Consistente em todo o projeto: sim. Evidência apenas — não autoriza gravar `ProjectContext.eap_prefix`.

## Matches seguros (38)

| Equipamento | Valor Monday | Prefixo observado | EAP oficial | Nome oficial | Status |
|---|---|---|---|---|---|
| Analisador de gás da Caldeira | Caldeira | — | 01.A | Caldeira | MATCH_UNIQUE_NAME |
| Bomba SUMP | Caldeira | — | 01.A | Caldeira | MATCH_UNIQUE_NAME |
| Caldeira de Biomassa | Caldeira | — | 01.A | Caldeira | MATCH_UNIQUE_NAME |
| Conjunto Turbo-Gerador | Caldeira | — | 01.A | Caldeira | MATCH_UNIQUE_NAME |
| Cubículos | Caldeira | — | 01.A | Caldeira | MATCH_UNIQUE_NAME |
| Eletrocentro SE12 | Caldeira | — | 01.A | Caldeira | MATCH_UNIQUE_NAME |
| Eletrocentros - Casa de Químicos | Caldeira | — | 01.A | Caldeira | MATCH_UNIQUE_NAME |
| Equipamentos da Biomassa: Linha de Alternativos | Caldeira | — | 01.A | Caldeira | MATCH_UNIQUE_NAME |
| Equipamentos da Biomassa: tremonhas, transportadores, peneiras, dutos, plataformas, torres, separadores e sistemas de nebulização. | Caldeira | — | 01.A | Caldeira | MATCH_UNIQUE_NAME |
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

## Revisão humana necessária (1)

| Equipamento | Valor Monday | Status | Motivo / decisão necessária |
|---|---|---|---|
| Estrutura Metálica - Pipe Rack | Pipe Rack | REVIEW_EAP_CATALOG | Nome corresponde a 00.A, que está em EAP_REVIEW_REQUIRED. |

## Não resolvidos (2)

| Equipamento | Valor bruto | Status | Motivo |
|---|---|---|---|
| Bomba SUMP - Drenagem | Drenagem | UNRESOLVED_GENERIC_VALUE | Valor sem código e sem nó oficial com este nome; não vira EAP. |
| LM - Isolamento térmico | Geral | UNRESOLVED_GENERIC_VALUE | Nome corresponde só a uma ILHA, que não é elegível para equipamento. |

## Múltiplas EAP

Nenhum equipamento com mais de uma EAP. Para este projeto, o `equipment.eap_node_id` singular é suficiente.

## EAPs candidatas a ProjectEap (não gravadas)

Somente códigos de matches seguros: `01.A`, `04.A`.

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
| `NO_EAP_MATCH` | 3 |
| `SAME_NAME` | 38 |
