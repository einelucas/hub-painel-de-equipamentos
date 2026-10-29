import { config } from "@vue/test-utils";
import { defineComponent } from "vue";
import { createVuetify } from "vuetify";
import * as components from "vuetify/components";
import * as directives from "vuetify/directives";

/**
 * Apenas o diálogo de confirmação antigo utiliza AppTeleport.
 * Os overlays do Vuetify usam seu próprio Teleport e são exercitados
 * de maneira nativa nos testes.
 */
const AppTeleportStub = defineComponent({
  name: "AppTeleport",
  setup(_, { slots }) {
    return () => slots.default?.();
  },
});

// happy-dom não fornece visualViewport, usado pelo VOverlay do Vuetify.
if (!("visualViewport" in globalThis)) {
  Object.defineProperty(globalThis, "visualViewport", {
    value: { width: 1024, height: 768, scale: 1, offsetLeft: 0, offsetTop: 0, addEventListener: () => {}, removeEventListener: () => {} },
    writable: true,
  });
}

const vuetify = createVuetify({ components, directives });

config.global.plugins = [...(config.global.plugins || []), vuetify];

config.global.stubs = {
  ...config.global.stubs,
  AppTeleport: AppTeleportStub,
};