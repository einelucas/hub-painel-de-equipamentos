import { inject, type InjectionKey } from "vue";
import type { EquipmentImport } from "~/composables/useEquipmentImport";

/** Estado do wizard compartilhado entre o modal e seus passos (sem store global). */
export const IMPORT_KEY: InjectionKey<EquipmentImport> = Symbol("equipment-import");

export function useImportState(): EquipmentImport {
  const state = inject(IMPORT_KEY);
  if (!state) throw new Error("Passo de importação usado fora do ImportEquipmentModal");
  return state;
}
