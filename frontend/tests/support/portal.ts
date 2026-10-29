import { DOMWrapper } from "@vue/test-utils";

/** Os overlays VDialog são teletransportados pelo Vuetify para o body. */
export function portal(): DOMWrapper<Element> {
  return new DOMWrapper(document.body);
}
