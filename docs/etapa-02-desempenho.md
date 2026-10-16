# Etapa 2 — Desempenho

## Escopo

Otimização dos carregamentos mais frequentes do módulo: Dashboard, listagem de
equipamentos, filas operacionais e catálogos usados pelos filtros.

## Backend

- As quatro agregações repetidas do Dashboard (componentes, CAPEX, OCs e
  negociações concluídas) passaram a ser obtidas em um único round-trip SQL.
- Os cálculos de prazo de cada equipamento são feitos uma vez e reutilizados
  pelos dois cards de prazo.
- Cada fila carrega somente os processos usados por suas etapas:
  Engenharia busca negociação; Jurídico busca processo jurídico e contratos;
  Suprimentos busca SC/OCI e OCs.
- A autorização por unidade reaproveita o escopo já carregado no request.
- A migration `0021_performance_indexes` adiciona índices compostos para os
  filtros das filas e para os relacionamentos 1:N de contratos, SC/OCI e OCs.

## Cache do frontend

O cache é apenas em memória no navegador e separado pela credencial atual:

- 5 minutos para catálogos;
- 30 segundos para Dashboard, equipamentos e filas;
- requisições simultâneas idênticas são coalescidas;
- qualquer POST, PUT, PATCH ou DELETE bem-sucedido invalida todas as leituras;
- login, sessão, notificações e defaults de primeiro acesso não são cacheados;
- SSR não compartilha o cache entre usuários.

## Medição

Os testes medem round-trips, que são estáveis na CI e representam diretamente
o custo de latência entre Railway e Neon.

| Fluxo | Antes | Depois | Redução mínima |
| --- | ---: | ---: | ---: |
| Dashboard filtrado por unidade | 11 SELECTs | até 7 SELECTs | 36% |
| Fila de Engenharia filtrada por unidade | 14 SELECTs | até 8 SELECTs | 42% |
| Segunda leitura frontend idêntica dentro do TTL | 2 HTTP | 1 HTTP | 50% |
| Duas leituras frontend simultâneas idênticas | 2 HTTP | 1 HTTP | 50% |

Os limites de consultas estão cobertos por
`test_dashboard_and_engineering_queue_have_bounded_query_counts`; cache,
coalescência e invalidação estão cobertos em `useApi.test.ts`.
