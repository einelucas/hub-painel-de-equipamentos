# Modelo de domínio, workflow e EAP

Fonte de interpretação: **código e migrations atuais** para o que está implementado; **decisões humanas aprovadas** para escolhas de domínio, especialmente a correspondência entre origem Monday e catálogo EAP. Documentos antigos com cardinalidades divergentes não devem reverter essas regras.

## Unidade, projeto e equipamento

~~~text
Unit
 └─ ProjectContext
    └─ Equipment
       ├─ EquipmentComponent[]         1:N
       ├─ EquipmentWorkPackage[]       N:N
       ├─ EquipmentSupplier            0..1 (regra operacional)
       ├─ Negotiation                  0..1
       ├─ LegalProcess                 0..1
       ├─ Contract[]                   0..N
       ├─ PurchaseRequest[]            0..N
       ├─ PurchaseOrder[]              0..N
       ├─ WorkflowTransition[]         histórico
       ├─ RequirementWaiver[]          dispensas
       ├─ ReopenRequest[]              aprovação de reabertura
       └─ OperationalStatusEvent[]      histórico do estado
~~~

`Unit` pode possuir diversos `ProjectContext`, inclusive fases e obras. Um board do Monday deve ser traduzido para um contexto, **não** para uma nova aplicação ou tabela de equipamentos.

`Equipment` é o registro mestre do pacote/equipamento. `EquipmentComponent` representa o subitem técnico; não presuma que um componente equivalha sempre a uma unidade financeira de compra. Os dados são filtrados por unidade/autorização.

## Fornecedores e pacotes

- `Supplier` é cadastro corporativo/global com código corporativo, nome e, quando disponível, documento. `SupplierAlias` registra nomes de origem.
- Reconciliação prioriza identificador/código corporativo, documento e aliases aprovados; não faz merge automático por similaridade.
- A associação de fornecedor conserva estrutura histórica, mas atualmente a operação limita a **um fornecedor vinculado por equipamento**; substituição é explícita.
- `EquipmentWorkPackage` é N:N. O campo legado `equipment.work_package_id` não significa que a cardinalidade global voltou a 1:1.

## Processos de compra

- `Negotiation` e `LegalProcess` são singulares para um Equipment.
- `Contract`, `PurchaseRequest` (SC/OCI) e `PurchaseOrder` (OC) são relações 1:N.
- Não use `Contract.delivery_at`: a janela contratual do processo está em `Equipment.contractual_delivery_start` e `contractual_delivery_end`. `EquipmentComponent.contract_delivery_at` é distinto e válido.
- Uma OC deve satisfazer os requisitos em **um mesmo registro**, sem somar dados incompletos de OCs diferentes.
- Arquivos de contratos pertencem ao contrato e usam armazenamento configurado.

## Workflow e estado operacional

`Equipment.current_stage` é a fase numérica 0–8 do fluxo de aquisição. O serviço de workflow no backend valida pré-condições, aplica transição e registra histórico. Um PATCH genérico de Equipment não deve ser usado para avançar estágio.

| Fase | Significado |
| --- | --- |
| 0 | Nova demanda |
| 1 | Negociação |
| 2 | Equalização |
| 3 | Abertura do chamado jurídico |
| 4 | Aprovação da minuta |
| 5 | Escrituração do contrato |
| 6 | SC ou OCI |
| 7 | Aprovação da OC |
| 8 | Concluído |

A regra vigente é progredir uma etapa por vez, com requisitos verificados por `backend/app/modules/workflow/stages.py`. O modelo de `RequirementWaiver` está indexado por equipamento, fase e grupo de requisitos; tem motivo, justificativa e auditoria. **Waiver não pula etapa** e não dispensa os grupos de conclusão: fornecedor, OC e valor total do projeto.

`operational_status` é independente da fase: `ACTIVE`, `STANDBY`, `CANCELLED` ou `IN_SANITATION`. Reabertura de processo usa solicitação/decisão; a capacidade de aprovar está atualmente no perfil ADMIN, sem afirmar que essa será a matriz corporativa definitiva.

## EAP: catálogo corporativo e contexto

~~~text
EapNode
ISLAND
 └─ PROCESS
    └─ AREA
~~~

- `EapNode.code` guarda o código corporativo, **sem prefixo de obra**.
- `ProjectContext.eap_prefix` é manual, opcional e não inferido de unidade, fase, nome de equipamento ou sequência numérica.
- Na exibição, prefixo e código EAP podem ser concatenados conforme a regra do contexto; o catálogo em si permanece canônico.
- `Equipment.eap_node_id` pode apontar para **PROCESS** ou **AREA**, nunca ISLAND.
- `Equipment.area_id` é legado durante a transição. Não sincronizar ou apagar automaticamente ao atribuir EAP.
- `ProjectEap` representa a ativação/relação de nós ao contexto; não presumir seu preenchimento em todos os bancos sem consultar o ambiente.

### Família geral e correções aprovadas

A família corporativa `00` representa áreas gerais; entre os exemplos aprovados estão `00.A` (Pipe Rack) e `00.C` (Drenagem). O texto de origem **“Geral” isolado não identifica um nó EAP** e deve continuar não resolvido até haver evidência específica.

As correções aprovadas para a leitura da Árvore incluem:

| Origem | Interpretação aprovada |
| --- | --- |
| `XX21`, `XX21.A` | Códigos corporativos `21` e `21.A` |
| `X02.G` | `06.G` |
| `X15.B` duplicado | Um único nó `15.B` |
| `X GERAL` | Cabeçalho visual; não é nó EAP |

A hierarquia segue a Árvore oficial e as correções aprovadas, **não** inferências pelo significado textual. Não inventar nós, prefixos ou parents por semelhança de nomes.

## Origem Monday e reconciliação

- **Monday** determina os equipamentos reais a importar, seus componentes, marcos e dados operacionais.
- **Árvore de Localização oficial** determina catálogo/hierarquia EAP.
- **LGE** é fonte complementar (nomenclaturas, parâmetros, lead times e referências), **não cria Equipment** nem mapeia EAP automaticamente.
- Para um equipamento, reconcilie o valor explícito de área/EAP informado na origem, associado a um mapping/alias aprovado. Nunca deduza EAP por `Equipment.name`.
- Match seguro pode ser aplicado; `REVIEW_*` e `UNRESOLVED_*` exigem revisão humana.
- Artefatos de reconciliação amarrados ao SHA do catálogo devem ser **regenerados/revistos** quando o catálogo mudar, nunca aplicados contornando a checagem de versão.

Fontes reais e artefatos corporativos podem ser necessários para operar esse fluxo, mas **não** devem ser incluídos no repositório público.

## Como alterar regras

Inspecione `backend/app/models/`, `backend/app/modules/workflow/`, migrations e testes antes de propor mudanças. Regras de origem específicas de um board devem entrar em configuração de `ProjectContext`/`ImportProfile` sempre que possível, preservando o modelo comum. Mudanças na cardinalidade, EAP e requisitos do workflow devem ser explicitamente aprovadas e testadas.

Consulte [importação Monday](importacao-monday.md), [arquitetura](arquitetura.md) e [API](api.md).
