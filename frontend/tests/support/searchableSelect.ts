import { nextTick } from "vue";
import { DOMWrapper } from "@vue/test-utils";
import type { VueWrapper } from "@vue/test-utils";

/**
 * Wrappers aceitos: o root do `mount`, o `DOMWrapper` (ou a variante sem
 * `exists` devolvida por `.get` no VTU 2.4) e escopos parciais como uma linha
 * de tabela.
 */
type ElementWrapper = DOMWrapper<Element> | Omit<DOMWrapper<Element>, "exists">;
type AnyWrapper = VueWrapper | ElementWrapper;

/**
 * O dropdown do ElSelect é teleportado para o `body`, então as opções não fazem
 * parte da árvore do wrapper. Este helper resolve o menu pelo `aria-controls`
 * do input interno, que aponta para o `listbox` do próprio select.
 */
function root(wrapper: AnyWrapper, testId: string): ElementWrapper {
  const found = wrapper
    .findAll(".searchable-select, .searchable-multi-select, .floating-filter-select")
    .find(
      (item) =>
        item.attributes("data-testid") === testId ||
        item.find(`[data-testid='${testId}']`).exists(),
    );
  if (!found) throw new Error(`SearchableSelect '${testId}' não encontrado`);
  return found;
}

/** Input interno do ElSelect que recebe foco, busca e teclado. */
function control(wrapper: AnyWrapper, testId: string): ElementWrapper {
  return root(wrapper, testId).get(".el-select__input");
}

/** `listbox` do menu, já dentro da árvore do `document.body`. */
function menu(wrapper: AnyWrapper, testId: string): Element | null {
  const menuId = control(wrapper, testId).attributes("aria-controls");
  return menuId ? document.getElementById(menuId) : null;
}

/** `listbox` do menu, já dentro da árvore do `document.body`. */
export function menuElement(wrapper: AnyWrapper, testId: string): Element | null {
  return menu(wrapper, testId);
}

/** Abre o menu sem fechá-lo caso ele já esteja aberto. */
export async function openMenu(wrapper: AnyWrapper, testId: string): Promise<void> {
  const input = control(wrapper, testId);
  if (input.attributes("aria-expanded") !== "true") await input.trigger("click");
}

/** Opções visíveis no menu (inclui a opção vazia, quando houver). */
export function menuOptions(wrapper: AnyWrapper, testId: string): DOMWrapper<Element>[] {
  const listbox = menu(wrapper, testId);
  if (!listbox) return [];
  return Array.from(listbox.querySelectorAll("[role='option']")).map(
    (item) => new DOMWrapper(item),
  );
}

function optionLabel(option: DOMWrapper<Element>): string {
  const strong = option.find("strong");
  if (strong.exists()) return strong.text();
  return option.text();
}

/** Abre o menu e devolve os rótulos das opções (inclui a opção vazia, se houver). */
export async function optionLabels(wrapper: AnyWrapper, testId: string): Promise<string[]> {
  await openMenu(wrapper, testId);
  return menuOptions(wrapper, testId).map(optionLabel);
}

/** Escolhe a opção pelo rótulo exato (do `strong`), como o usuário faria. */
export async function chooseOption(
  wrapper: AnyWrapper,
  testId: string,
  label: string,
): Promise<void> {
  await openMenu(wrapper, testId);
  const option = menuOptions(wrapper, testId).find(
    (item) => optionLabel(item) === label,
  );
  if (!option) {
    const available = menuOptions(wrapper, testId)
      .map(optionLabel)
      .filter(Boolean)
      .join(", ");
    throw new Error(
      `Opção '${label}' não encontrada em '${testId}'${available ? ` (opções: ${available})` : ""}`,
    );
  }
  await option.trigger("click");
  await nextTick();
}

/** Texto exibido no campo fechado: rótulo da opção escolhida ou vazio. */
export function shownValue(wrapper: AnyWrapper, testId: string): string {
  return root(wrapper, testId).attributes("data-selected-label") ?? "";
}

export function isDisabled(wrapper: AnyWrapper, testId: string): boolean {
  return root(wrapper, testId).attributes("data-disabled") === "true";
}
