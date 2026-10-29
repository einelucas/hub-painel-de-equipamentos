import { config } from "@vue/test-utils";
import { createVuetify } from "vuetify";
import * as components from "vuetify/components";
import * as directives from "vuetify/directives";
import { hubAutocompleteDefaults } from "~/config/vuetifyDefaults";

// happy-dom não fornece visualViewport, usado pelo VOverlay do Vuetify.
if (!("visualViewport" in globalThis)) {
  Object.defineProperty(globalThis, "visualViewport", {
    value: {
      width: 1024,
      height: 768,
      scale: 1,
      offsetLeft: 0,
      offsetTop: 0,
      addEventListener: () => {},
      removeEventListener: () => {},
    },
    writable: true,
  });
}

const vuetify = createVuetify({
  components,
  directives,
  defaults: { VAutocomplete: hubAutocompleteDefaults },
});
config.global.plugins = [...(config.global.plugins || []), vuetify];
