import { config } from "@vue/test-utils";
import { defineComponent } from "vue";
import { createVuetify } from "vuetify";
import * as components from "vuetify/components";
import * as directives from "vuetify/directives";

/**
 * O `AppTeleport` (usado apenas pelos diálogos do Hub) é substituído por um
 * pass-through nos testes: o conteúdo continua dentro do wrapper e as
 * asserções de modal seguem funcionando. O `Teleport` nativo do Element Plus
 * permanece real, porque stubbá-lo faz o `ElSelect` entrar em atualização
 * recursiva no happy-dom.
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