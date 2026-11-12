<script setup lang="ts">
import { computed, nextTick, onMounted, ref } from "vue";
import type { ApexOptions } from "apexcharts";
import {
  mdiFilePdfBox,
  mdiImageOutline,
  mdiLanguageHtml5,
  mdiRefresh,
} from "@mdi/js";
import { CalendarClock, Clock3 } from "lucide-vue-next";
import {
  VAlert,
  VBtn,
  VCard,
  VCardText,
  VChip,
  VDivider,
  VProgressLinear,
  VSkeletonLoader,
  VTable,
} from "vuetify/components";
import type { Equipment, EquipmentList } from "~/types/equipment";
import {
  buildEquipmentReport,
  chunks,
  formatReportDate,
  type EquipmentReportMetrics,
} from "~/utils/equipmentReport";
import { collectAllPages } from "~/utils/pagination";
import {
  captureReportElement,
  stitchReportCanvases,
  waitForReportAssets,
} from "~/utils/reportCapture";

const props = defineProps<{
  unitId: string;
  projectContextId: string;
  unitName: string;
  projectName: string;
}>();
const emit = defineEmits<{ close: [] }>();
const api = useApi();
const previewEl = ref<HTMLElement | null>(null);
const previewMode = ref<"pdf" | "html">("pdf");
const htmlPreview = ref("");
const htmlPreviewLoading = ref(false);
const loading = ref(true);
const downloading = ref<"pdf" | "png" | "html" | null>(null);
const error = ref("");
const downloadError = ref("");
const progress = ref("");
const rows = ref<Equipment[]>([]);
const generatedAt = ref(new Date());

const metrics = computed<EquipmentReportMetrics>(() =>
  buildEquipmentReport(rows.value, generatedAt.value),
);
const overduePages = computed(() =>
  chunks(metrics.value.overdueEquipments, 10),
);
const pageCount = computed(() => 1 + overduePages.value.length);
const busy = computed(
  () => loading.value || downloading.value !== null || htmlPreviewLoading.value,
);
const totalLabel = computed(() => number(metrics.value.total));
const generatedLabel = computed(() =>
  generatedAt.value.toLocaleString("pt-BR", {
    dateStyle: "short",
    timeStyle: "short",
  }),
);
const fileBase = computed(
  () =>
    `report-equipamentos-${slug(props.unitName)}-${slug(props.projectName)}-${generatedAt.value
      .toISOString()
      .slice(0, 10)}`,
);

const statusSeries = computed(() => [
  { name: "Concluído", data: [metrics.value.completed] },
  { name: "No prazo", data: [metrics.value.onTime] },
  { name: "Atrasado", data: [metrics.value.overdue] },
  { name: "Sem classificação", data: [metrics.value.unclassified] },
]);
const statusChartOptions = computed<ApexOptions>(() => ({
  chart: {
    animations: { enabled: false },
    stacked: true,
    stackType: "100%",
    toolbar: { show: false },
  },
  colors: ["#609346", "#5b83b4", "#c26850", "#aab4c0"],
  legend: { show: false },
  dataLabels: {
    enabled: true,
    formatter: (value: number) =>
      value > 0 ? `${value.toFixed(1).replace(".", ",")}%` : "",
    style: { colors: ["#ffffff"], fontSize: "8px", fontWeight: 700 },
    dropShadow: { enabled: false },
  },
  plotOptions: {
    bar: {
      horizontal: true,
      barHeight: "56%",
      borderRadius: 4,
      borderRadiusApplication: "around",
      borderRadiusWhenStacked: "all",
      dataLabels: {
        position: "center",
        hideOverflowingLabels: false,
      },
    },
  },
  grid: { show: false, padding: { top: -16, right: 0, bottom: -18, left: 0 } },
  stroke: { colors: ["#ffffff"], width: 1 },
  xaxis: {
    categories: ["Carteira"],
    max: 100,
    labels: { show: false },
    axisBorder: { show: false },
    axisTicks: { show: false },
  },
  yaxis: { show: false },
  tooltip: {
    y: { formatter: (value: number) => `${number(value)} equipamento(s)` },
  },
}));

const pipelineSeries = computed(() => [
  {
    name: "Equipamentos",
    data: metrics.value.pipeline.map((item) => item.count),
  },
]);
const pipelineTotal = computed(() =>
  metrics.value.pipeline.reduce((sum, item) => sum + item.count, 0),
);
const pipelineChartOptions = computed<ApexOptions>(() => ({
  chart: { animations: { enabled: false } },
  colors: ["#304f7e"],
  grid: { borderColor: "#e7ebf0", strokeDashArray: 4 },
  dataLabels: {
    enabled: true,
    formatter: (value: number) => (value > 0 ? number(value) : ""),
    textAnchor: "start",
    offsetX: 7,
    style: {
      colors: ["#304f7e"],
      fontSize: "10px",
      fontWeight: 700,
    },
    background: { enabled: false },
  },
  plotOptions: {
    bar: {
      borderRadius: 4,
      borderRadiusApplication: "end",
      horizontal: true,
      barHeight: "58%",
      dataLabels: { position: "top" },
    },
  },
  xaxis: {
    categories: metrics.value.pipeline.map((item) => item.label),
    labels: { formatter: (value: string) => number(Number(value)) },
  },
  yaxis: { labels: { maxWidth: 190, style: { fontSize: "10px" } } },
  tooltip: {
    y: { formatter: (value: number) => `${number(value)} equipamento(s)` },
  },
}));

function slug(value: string): string {
  return value
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "")
    .slice(0, 48);
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

/** O relatório sempre representa toda a obra selecionada. Filtros locais da
 * tabela de equipamentos não são propagados para esta consulta. */
async function loadReport(): Promise<void> {
  loading.value = true;
  rows.value = [];
  htmlPreview.value = "";
  error.value = "";
  downloadError.value = "";
  progress.value = "Consultando a carteira da obra...";
  try {
    const equipments = await collectAllPages<Equipment>(
      (page) =>
        api.get<EquipmentList>(
          "/equipments",
          {
            unit_id: props.unitId,
            project_context_id: props.projectContextId,
            page,
            pageSize: 100,
            sortBy: "name",
          },
          { force: true },
        ),
      {
        onProgress: (page, totalPages) => {
          progress.value = `Carregando equipamentos · página ${page} de ${totalPages}`;
        },
      },
    );
    if (
      equipments.some(
        (item) =>
          item.unit.id !== props.unitId ||
          item.projectContext.id !== props.projectContextId,
      )
    ) {
      throw new Error(
        "A API retornou equipamentos de outra obra. O relatório foi bloqueado por segurança.",
      );
    }
    generatedAt.value = new Date();
    rows.value = equipments;
    if (previewMode.value === "html" && rows.value.length) {
      try {
        progress.value = "Atualizando a visualização HTML...";
        await refreshHtmlPreview();
      } catch (caught) {
        previewMode.value = "pdf";
        downloadError.value =
          caught instanceof Error
            ? caught.message
            : "Não foi possível atualizar a visualização HTML.";
      }
    }
    await nextTick();
  } catch (caught) {
    error.value =
      caught instanceof Error ? caught.message : "Falha ao gerar o relatório.";
  } finally {
    loading.value = false;
    progress.value = "";
  }
}

function reportElements(): HTMLElement[] {
  const elements = [
    ...(previewEl.value?.querySelectorAll<HTMLElement>(".report-page") ?? []),
  ];
  if (elements.length !== pageCount.value) {
    throw new Error("O relatório não terminou de renderizar.");
  }
  return elements;
}

async function prepareExport(): Promise<HTMLElement[]> {
  await nextTick();
  const pages = reportElements();
  await waitForReportAssets(previewEl.value ?? pages[0]!);
  return pages;
}

async function savePdf(): Promise<void> {
  if (busy.value || !rows.value.length) return;
  // A exportação PDF continua usando as páginas Vue, mesmo na prévia HTML.
  const restoreHtml = previewMode.value === "html";
  if (restoreHtml) previewMode.value = "pdf";
  downloading.value = "pdf";
  downloadError.value = "";
  try {
    const pages = await prepareExport();
    const { jsPDF } = await import("jspdf");
    const pdf = new jsPDF({
      orientation: "portrait",
      unit: "mm",
      format: "a4",
      compress: true,
    });
    for (let index = 0; index < pages.length; index += 1) {
      progress.value = `Preparando PDF · página ${index + 1} de ${pages.length}`;
      if (index > 0) pdf.addPage();
      const canvas = await captureReportElement(pages[index]!, { scale: 2 });
      pdf.addImage(
        canvas.toDataURL("image/jpeg", 0.92),
        "JPEG",
        0,
        0,
        210,
        297,
      );
    }
    pdf.save(`${fileBase.value}.pdf`);
  } catch (caught) {
    downloadError.value =
      caught instanceof Error
        ? caught.message
        : "Não foi possível salvar o PDF.";
  } finally {
    if (restoreHtml) previewMode.value = "html";
    downloading.value = null;
    progress.value = "";
  }
}

async function saveHtml(): Promise<void> {
  if (busy.value || !rows.value.length) return;
  downloading.value = "html";
  downloadError.value = "";
  progress.value = "Preparando HTML interativo e incorporando os gráficos...";
  try {
    const { downloadEquipmentReportHtml } = await import(
      "~/utils/equipmentReportHtml"
    );
    await downloadEquipmentReportHtml(`${fileBase.value}.html`, {
      unitName: props.unitName,
      projectName: props.projectName,
      generatedAt: generatedAt.value,
      metrics: metrics.value,
    });
  } catch (caught) {
    downloadError.value =
      caught instanceof Error
        ? caught.message
        : "Não foi possível salvar o HTML.";
  } finally {
    downloading.value = null;
    progress.value = "";
  }
}

/** Monta exatamente o documento autônomo gerado pelo botão Salvar HTML. */
async function refreshHtmlPreview(): Promise<void> {
  const { generateEquipmentReportHtml } = await import(
    "~/utils/equipmentReportHtml"
  );
  htmlPreview.value = await generateEquipmentReportHtml({
    unitName: props.unitName,
    projectName: props.projectName,
    generatedAt: generatedAt.value,
    metrics: metrics.value,
  });
}

async function togglePreview(): Promise<void> {
  if (busy.value || !rows.value.length) return;
  if (previewMode.value === "html") {
    previewMode.value = "pdf";
    return;
  }
  if (!htmlPreview.value) {
    htmlPreviewLoading.value = true;
    downloadError.value = "";
    progress.value = "Preparando a visualização HTML...";
    try {
      await refreshHtmlPreview();
    } catch (caught) {
      downloadError.value =
        caught instanceof Error
          ? caught.message
          : "Não foi possível visualizar o modelo HTML.";
      return;
    } finally {
      htmlPreviewLoading.value = false;
      progress.value = "";
    }
  }
  previewMode.value = "html";
}

function saveCanvas(
  canvas: HTMLCanvasElement,
  filename: string,
): Promise<void> {
  return new Promise((resolve, reject) => {
    canvas.toBlob((blob) => {
      if (!blob) {
        reject(new Error("O navegador não conseguiu preparar a imagem PNG."));
        return;
      }
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = filename;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      window.setTimeout(() => URL.revokeObjectURL(url), 10_000);
      resolve();
    }, "image/png");
  });
}

/** Até seis páginas por PNG para não ultrapassar o limite de canvas de
 * navegadores móveis. Relatórios maiores são divididos em arquivos numerados. */
async function savePng(): Promise<void> {
  if (busy.value || !rows.value.length) return;
  const restoreHtml = previewMode.value === "html";
  if (restoreHtml) previewMode.value = "pdf";
  downloading.value = "png";
  downloadError.value = "";
  try {
    const pages = await prepareExport();
    for (let start = 0; start < pages.length; start += 6) {
      const batch = pages.slice(start, start + 6);
      const captured: HTMLCanvasElement[] = [];
      for (let index = 0; index < batch.length; index += 1) {
        progress.value = `Preparando PNG · página ${start + index + 1} de ${pages.length}`;
        captured.push(
          await captureReportElement(batch[index]!, { scale: 1.5 }),
        );
      }
      const canvas = stitchReportCanvases(captured);
      const suffix =
        pages.length > 6
          ? `-paginas-${String(start + 1).padStart(2, "0")}-${String(start + batch.length).padStart(2, "0")}`
          : "";
      await saveCanvas(canvas, `${fileBase.value}${suffix}.png`);
    }
  } catch (caught) {
    downloadError.value =
      caught instanceof Error
        ? caught.message
        : "Não foi possível salvar o PNG.";
  } finally {
    if (restoreHtml) previewMode.value = "html";
    downloading.value = null;
    progress.value = "";
  }
}

onMounted(() => void loadReport());
</script>

<template>
  <AppModal
    :open="true"
    :title="`Relatório executivo · ${projectName}`"
    size="wide"
    :busy="downloading !== null"
    @close="emit('close')"
  >
    <div class="report-shell">
      <div class="report-toolbar">
        <div class="report-toolbar-copy">
          <strong>{{ unitName }} · {{ projectName }}</strong>
          <span>Escopo completo da obra · dados consultados no Hub</span>
        </div>
        <div class="report-toolbar-actions">
          <VBtn
            variant="outlined"
            color="secondary"
            size="small"
            :prepend-icon="mdiRefresh"
            :disabled="busy"
            @click="loadReport"
          >
            Atualizar
          </VBtn>
          <VBtn
            variant="tonal"
            color="primary"
            size="small"
            :prepend-icon="mdiFilePdfBox"
            :loading="downloading === 'pdf'"
            :disabled="busy || !rows.length"
            data-testid="report-pdf"
            @click="savePdf"
          >
            Salvar PDF
          </VBtn>
          <VBtn
            variant="outlined"
            color="primary"
            size="small"
            :prepend-icon="mdiLanguageHtml5"
            :loading="downloading === 'html'"
            :disabled="busy || !rows.length"
            data-testid="report-html"
            @click="saveHtml"
          >
            Salvar HTML
          </VBtn>
          <VBtn
            variant="outlined"
            color="primary"
            size="small"
            :icon="previewMode === 'pdf' ? mdiLanguageHtml5 : mdiFilePdfBox"
            :loading="htmlPreviewLoading"
            :disabled="busy || !rows.length"
            :aria-label="previewMode === 'pdf' ? 'Visualizar modelo HTML' : 'Voltar à visualização PDF'"
            :aria-pressed="previewMode === 'html'"
            :title="previewMode === 'pdf' ? 'Visualizar modelo HTML' : 'Voltar à visualização PDF'"
            data-testid="report-preview-toggle"
            @click="togglePreview"
          />
          <VBtn
            variant="outlined"
            color="primary"
            size="small"
            :prepend-icon="mdiImageOutline"
            :loading="downloading === 'png'"
            :disabled="busy || !rows.length"
            data-testid="report-png"
            @click="savePng"
          >
            Salvar PNG
          </VBtn>
        </div>
      </div>

      <div v-if="busy" class="report-progress" role="status" aria-live="polite">
        <VProgressLinear indeterminate color="primary" height="3" />
        <span>{{
          progress ||
          (loading ? "Preparando relatório..." : "Gerando arquivo...")
        }}</span>
      </div>

      <VAlert v-if="error" type="error" variant="tonal" density="compact">
        <div class="report-alert-content">
          <span
            ><strong>Não foi possível preparar o relatório.</strong>
            {{ error }}</span
          >
          <VBtn variant="outlined" size="small" @click="loadReport"
            >Tentar novamente</VBtn
          >
        </div>
      </VAlert>
      <VAlert
        v-else-if="downloadError"
        type="error"
        variant="tonal"
        density="compact"
        closable
        @click:close="downloadError = ''"
      >
        {{ downloadError }}
      </VAlert>

      <div v-if="loading" class="report-loading" aria-hidden="true">
        <VSkeletonLoader type="heading, paragraph, image, paragraph" />
      </div>
      <VAlert
        v-else-if="!error && !rows.length"
        type="info"
        variant="tonal"
        title="Sem equipamentos nesta obra"
        text="O relatório não será exportado sem registros cadastrados no contexto selecionado."
      />

      <div
        v-if="!error && rows.length && previewMode === 'pdf'"
        ref="previewEl"
        class="report-preview"
      >
        <VCard class="report-page" elevation="1" rounded="lg">
          <div class="report-accent" />
          <header class="paper-header">
            <img
              class="paper-logo"
              src="/brand/logo-inpasa.png"
              alt="Inpasa"
              crossorigin="anonymous"
            />
            <span class="paper-label">RELATÓRIO EXECUTIVO · EQUIPAMENTOS</span>
          </header>
          <VDivider />
          <VCardText class="paper-content">
            <div class="paper-heading paper-heading--cover">
              <div class="cover-copy">
                <p class="paper-kicker">CARTEIRA DE EQUIPAMENTOS</p>
                <h1>{{ projectName }}</h1>
                <p class="paper-subtitle">
                  {{ unitName }} · Emitido em {{ generatedLabel }}
                </p>
              </div>
            </div>

            <section class="paper-section">
              <div class="section-title">
                <span class="section-index">01</span>
                <h2>Resumo executivo</h2>
              </div>
              <p class="paper-paragraph">
                A carteira da obra possui
                <b>{{ totalLabel }} Aquisições previstas</b>. Desse total,
                <b>{{ number(metrics.completed) }}</b> aquisições já foram
                concluídas, representando aproximadamente
                <b>{{ percent(metrics.completedPercent) }}</b> de avanço da
                carteira.
              </p>
            </section>

            <section class="paper-section overview-grid">
              <VCard class="chart-panel" variant="outlined" rounded="lg">
                <div class="panel-heading">
                  <div>
                    <span>STATUS DA CARTEIRA</span>
                    <h3 class="minor-heading">Situação das negociações</h3>
                  </div>
                  <div class="completion-total">
                    <strong>{{ number(metrics.completed) }}</strong>
                    <small>de {{ totalLabel }} concluídas</small>
                  </div>
                </div>
                <ChartCanvas
                  class="report-chart status-chart"
                  type="bar"
                  :options="statusChartOptions"
                  :series="statusSeries"
                  :height="105"
                  label="Distribuição da situação das negociações"
                />
                <div
                  class="status-chips"
                  aria-label="Legenda da situação das negociações"
                >
                  <VChip size="x-small" color="success" variant="tonal"
                    >Concluído · {{ number(metrics.completed) }}</VChip
                  >
                  <VChip size="x-small" color="primary" variant="tonal"
                    >No prazo · {{ number(metrics.onTime) }}</VChip
                  >
                  <VChip size="x-small" color="error" variant="tonal"
                    >Atrasado · {{ number(metrics.overdue) }}</VChip
                  >
                  <VChip size="x-small" variant="tonal"
                    >Sem classificação ·
                    {{ number(metrics.unclassified) }}</VChip
                  >
                </div>
              </VCard>
              <div class="overview-side">
                <VCard
                  class="startup-card"
                  variant="tonal"
                  color="primary"
                  rounded="lg"
                >
                  <div class="startup-card-heading">
                    <span>PRÓXIMO STARTUP CADASTRADO</span>
                    <span class="startup-icon" aria-hidden="true">
                      <CalendarClock :size="18" :stroke-width="1.8" />
                    </span>
                  </div>
                  <strong>{{
                    metrics.nextStartup
                      ? formatReportDate(metrics.nextStartup)
                      : "Não informado"
                  }}</strong>
                  <div class="startup-countdown">
                    <Clock3 :size="12" :stroke-width="2" aria-hidden="true" />
                    <small
                      >{{ metrics.daysToNextStartup ?? "—" }} dias
                      restantes</small
                    >
                  </div>
                </VCard>
                <VCard class="attention-card" variant="outlined" rounded="lg">
                  <strong>Principais pontos de atenção</strong>
                  <p>
                    Os principais riscos da carteira estão concentrados nos
                    equipamentos que permanecem nas etapas de Nova Demanda,
                    Negociação e Equalização, uma vez que ainda não iniciaram o
                    processo formal de aquisição.
                  </p>
                </VCard>
              </div>
            </section>

            <section class="paper-section pipeline-section">
              <div class="pipeline-heading">
                <div class="section-title">
                  <span class="section-index">02</span>
                  <div>
                    <h2>Pipeline de aquisição</h2>
                    <p>Distribuição por etapa após Negociação e Equalização</p>
                  </div>
                </div>
                <div class="pipeline-total">
                  <strong>{{ number(pipelineTotal) }}</strong>
                  <span>nas etapas posteriores</span>
                </div>
              </div>
              <VCard
                class="chart-panel pipeline-panel"
                variant="outlined"
                rounded="lg"
              >
                <ChartCanvas
                  class="report-chart pipeline-chart"
                  type="bar"
                  :options="pipelineChartOptions"
                  :series="pipelineSeries"
                  :height="190"
                  label="Distribuição de equipamentos por etapa do pipeline"
                />
              </VCard>
              <VAlert
                class="table-commentary pipeline-commentary"
                type="info"
                variant="tonal"
                density="compact"
              >
                <strong>Comentário executivo</strong>
                <p>
                  Os equipamentos que já concluíram a negociação seguem o fluxo
                  normal de aquisição, contratação e emissão de ordem de compra,
                  sendo monitorados pelas áreas responsáveis.
                </p>
              </VAlert>
            </section>
          </VCardText>
          <footer class="paper-footer">
            <span>INPASA · Planejamento / Painel de Equipamentos</span>
            <span>1 / {{ pageCount }}</span>
          </footer>
        </VCard>

        <VCard
          v-for="(batch, index) in overduePages"
          :key="`overdue-${index}`"
          class="report-page"
          elevation="1"
          rounded="lg"
        >
          <div class="report-accent" />
          <header class="paper-header">
            <img
              class="paper-logo"
              src="/brand/logo-inpasa.png"
              alt="Inpasa"
              crossorigin="anonymous"
            />
            <span class="paper-label">{{ unitName }} · {{ projectName }}</span>
          </header>
          <VDivider />
          <VCardText class="paper-content">
            <div class="risk-heading">
              <div class="section-title report-table-title">
                <span class="section-index">03</span>
                <div>
                  <h2>Equipamentos em atraso na negociação</h2>
                  <p>
                    Prioridades para acompanhamento ·
                    {{ number(metrics.overdue) }} equipamentos
                  </p>
                </div>
              </div>
              <div class="risk-total">
                <strong>{{ number(metrics.overdue) }}</strong>
                <span>em atraso</span>
              </div>
            </div>
            <VTable class="overdue-table" density="compact">
              <thead>
                <tr>
                  <th>Equipamento</th>
                  <th>Etapa</th>
                  <th>Responsável</th>
                  <th>Data limite</th>
                  <th>Dias em atraso</th>
                  <th>Tratativa</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="item in batch" :key="item.equipment.id">
                  <td>
                    <strong>{{ item.equipment.name }}</strong>
                  </td>
                  <td>
                    <VChip size="x-small" variant="tonal">{{
                      item.equipment.stageName
                    }}</VChip>
                  </td>
                  <td>
                    {{
                      item.equipment.responsibleUser?.name || "Não atribuído"
                    }}
                  </td>
                  <td>
                    {{
                      formatReportDate(
                        item.equipment.calculated.negotiationDeadline,
                      )
                    }}
                  </td>
                  <td class="late-days">{{ item.daysLate ?? "—" }}</td>
                  <td class="treatment">Não informada</td>
                </tr>
                <tr v-if="!batch.length">
                  <td colspan="6" class="no-overdue">
                    Nenhum equipamento com negociação em atraso.
                  </td>
                </tr>
              </tbody>
            </VTable>
            <VAlert
              class="table-commentary"
              type="info"
              variant="tonal"
              density="compact"
            >
              <strong>Comentário executivo</strong>
              <p v-if="metrics.overdue">
                Os equipamentos listados acima possuem prazo de negociação
                vencido e estão sendo acompanhados junto aos responsáveis para a
                conclusão das tratativas e avanço ao processo de aquisição.
              </p>
              <p v-else>
                Não há registros classificados como atrasados no momento da
                emissão.
              </p>
            </VAlert>
            <VAlert
              v-if="metrics.overdue"
              class="final-consideration"
              type="warning"
              variant="tonal"
              density="compact"
            >
              <strong>Consideração final</strong>
              <p>
                O principal ponto de atenção da carteira permanece nos
                equipamentos com negociação em atraso, uma vez que estes ainda
                não ingressaram no fluxo formal de aquisição e podem impactar o
                cronograma do projeto caso não sejam regularizados dentro do
                prazo.
              </p>
            </VAlert>
          </VCardText>
          <footer class="paper-footer">
            <span>INPASA · Planejamento / Painel de Equipamentos</span>
            <span>{{ index + 2 }} / {{ pageCount }}</span>
          </footer>
        </VCard>
      </div>
      <div
        v-else-if="!error && rows.length && htmlPreview"
        class="report-html-preview"
      >
        <iframe
          class="report-html-frame"
          title="Visualização do relatório executivo em HTML"
          :srcdoc="htmlPreview"
          sandbox="allow-scripts"
          referrerpolicy="no-referrer"
        />
      </div>

      <p v-if="rows.length" class="preview-note">
        O PDF contém todas as páginas. O PNG é contínuo; relatórios com mais de
        seis páginas são divididos em arquivos numerados. O HTML é interativo e
        funciona offline.
      </p>
    </div>
  </AppModal>
</template>

<style scoped>
.report-shell {
  display: grid;
  gap: 13px;
  color: #213758;
}
.report-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
  flex-wrap: wrap;
  padding-bottom: 8px;
  border-bottom: 1px solid #e8edf4;
}
.report-toolbar-copy {
  display: grid;
  gap: 2px;
}
.report-toolbar-copy strong {
  font-size: 14px;
  color: #233e60;
}
.report-toolbar-copy span,
.report-progress span {
  font-size: 11px;
  color: #8594a8;
}
.report-toolbar-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 7px;
}
.report-progress {
  display: grid;
  gap: 7px;
}
.report-alert-content {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}
.report-loading {
  min-height: 520px;
  padding: 24px;
  border: 1px solid #e8edf4;
  border-radius: 12px;
}
.report-html-preview {
  overflow: hidden;
  padding: 12px;
  border-radius: 12px;
  background: #eef1f5;
}
.report-html-frame {
  display: block;
  width: 100%;
  height: min(74vh, 950px);
  min-height: 520px;
  border: 1px solid #dce3eb;
  border-radius: 10px;
  background: #fff;
}
.report-preview {
  display: grid;
  justify-items: center;
  gap: 18px;
  padding: 12px;
  overflow: auto;
  background: #eef1f5;
  border-radius: 12px;
}
.report-page {
  position: relative;
  display: flex;
  flex-direction: column;
  flex: 0 0 auto;
  width: 794px;
  height: 1123px;
  overflow: hidden;
  color: #243b58;
  background: #fff;
  font-family: "Manrope", Arial, sans-serif;
}
.report-accent {
  flex: 0 0 7px;
  background: linear-gradient(90deg, #304f7e 0 72%, #609346 72%);
}
.paper-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  min-height: 68px;
  padding: 12px 36px;
}
.paper-logo {
  display: block;
  width: auto;
  max-width: 150px;
  height: 39px;
  object-fit: contain;
}
.paper-label {
  color: #718096;
  font-size: 9px;
  font-weight: 750;
  letter-spacing: 0.1em;
  text-transform: uppercase;
}
.paper-content {
  flex: 1 1 auto;
  padding: 30px 38px 60px !important;
}
.paper-heading {
  margin-bottom: 28px;
}
.paper-kicker {
  margin: 0 0 7px;
  color: #5f7d9f;
  font-size: 9px;
  font-weight: 800;
  letter-spacing: 0.15em;
}
.paper-heading h1 {
  margin: 0;
  color: #203b5d;
  font-size: 30px;
  line-height: 1.15;
}
.paper-subtitle {
  margin: 8px 0 0;
  color: #7c8999;
  font-size: 11px;
}
.paper-section {
  margin-bottom: 24px;
}
.section-title {
  display: flex;
  align-items: center;
  gap: 11px;
  margin-bottom: 13px;
}
.section-title h2 {
  margin: 0;
  color: #263f5f;
  font-size: 16px;
}
.section-index {
  display: inline-flex;
  align-items: center;
  width: auto;
  height: 22px;
  padding-right: 10px;
  border-right: 1px solid #d4dde8;
  color: #304f7e;
  background: transparent;
  font-size: 10px;
  font-weight: 800;
  letter-spacing: 0.08em;
}
.paper-paragraph {
  margin: 0;
  color: #607086;
  font-size: 11px;
  line-height: 1.65;
}
.overview-grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: 11px;
  align-items: start;
}
.minor-heading {
  margin: 0 0 5px;
  color: #405a78;
  font-size: 12px;
}
.completion-total {
  display: grid;
  justify-items: end;
}
.completion-total strong {
  color: #609346;
  font-size: 20px;
  line-height: 1;
}
.completion-total small {
  margin-top: 3px;
  color: #8996a5;
  font-size: 8px;
}
.status-chips {
  display: flex;
  justify-content: center;
  gap: 5px;
  flex-wrap: wrap;
  margin-top: -3px;
}
.overview-side {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 11px;
  padding-top: 0;
}
.startup-card,
.attention-card {
  display: grid;
  gap: 8px;
  padding: 18px !important;
}
.startup-card-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}
.startup-card-heading > span:first-child {
  font-size: 8px;
  font-weight: 800;
  letter-spacing: 0.1em;
}
.startup-icon {
  display: inline-grid;
  place-items: center;
  width: 28px;
  height: 28px;
  border: 1px solid rgb(48 79 126 / 12%);
  border-radius: 9px;
  color: #304f7e;
  background: rgb(255 255 255 / 62%);
}
.startup-card strong {
  font-size: 21px;
}
.startup-countdown {
  display: flex;
  align-items: center;
  gap: 5px;
  color: #617b9a;
}
.startup-countdown small {
  font-size: 9px;
  font-weight: 650;
}
.attention-card strong {
  color: #344e6c;
  font-size: 11px;
}
.attention-card p {
  margin: 0;
  color: #6e7d8f;
  font-size: 10px;
  line-height: 1.55;
}
.report-table-title {
  margin: 0 0 24px;
}
.report-table-title p {
  margin: 3px 0 0;
  color: #8793a2;
  font-size: 10px;
}
.overdue-table {
  border: 1px solid #e7ebf0;
  border-radius: 8px;
  overflow: hidden;
}
.overdue-table :deep(table) {
  table-layout: fixed;
}
.overdue-table :deep(th) {
  height: 38px !important;
  color: #64748b !important;
  background: #f5f7fa;
  font-size: 8px !important;
  font-weight: 800 !important;
  text-transform: uppercase;
}
.overdue-table :deep(td) {
  height: 57px !important;
  padding: 7px 9px !important;
  color: #53657a;
  font-size: 9px !important;
  line-height: 1.35;
}
.overdue-table :deep(th:nth-child(1)) {
  width: 24%;
}
.overdue-table :deep(th:nth-child(2)) {
  width: 18%;
}
.overdue-table :deep(th:nth-child(3)) {
  width: 17%;
}
.overdue-table :deep(th:nth-child(4)) {
  width: 15%;
}
.overdue-table :deep(th:nth-child(5)) {
  width: 13%;
}
.overdue-table :deep(th:nth-child(6)) {
  width: 13%;
}
.late-days {
  color: #b75b47 !important;
  font-weight: 800;
  text-align: center;
}
.treatment {
  color: #9aa5b2 !important;
}
.no-overdue {
  padding: 34px !important;
  text-align: center;
}
.table-commentary {
  margin-top: 20px;
  font-size: 10px;
}
.table-commentary p {
  margin: 4px 0 0;
  line-height: 1.55;
}
.final-consideration {
  margin-top: 10px;
  font-size: 10px;
}
.final-consideration p {
  margin: 4px 0 0;
  line-height: 1.55;
}
.pipeline-section {
  margin-top: 20px;
}
.pipeline-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
  margin-bottom: 10px;
}
.pipeline-heading .section-title {
  margin: 0;
}
.pipeline-heading .section-title p {
  margin: 2px 0 0;
  color: #8794a5;
  font-size: 9px;
}
.pipeline-total {
  display: grid;
  min-width: 116px;
  padding-left: 18px;
  border-left: 1px solid #e2e7ed;
  text-align: right;
}
.pipeline-total strong {
  color: #304f7e;
  font-size: 22px;
  line-height: 1;
}
.pipeline-total span {
  margin-top: 3px;
  color: #8996a5;
  font-size: 7px;
  text-transform: uppercase;
}
.pipeline-chart {
  margin: 0;
}
.pipeline-commentary {
  margin-top: 10px;
}
.paper-footer {
  position: absolute;
  right: 0;
  bottom: 0;
  left: 0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 43px;
  padding: 0 38px;
  border-top: 1px solid #edf0f4;
  color: #929eac;
  font-size: 8px;
  line-height: 1;
}
.preview-note {
  margin: 0;
  color: #7d8b9d;
  font-size: 11px;
}

/* Identidade editorial do relatório. As dimensões continuam fixas em A4 para
 * que a prévia, o PDF e o PNG compartilhem exatamente a mesma composição. */
.report-preview {
  gap: 26px;
  padding: 28px;
  background:
    radial-gradient(circle at 12% 5%, rgb(48 79 126 / 8%), transparent 27%),
    #e9edf2;
}
.report-page {
  border: 1px solid #dce3eb;
  border-radius: 14px !important;
  box-shadow: 0 18px 45px rgb(30 55 85 / 14%) !important;
}
.report-accent {
  flex-basis: 5px;
  background: linear-gradient(
    90deg,
    #304f7e 0 68%,
    #f0a536 68% 84%,
    #609346 84%
  );
}
.paper-header {
  min-height: 74px;
  padding: 14px 38px;
  background: #fff;
}
.paper-logo {
  max-width: 142px;
  height: 41px;
}
.paper-label {
  padding: 6px 10px;
  border: 1px solid #e2e8ef;
  border-radius: 999px;
  color: #5f7188;
  background: #f7f9fb;
  font-size: 8px;
}
.paper-content {
  padding: 26px 36px 60px !important;
}
.paper-heading--cover {
  position: relative;
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  min-height: 144px;
  margin: 0 0 26px;
  padding: 28px 30px;
  overflow: hidden;
  border-radius: 14px;
  color: #fff;
  background:
    linear-gradient(
      90deg,
      rgb(27 53 85 / 88%) 0%,
      rgb(31 61 96 / 72%) 34%,
      rgb(32 66 104 / 28%) 63%,
      rgb(23 56 91 / 5%) 100%
    ),
    url("/brand/usina.jpg") 62% 56% / cover no-repeat,
    #304f7e;
}
.paper-heading--cover::before,
.paper-heading--cover::after {
  display: none;
}
.cover-copy {
  position: relative;
  z-index: 1;
}
.paper-heading--cover .paper-kicker,
.paper-heading--cover .paper-subtitle {
  color: rgb(255 255 255 / 72%);
}
.paper-heading--cover h1 {
  max-width: 470px;
  color: #fff;
  font-size: 31px;
  letter-spacing: -0.025em;
}
.section-title {
  gap: 10px;
}
.section-index {
  width: auto;
  height: 22px;
  border-radius: 0;
  box-shadow: none;
}
.overview-grid {
  grid-template-columns: 1fr;
  gap: 11px;
  margin-bottom: 0;
}
.chart-panel {
  padding: 16px 18px 14px !important;
  border-color: #e1e7ee !important;
  background: #fff;
  box-shadow: 0 8px 22px rgb(35 59 87 / 6%);
}
.panel-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding-bottom: 9px;
  border-bottom: 1px solid #edf0f4;
}
.panel-heading span {
  color: #8a97a6;
  font-size: 7px;
  font-weight: 800;
  letter-spacing: 0.12em;
}
.panel-heading .minor-heading {
  margin: 2px 0 0;
}
.panel-heading > strong {
  color: #609346;
  font-size: 18px;
}
.overview-side {
  grid-template-columns: 1fr 1fr;
  gap: 11px;
  padding-top: 0;
}
.startup-card {
  position: relative;
  gap: 4px;
  min-height: 105px;
  padding: 15px 17px !important;
  overflow: hidden;
  border: 1px solid #d9e3ee !important;
  background: linear-gradient(145deg, #eaf0f7, #f4f7fa) !important;
}
.startup-card strong {
  color: #294c76;
  font-size: 24px;
  letter-spacing: -0.02em;
}
.attention-card {
  min-height: 105px;
  padding: 15px 17px !important;
  border-color: #ead8d1 !important;
  background: linear-gradient(145deg, #fff, #fff8f5);
}
.attention-card strong {
  color: #9d503f;
}
.risk-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20px;
  margin-bottom: 18px;
  padding: 0;
  border: 0;
  border-radius: 0;
  background: transparent;
}
.risk-heading .report-table-title {
  margin: 0;
}
.risk-total {
  display: grid;
  min-width: 92px;
  padding-left: 20px;
  border-left: 1px solid #dfe5ec;
  text-align: right;
}
.risk-total strong {
  color: #b65b47;
  font-size: 27px;
  line-height: 1;
}
.risk-total span {
  margin-top: 4px;
  color: #9a756c;
  font-size: 8px;
  font-weight: 800;
  text-transform: uppercase;
}
.overdue-table {
  border-color: #dfe5eb;
  border-radius: 10px;
  box-shadow: 0 8px 20px rgb(39 62 91 / 5%);
}
.overdue-table :deep(th) {
  color: #fff !important;
  background: #304f7e;
}
.overdue-table :deep(tbody tr:nth-child(even)) {
  background: #f8fafc;
}
.overdue-table :deep(td) {
  border-bottom-color: #edf0f4 !important;
}
.late-days {
  color: #ad4f3c !important;
  background: #fff5f2;
}
.table-commentary {
  border-radius: 10px;
}
.pipeline-panel {
  margin-top: 0;
  padding: 2px 18px 0 !important;
  background: linear-gradient(180deg, #fff, #fbfcfd);
}
.paper-footer {
  min-height: 43px;
  color: #76869a;
  background: #f8fafc;
}
@media (max-width: 900px) {
  .report-preview {
    justify-items: start;
  }
}
@media (max-width: 640px) {
  .report-toolbar-actions,
  .report-alert-content {
    width: 100%;
  }
  .report-alert-content {
    align-items: stretch;
    flex-direction: column;
  }
}
</style>
