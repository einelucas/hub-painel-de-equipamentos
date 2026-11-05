/**
 * Aparência nativa dos seletores do Hub.
 * Fonte única para a aplicação e os testes de componentes.
 * O Vuetify gerencia a label flutuante, os ícones, as bordas e os estados.
 */
export const hubAutocompleteDefaults = {
  variant: "outlined",
  color: "primary",
  baseColor: "secondary",
  bgColor: "surface",
  rounded: "lg",
  density: "comfortable",
  hideDetails: "auto",
  // Busca dos selects ignora acentos: `incendio` encontra `Incêndio`.
  ignoreAccents: true,
} as const;
