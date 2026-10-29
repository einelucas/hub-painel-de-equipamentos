import { config } from "@vue/test-utils";
import { defineComponent } from "vue";
import { createVuetify } from "vuetify";
import { aliases, mdi } from "vuetify/iconsets/mdi-svg";

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

const vuetify = createVuetify({
  icons: {
    defaultSet: "mdi",
    aliases,
    sets: { mdi },
  },
  defaults: {
    VBtn: {
      color: "primary",
      variant: "outlined",
      rounded: "lg",
      elevation: 0,
    },
  },
});

config.global.plugins = [...(config.global.plugins ?? []), vuetify];

config.global.stubs = {
  ...config.global.stubs,
  AppTeleport: AppTeleportStub,
};
