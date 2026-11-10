<script setup lang="ts">
import { computed, nextTick, onMounted, ref } from "vue";
import { mdiFilePdfBox, mdiImageOutline, mdiRefresh } from "@mdi/js";
import { VBtn, VProgressLinear } from "vuetify/components";
import VueApexCharts from "vue3-apexcharts";
import type { Equipment, EquipmentList } from "~/types/equipment";
import {
  buildEquipmentReport,
  chunks,
  formatReportDate,
  type EquipmentReportMetrics,
} from "~/utils/equipmentReport";
import { collectAllPages } from "~/utils/pagination";

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
const generatedAt = ref<Date>(new Date());
const metrics = computed<EquipmentReportMetrics>(() =>
  buildEquipmentReport(rows.value, generatedAt.value),
);
const overduePages = computed(() => chunks(metrics.value.overdueEquipments, 6));
const pageCount = computed(() => 2 + overduePages.value.length);
const busy = computed(() => loading.value || downloading.value !== null);
const totalLabel = computed(() => number(metrics.value.total));
const fileBase = computed(
  () =>
    `report-equipamentos-${slug(props.unitName)}-${slug(props.projectName)}-${generatedAt.value
      .toISOString()
      .slice(0, 10)}`,
);

// Configuração do gráfico de barras para Pipeline de Aquisição (Design padrão ApexCharts)
const pipelineChartOptions = computed(() => ({
  series: [
    {
      name: "Equipamentos",
      data: metrics.value.pipeline.map(item => item.count)
    }
  ],
  chart: {
    type: "bar",
    height: 350,
    fontFamily: "Arial, Helvetica, sans-serif"
  },
  plotOptions: {
    bar: {
      borderRadius: 4,
      borderRadiusApplication: "end",
      horizontal: true
    }
  },
  dataLabels: {
    enabled: false
  },
  title: {
    text: "Pipeline de Aquisição - Distribuição por Etapa",
    align: "left",
    style: { fontSize: "14px", fontWeight: "bold", color: "#213758" }
  },
  xaxis: {
    categories: metrics.value.pipeline.map(item => item.label),
    labels: {
      style: { colors: "#536a84", fontSize: "11px" }
    }
  },
  yaxis: {
    labels: {
      style: { colors: "#536a84", fontSize: "11px" },
      formatter: (val: number) => number(val)
    }
  },
  colors: ["#008FFB"],
  tooltip: {
    enabled: true,
    y: {
      formatter: (val: number) => `${number(val)} equipamentos`
    }
  },
  grid: {
    borderColor: "#e9eef3",
    strokeDashArray: 4
  }
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
  return `${value.toLocaleString("pt-BR", { minimumFractionDigits: 1, maximumFractionDigits: 1 })}%`;
}
const generatedLabel = computed(() =>
  generatedAt.value.toLocaleString("pt-BR", {
    dateStyle: "short",
    timeStyle: "short",
  }),
);
const riskNarrative = computed(() => {
  const { overdue, earlyStage, unclassified } = metrics.value;
  const parts: string[] = [];
  if (overdue)
    parts.push(
      `${number(overdue)} equipamento(s) com prazo de negociação vencido`,
    );
  if (earlyStage)
    parts.push(
      `${number(earlyStage)} em Nova Demanda, Negociação ou Equalização`,
    );
  if (unclassified)
    parts.push(`${number(unclassified)} sem classificação de prazo disponível`);
  return parts.length
    ? `Pontos de atenção: ${parts.join("; ")}. Os registros exigem acompanhamento conforme seu estágio.`
    : "Não foram identificados atrasos ou pendências de classificação no recorte disponível.";
});

/** Não propaga o filtro de equipamento nem os filtros locais da tabela.
 * O relatório pertence ao ProjectContext inteiro da Unidade selecionada. */
async function loadReport(): Promise<void> {
  loading.value = true;
  rows.value = [];
  error.value = "";
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
        "A API retornou equipamentos de outra obra. O report foi bloqueado por segurança.",
      );
    }
    generatedAt.value = new Date();
    rows.value = equipments;
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
  if (elements.length !== pageCount.value)
    throw new Error("O report não terminou de renderizar.");
  return elements;
}

/**
 * Função para preparar gráficos ApexCharts para captura
 * Substitui temporariamente canvas por imagens para html2canvas capturar corretamente
 */
async function prepareChartsForCapture(container: HTMLElement): Promise<() => void> {
  const apexChartElements = container.querySelectorAll('.apexcharts-canvas');
  const replacements: Array<{ original: HTMLElement, replacement: HTMLElement }> = [];
  
  // Aguarda gráficos estarem prontos e obtém imagens
  await Promise.all(
    Array.from(apexChartElements).map(async (chartEl) => {
      try {
        // Tenta obter o objeto chart do ApexCharts
        const chartInstance = (window as any).ApexCharts?.getChartByElement?.(chartEl);
        
        if (chartInstance && typeof chartInstance.dataURI === 'function') {
          // Obtém a imagem do gráfico
          const dataURI = await chartInstance.dataURI();
          
          // Cria uma imagem a partir do dataURI
          const img = new Image();
          img.src = dataURI;
          
          // Aguarda a imagem carregar
          await new Promise((resolve, reject) => {
            img.onload = resolve;
            img.onerror = reject;
          });
          
          // Substitui o canvas pela imagem
          replacements.push({
            original: chartEl,
            replacement: img
          });
          
          chartEl.replaceWith(img);
        }
      } catch (error) {
        console.warn('Não foi possível capturar gráfico ApexCharts:', error);
      }
    })
  );
  
  // Retorna função para restaurar os elementos originais
  return () => {
    replacements.forEach(({ original, replacement }) => {
      replacement.replaceWith(original);
    });
  };
}

async function capture(
  page: HTMLElement,
  scale: number,
): Promise<HTMLCanvasElement> {
  const { default: html2canvas } = await import("html2canvas");
  
  // Prepara gráficos ApexCharts para captura (substitui canvas por imagens)
  let restoreCharts: (() => void) | undefined;
  try {
    restoreCharts = await prepareChartsForCapture(page);
  } catch {
    // Se falhar, continua sem substituição
    restoreCharts = undefined;
  }
  
  try {
    const canvas = await html2canvas(page, {
      scale,
      backgroundColor: "#ffffff",
      useCORS: true,
      allowTaint: true,
      foreignObjectRendering: true,
      scrollX: 0,
      scrollY: -window.scrollY,
      logging: false,
      // Configurações para melhor captura
      canvas: {
        useCORS: true,
      },
      ignoreElements: (element) => {
        return false;
      },
      onclone: (clonedDoc) => {
        // Garante que gráficos estejam visíveis
        const styles = clonedDoc.createElement('style');
        styles.textContent = `
          * { animation: none !important; transition: none !important; }
          .apexcharts-canvas { opacity: 1 !important; visibility: visible !important; }
        `;
        clonedDoc.head.appendChild(styles);
      }
    });
    return canvas;
  } finally {
    // Restaura os gráficos originais
    if (restoreCharts) {
      restoreCharts();
    }
  }
}

async function savePdf(): Promise<void> {
  if (busy.value || !rows.value.length) return;
  downloading.value = "pdf";
  downloadError.value = "";
  try {
    await nextTick();
    await document.fonts.ready;
    
    // Aguarda gráficos ApexCharts renderizarem
    await new Promise(resolve => setTimeout(resolve, 300));
    
    const { jsPDF } = await import("jspdf");
    const pdf = new jsPDF({
      orientation: "portrait",
      unit: "mm",
      format: "a4",
      compress: true,
    });
    const pages = reportElements();
    for (let index = 0; index < pages.length; index++) {
      progress.value = `Preparando PDF · página ${index + 1} de ${pages.length}`;
      if (index > 0) pdf.addPage();
      const canvas = await capture(pages[index]!, 2);
      pdf.addImage(
        canvas.toDataURL("image/jpeg", 0.91),
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
    downloading.value = null;
    progress.value = "";
  }
}

function saveCanvas(
  canvas: HTMLCanvasElement,
  filename: string,
): Promise<void> {
  return new Promise((resolve, reject) => {
    canvas.toBlob((blob) => {
      if (!blob)
        return reject(
          new Error("O navegador não conseguiu preparar a imagem PNG."),
        );
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

/** Até seis páginas por PNG, evitando ultrapassar o limite de canvas mobile.
 * Para reports longos, a sequência é salva em arquivos PNG numerados. */
async function savePng(): Promise<void> {
  if (busy.value || !rows.value.length) return;
  downloading.value = "png";
  downloadError.value = "";
  try {
    await nextTick();
    await document.fonts.ready;
    
    // Aguarda gráficos ApexCharts renderizarem
    await new Promise(resolve => setTimeout(resolve, 300));
    
    const pages = reportElements();
    for (let start = 0; start < pages.length; start += 6) {
      const batch = pages.slice(start, start + 6);
      const scale = 1.5;
      const first = await capture(batch[0]!, scale);
      const canvas = document.createElement("canvas");
      canvas.width = first.width;
      canvas.height = first.height * batch.length;
      const ctx = canvas.getContext("2d");
      if (!ctx)
        throw new Error("O navegador não oferece suporte à exportação de PNG.");
      ctx.fillStyle = "#ffffff";
      ctx.fillRect(0, 0, canvas.width, canvas.height);
      ctx.drawImage(first, 0, 0);
      for (let index = 1; index < batch.length; index++) {
        progress.value = `Preparando PNG · página ${start + index + 1} de ${pages.length}`;
        const next = await capture(batch[index]!, scale);
        ctx.drawImage(next, 0, index * first.height);
      }
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
    downloading.value = null;
    progress.value = "";
  }
}

onMounted(() => void loadReport());
</script>

<template>
  <AppModal
    :open="true"
    :title="`Report executivo · ${projectName}`"
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
            >Atualizar</VBtn
          >
          <VBtn
            variant="flat"
            color="primary"
            size="small"
            :prepend-icon="mdiFilePdfBox"
            :loading="downloading === 'pdf'"
            :disabled="busy || !rows.length"
            data-testid="report-pdf"
            @click="savePdf"
            >Salvar PDF</VBtn
          >
          <VBtn
            variant="outlined"
            color="primary"
            size="small"
            :prepend-icon="mdiImageOutline"
            :loading="downloading === 'png'"
            :disabled="busy || !rows.length"
            data-testid="report-png"
            @click="savePng"
            >Salvar PNG</VBtn
          >
        </div>
      </div>
      <div v-if="busy" class="report-progress" role="status" aria-live="polite">
        <VProgressLinear indeterminate color="primary" height="3" />
        <span>{{
          progress || (loading ? "Preparando report..." : "Gerando arquivo...")
        }}</span>
      </div>
      <div v-if="error" class="report-state" role="alert">
        <strong>Não foi possível preparar o report.</strong>
        <span>{{ error }}</span>
        <VBtn variant="outlined" size="small" @click="loadReport"
          >Tentar novamente</VBtn
        >
      </div>
      <p v-else-if="downloadError" class="report-download-error" role="alert">
        {{ downloadError }}
      </p>
      <div v-if="!loading && !error && !rows.length" class="report-state">
        <strong>Sem equipamentos nesta obra</strong>
        <span
          >O relatório não será exportado sem registros cadastrados no contexto
          selecionado.</span
        >
      </div>

      <div v-if="!error && rows.length" ref="previewEl" class="report-preview">
        <!-- Página 1: resumo executivo -->
        <article class="report-page">
          <div class="report-accent"></div>
          <header class="paper-header">
            <div class="paper-brand">
              <strong>HUB</strong><span>AUTOMAÇÃO / PLANEJAMENTO</span>
            </div>
            <span class="paper-label">RELATÓRIO EXECUTIVO · EQUIPAMENTOS</span>
          </header>
          <div class="paper-heading">
            <p class="paper-kicker">CARTEIRA DE EQUIPAMENTOS</p>
            <h1>{{ projectName }}</h1>
            <p class="paper-subtitle">
              {{ unitName }} <span>·</span> Emitido em {{ generatedLabel }}
            </p>
          </div>
          <section class="paper-section">
            <div class="section-title">
              <span class="section-index">01</span>
              <h2>Resumo executivo</h2>
            </div>
            <p class="paper-paragraph">
              A carteira da obra possui <b>{{ totalLabel }} equipamentos</b> e
              <b
                >{{ number(metrics.components) }} componentes/subitens
                cadastrados</b
              >. Desse total,
              <b>{{ number(metrics.completed) }}</b> equipamentos têm negociação
              concluída conforme o indicador calculado pelo Hub, o equivalente a
              <b>{{ percent(metrics.completedPercent) }}</b
              >.
            </p>
            <div class="metric-grid">
              <div class="metric">
                <span>Equipamentos</span><strong>{{ totalLabel }}</strong
                ><small>Carteira da obra</small>
              </div>
              <div class="metric">
                <span>Negociação concluída</span
                ><strong>{{ number(metrics.completed) }}</strong
                ><small>{{ percent(metrics.completedPercent) }} do total</small>
              </div>
              <div class="metric metric-warning">
                <span>Em atraso</span
                ><strong>{{ number(metrics.overdue) }}</strong
                ><small>{{ percent(metrics.overduePercent) }} do total</small>
              </div>
              <div class="metric">
                <span>Componentes</span
                ><strong>{{ number(metrics.components) }}</strong
                ><small>Indicador técnico separado</small>
              </div>
            </div>
          </section>
          <section class="paper-section">
            <h3 class="minor-heading">Andamento das negociações</h3>
            <div class="completion-top">
              <span>Concluídas</span
              ><strong>{{ percent(metrics.completedPercent) }}</strong>
            </div>
            <div class="completion-track">
              <div :style="{ width: `${metrics.completedPercent}%` }"></div>
            </div>
            <div class="status-legend">
              <span
                ><i class="dot done"></i> Concluído
                <b>{{ percent(metrics.completedPercent) }}</b></span
              >
              <span
                ><i class="dot time"></i> Dentro do prazo
                <b>{{ percent(metrics.onTimePercent) }}</b></span
              >
              <span
                ><i class="dot late"></i> Atrasado
                <b>{{ percent(metrics.overduePercent) }}</b></span
              >
              <span
                ><i class="dot unknown"></i> Sem classificação
                <b>{{ percent(metrics.unclassifiedPercent) }}</b></span
              >
            </div>
          </section>
          <section class="paper-section">
            <div class="startup-card">
              <div>
                <span class="subheading">PRÓXIMO STARTUP CADASTRADO</span>
                <strong>{{
                  metrics.nextStartup
                    ? formatReportDate(metrics.nextStartup)
                    : "Não informado"
                }}</strong>
                <p>
                  Menor data futura de startup registrada nos equipamentos da
                  obra.
                </p>
              </div>
              <div class="startup-days">
                <strong>{{ metrics.daysToNextStartup ?? "—" }}</strong>
                <span>dias restantes</span>
              </div>
            </div>
          </section>
          <section class="paper-section">
            <h3 class="minor-heading">Principais pontos de atenção</h3>
            <p class="paper-paragraph attention-copy">{{ riskNarrative }}</p>
          </section>
          <footer class="paper-footer">
            <span>HUB · Planejamento / Painel de Equipamentos</span
            ><span>1 / {{ pageCount }}</span>
          </footer>
        </article>

        <!-- Página(s) 2..N: tabela integral de atrasos, sem cortar a listagem -->
        <article
          v-for="(batch, index) in overduePages"
          :key="`overdue-${index}`"
          class="report-page"
        >
          <div class="report-accent"></div>
          <header class="paper-header">
            <div class="paper-brand">
              <strong>HUB</strong><span>AUTOMAÇÃO / PLANEJAMENTO</span>
            </div>
            <span class="paper-label">{{ unitName }} · {{ projectName }}</span>
          </header>
          <div class="section-title report-table-title">
            <span class="section-index">02</span>
            <div>
              <h2>Equipamentos em atraso na negociação</h2>
              <p>
                Prioridades para acompanhamento ·
                {{ number(metrics.overdue) }} equipamentos
              </p>
            </div>
          </div>
          <table class="overdue-table">
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
                <td>{{ item.equipment.stageName }}</td>
                <td>
                  {{ item.equipment.responsibleUser?.name || "Não atribuído" }}
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
                  Nenhum equipamento com negociação em atraso neste recorte.
                </td>
              </tr>
            </tbody>
          </table>
          <div class="table-commentary">
            <b>Comentário executivo</b>
            <p v-if="metrics.overdue">
              Os equipamentos listados possuem negociação classificada como
              atrasada pelo Hub e precisam de acompanhamento junto aos
              responsáveis para regularização do processo de aquisição.
            </p>
            <p v-else>
              Não há registros classificados como atrasados no momento da
              emissão.
            </p>
          </div>
          <footer class="paper-footer">
            <span>HUB · Planejamento / Painel de Equipamentos</span
            ><span>{{ index + 2 }} / {{ pageCount }}</span>
          </footer>
        </article>

        <!-- Última página: etapas posteriores e conclusão -->
        <article class="report-page">
          <div class="report-accent"></div>
          <header class="paper-header">
            <div class="paper-brand">
              <strong>HUB</strong><span>AUTOMAÇÃO / PLANEJAMENTO</span>
            </div>
            <span class="paper-label">{{ unitName }} · {{ projectName }}</span>
          </header>
          <section class="paper-section">
            <div class="section-title">
              <span class="section-index">03</span>
              <h2>Pipeline de aquisição</h2>
            </div>
            <p class="paper-paragraph">
              Distribuição de equipamentos nas etapas posteriores à Negociação e
              Equalização, a partir da fase corrente registrada no Hub.
            </p>
            <ClientOnly>
              <VueApexCharts
                :options="pipelineChartOptions"
                type="bar"
                height="350"
              />
            </ClientOnly>
            <p class="paper-caption">
              Contagens por etapa corrente. Equipamentos em Nova Demanda,
              Negociação e Equalização não aparecem nas barras acima.
            </p>
            <div class="table-commentary">
              <b>Comentário executivo</b>
              <p>
                Os equipamentos que concluíram as etapas iniciais seguem o fluxo
                de abertura de chamado, aprovação de minuta, escrituração,
                SC/OCI, aprovação de ordem de compra e conclusão, conforme seu
                estágio cadastrado.
              </p>
            </div>
          </section>
          <section class="paper-section closing-section">
            <div class="section-title">
              <span class="section-index">04</span>
              <h2>Considerações finais</h2>
            </div>
            <p class="paper-paragraph">
              {{
                metrics.overdue
                  ? `O principal ponto de atenção está nos ${number(metrics.overdue)} equipamentos com prazo de negociação vencido. O acompanhamento das tratativas é importante para reduzir riscos ao cronograma da obra.`
                  : "Não foram identificados equipamentos com negociação classificada como atrasada na data desta consulta. Recomenda-se manter o monitoramento periódico dos prazos e da evolução do pipeline."
              }}
            </p>
          </section>
          <footer class="paper-footer">
            <span>HUB · Planejamento / Painel de Equipamentos</span
            ><span>{{ pageCount }} / {{ pageCount }}</span>
          </footer>
        </article>
      </div>
      <p v-if="rows.length" class="preview-note">
        O PDF contém todas as páginas. O PNG é gerado como uma imagem contínua;
        para reports com mais de 6 páginas, os arquivos são divididos em
        sequências numeradas.
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
.report-toolbar-copy span {
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
  color: #74849b;
  font-size: 12px;
}
.report-state {
  display: grid;
  gap: 9px;
  justify-items: start;
  padding: 34px;
  background: #f5f8fb;
  border: 1px solid #e2e9f2;
  border-radius: 12px;
}
.report-state strong {
  font-size: 15px;
}
.report-state span,
.report-download-error {
  font-size: 12px;
  color: #b45242;
}
.report-download-error {
  margin: 0;
  padding: 8px;
  border-radius: 6px;
  background: #fff4f1;
}
.report-preview {
  display: grid;
  justify-items: center;
  gap: 20px;
  padding: 22px 0;
  overflow-x: auto;
  background: #e9edf3;
  border-radius: 9px;
}
.report-page {
  position: relative;
  isolation: isolate;
  box-sizing: border-box;
  flex: none;
  width: 794px;
  height: 1123px;
  padding: 52px 54px 65px;
  overflow: hidden;
  background: white;
  box-shadow: 0 6px 24px rgba(26, 45, 73, 0.11);
  color: #263d59;
  font-family: Arial, Helvetica, sans-serif;
}
.report-accent {
  position: absolute;
  left: 0;
  top: 0;
  width: 100%;
  height: 9px;
  background: #213758;
}
.paper-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
  padding-bottom: 20px;
  border-bottom: 1px solid #dfe6ee;
}
.paper-brand {
  display: flex;
  align-items: baseline;
  gap: 11px;
}
.paper-brand strong {
  color: #213758;
  font-size: 27px;
  font-weight: 900;
  letter-spacing: -0.08em;
}
.paper-brand span {
  color: #8b98aa;
  font-size: 9px;
  font-weight: 750;
  letter-spacing: 0.09em;
}
.paper-label {
  font-size: 9px;
  font-weight: 700;
  letter-spacing: 0.045em;
  color: #8391a4;
  text-align: right;
}
.paper-heading {
  padding-top: 33px;
  padding-bottom: 25px;
}
.paper-kicker {
  margin: 0 0 10px;
  font-size: 10px;
  color: #7690ac;
  font-weight: 800;
  letter-spacing: 0.13em;
}
.paper-heading h1 {
  margin: 0;
  font-size: 34px;
  line-height: 1.14;
  color: #213758;
  font-weight: 800;
}
.paper-subtitle {
  margin: 10px 0 0;
  color: #7e8fa2;
  font-size: 12px;
}
.paper-subtitle span {
  padding: 0 7px;
}
.paper-section {
  margin-bottom: 27px;
}
.section-title {
  display: flex;
  gap: 11px;
  align-items: center;
  margin-bottom: 13px;
}
.section-index {
  flex: 0 0 29px;
  width: 29px;
  height: 29px;
  display: grid;
  place-items: center;
  background: #eaf0f7;
  border-radius: 7px;
  color: #315273;
  font-size: 11px;
  font-weight: 800;
}
.section-title h2 {
  margin: 0;
  color: #233e5d;
  font-size: 19px;
  font-weight: 800;
  line-height: 1.25;
}
.section-title p {
  margin: 5px 0 0;
  font-size: 11px;
  color: #8d99aa;
}
.paper-paragraph {
  margin: 0;
  font-size: 12px;
  line-height: 1.72;
  color: #5d6c7f;
}
.paper-paragraph b {
  color: #213758;
  font-weight: 800;
}
.metric-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 9px;
  margin-top: 18px;
}
.metric {
  display: grid;
  align-content: start;
  gap: 8px;
  min-height: 102px;
  padding: 14px 11px;
  background: #f6f8fb;
  border: 1px solid #edf1f5;
  border-radius: 8px;
}
.metric span {
  font-size: 10px;
  color: #8290a2;
}
.metric strong {
  font-size: 26px;
  line-height: 1;
  color: #263f5d;
}
.metric small {
  font-size: 9px;
  color: #8796a8;
}
.metric-warning strong {
  color: #bf6747;
}
.minor-heading {
  margin: 0 0 12px;
  font-size: 14px;
  color: #2d4664;
}
.completion-top {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 7px;
  font-size: 11px;
  color: #8695a5;
}
.completion-top strong {
  font-size: 14px;
  color: #4f8e70;
}
.completion-track {
  height: 11px;
  overflow: hidden;
  background: #e9eef3;
  border-radius: 6px;
}
.completion-track div {
  height: 100%;
  border-radius: 6px;
  background: #5b997c;
}
.status-legend {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px 14px;
  margin-top: 13px;
}
.status-legend > span {
  display: flex;
  gap: 7px;
  align-items: center;
  color: #798a9a;
  font-size: 10px;
}
.status-legend b {
  margin-left: auto;
  font-size: 11px;
  color: #2d4764;
}
.dot {
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: 100%;
}
.dot.done {
  background: #5b997c;
}
.dot.time {
  background: #6d9ac4;
}
.dot.late {
  background: #cf775e;
}
.dot.unknown {
  background: #c5cdd7;
}
.startup-card {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 15px 19px;
  background: #f1f5fa;
  border-left: 3px solid #3b5e83;
  border-radius: 6px;
}
.startup-card > div:first-child {
  display: grid;
  gap: 5px;
}
.startup-card .subheading {
  font-size: 9px;
  letter-spacing: 0.1em;
  color: #7e91a6;
  font-weight: 800;
}
.startup-card strong {
  font-size: 23px;
  color: #213758;
}
.startup-card p {
  margin: 0;
  font-size: 10px;
  color: #8998aa;
}
.startup-days {
  display: grid;
  text-align: center;
  gap: 4px;
  min-width: 90px;
}
.startup-days strong {
  font-size: 30px;
  color: #345578;
}
.startup-days span {
  font-size: 10px;
  color: #8e9caf;
}
.attention-copy {
  padding: 13px 16px;
  background: #fff9f4;
  border-left: 3px solid #cf9565;
  border-radius: 4px;
}
.paper-footnote {
  position: absolute;
  left: 54px;
  right: 54px;
  bottom: 87px;
  padding-top: 9px;
  border-top: 1px solid #eef1f5;
  font-size: 9px;
  line-height: 1.5;
  color: #98a4b2;
}
.paper-footer {
  position: absolute;
  left: 54px;
  right: 54px;
  bottom: 43px;
  display: flex;
  justify-content: space-between;
  border-top: 1px solid #dfe5eb;
  padding-top: 11px;
  font-size: 9px;
  color: #8b98a8;
}
.report-table-title {
  margin: 38px 0 25px;
  align-items: flex-start;
}
.overdue-table {
  width: 100%;
  border-collapse: collapse;
  table-layout: fixed;
  text-align: left;
}
.overdue-table th {
  padding: 12px 8px;
  background: #263e5a;
  color: #fff;
  font-size: 9px;
  line-height: 1.35;
  font-weight: 750;
  overflow-wrap: anywhere;
}
.overdue-table td {
  padding: 12px 8px;
  border-bottom: 1px solid #e9edf3;
  color: #68788b;
  font-size: 10px;
  line-height: 1.45;
  vertical-align: top;
  overflow-wrap: anywhere;
}
.overdue-table td strong {
  color: #314864;
  font-weight: 750;
}
.overdue-table tr:nth-child(even) td {
  background: #fafbfd;
}
.overdue-table th:nth-child(1) {
  width: 25%;
}
.overdue-table th:nth-child(2) {
  width: 16%;
}
.overdue-table th:nth-child(3) {
  width: 17%;
}
.overdue-table th:nth-child(4) {
  width: 15%;
}
.overdue-table th:nth-child(5) {
  width: 13%;
}
.overdue-table th:nth-child(6) {
  width: 14%;
}
.overdue-table .late-days {
  color: #c26850;
  font-weight: 750;
  text-align: center;
}
.overdue-table .treatment {
  color: #a1aab5;
}
.overdue-table .no-overdue {
  text-align: center;
  padding: 36px;
  color: #8491a2;
}
.table-commentary {
  margin-top: 25px;
  padding: 16px 19px;
  border-left: 3px solid #8cabc5;
  background: #f3f7fb;
  border-radius: 4px;
}
.table-commentary b {
  display: block;
  font-size: 11px;
  color: #2c4d70;
  margin-bottom: 6px;
}
.table-commentary p {
  margin: 0;
  color: #718196;
  font-size: 11px;
  line-height: 1.7;
}
.pipeline-chart {
  margin: 10px 0;
}
.paper-caption {
  margin: 22px 0 0;
  color: #95a1af;
  font-size: 9px;
  line-height: 1.5;
}
.closing-section {
  padding-top: 23px;
  border-top: 1px solid #e9edf2;
}
.preview-note {
  margin: 0;
  font-size: 11px;
  color: #8795a6;
  line-height: 1.5;
}
@media (max-width: 640px) {
  .report-toolbar-actions {
    width: 100%;
  }
  .report-preview {
    justify-items: start;
  }
}
</style>
