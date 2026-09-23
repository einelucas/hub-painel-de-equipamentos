import type {
  AvailableTransitions,
  EquipmentOperationalStatus,
  EquipmentProcesses,
  HistoryList,
  ReopenRequest,
  TransitionOption,
  WorkflowException,
} from "~/types/equipment";
import type { ProcessResource } from "~/utils/workflow";

interface ReopenRequestList {
  items: ReopenRequest[];
}
interface WorkflowExceptionList {
  items: WorkflowException[];
}

export function useEquipmentWorkflow(equipmentId: Ref<string>) {
  const api = useApi();
  const processes = ref<EquipmentProcesses | null>(null);
  const transitions = ref<AvailableTransitions | null>(null);
  const history = ref<HistoryList["items"]>([]);
  const operationalStatus = ref<EquipmentOperationalStatus | null>(null);
  const exceptions = ref<WorkflowException[]>([]);
  const reopenRequests = ref<ReopenRequest[]>([]);
  const loading = ref(true);
  const saving = ref(false);
  const advancing = ref(false);
  const busy = ref(false);
  const error = ref("");
  const actionError = ref("");
  const actionSuccess = ref("");

  const advance = computed<TransitionOption | null>(
    () => transitions.value?.transitions.find((item) => item.kind === "advance") ?? null,
  );

  const activeException = computed<WorkflowException | null>(
    () => exceptions.value.find((item) => item.status === "ACTIVE") ?? null,
  );

  const pendingReopenRequest = computed<ReopenRequest | null>(
    () => reopenRequests.value.find((item) => item.status === "PENDING") ?? null,
  );

  async function load(): Promise<void> {
    loading.value = true;
    error.value = "";
    try {
      const [processResult, transitionResult, historyResult, statusResult, exceptionResult, reopenResult] =
        await Promise.all([
          api.get<EquipmentProcesses>(`/equipments/${equipmentId.value}/processes`),
          api.get<AvailableTransitions>(`/equipments/${equipmentId.value}/available-transitions`),
          api.get<HistoryList>(`/equipments/${equipmentId.value}/history`),
          api.get<EquipmentOperationalStatus>(`/equipments/${equipmentId.value}/operational-status`),
          api.get<WorkflowExceptionList>(`/equipments/${equipmentId.value}/workflow-exceptions`),
          api.get<ReopenRequestList>(`/equipments/${equipmentId.value}/reopen-requests`),
        ]);
      processes.value = processResult;
      transitions.value = transitionResult;
      history.value = historyResult.items;
      operationalStatus.value = statusResult;
      exceptions.value = exceptionResult.items;
      reopenRequests.value = reopenResult.items;
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

  async function requestTransition(targetStage: number): Promise<boolean> {
    advancing.value = true;
    actionError.value = "";
    actionSuccess.value = "";
    try {
      transitions.value = await api.post<AvailableTransitions>(
        `/equipments/${equipmentId.value}/transitions`,
        { targetStage, reason: null },
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

  async function run<T>(action: () => Promise<T>, fallback: string): Promise<T | null> {
    busy.value = true;
    actionError.value = "";
    actionSuccess.value = "";
    try {
      const result = await action();
      await load();
      return result;
    } catch (caught) {
      actionError.value = caught instanceof Error ? caught.message : fallback;
      return null;
    } finally {
      busy.value = false;
    }
  }

  // --- Etapa 7B: estado operacional ---

  function enterStandby(justification: string): Promise<unknown> {
    return run(
      () => api.post(`/equipments/${equipmentId.value}/standby`, { justification }),
      "Não foi possível colocar em Standby.",
    );
  }

  function liftStandby(justification: string): Promise<unknown> {
    return run(
      () => api.post(`/equipments/${equipmentId.value}/standby/lift`, { justification: justification || null }),
      "Não foi possível remover o Standby.",
    );
  }

  function cancelEquipment(justification: string): Promise<unknown> {
    return run(
      () => api.post(`/equipments/${equipmentId.value}/cancel`, { justification }),
      "Não foi possível cancelar o equipamento.",
    );
  }

  function enterSanitation(justification: string): Promise<unknown> {
    return run(
      () => api.post(`/equipments/${equipmentId.value}/sanitation`, { justification }),
      "Não foi possível colocar em Saneamento.",
    );
  }

  function endSanitation(justification: string): Promise<unknown> {
    return run(
      () => api.post(`/equipments/${equipmentId.value}/sanitation/end`, { justification: justification || null }),
      "Não foi possível encerrar o Saneamento.",
    );
  }

  // --- Etapa 7B: exceções de workflow ---

  function createException(type: string, justification: string): Promise<unknown> {
    return run(
      () => api.post(`/equipments/${equipmentId.value}/workflow-exceptions`, { type, justification }),
      "Não foi possível abrir a exceção de fluxo.",
    );
  }

  function cancelException(exceptionId: string): Promise<unknown> {
    return run(
      () => api.post(`/equipments/${equipmentId.value}/workflow-exceptions/${exceptionId}/cancel`, {}),
      "Não foi possível cancelar a exceção de fluxo.",
    );
  }

  // --- Etapa 7C: reabertura com aprovação ---

  function requestReopen(targetStage: number, justification: string): Promise<unknown> {
    return run(
      () => api.post(`/equipments/${equipmentId.value}/reopen-requests`, { targetStage, justification }),
      "Não foi possível solicitar a reabertura.",
    );
  }

  function approveReopen(requestId: string, note: string): Promise<unknown> {
    return run(
      () =>
        api.post(`/equipments/${equipmentId.value}/reopen-requests/${requestId}/approve`, {
          note: note || null,
        }),
      "Não foi possível aprovar a reabertura.",
    );
  }

  function rejectReopen(requestId: string, note: string): Promise<unknown> {
    return run(
      () =>
        api.post(`/equipments/${equipmentId.value}/reopen-requests/${requestId}/reject`, {
          note: note || null,
        }),
      "Não foi possível rejeitar a reabertura.",
    );
  }

  return {
    processes,
    transitions,
    history,
    operationalStatus,
    exceptions,
    reopenRequests,
    activeException,
    pendingReopenRequest,
    loading,
    saving,
    advancing,
    busy,
    error,
    actionError,
    actionSuccess,
    advance,
    load,
    saveProcess,
    requestTransition,
    enterStandby,
    liftStandby,
    cancelEquipment,
    enterSanitation,
    endSanitation,
    createException,
    cancelException,
    requestReopen,
    approveReopen,
    rejectReopen,
  };
}
