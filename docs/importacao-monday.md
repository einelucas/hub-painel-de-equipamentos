# Importação Monday → domínio do Hub

O motor de importação converte boards operacionais aprovados em entidades do Hub. **Não copia um quadro para novas tabelas**, não cria aplicações por obra e não usa a LGE como fonte de Equipment.

~~~mermaid
flowchart LR
  XLSX["Export Monday aprovado"] --> PROFILE["ImportProfile"]
  PROFILE --> PARSE["Parse/normalize"]
  PARSE --> STAGE["Staging e issues"]
  STAGE --> PLAN["Mapping e plan"]
  PLAN --> DRY["Revisão/dry-run"]
  DRY --> APPLY["Apply transacional autorizado"]
  APPLY --> REC["Reconciliation e auditoria"]
~~~

## Fontes e responsabilidade

- **Monday:** equipamentos reais, componentes/subitens, status, responsáveis, contratos, SC/OCI, OC e referências operacionais.
- **Árvore de Localização oficial:** catálogo e hierarquia EAP; correções aprovadas são parte da política de mapeamento.
- **LGE:** fonte complementar de parâmetros, nomenclatura, referências e indicadores; não produz Equipment nem ExternalMapping em massa.
- **Contexto do Hub:** `Unit` e `ProjectContext` identificam a obra/fase. O prefixo EAP é configurado manualmente.

Fontes reais devem permanecer fora do repositório público.

## Componentes implementados

| Parte | Local |
| --- | --- |
| Endpoints administrativos | `backend/app/modules/imports/controllers.py` |
| Orquestração HTTP, stage/plan/mapping | `backend/app/modules/imports/services.py` |
| Jobs de apply e estado/progresso | `backend/app/modules/imports/apply_jobs.py` |
| Motor/parser/normalização/planejamento | `backend/app/modules/monday_import/` |
| CLI administrativa | `backend/app/modules/monday_import/cli.py` |
| Modelos de staging | `backend/app/models/monday_import.py` |
| EAP | `backend/app/modules/eap_catalog/` e `eap_reconciliation/` |
| Interface | `frontend/components/imports/` e módulos de administração |

## Profiles: adaptar origem sem duplicar domínio

`ImportProfile` é um arquivo JSON declarativo para diferenças de boards: nomes de colunas, grupos, status, identificadores, campos opcionais/ignorados, mapeamento de conceitos e expectativas de contagem. O motor recebe o profile como dado; não exija um script `import_<nova_obra>.py` por board.

A identidade externa deve priorizar o **Item ID do Monday** quando disponível/confiável. Fallback por nome/contexto cria risco de duplicação após renomeação; preserve mapping e reporte conflitos. Para componentes, prefira o identificador do subitem quando existir. Não faça deduplicação fuzzy silenciosa.

## Fluxo pela interface

A API expõe `/api/v1/imports/monday`:

1. `GET /profiles` — perfis disponíveis.
2. `POST /batches` — arquivo XLSX, profile e contexto; grava **staging**, não Equipment.
3. `GET /batches/{batch_id}` — erros, avisos e informações do lote.
4. `POST /plan` — produz proposta com mappings, validações e bloqueios.
5. Revisão humana do plano e dos conflitos, incluindo valores desconhecidos e catálogos.
6. `POST /apply` — aceita operação (HTTP 202) e inicia job sujeito a confirmação e proteções.
7. `GET /apply/{job_id}` — consulta status/progresso/resultado; verificar reconciliação final.

Um upload válido **não significa que dados foram aplicados**. Múltiplos batches e um mesmo contexto exigem idempotência e prevenção de concorrência.

## CLI do motor

Executar em `backend/` com ambiente explícito:

~~~bash
python -m app.modules.monday_import --help
python -m app.modules.monday_import dry-run --help
python -m app.modules.monday_import stage --help
python -m app.modules.monday_import plan --help
python -m app.modules.monday_import apply --help
python -m app.modules.monday_import reconcile --help
~~~

Verifique opções e assinatura efetiva via `--help` antes de executar; operações de apply exigem `--confirm` e bloqueios de segurança. Jamais use um arquivo real para demonstração pública.

## Política de transformação

- Normalizar colunas conhecidas por conceito, mantendo o valor raw original para rastreabilidade.
- Colunas desconhecidas devem ser relatadas e preservadas no estágio raw, nunca descartadas silenciosamente.
- Fórmulas/mirrors da planilha devem virar cálculos do domínio/SQL/API quando houver regra confirmada. Campo incompleto retorna estado não calculável, não fórmula inventada.
- Mappings de disciplina, responsável, área/EAP e fornecedores precisam ser aprovados no contexto correspondente.
- Um fornecedor pode ser corporativo global; reconciliação prioriza código/CNPJ e aliases aprovados, sem mesclagem por nome parecido.
- Equipamentos importados continuam submetidos ao workflow e às cardinalidades atuais do domínio; import não cria exceções globais.

## Segurança, aplicação e reconciliação

`plan` deve ser reproduzível e revisado; `apply` deve validar versão/contexto, abortar em conflito, executar transações e deixar auditoria. O backend possui guardas para destinos de desenvolvimento/teste; isso **não** substitui autorização humana, backup ou homologação. Não rode imports em produção apenas porque o endpoint existe.

Em EAP, a associação é uma operação distinta: catálogo oficial privado → normalização do valor de área/EAP Monday → match seguro → revisão de ambiguidades → apply. Não infira EAP por nome do equipamento; preserve `area_id` legado durante a transição. Artefatos presos ao SHA do catálogo exigem regeneração antes de novo apply.

**Checklist de reconciliação:** contagem de equipamentos/componentes, identidades externas, work packages, fornecedores, contratos, solicitações, OCs, estados, pendências não resolvidas e logs/auditoria. Não declarar sucesso só porque HTTP retornou 202.

Veja [domínio e EAP](dominio-eap.md), [API](api.md), [ambientes](ambientes-deploy.md) e [testes](testes.md).
