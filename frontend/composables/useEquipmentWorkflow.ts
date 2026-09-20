import type {
  AvailableTransitions,
  EquipmentProcesses,
  HistoryList,
  TransitionOption,
} from "~/types/equipment";
import type { ProcessResource } from "~/utils/workflow";

export function useEquipmentWorkflow(equipmentId: Ref<string>) {
  const api = useApi();
  const processes = ref<EquipmentProcesses | null>(null);
  const transitions = ref<AvailableTransitions | null>(null);
  const history = ref<HistoryList["items"]>([]);
  const loading = ref(true);
  const saving = ref(false);
  const advancing = ref(false);
  const error = ref("");
  const actionError = ref("");
  const actionSuccess = ref("");

  const advance = computed<TransitionOption | null>(
    () => transitions.value?.transitions.find((item) => item.kind === "advance") ?? null,
  );
  const reopen = computed<TransitionOption | null>(
    () => transitions.value?.transitions.find((item) => item.kind === "reopen") ?? null,
  );

  async function load(): Promise<void> {
    loading.value = true;
    error.value = "";
    try {
      const [processResult, transitionResult, historyResult] = await Promise.all([
        api.get<EquipmentProcesses>(`/equipments/${equipmentId.value}/processes`),
        api.get<AvailableTransitions>(`/equipments/${equipmentId.value}/available-transitions`),
        api.get<HistoryList>(`/equipments/${equipmentId.value}/history`),
      ]);
      processes.value = processResult;
      transitions.value = transitionResult;
      history.value = historyResult.items;
    } catch (caught) {
      error.value =
        caught instanceof Error ? caught.message : "Não foi possível carregar o processo.";
    } finally {
      loading.value = false;
    }
  }

  /** Salvar dados do processo nunca avança a etapa — são ações separadas. */
  async function saveProcess(
    resource: ProcessResource,
    payload: Record<string, unknown>,
  ): Promise<boolean> {
    saving.value = true;
    actionError.value = "";
    actionSuccess.value = "";
    try {
      await api.patch(`/equipments/${equipmentId.value}/${resource}`, payload);
      await load();
      actionSuccess.value = "Alterações salvas.";
      return true;
    } catch (caught) {
      actionError.value =
        caught instanceof Error ? caught.message : "Não foi possível salvar as alterações.";
      return false;
    } finally {
      saving.value = false;
    }
  }

  async function requestTransition(targetStage: number, reason?: string): Promise<boolean> {
    advancing.value = true;
    actionError.value = "";
    actionSuccess.value = "";
    try {
      transitions.value = await api.post<AvailableTransitions>(
        `/equipments/${equipmentId.value}/transitions`,
        { targetStage, reason: reason?.trim() || null },
      );
      actionSuccess.value = `Etapa atualizada para ${transitions.value.currentStage} · ${transitions.value.currentStageLabel}.`;
      return true;
    } catch (caught) {
      actionError.value =
        caught instanceof Error ? caught.message : "Não foi possível alterar a etapa.";
      return false;
    } finally {
      advancing.value = false;
    }
  }

  return {
    processes,
    transitions,
    history,
    loading,
    saving,
    advancing,
    error,
    actionError,
    actionSuccess,
    advance,
    reopen,
    load,
    saveProcess,
    requestTransition,
  };
}
