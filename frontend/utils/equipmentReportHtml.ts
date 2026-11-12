import apexChartsRuntimeUrl from "apexcharts/dist/apexcharts.min.js?url";
import type { Equipment } from "~/types/equipment";
import type { EquipmentReportMetrics } from "~/utils/equipmentReport";
import { equipmentReportStatusGroup, formatReportDate } from "~/utils/equipmentReport";

export interface EquipmentReportHtmlInput {
  unitName: string;
  projectName: string;
  generatedAt: Date;
  metrics: EquipmentReportMetrics;
  equipments: Equipment[];
  logoDataUrl: string;
  apexChartsRuntime: string;
}

function escapeHtml(value: unknown): string {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function safeJson(value: unknown): string {
  return JSON.stringify(value)
    .replaceAll("<", "\\u003c")
    .replaceAll(">", "\\u003e")
    .replaceAll("&", "\\u0026")
    .replaceAll("\u2028", "\\u2028")
    .replaceAll("\u2029", "\\u2029");
}

function number(value: number): string {
  return new Intl.NumberFormat("pt-BR").format(value);
}

function percent(value: number): string {
  return `${value.toLocaleString("pt-BR", {
    minimumFractionDigits: 1,
    maximumFractionDigits: 1,
  })}%`;
}

function generatedLabel(value: Date): string {
  return value.toLocaleString("pt-BR", {
    dateStyle: "short",
    timeStyle: "short",
  });
}

function overdueRows(metrics: EquipmentReportMetrics): string {
  if (!metrics.overdueEquipments.length) {
    return '<tr><td class="empty" colspan="6">Nenhum equipamento com negociação em atraso.</td></tr>';
  }
  return metrics.overdueEquipments
    .map(
      ({ equipment, daysLate }) => `
      <tr>
        <td><button type="button" class="equipment-detail-link" data-equipment-id="${escapeHtml(equipment.id)}" aria-label="Ver detalhes de ${escapeHtml(equipment.name)}">${escapeHtml(equipment.name)}</button></td>
        <td><span class="stage">${escapeHtml(equipment.stageName)}</span></td>
        <td>${escapeHtml(equipment.responsibleUser?.name || "Não atribuído")}</td>
        <td>${escapeHtml(formatReportDate(equipment.calculated.negotiationDeadline))}</td>
        <td class="late">${escapeHtml(daysLate ?? "—")}</td>
        <td class="muted">Não informada</td>
      </tr>`,
    )
    .join("");
}

function embeddedRuntime(runtime: string): string {
  return runtime.replace(/<\/script/gi, "<\\/script");
}

/** Gera um snapshot autocontido. Não há URLs externas, tokens, chamadas de API
 * ou dependência do Nuxt: dados, CSS, logo e runtime ApexCharts ficam no HTML. */
export function buildEquipmentReportHtml(
  input: EquipmentReportHtmlInput,
): string {
  const { metrics } = input;
  const pipelineTotal = metrics.pipeline.reduce(
    (sum, item) => sum + item.count,
    0,
  );
  const chartData = {
    status: {
      series: [
        { name: "Concluído", data: [metrics.completed] },
        { name: "No prazo", data: [metrics.onTime] },
        { name: "Atrasado", data: [metrics.overdue] },
        { name: "Sem classificação", data: [metrics.unclassified] },
      ],
    },
    pipeline: {
      categories: metrics.pipeline.map((item) => item.label),
      series: [
        {
          name: "Equipamentos",
          data: metrics.pipeline.map((item) => item.count),
        },
      ],
    },
  };
  // Snapshot seguro para consulta offline. Nada depende de API depois do download.
  const overdueDays = new Map(
    metrics.overdueEquipments.map(({ equipment, daysLate }) => [equipment.id, daysLate]),
  );
  const detailRows = input.equipments.map((equipment) => ({
    id: equipment.id,
    name: equipment.name,
    stage: equipment.currentStage,
    stageName: equipment.stageName,
    group: equipmentReportStatusGroup(equipment),
    unit: equipment.unit.name,
    project: equipment.projectContext.name,
    responsible: equipment.responsibleUser?.name || "Não atribuído",
    deadline: formatReportDate(equipment.calculated?.negotiationDeadline),
    fields: [
      ["Unidade", equipment.unit.name],
      ["Obra", equipment.projectContext.name],
      ["Etapa de aquisição", equipment.stageName],
      ["Responsável", equipment.responsibleUser?.name || "Não atribuído"],
      ["Disciplina", equipment.discipline?.name || "Não informada"],
      ["Área / EAP", equipment.eapNode ? `${equipment.eapNode.code} · ${equipment.eapNode.name}` : equipment.area?.name || "Não informada"],
      ["Fornecedor", equipment.supplier?.name || "Não informado"],
      ["Work Packages", equipment.workPackages.map((wp) => wp.code || wp.name).join(", ") || "Não informados"],
      ["Origem", equipment.origin || "Não informada"],
      ["Criticidade", equipment.criticalityLabel?.name || equipment.criticality || "Não informada"],
      ["Startup", formatReportDate(equipment.startupAt)],
      ["Prazo limite de negociação", formatReportDate(equipment.calculated?.negotiationDeadline)],
      ["Dias em atraso", overdueDays.get(equipment.id) ?? "—"],
      ["Prazo limite de entrega em obra", formatReportDate(equipment.calculated?.deliveryDeadline)],
      ["Início da entrega contratual", formatReportDate(equipment.contractualDeliveryStart)],
      ["Fim da entrega contratual", formatReportDate(equipment.contractualDeliveryEnd)],
      ["Componentes", equipment.componentsCount],
      ["CAPEX estimado", equipment.capexEstimated ?? "Não informado"],
      ["Valor total do projeto", equipment.projectTotalValue ?? "Não informado"],
      ["Estado operacional", equipment.operationalStatus],
    ],
  }));
  const interactiveData = {
    equipments: detailRows,
    status: ["completed", "onTime", "overdue", "unclassified"].map((group) =>
      detailRows.filter((item) => item.group === group).map((item) => item.id),
    ),
    pipeline: metrics.pipeline.map(({ stage }) =>
      detailRows.filter((item) => item.stage === stage).map((item) => item.id),
    ),
  };
  const title = `Relatório executivo · ${input.projectName}`;

  return `<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <meta http-equiv="Content-Security-Policy" content="default-src 'none'; img-src data:; style-src 'unsafe-inline'; script-src 'unsafe-inline'; font-src data:; connect-src 'none'">
  <title>${escapeHtml(title)}</title>
  <style>
    /* ============================================
     * VARIÁVEIS CSS E RESET GLOBAL
     * ============================================ */
    
    /* Define esquemas de cores do tema:
       - Cores primárias: navy, green, amber, red
       - Cores de texto: ink, muted
       - Cores de borda/fundo: line, surface */
    :root{color-scheme:light;--navy:#304f7e;--navy-dark:#203b5d;--green:#609346;--amber:#eaa239;--red:#c26850;--ink:#263f5f;--muted:#68788c;--line:#e1e7ee;--surface:#f4f7fa}
    
    /* Reset global: define box-sizing para todos os elementos */
    *{box-sizing:border-box}
    
    /* Configurações básicas do HTML:
       - Scroll suave */
    html{scroll-behavior:smooth}
    
    /* Estilos do body:
       - Remove margens, define fundo claro e cor de texto principal
       - Fonte: Manrope (padronizada no projeto) com fallback para Arial/sans-serif */
    body{margin:0;background:#e9edf2;color:var(--ink);font-family:"Manrope",Arial,sans-serif;line-height:1.5}
    
    /* ============================================
     * LAYOUT PRINCIPAL
     * ============================================ */
    
    /* Contêiner da página:
       - Largura máxima de 1180px, com margens laterais de 32px
       - Margem superior de 28px, inferior de 50px */
    .page{width:min(1180px,calc(100% - 32px));margin:28px auto 50px}
    
    /* Cartão do relatório:
       - Borda arredondada, sombra suave e fundo branco */
    .report{overflow:hidden;border:1px solid #dbe3eb;border-radius:18px;background:#fff;box-shadow:0 22px 60px rgb(29 53 82 / 14%)}
    
    /* Barra de destaque superior:
       - Gradiente horizontal nas cores do tema (navy -> amber -> green) */
    .accent{height:6px;background:linear-gradient(90deg,var(--navy) 0 68%,var(--amber) 68% 84%,var(--green) 84%)}
    
    /* ============================================
     * HEADER
     * ============================================ */
    
    /* Cabeçalho do relatório:
       - Layout flex para alinhar logo e label
       - Borda inferior para separar visualmente do conteúdo */
    header{display:flex;align-items:center;justify-content:space-between;gap:20px;padding:20px 34px;border-bottom:1px solid var(--line)}
    header img{width:150px;height:auto}
    
    /* Label "RELATÓRIO EXECUTIVO":
       - Estilo de tag/pill com borda e fundo claro
       - Texto pequeno, negrito e com tracking */
    .label{padding:7px 12px;border:1px solid var(--line);border-radius:999px;background:#f8fafc;color:#61738a;font-size:11px;font-weight:750;letter-spacing:.08em}
    
    /* ============================================
     * HERO SECTION
     * ============================================ */
    main{padding:30px 34px 38px}
    
    /* Área do título principal:
       - Background com gradiente azul escuro
       - Círculo decorativo laranja (pseudo-elemento ::after) */
    .hero{position:relative;display:flex;align-items:flex-end;justify-content:space-between;min-height:190px;padding:34px;overflow:hidden;border-radius:16px;color:#fff;background:linear-gradient(115deg,#1e3a5b,#304f7e)}
    .hero:after{position:absolute;right:-50px;bottom:-90px;width:250px;height:250px;border-radius:50%;background:rgb(240 165 54 / 18%);content:""}
    
    /* Eyebrow text (categoria do conteúdo) */
    .eyebrow{margin:0 0 8px;color:rgb(255 255 255 / 70%);font-size:11px;font-weight:800;letter-spacing:.14em}
    
    /* Título principal e subtítulo:
       - z-index para garantir que fiquem acima do círculo decorativo
       - Fonte responsiva (clamp) entre 28px e 46px */
    .hero h1{position:relative;z-index:1;margin:0;font-size:clamp(28px,5vw,46px);line-height:1.1}
    .hero p:last-child{position:relative;z-index:1;margin:10px 0 0;color:rgb(255 255 255 / 76%)}
    
    /* ============================================
     * SEÇÕES E TÍTULOS
     * ============================================ */
    section{margin-top:34px}
    
    /* Título das seções:
       - Layout flex com número de índice e título
       - Gap de 11px entre índice e título */
    .section-title{display:flex;align-items:center;gap:11px;margin-bottom:13px}
    
    /* Número de índice (01, 02, 03):
       - Estilo de separador com borda à direita */
    .index{display:inline-flex;align-items:center;width:auto;height:22px;padding-right:10px;border-right:1px solid #d4dde8;color:#304f7e;background:transparent;font-size:10px;font-weight:800;letter-spacing:.08em}
    .section-title h2{margin:0;font-size:21px;color:#263f5f}
    
    /* Texto introdutório (lead):
       - Cor muted (secundária) */
    .lead{margin:0;color:var(--muted);font-size:15px}
    
    /* ============================================
     * CARDS DE MÉTRICAS (Resumo executivo)
     * ============================================ */
    
    /* Grid de 4 colunas para as métricas */
    .metrics{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin-top:20px}
    
    /* Card individual de métrica:
       - Borda arredondada, sombra suave
       - Fundo com gradiente sutil
       - Barra colorida no topo (pseudo-elemento ::before) */
    .metric{position:relative;display:grid;gap:4px;min-height:116px;padding:18px;overflow:hidden;border:1px solid var(--line);border-radius:13px;background:linear-gradient(145deg,#fff,#fafbfd);box-shadow:0 8px 20px rgb(39 62 91 / 6%)}
    .metric:before{position:absolute;inset:0 0 auto;height:4px;background:var(--navy);content:""}
    
    /* Variações de cor da barra superior conforme status:
       - success: verde (métricas positivas)
       - risk: vermelho (métricas de risco)
       - neutral: amber (métricas neutras) */
    .metric.success:before{background:var(--green)}
    .metric.risk:before{background:var(--red)}
    .metric.neutral:before{background:var(--amber)}
    
    /* Tipografia dentro dos cards:
       - span: label da métrica (ex: "Equipamentos")
       - strong: valor numérico principal
       - small: descrição secundária */
    .metric span{color:#76869a;font-size:11px;font-weight:750;text-transform:uppercase}
    .metric strong{color:var(--navy-dark);font-size:31px;letter-spacing:-.03em}
    .metric small{color:#98a3b0}
    
    /* ============================================
     * DASHBOARD (Gráficos)
     * ============================================ */
    
    /* Layout de grid para o dashboard:
       - Coluna principal (1.45fr) para gráficos
       - Sidebar (0.55fr, min 260px) para informações adicionais */
    .dashboard-grid{display:grid;grid-template-columns:minmax(0,1.45fr) minmax(260px,.55fr);gap:16px}
    
    /* Painel (contêiner do gráfico):
       - Borda, sombra e fundo branco */
    .panel{padding:20px;border:1px solid var(--line);border-radius:14px;background:#fff;box-shadow:0 9px 24px rgb(35 59 87 / 6%)}
    
    /* Cabeçalho do painel:
       - Layout flex entre label e título
       - Borda inferior para separar do conteúdo */
    .panel-head{display:flex;align-items:center;justify-content:space-between;gap:14px;padding-bottom:12px;border-bottom:1px solid #edf0f4}
    .panel-head span{color:#8a97a6;font-size:10px;font-weight:800;letter-spacing:.12em}
    .panel-head h3{margin:2px 0 0}
    .panel-head strong{color:var(--green);font-size:24px}
    
    /* Sidebar:
       - Layout de grid vertical */
    .side{display:grid;gap:16px}
    
    /* Card "Próximo Startup":
       - Fundo com gradiente azul claro
       - Estilo para label, valor e subtítulo */
    .startup{display:grid;gap:8px;padding:22px;border-radius:14px;background:linear-gradient(145deg,#eaf0f7,#f5f8fb)}
    .startup span{color:#5f7692;font-size:10px;font-weight:800;letter-spacing:.08em}
    .startup strong{color:#294c76;font-size:27px}
    .startup small{color:#72849a}
    
    /* Card "Pontos de atenção":
       - Borda vermelha clara, fundo com gradiente sutil */
    .attention{padding:22px;border:1px solid #ead8d1;border-radius:14px;background:linear-gradient(145deg,#fff,#fff8f5)}
    .attention strong{color:#9d503f}
    .attention p{margin:8px 0 0;color:var(--muted);font-size:13px}
    
    /* ============================================
     * SEÇÃO DE PIPELINE
     * ============================================ */
    
    /* Cabeçalho do pipeline:
       - Layout flex entre título e total */
    .pipeline-head{display:flex;align-items:center;justify-content:space-between;gap:20px}
    
    /* Contador total do pipeline:
       - Alinhado à direita */
    .pipeline-total{display:grid;text-align:right}
    .pipeline-total strong{font-size:27px}
    .pipeline-total span{color:var(--muted);font-size:11px;text-transform:uppercase}
    
    /* ============================================
     * COMENTÁRIOS EXECUTIVOS
     * ============================================ */
    
    /* Box de comentário:
       - Borda esquerda azul, fundo claro
       - Layout para destacar informação */
    .comment{margin-top:16px;padding:16px 18px;border-left:4px solid #7294ba;border-radius:8px;background:#eef4fa;color:#536b87}
    .comment strong{display:block}
    .comment p{margin:4px 0 0}
    
    /* ============================================
     * SEÇÃO DE RISCOS (Equipamentos em atraso)
     * ============================================ */
    
    /* Cabeçalho da seção de riscos:
       - Borda vermelha clara */
    .risk-head{
    display:flex;
    align-items:center;
    justify-content:space-between;
    gap:20px;
    padding:20px 22px}
    
    /* Contador de itens em risco */
    .risk-total{
    display:grid;
    min-width:100px;
    padding-left:20px;
    border-left:1px solid #ead3cc;
    text-align:right
    }

    .risk-total strong{color:#b65b47;font-size:30px;line-height:1}
    .risk-total span{color:#9a756c;font-size:10px;font-weight:800;text-transform:uppercase}
    
    /* ============================================
     * TABELAS
     * ============================================ */
    
    /* Contêiner da tabela:
       - Overflow auto para scroll horizontal se necessário
       - Borda e sombra */
    .table-wrap{margin-top:18px;overflow:auto;border:1px solid #dfe5eb;border-radius:12px;box-shadow:0 8px 20px rgb(39 62 91 / 5%)}
    table{width:100%;border-collapse:collapse;min-width:860px}
    th{padding:12px;background:var(--navy);color:#fff;font-size:11px;text-align:left;text-transform:uppercase;font-weight:800}
    td{padding:13px 12px;border-bottom:1px solid #edf0f4;color:#53657a;font-size:12px}
    tbody tr:nth-child(even){background:#f8fafc}
    
    /* Estilos específicos de células:
       - .stage: tag de etapa (pill azul claro)
       - .late: células com valores em atraso (fundo vermelho claro)
       - .muted: texto secundário
       - .empty: célula vazia */
    .stage{display:inline-block;padding:4px 8px;border-radius:999px;background:#e9eff6;color:#365b87}
    .late{background:#fff5f2;color:#ad4f3c;font-weight:800;text-align:center}
    .muted{color:#98a3b0}
    .empty{padding:38px;text-align:center}
    
    /* ============================================
     * FOOTER
     * ============================================ */
    
    /* Rodapé:
       - Layout flex para separar informações
       - Fundo claro, texto muted */
    footer{display:flex;justify-content:space-between;gap:16px;padding:15px 34px;border-top:1px solid var(--line);background:#f8fafc;color:#76869a;font-size:11px}
    
    /* ============================================
     * RESPONSIVIDADE
     * ============================================ */
    
    /* Em telas até 800px:
       - Reduz margens e padding
       - Esconde o label do header
       - Grid de métricas passa para 2 colunas
       - Dashboard passa para 1 coluna
       - Títulos de seção passam para layout vertical */
    @media(max-width:800px){
      .page{width:min(100% - 16px,1180px);margin:8px auto}
      .report{border-radius:12px}
      header,main,footer{padding-left:18px;padding-right:18px}
      .label{display:none}
      .hero{min-height:160px;padding:24px}
      .metrics{grid-template-columns:repeat(2,1fr)}
      .dashboard-grid{grid-template-columns:1fr}
      .pipeline-head,.risk-head{align-items:flex-start;flex-direction:column}
      .pipeline-total,.risk-total{padding:0;border:0;text-align:left}
    }
    
    /* Em telas até 480px:
       - Logo menor
       - Grid de métricas passa para 1 coluna
       - Tamanho de fonte do título reduzido
       - Cards de métricas mais compactos */
    @media(max-width:480px){
      header img{width:120px}
      .metrics{grid-template-columns:1fr}
      .hero h1{font-size:28px}
      .metric{min-height:100px}
    }
    
    /* Interações exclusivas do HTML; não alteram o layout do relatório. */
    .equipment-detail-link{border:0;background:none;padding:0;color:inherit;font:inherit;font-weight:800;text-align:left;cursor:pointer}
    .equipment-detail-link:hover,.equipment-detail-link:focus-visible{color:var(--navy);text-decoration:underline;text-underline-offset:3px}
    #status-chart .apexcharts-bar-area,#pipeline-chart .apexcharts-bar-area{cursor:pointer}
    .detail-overlay[hidden]{display:none}
    .detail-overlay{position:fixed;z-index:9999;inset:0;background:rgb(22 39 61 / 60%);display:flex;align-items:center;justify-content:center;padding:20px}
    .detail-dialog{width:min(900px,100%);max-height:min(90vh,940px);overflow:hidden;display:flex;flex-direction:column;border:1px solid #dce5ee;border-radius:16px;background:#fff;box-shadow:0 28px 80px rgb(0 0 0 / 25%)}
    .detail-head{display:flex;align-items:flex-start;justify-content:space-between;gap:18px;padding:22px 26px;border-bottom:1px solid var(--line)}
    .detail-head p{margin:0;color:var(--muted);font-size:11px;font-weight:800;letter-spacing:.08em;text-transform:uppercase}
    .detail-head h2{margin:4px 0 0;color:var(--ink);font-size:20px;line-height:1.3}
    .detail-close{flex:none;border:1px solid var(--line);border-radius:8px;background:#f8fafc;color:var(--ink);width:34px;height:34px;font-size:21px;cursor:pointer}
    .detail-body{overflow-y:auto;padding:22px 26px}
    .detail-caption{margin:0 0 16px;color:var(--muted);font-size:12px}
    .detail-table{width:100%;min-width:650px}
    .detail-table th{padding:11px 12px}
    .detail-table td{padding:12px}
    .detail-empty{padding:32px 12px;text-align:center;color:var(--muted)}
    .detail-back{border:0;background:none;padding:0 0 16px;color:var(--navy);font-size:12px;font-weight:800;cursor:pointer}
    .detail-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}
    .detail-field{min-width:0;border:1px solid var(--line);border-radius:9px;padding:12px 14px;background:#fbfcfe}
    .detail-field dt{font-size:10px;letter-spacing:.045em;color:var(--muted);font-weight:800;text-transform:uppercase}
    .detail-field dd{margin:5px 0 0;font-size:13px;color:var(--ink);overflow-wrap:anywhere}
    @media(max-width:600px){.detail-head,.detail-body{padding:16px}.detail-grid{grid-template-columns:1fr}.detail-head h2{font-size:17px}}
    /* Para impressão:
       - Remove fundos e sombras
       - Evita quebra de página dentro de painéis e tabelas */
    @media print{
      body{background:#fff}
      .page{width:100%;margin:0}
      .report{border:0;box-shadow:none}
      .panel,.metric,.table-wrap{break-inside:avoid}
      section{break-inside:avoid}
      .detail-overlay{display:none!important}
    }
  </style>
</head>
<body>
  <div class="page">
    <article class="report">
      <div class="accent"></div>
      <header>
        <img src="${escapeHtml(input.logoDataUrl)}" alt="Inpasa">
        <span class="label">RELATÓRIO EXECUTIVO · EQUIPAMENTOS</span>
      </header>
      <main>
        <div class="hero">
          <div><p class="eyebrow">CARTEIRA DE EQUIPAMENTOS</p><h1>${escapeHtml(input.projectName)}</h1><p>${escapeHtml(input.unitName)} · Emitido em ${escapeHtml(generatedLabel(input.generatedAt))}</p></div>
        </div>
        <section>
          <div class="section-title"><span class="index">01</span><h2>Resumo executivo</h2></div>
          <p class="lead">A carteira da obra possui <strong>${number(metrics.total)} aquisições previstas</strong>. Desse total, <strong>${number(metrics.completed)}</strong> aquisições já foram concluídas, representando aproximadamente <strong>${percent(metrics.completedPercent)}</strong> de avanço da carteira.</p>
          <div class="metrics">
            <div class="metric"><span>Equipamentos</span><strong>${number(metrics.total)}</strong><small>Carteira da obra</small></div>
            <div class="metric success"><span>Negociação concluída</span><strong>${number(metrics.completed)}</strong><small>${percent(metrics.completedPercent)} do total</small></div>
            <div class="metric risk"><span>Em atraso</span><strong>${number(metrics.overdue)}</strong><small>${percent(metrics.overduePercent)} do total</small></div>
            <div class="metric neutral"><span>Componentes</span><strong>${number(metrics.components)}</strong><small>Indicador técnico</small></div>
          </div>
        </section>
        <section class="dashboard-grid">
          <div class="panel"><div class="panel-head"><div><span>STATUS DA CARTEIRA</span><h3>Situação das negociações</h3></div><strong>${percent(metrics.completedPercent)}</strong></div><div id="status-chart" role="img" aria-label="Situação das negociações"></div></div>
          <div class="side">
            <div class="startup"><span>PRÓXIMO STARTUP CADASTRADO</span><strong>${escapeHtml(metrics.nextStartup ? formatReportDate(metrics.nextStartup) : "Não informado")}</strong><small>${escapeHtml(metrics.daysToNextStartup ?? "—")} dias restantes</small></div>
            <div class="attention"><strong>Principais pontos de atenção</strong><p>Os principais riscos da carteira estão concentrados nos equipamentos que permanecem nas etapas de Nova Demanda, Negociação e Equalização, uma vez que ainda não iniciaram o processo formal de aquisição.</p></div>
          </div>
        </section>
        <section>
          <div class="pipeline-head"><div class="section-title"><span class="index">02</span><div><h2>Pipeline de aquisição</h2><p class="lead">Distribuição por etapa após Negociação e Equalização</p></div></div><div class="pipeline-total"><strong>${number(pipelineTotal)}</strong><span>nas etapas posteriores</span></div></div>
          <div class="panel"><div id="pipeline-chart" role="img" aria-label="Distribuição de equipamentos por etapa"></div></div>
          <div class="comment"><strong>Comentário executivo</strong><p>Os equipamentos que já concluíram a negociação seguem o fluxo normal de aquisição, contratação e emissão de ordem de compra, sendo monitorados pelas áreas responsáveis.</p></div>
        </section>
        <section>
          <div class="risk-head"><div class="section-title"><span class="index">03</span><div><h2>Equipamentos em atraso na negociação</h2><p class="lead">Prioridades para acompanhamento · ${number(metrics.overdue)} equipamentos</p></div></div><div class="risk-total"><strong>${number(metrics.overdue)}</strong><span>em atraso</span></div></div>
          <div class="table-wrap"><table><thead><tr><th>Equipamento</th><th>Etapa</th><th>Responsável</th><th>Data limite</th><th>Dias em atraso</th><th>Tratativa</th></tr></thead><tbody>${overdueRows(metrics)}</tbody></table></div>
          <div class="comment"><strong>Comentário executivo</strong><p>${metrics.overdue ? "Os equipamentos listados acima possuem prazo de negociação vencido e estão sendo acompanhados junto aos responsáveis para a conclusão das tratativas e avanço ao processo de aquisição." : "Não há registros classificados como atrasados no momento da emissão."}</p></div>
          ${metrics.overdue ? '<div class="comment"><strong>Consideração final</strong><p>O principal ponto de atenção da carteira permanece nos equipamentos com negociação em atraso, uma vez que estes ainda não ingressaram no fluxo formal de aquisição e podem impactar o cronograma do projeto caso não sejam regularizados dentro do prazo.</p></div>' : ""}
        </section>
      </main>
      <footer><span>INPASA · Planejamento / Painel de Equipamentos</span><span>Snapshot emitido em ${escapeHtml(generatedLabel(input.generatedAt))}</span></footer>
    </article>
  </div>
  <div id="equipment-detail-overlay" class="detail-overlay" hidden aria-hidden="true">
    <section class="detail-dialog" role="dialog" aria-modal="true" aria-labelledby="equipment-detail-title" tabindex="-1">
      <div class="detail-head">
        <div><p>DETALHAMENTO DA CARTEIRA</p><h2 id="equipment-detail-title"></h2></div>
        <button type="button" class="detail-close" id="equipment-detail-close" aria-label="Fechar detalhes">×</button>
      </div>
      <div id="equipment-detail-content" class="detail-body"></div>
    </section>
  </div>
  <script>${embeddedRuntime(input.apexChartsRuntime)}</script>
  <script>
    "use strict";
    const reportData=${safeJson(chartData)};
    const interactiveData=${safeJson(interactiveData)};
    const overlay=document.getElementById('equipment-detail-overlay');
    const dialog=overlay.querySelector('.detail-dialog');
    const detailTitle=document.getElementById('equipment-detail-title');
    const detailContent=document.getElementById('equipment-detail-content');
    const closeButton=document.getElementById('equipment-detail-close');
    let previousFocus=null;
    let previousGroup=null;
    const equipmentById=new Map(interactiveData.equipments.map(function(item){return [item.id,item]}));
    function element(tag,cls,value){
      const node=document.createElement(tag);
      if(cls)node.className=cls;
      if(value!==undefined)node.textContent=String(value);
      return node;
    }
    function openOverlay(title){
      previousFocus=overlay.hidden?document.activeElement:previousFocus;
      detailTitle.textContent=title;
      overlay.hidden=false;
      overlay.setAttribute('aria-hidden','false');
      document.body.style.overflow='hidden';
      closeButton.focus();
    }
    function closeOverlay(){
      overlay.hidden=true;
      overlay.setAttribute('aria-hidden','true');
      document.body.style.overflow='';
      previousGroup=null;
      if(previousFocus&&typeof previousFocus.focus==='function')previousFocus.focus();
    }
    function showEquipmentDetails(item){
      if(!item)return;
      openOverlay(item.name);
      detailContent.replaceChildren();
      if(previousGroup){
        const back=element('button','detail-back','← Voltar à lista');
        back.type='button';
        back.addEventListener('click',function(){showGroup(previousGroup.title,previousGroup.ids)});
        detailContent.appendChild(back);
      }
      const grid=element('dl','detail-grid');
      item.fields.forEach(function(pair){
        const field=element('div','detail-field');
        field.appendChild(element('dt','',pair[0]));
        field.appendChild(element('dd','',pair[1]));
        grid.appendChild(field);
      });
      detailContent.appendChild(grid);
    }
    function showGroup(title,ids){
      const items=ids.map(function(id){return equipmentById.get(id)}).filter(Boolean);
      previousGroup={title:title,ids:ids};
      openOverlay(title);
      detailContent.replaceChildren();
      detailContent.appendChild(element('p','detail-caption',items.length+' equipamento(s) neste recorte.'));
      if(!items.length){detailContent.appendChild(element('p','detail-empty','Nenhum equipamento nesta classificação.'));return}
      const wrap=element('div','table-wrap');
      const table=element('table','detail-table');
      const thead=element('thead');
      const heading=element('tr');
      ['Equipamento','Obra','Etapa','Responsável','Prazo'].forEach(function(label){heading.appendChild(element('th','',label))});
      thead.appendChild(heading);
      table.appendChild(thead);
      const body=element('tbody');
      items.forEach(function(item){
        const tr=element('tr');
        const td=element('td');
        const button=element('button','equipment-detail-link',item.name);
        button.type='button';
        button.addEventListener('click',function(){showEquipmentDetails(item)});
        td.appendChild(button);
        tr.appendChild(td);
        [item.project,item.stageName,item.responsible,item.deadline].forEach(function(value){tr.appendChild(element('td','',value))});
        body.appendChild(tr);
      });
      table.appendChild(body);wrap.appendChild(table);detailContent.appendChild(wrap);
    }
    closeButton.addEventListener('click',closeOverlay);
    overlay.addEventListener('click',function(event){if(event.target===overlay)closeOverlay()});
    document.addEventListener('keydown',function(event){
      if(overlay.hidden)return;
      if(event.key==='Escape'){event.preventDefault();closeOverlay()}
      if(event.key==='Tab'){
        const focusable=Array.from(dialog.querySelectorAll('button:not([disabled])'));
        const first=focusable[0],last=focusable[focusable.length-1];
        if(event.shiftKey&&document.activeElement===first){event.preventDefault();last.focus()}
        else if(!event.shiftKey&&document.activeElement===last){event.preventDefault();first.focus()}
      }
    });
    document.addEventListener('click',function(event){
      const button=event.target.closest&&event.target.closest('[data-equipment-id]');
      if(button){previousGroup=null;showEquipmentDetails(equipmentById.get(button.dataset.equipmentId))}
    });
    const statusLabels=['Concluídos','No prazo','Atrasados','Sem classificação'];
    const common={chart:{fontFamily:'Manrope, Segoe UI, Arial, sans-serif',foreColor:'#667085',toolbar:{show:false},animations:{enabled:false}},noData:{text:'Sem dados'},tooltip:{theme:'light'}};
    const statusChart=new ApexCharts(document.querySelector('#status-chart'),{...common,chart:{...common.chart,type:'bar',stacked:true,stackType:'100%',height:230,events:{dataPointSelection:function(event,ctx,selection){const index=selection.seriesIndex;if(index>=0&&index<4)showGroup(statusLabels[index],interactiveData.status[index])},legendClick:function(ctx,index){if(index>=0&&index<4)showGroup(statusLabels[index],interactiveData.status[index])}}},series:reportData.status.series,colors:['#609346','#5b83b4','#c26850','#aab4c0'],plotOptions:{bar:{horizontal:true,borderRadius:5,barHeight:'55%'}},dataLabels:{enabled:true,formatter:value=>value>0?value.toFixed(1).replace('.',',')+'%':''},xaxis:{categories:['Carteira'],max:100,labels:{show:false}},yaxis:{show:false},legend:{show:true,position:'bottom',onItemClick:{toggleDataSeries:false}},grid:{show:false},tooltip:{y:{formatter:value=>value.toLocaleString('pt-BR')+' equipamento(s)'}}});
    const pipelineChart=new ApexCharts(document.querySelector('#pipeline-chart'),{...common,chart:{...common.chart,type:'bar',height:390,events:{dataPointSelection:function(event,ctx,selection){const index=selection.dataPointIndex;if(index>=0&&index<interactiveData.pipeline.length)showGroup(reportData.pipeline.categories[index],interactiveData.pipeline[index])}}},series:reportData.pipeline.series,colors:['#304f7e'],plotOptions:{bar:{horizontal:true,borderRadius:5,barHeight:'58%',dataLabels:{position:'top'}}},dataLabels:{enabled:true,offsetX:8,style:{colors:['#304f7e']},formatter:value=>value>0?value.toLocaleString('pt-BR'):''},xaxis:{categories:reportData.pipeline.categories,labels:{formatter:value=>Number(value).toLocaleString('pt-BR')}},legend:{show:false},grid:{borderColor:'#e7ebf0',strokeDashArray:4},tooltip:{y:{formatter:value=>value.toLocaleString('pt-BR')+' equipamento(s)'}}});
    Promise.all([statusChart.render(),pipelineChart.render()]).then(()=>{document.documentElement.dataset.chartsReady='true'}).catch(()=>{document.documentElement.dataset.chartsReady='false'});
  </script>
</body>
</html>`;
}

async function logoDataUrl(): Promise<string> {
  const response = await fetch("/brand/logo-inpasa.png", {
    credentials: "same-origin",
  });
  if (!response.ok)
    throw new Error("Não foi possível incorporar a logo da Inpasa ao HTML.");
  const bytes = new Uint8Array(await response.arrayBuffer());
  let binary = "";
  const chunkSize = 0x8000;
  for (let offset = 0; offset < bytes.length; offset += chunkSize) {
    binary += String.fromCharCode(
      ...bytes.subarray(offset, offset + chunkSize),
    );
  }
  return `data:${response.headers.get("content-type") || "image/png"};base64,${btoa(binary)}`;
}

async function apexRuntime(): Promise<string> {
  const response = await fetch(apexChartsRuntimeUrl, {
    credentials: "same-origin",
  });
  if (!response.ok)
    throw new Error(
      "Não foi possível incorporar os gráficos interativos ao HTML.",
    );
  return response.text();
}

/** Mesma fonte de HTML para download e prévia isolada no Hub.
 * O documento permanece autocontido, inclusive para uso offline. */
export async function generateEquipmentReportHtml(
  input: Omit<EquipmentReportHtmlInput, "logoDataUrl" | "apexChartsRuntime">,
): Promise<string> {
  const [logo, runtime] = await Promise.all([logoDataUrl(), apexRuntime()]);
  return buildEquipmentReportHtml({
    ...input,
    logoDataUrl: logo,
    apexChartsRuntime: runtime,
  });
}

export async function downloadEquipmentReportHtml(
  fileName: string,
  input: Omit<EquipmentReportHtmlInput, "logoDataUrl" | "apexChartsRuntime">,
): Promise<void> {
  const html = await generateEquipmentReportHtml(input);
  const blob = new Blob([html], { type: "text/html;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = fileName.toLowerCase().endsWith(".html")
    ? fileName
    : `${fileName}.html`;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 10_000);
}
