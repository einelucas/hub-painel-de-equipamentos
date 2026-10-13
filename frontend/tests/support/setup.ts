import { config } from "@vue/test-utils";

// Menus e modais são teleportados para o body; nos testes eles renderizam no
// próprio componente, para que `wrapper.find` os alcance.
config.global.stubs = { ...config.global.stubs, teleport: true };
