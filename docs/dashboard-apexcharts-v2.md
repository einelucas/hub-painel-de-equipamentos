# Dashboard Geral 2.0 — ApexCharts

**Origem do patch:** branch `main` no commit `6099bdd643f763d544a9ba1a4eb6637d0ab09681` (05/11/2026).

## Implementação

- Mantém `vue3-apexcharts` e `ChartCanvas.vue`, com renderização `ClientOnly`.
- Substitui visualizações operacionais por barras horizontais, medidor radial e barra empilhada.
- Introduz abas de análise por EAP/projeto/disciplina, cronograma e finanças/histórico.
- Novo endpoint `GET /api/v1/dashboard/analytics` no mesmo router e com a mesma permissão `EQUIPMENTS_READ` e filtros de `/dashboard/summary`.
- Reaproveita funções oficiais do domínio para o cálculo de risco de entrega; não cria novas fórmulas ou valores fictícios.
- O endpoint `summary` permanece sem alterações de contrato.

## Dados e limitações intencionais

- Agrupamento EAP usa `Equipment.eap_node_id`, nunca inferência pelo nome. Os nós `Sem EAP` são explícitos.
- Janela contratual só entra na timeline se ambas as datas existirem e forem válidas. Dias são inclusivos.
- Startups são eventos distintos de janelas contratuais. Os dados são os de `Equipment.startup_at`, não dos componentes.
- O gráfico de OC cobre os últimos 12 meses por `PurchaseOrder.ordered_at` e só considera ordens emitidas com número. Sem data ou sem valor não são projetadas no gráfico.
- `capex_estimated` não é substituído pela soma das OCs; só valores preenchidos entram no CAPEX por fase.
- Movimentações do workflow representam contagens de `WorkflowTransition`, não estoque histórico do pipeline. Dados importados sem histórico completo não são reconstruídos.
- Barras EAP/áreas mostram no máximo 10/12 grupos, comunicando quantos não estão visíveis. Os KPIs continuam considerando o recorte completo.
- O dashboard continua utilizável mesmo que o endpoint de analytics falhe: KPIs e gráficos originais são independentes.

## Instalação

Extrair o ZIP **na raiz do repositório**, substituindo arquivos com os mesmos caminhos. Não requer migrations nem dependências novas.

```sh
cd frontend
pnpm install --frozen-lockfile
pnpm lint
pnpm typecheck
pnpm test
pnpm build
```

```sh
cd backend
python -m ruff check app/modules/dashboard tests/unit/test_dashboard_analytics.py
python -m pytest tests/unit/test_dashboard_analytics.py
```

Testar também `/api/v1/dashboard/analytics` com papéis `VIEWER`, `ANALYST` e `ADMIN`, unidade limitada e recorte vazio. Validar no ambiente TEST, antes de promover a DEV/produção.

**Aviso:** o patch foi produzido por inspeção de código do GitHub, não foi aplicado em banco nem publicado. O build completo requer as dependências do repositório e deve ser executado no ambiente do projeto. Antes de produção, revisar a licença corporativa do ApexCharts.
