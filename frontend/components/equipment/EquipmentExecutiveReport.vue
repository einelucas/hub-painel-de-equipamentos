<script setup lang="ts">
import { computed, nextTick, onMounted, ref } from "vue";
import type { ApexOptions } from "apexcharts";
import { mdiFilePdfBox, mdiImageOutline, mdiRefresh } from "@mdi/js";
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
const loading = ref(true);
const downloading = ref<"pdf" | "png" | null>(null);
const error = ref("");
const downloadError = ref("");
const progress = ref("");
const rows = ref<Equipment[]>([]);
const generatedAt = ref(new Date());

const metrics = computed<EquipmentReportMetrics>(() =>
  buildEquipmentReport(rows.value, generatedAt.value),
);
const overduePages = computed(() => chunks(metrics.value.overdueEquipments, 6));
const pageCount = computed(() => 2 + overduePages.value.length);
const busy = computed(() => loading.value || downloading.value !== null);
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
  metrics.value.completed,
  metrics.value.onTime,
  metrics.value.overdue,
  metrics.value.unclassified,
]);
const statusChartOptions = computed<ApexOptions>(() => ({
  labels: ["Concluído", "Dentro do prazo", "Atrasado", "Sem classificação"],
  colors: ["#609346", "#5b83b4", "#c26850", "#aab4c0"],
  legend: {
    // A legenda HTML do Apex não faz parte do SVG. A versão visível abaixo é
    // construída com VChip para permanecer também no PDF/PNG.
    show: false,
  },
  dataLabels: {
    enabled: true,
    formatter: (value: number) => `${value.toFixed(1).replace(".", ",")}%`,
  },
  plotOptions: {
    pie: {
      donut: {
        size: "66%",
        labels: {
          show: true,
          total: {
            show: true,
            label: "Equipamentos",
            formatter: () => number(metrics.value.total),
          },
        },
      },
    },
  },
  stroke: { colors: ["#ffffff"], width: 2 },
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
  dataLabels: { enabled: true, style: { fontSize: "10px" } },
  plotOptions: {
    bar: {
      borderRadius: 4,
      borderRadiusApplication: "end",
      horizontal: true,
      barHeight: "58%",
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

const riskNarrative = computed(() => {
  const { overdue, earlyStage, unclassified } = metrics.value;
  const parts: string[] = [];
  if (overdue) {
    parts.push(`${number(overdue)} equipamento(s) com prazo de negociação vencido`);
  }
  if (earlyStage) {
    parts.push(`${number(earlyStage)} em Nova Demanda, Negociação ou Equalização`);
  }
  if (unclassified) {
    parts.push(`${number(unclassified)} sem classificação de prazo disponível`);
  }
  return parts.length
    ? `Pontos de atenção: ${parts.join("; ")}. Os registros exigem acompanhamento conforme seu estágio.`
    : "Não foram identificados atrasos ou pendências de classificação no recorte disponível.";
});

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
      caught instanceof Error ? caught.message : "Não foi possível salvar o PDF.";
  } finally {
    downloading.value = null;
    progress.value = "";
  }
}

function saveCanvas(canvas: HTMLCanvasElement, filename: string): Promise<void> {
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
      caught instanceof Error ? caught.message : "Não foi possível salvar o PNG.";
  } finally {
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
        <span>{{ progress || (loading ? "Preparando relatório..." : "Gerando arquivo...") }}</span>
      </div>

      <VAlert v-if="error" type="error" variant="tonal" density="compact">
        <div class="report-alert-content">
          <span><strong>Não foi possível preparar o relatório.</strong> {{ error }}</span>
          <VBtn variant="outlined" size="small" @click="loadReport">Tentar novamente</VBtn>
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

      <div v-if="!error && rows.length" ref="previewEl" class="report-preview">
        <VCard class="report-page" elevation="1" rounded="lg">
          <div class="report-accent" />
          <header class="paper-header">
            <img
              class="paper-logo"
              src="/brand/logo-inpasa.png"
              alt="Inpasa"
              crossorigin="anonymous"
            >
            <span class="paper-label">RELATÓRIO EXECUTIVO · EQUIPAMENTOS</span>
          </header>
          <VDivider />
          <VCardText class="paper-content">
            <div class="paper-heading paper-heading--cover">
              <div class="cover-copy">
                <p class="paper-kicker">CARTEIRA DE EQUIPAMENTOS</p>
                <h1>{{ projectName }}</h1>
                <p class="paper-subtitle">{{ unitName }} · Emitido em {{ generatedLabel }}</p>
              </div>
              <div class="cover-stamp" aria-hidden="true">
                <span>VISÃO</span>
                <strong>EXECUTIVA</strong>
              </div>
            </div>

            <section class="paper-section">
              <div class="section-title">
                <span class="section-index">01</span>
                <h2>Resumo executivo</h2>
              </div>
              <p class="paper-paragraph">
                A carteira da obra possui <b>{{ totalLabel }} equipamentos</b> e
                <b>{{ number(metrics.components) }} componentes/subitens</b>. Desse total,
                <b>{{ number(metrics.completed) }}</b> têm negociação concluída,
                equivalente a <b>{{ percent(metrics.completedPercent) }}</b>.
              </p>
              <div class="metric-grid">
                <VCard class="metric metric-primary" variant="outlined" rounded="lg">
                  <span>Equipamentos</span><strong>{{ totalLabel }}</strong><small>Carteira da obra</small>
                </VCard>
                <VCard class="metric metric-success" variant="outlined" rounded="lg">
                  <span>Negociação concluída</span><strong>{{ number(metrics.completed) }}</strong><small>{{ percent(metrics.completedPercent) }} do total</small>
                </VCard>
                <VCard class="metric metric-warning" variant="outlined" rounded="lg">
                  <span>Em atraso</span><strong>{{ number(metrics.overdue) }}</strong><small>{{ percent(metrics.overduePercent) }} do total</small>
                </VCard>
                <VCard class="metric metric-neutral" variant="outlined" rounded="lg">
                  <span>Componentes</span><strong>{{ number(metrics.components) }}</strong><small>Indicador técnico</small>
                </VCard>
              </div>
            </section>

            <section class="paper-section overview-grid">
              <VCard class="chart-panel" variant="outlined" rounded="lg">
                <div class="panel-heading">
                  <div>
                    <span>STATUS DA CARTEIRA</span>
                    <h3 class="minor-heading">Situação das negociações</h3>
                  </div>
                  <strong>{{ percent(metrics.completedPercent) }}</strong>
                </div>
                <ChartCanvas
                  class="report-chart"
                  type="donut"
                  :options="statusChartOptions"
                  :series="statusSeries"
                  :height="245"
                  label="Distribuição da situação das negociações"
                />
                <div class="status-chips" aria-label="Legenda da situação das negociações">
                  <VChip size="x-small" color="success" variant="tonal">Concluído · {{ number(metrics.completed) }}</VChip>
                  <VChip size="x-small" color="primary" variant="tonal">No prazo · {{ number(metrics.onTime) }}</VChip>
                  <VChip size="x-small" color="error" variant="tonal">Atrasado · {{ number(metrics.overdue) }}</VChip>
                  <VChip size="x-small" variant="tonal">Sem classificação · {{ number(metrics.unclassified) }}</VChip>
                </div>
              </VCard>
              <div class="overview-side">
                <VCard class="startup-card" variant="tonal" color="primary" rounded="lg">
                  <span>PRÓXIMO STARTUP CADASTRADO</span>
                  <strong>{{ metrics.nextStartup ? formatReportDate(metrics.nextStartup) : "Não informado" }}</strong>
                  <small>{{ metrics.daysToNextStartup ?? "—" }} dias restantes</small>
                </VCard>
                <VCard class="attention-card" variant="outlined" rounded="lg">
                  <strong>Principais pontos de atenção</strong>
                  <p>{{ riskNarrative }}</p>
                </VCard>
              </div>
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
            <img class="paper-logo" src="/brand/logo-inpasa.png" alt="Inpasa" crossorigin="anonymous">
            <span class="paper-label">{{ unitName }} · {{ projectName }}</span>
          </header>
          <VDivider />
          <VCardText class="paper-content">
            <div class="risk-heading">
              <div class="section-title report-table-title">
                <span class="section-index">02</span>
                <div>
                  <h2>Equipamentos em atraso na negociação</h2>
                  <p>Prioridades para acompanhamento · {{ number(metrics.overdue) }} equipamentos</p>
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
                  <td><strong>{{ item.equipment.name }}</strong></td>
                  <td><VChip size="x-small" variant="tonal">{{ item.equipment.stageName }}</VChip></td>
                  <td>{{ item.equipment.responsibleUser?.name || "Não atribuído" }}</td>
                  <td>{{ formatReportDate(item.equipment.calculated.negotiationDeadline) }}</td>
                  <td class="late-days">{{ item.daysLate ?? "—" }}</td>
                  <td class="treatment">Não informada</td>
                </tr>
                <tr v-if="!batch.length">
                  <td colspan="6" class="no-overdue">Nenhum equipamento com negociação em atraso.</td>
                </tr>
              </tbody>
            </VTable>
            <VAlert class="table-commentary" type="info" variant="tonal" density="compact">
              <strong>Comentário executivo</strong>
              <p v-if="metrics.overdue">
                Os equipamentos listados possuem negociação classificada como atrasada pelo Hub e precisam de acompanhamento para regularização.
              </p>
              <p v-else>Não há registros classificados como atrasados no momento da emissão.</p>
            </VAlert>
          </VCardText>
          <footer class="paper-footer">
            <span>INPASA · Planejamento / Painel de Equipamentos</span>
            <span>{{ index + 2 }} / {{ pageCount }}</span>
          </footer>
        </VCard>

        <VCard class="report-page" elevation="1" rounded="lg">
          <div class="report-accent" />
          <header class="paper-header">
            <img class="paper-logo" src="/brand/logo-inpasa.png" alt="Inpasa" crossorigin="anonymous">
            <span class="paper-label">{{ unitName }} · {{ projectName }}</span>
          </header>
          <VDivider />
          <VCardText class="paper-content">
            <section class="paper-section">
              <div class="pipeline-hero">
                <div>
                  <span>FLUXO DE AQUISIÇÃO</span>
                  <strong>{{ number(pipelineTotal) }}</strong>
                  <small>equipamentos nas etapas posteriores</small>
                </div>
                <p>Visão consolidada do avanço da carteira após as etapas iniciais de negociação.</p>
              </div>
              <div class="section-title">
                <span class="section-index">03</span>
                <h2>Pipeline de aquisição</h2>
              </div>
              <p class="paper-paragraph">
                Distribuição por etapa corrente dos equipamentos que avançaram além de Negociação e Equalização.
              </p>
              <VCard class="chart-panel pipeline-panel" variant="outlined" rounded="lg">
                <ChartCanvas
                  class="report-chart pipeline-chart"
                  type="bar"
                  :options="pipelineChartOptions"
                  :series="pipelineSeries"
                  :height="350"
                  label="Distribuição de equipamentos por etapa do pipeline"
                />
              </VCard>
              <p class="paper-caption">
                Equipamentos em Nova Demanda, Negociação e Equalização não aparecem nas barras acima.
              </p>
              <VAlert class="table-commentary" type="info" variant="tonal" density="compact">
                O pipeline usa a fase corrente registrada no Hub e preserva a distinção entre equipamento e componente.
              </VAlert>
            </section>
            <section class="paper-section closing-section">
              <div class="section-title">
                <span class="section-index">04</span>
                <h2>Considerações finais</h2>
              </div>
              <p class="paper-paragraph">
                {{ metrics.overdue
                  ? `O principal ponto de atenção está nos ${number(metrics.overdue)} equipamentos com prazo de negociação vencido. Recomenda-se acompanhar as tratativas para reduzir riscos ao cronograma.`
                  : "Não foram identificados equipamentos com negociação atrasada nesta consulta. Recomenda-se manter o monitoramento periódico dos prazos e do pipeline." }}
              </p>
            </section>
          </VCardText>
          <footer class="paper-footer">
            <span>INPASA · Planejamento / Painel de Equipamentos</span>
            <span>{{ pageCount }} / {{ pageCount }}</span>
          </footer>
        </VCard>
      </div>

      <p v-if="rows.length" class="preview-note">
        O PDF contém todas as páginas. O PNG é contínuo; relatórios com mais de seis páginas são divididos em arquivos numerados.
      </p>
    </div>
  </AppModal>
</template>

<style scoped>
.report-shell { display: grid; gap: 13px; color: #213758; }
.report-toolbar { display: flex; align-items: center; justify-content: space-between; gap: 18px; flex-wrap: wrap; padding-bottom: 8px; border-bottom: 1px solid #e8edf4; }
.report-toolbar-copy { display: grid; gap: 2px; }
.report-toolbar-copy strong { font-size: 14px; color: #233e60; }
.report-toolbar-copy span, .report-progress span { font-size: 11px; color: #8594a8; }
.report-toolbar-actions { display: flex; flex-wrap: wrap; gap: 7px; }
.report-progress { display: grid; gap: 7px; }
.report-alert-content { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.report-loading { min-height: 520px; padding: 24px; border: 1px solid #e8edf4; border-radius: 12px; }
.report-preview { display: grid; justify-items: center; gap: 18px; padding: 12px; overflow: auto; background: #eef1f5; border-radius: 12px; }
.report-page { position: relative; display: flex; flex-direction: column; flex: 0 0 auto; width: 794px; height: 1123px; overflow: hidden; color: #243b58; background: #fff; font-family: "Manrope", Arial, sans-serif; }
.report-accent { flex: 0 0 7px; background: linear-gradient(90deg, #304f7e 0 72%, #609346 72%); }
.paper-header { display: flex; align-items: center; justify-content: space-between; min-height: 68px; padding: 12px 36px; }
.paper-logo { display: block; width: auto; max-width: 150px; height: 39px; object-fit: contain; }
.paper-label { color: #718096; font-size: 9px; font-weight: 750; letter-spacing: .1em; text-transform: uppercase; }
.paper-content { flex: 1 1 auto; padding: 30px 38px 20px !important; }
.paper-heading { margin-bottom: 28px; }
.paper-kicker { margin: 0 0 7px; color: #5f7d9f; font-size: 9px; font-weight: 800; letter-spacing: .15em; }
.paper-heading h1 { margin: 0; color: #203b5d; font-size: 30px; line-height: 1.15; }
.paper-subtitle { margin: 8px 0 0; color: #7c8999; font-size: 11px; }
.paper-section { margin-bottom: 24px; }
.section-title { display: flex; align-items: center; gap: 11px; margin-bottom: 13px; }
.section-title h2 { margin: 0; color: #263f5f; font-size: 16px; }
.section-index { display: inline-grid; place-items: center; width: 28px; height: 28px; border-radius: 8px; color: #fff; background: #304f7e; font-size: 9px; font-weight: 800; }
.paper-paragraph { margin: 0; color: #607086; font-size: 11px; line-height: 1.65; }
.metric-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; margin-top: 18px; }
.metric { display: grid; gap: 4px; min-height: 95px; padding: 13px !important; border-color: #dfe6ee !important; }
.metric span { color: #77869a; font-size: 9px; font-weight: 700; text-transform: uppercase; }
.metric strong { color: #2c4f75; font-size: 24px; line-height: 1; }
.metric small { color: #9aa5b2; font-size: 8px; }
.metric-warning { border-color: #e5c1b7 !important; background: #fff9f7; }
.metric-warning strong { color: #b25d49; }
.overview-grid { display: grid; grid-template-columns: 1.16fr .84fr; gap: 22px; align-items: start; }
.minor-heading { margin: 0 0 5px; color: #405a78; font-size: 12px; }
.status-chips { display: flex; justify-content: center; gap: 5px; flex-wrap: wrap; margin-top: -5px; }
.overview-side { display: grid; gap: 12px; padding-top: 27px; }
.startup-card, .attention-card { display: grid; gap: 8px; padding: 18px !important; }
.startup-card span { font-size: 8px; font-weight: 800; letter-spacing: .08em; }
.startup-card strong { font-size: 21px; }
.startup-card small { font-size: 10px; }
.attention-card strong { color: #344e6c; font-size: 11px; }
.attention-card p { margin: 0; color: #6e7d8f; font-size: 10px; line-height: 1.55; }
.report-table-title { margin: 0 0 24px; }
.report-table-title p { margin: 3px 0 0; color: #8793a2; font-size: 10px; }
.overdue-table { border: 1px solid #e7ebf0; border-radius: 8px; overflow: hidden; }
.overdue-table :deep(table) { table-layout: fixed; }
.overdue-table :deep(th) { height: 38px !important; color: #64748b !important; background: #f5f7fa; font-size: 8px !important; font-weight: 800 !important; text-transform: uppercase; }
.overdue-table :deep(td) { height: 57px !important; padding: 7px 9px !important; color: #53657a; font-size: 9px !important; line-height: 1.35; }
.overdue-table :deep(th:nth-child(1)) { width: 24%; }
.overdue-table :deep(th:nth-child(2)) { width: 18%; }
.overdue-table :deep(th:nth-child(3)) { width: 17%; }
.overdue-table :deep(th:nth-child(4)) { width: 15%; }
.overdue-table :deep(th:nth-child(5)) { width: 13%; }
.overdue-table :deep(th:nth-child(6)) { width: 13%; }
.late-days { color: #b75b47 !important; font-weight: 800; text-align: center; }
.treatment { color: #9aa5b2 !important; }
.no-overdue { padding: 34px !important; text-align: center; }
.table-commentary { margin-top: 20px; font-size: 10px; }
.table-commentary p { margin: 4px 0 0; line-height: 1.55; }
.pipeline-chart { margin: 12px 0 4px; }
.paper-caption { margin: 5px 0 0; color: #939eaa; font-size: 9px; }
.closing-section { margin-top: 27px; padding-top: 22px; border-top: 1px solid #e9edf2; }
.paper-footer { display: flex; align-items: center; justify-content: space-between; min-height: 40px; padding: 0 38px; border-top: 1px solid #edf0f4; color: #929eac; font-size: 8px; }
.preview-note { margin: 0; color: #7d8b9d; font-size: 11px; }

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
  background: linear-gradient(90deg, #304f7e 0 68%, #f0a536 68% 84%, #609346 84%);
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
  padding: 26px 36px 18px !important;
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
    linear-gradient(115deg, rgb(30 58 91 / 98%), rgb(48 79 126 / 94%)),
    #304f7e;
}
.paper-heading--cover::before,
.paper-heading--cover::after {
  position: absolute;
  border-radius: 50%;
  content: "";
}
.paper-heading--cover::before {
  top: -74px;
  right: 64px;
  width: 190px;
  height: 190px;
  border: 34px solid rgb(255 255 255 / 6%);
}
.paper-heading--cover::after {
  right: -35px;
  bottom: -64px;
  width: 155px;
  height: 155px;
  background: rgb(240 165 54 / 16%);
}
.cover-copy,
.cover-stamp {
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
  letter-spacing: -.025em;
}
.cover-stamp {
  display: grid;
  gap: 2px;
  min-width: 112px;
  padding: 12px 14px;
  border: 1px solid rgb(255 255 255 / 18%);
  border-radius: 10px;
  background: rgb(255 255 255 / 8%);
  backdrop-filter: blur(4px);
}
.cover-stamp span {
  color: rgb(255 255 255 / 62%);
  font-size: 7px;
  font-weight: 800;
  letter-spacing: .16em;
}
.cover-stamp strong {
  color: #fff;
  font-size: 10px;
  letter-spacing: .08em;
}
.section-title {
  gap: 10px;
}
.section-index {
  width: 30px;
  height: 30px;
  border-radius: 9px;
  box-shadow: 0 5px 12px rgb(48 79 126 / 18%);
}
.metric-grid {
  gap: 11px;
  margin-top: 16px;
}
.metric {
  position: relative;
  min-height: 102px;
  padding: 15px 14px 13px !important;
  overflow: hidden;
  border-color: #e2e7ed !important;
  background: linear-gradient(145deg, #fff, #fafbfd);
  box-shadow: 0 7px 18px rgb(39 62 91 / 6%);
}
.metric::before {
  position: absolute;
  top: 0;
  right: 0;
  left: 0;
  height: 3px;
  background: #8797a9;
  content: "";
}
.metric-primary::before { background: #304f7e; }
.metric-success::before { background: #609346; }
.metric-warning::before { background: #c26850; }
.metric-neutral::before { background: #f0a536; }
.metric strong {
  margin-top: 3px;
  font-size: 26px;
  letter-spacing: -.03em;
}
.overview-grid {
  grid-template-columns: 1.2fr .8fr;
  gap: 16px;
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
  letter-spacing: .12em;
}
.panel-heading .minor-heading { margin: 2px 0 0; }
.panel-heading > strong {
  color: #609346;
  font-size: 18px;
}
.status-chips {
  gap: 4px;
  margin-top: -8px;
}
.overview-side {
  gap: 12px;
  padding-top: 0;
}
.startup-card {
  min-height: 130px;
  padding: 20px !important;
  background: linear-gradient(145deg, #eaf0f7, #f4f7fa) !important;
}
.startup-card strong {
  color: #294c76;
  font-size: 24px;
  letter-spacing: -.02em;
}
.attention-card {
  min-height: 155px;
  border-color: #ead8d1 !important;
  background: linear-gradient(145deg, #fff, #fff8f5);
}
.attention-card strong { color: #9d503f; }
.risk-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20px;
  margin-bottom: 22px;
  padding: 20px 22px;
  border: 1px solid #ebd7d1;
  border-radius: 13px;
  background: linear-gradient(100deg, #fff8f5, #fff);
}
.risk-heading .report-table-title { margin: 0; }
.risk-total {
  display: grid;
  min-width: 92px;
  padding-left: 20px;
  border-left: 1px solid #ead3cc;
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
.overdue-table :deep(tbody tr:nth-child(even)) { background: #f8fafc; }
.overdue-table :deep(td) { border-bottom-color: #edf0f4 !important; }
.late-days {
  color: #ad4f3c !important;
  background: #fff5f2;
}
.table-commentary {
  border-radius: 10px;
}
.pipeline-hero {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 30px;
  margin-bottom: 25px;
  padding: 23px 26px;
  border-radius: 14px;
  color: #fff;
  background: linear-gradient(110deg, #254365, #375f8d);
}
.pipeline-hero > div { display: grid; }
.pipeline-hero span {
  color: rgb(255 255 255 / 68%);
  font-size: 7px;
  font-weight: 800;
  letter-spacing: .13em;
}
.pipeline-hero strong {
  margin: 5px 0 1px;
  font-size: 30px;
  line-height: 1;
}
.pipeline-hero small { color: rgb(255 255 255 / 72%); font-size: 9px; }
.pipeline-hero p {
  max-width: 330px;
  margin: 0;
  color: rgb(255 255 255 / 78%);
  font-size: 10px;
  line-height: 1.55;
}
.pipeline-panel {
  margin-top: 14px;
  padding: 8px 18px 2px !important;
  background: linear-gradient(180deg, #fff, #fbfcfd);
}
.paper-footer {
  min-height: 43px;
  color: #76869a;
  background: #f8fafc;
}
@media (max-width: 900px) { .report-preview { justify-items: start; } }
@media (max-width: 640px) { .report-toolbar-actions, .report-alert-content { width: 100%; } .report-alert-content { align-items: stretch; flex-direction: column; } }
</style>
