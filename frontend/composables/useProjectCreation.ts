import { ref } from "vue";

const open = ref(false);
const initialUnitId = ref("");
const createdRevision = ref(0);

/** Estado único do wizard de Nova Obra. Qualquer ponto da interface apenas
 * solicita sua abertura; o modal continua montado uma única vez na navbar. */
export function useProjectCreation() {
  function openNewProject(unitId = ""): void {
    initialUnitId.value = unitId;
    open.value = true;
  }

  function closeNewProject(): void {
    open.value = false;
  }

  function notifyCreated(): void {
    createdRevision.value += 1;
  }

  return { open, initialUnitId, createdRevision, openNewProject, closeNewProject, notifyCreated };
}
