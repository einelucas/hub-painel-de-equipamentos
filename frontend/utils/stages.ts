export const EQUIPMENT_STAGES = [
  "Nova demanda",
  "Negociação",
  "Equalização",
  "Abertura do chamado",
  "Aprovação da minuta",
  "Escrituração do contrato",
  "SC ou OCI",
  "Aprovação da OC",
  "Concluído",
] as const;

export function stageTone(stage: number): string {
  if (stage === 8) return "stage-badge--complete";
  if (stage >= 5) return "stage-badge--advanced";
  if (stage >= 2) return "stage-badge--progress";
  return "stage-badge--new";
}
