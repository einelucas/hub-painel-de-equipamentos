import type { DOMWrapper, VueWrapper } from "@vue/test-utils";

type AnyWrapper = VueWrapper | DOMWrapper<Element>;

/** Raiz do `SearchableSelect` cujo input tem o `data-testid` informado. */
function root(wrapper: AnyWrapper, testId: string): DOMWrapper<Element> {
  const found = wrapper
    .findAll(".searchable-select")
    .find((item) => item.find(`[data-testid='${testId}']`).exists());
  if (!found) throw new Error(`SearchableSelect '${testId}' não encontrado`);
  return found;
}

/** Abre o menu e devolve os rótulos das opções (inclui a opção vazia, se houver). */
export async function optionLabels(wrapper: AnyWrapper, testId: string): Promise<string[]> {
  await wrapper.get(`[data-testid='${testId}']`).trigger("focus");
  return root(wrapper, testId)
    .findAll("[role='option']")
    .map((item) => item.find("strong").text());
}

/** Escolhe a opção pelo rótulo exato, como o usuário faria. */
export async function chooseOption(wrapper: AnyWrapper, testId: string, label: string): Promise<void> {
  await wrapper.get(`[data-testid='${testId}']`).trigger("focus");
  const option = root(wrapper, testId)
    .findAll("[role='option']")
    .find((item) => item.find("strong").text() === label);
  if (!option) throw new Error(`Opção '${label}' não encontrada em '${testId}'`);
  await option.trigger("mousedown");
}

/** Texto exibido no campo fechado: rótulo da opção escolhida ou vazio. */
export function shownValue(wrapper: AnyWrapper, testId: string): string {
  return (wrapper.get(`[data-testid='${testId}']`).element as HTMLInputElement).value;
}

export function isDisabled(wrapper: AnyWrapper, testId: string): boolean {
  return (wrapper.get(`[data-testid='${testId}']`).element as HTMLInputElement).disabled;
}
