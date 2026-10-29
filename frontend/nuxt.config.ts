import { createRequire } from "node:module";

// O dayjs publicado e CJS (UMD em dayjs.min.js). Com rolldown-vite o otimizador
// nao faz o pre-bundle dele e o browser/SSR recebem o arquivo cru, quebrando com
// "does not provide an export named 'default'". Aliases para o build ESM oficial
// do proprio dayjs resolvem isso. Caminhos absolutos: rolldown-vite nao expande
// capturas ($1) em alias, entao os plugins sao mapeados um a um.
const require = createRequire(import.meta.url);
const dayjsRoot = require
  .resolve("dayjs/package.json")
  .replace(/[\\/]package\.json$/, "")
  .replace(/\\/g, "/");
const dayjsEsm = `${dayjsRoot}/esm`;
const dayjsPlugins = [
  "advancedFormat",
  "customParseFormat",
  "dayOfYear",
  "isSameOrAfter",
  "isSameOrBefore",
  "localeData",
  "quarterOfYear",
  "weekOfYear",
  "weekYear",
];

export default defineNuxtConfig({
  compatibilityDate: "2025-07-15",
  devtools: { enabled: true },
  modules: [
    "@pinia/nuxt",
    "@nuxtjs/tailwindcss",
    "@nuxt/eslint",
    "vuetify-nuxt-module",
    "@element-plus/nuxt",
  ],
  components: [{ path: "~/components", pathPrefix: false }],
  css: [
    "~/assets/css/vue.css",
    "element-plus/dist/index.css",
    "~/assets/css/element-plus.css",
  ],
  vuetify: {
    moduleOptions: {
      styles: true,
      // Evita sobrescrever o useLayout nativo do Nuxt.
      prefixComposables: ["useLayout"],
    },
    vuetifyOptions: {
      theme: {
        defaultTheme: "light",
        themes: {
          light: {
            dark: false,
            colors: {
              background: "#f4f5f7",
              surface: "#ffffff",
              primary: "#304f7e",
              "primary-darken-1": "#213758",
              secondary: "#6b7280",
              "secondary-darken-1": "#4b5563",
              accent: "#eaa239",
              error: "#c0392b",
              info: "#007cc5",
              success: "#609346",
              warning: "#eaa239",
            },
          },
        },
      },
      icons: {
        defaultSet: "mdi-svg",
      },
      locale: {
        locale: "pt",
        fallback: "en",
      },
      localeMessages: ["en", "pt"],
      defaults: {
        VBtn: { rounded: "lg", elevation: 0 },
        VCard: { rounded: "lg", elevation: 0 },
        VTextField: {
          variant: "outlined",
          density: "comfortable",
          hideDetails: "auto",
        },
        VSelect: {
          variant: "outlined",
          density: "comfortable",
          hideDetails: "auto",
        },
        VAutocomplete: {
          variant: "outlined",
          color: "primary",
          density: "comfortable",
          hideDetails: "auto",
        },
      },
    },
  },
  // O CSS completo é importado manualmente para garantir a ordem dos overrides.
  elementPlus: {
    importStyle: false,
    defaultLocale: "pt-br",
    installMethods: ["ElLoading", "ElMessage", "ElMessageBox", "ElNotification"],
  },
  vite: {
    resolve: {
      alias: [
        { find: /^dayjs$/, replacement: `${dayjsEsm}/index.js` },
        ...dayjsPlugins.map((plugin) => ({
          find: `dayjs/plugin/${plugin}.js`,
          replacement: `${dayjsEsm}/plugin/${plugin}/index.js`,
        })),
        // Imports sem sufixo .js caem no diretorio do plugin (resolver pega o index.js).
        { find: /^dayjs\/plugin\//, replacement: `${dayjsEsm}/plugin/` },
        { find: /^dayjs\/locale\//, replacement: `${dayjsEsm}/locale/` },
      ],
    },
  },
  runtimeConfig: {
    public: {
      apiBaseUrl: process.env.NUXT_PUBLIC_API_BASE_URL || "http://localhost:8000/api/v1",
      oidcIssuer: process.env.NUXT_PUBLIC_OIDC_ISSUER || "",
      oidcClientId: process.env.NUXT_PUBLIC_OIDC_CLIENT_ID || "",
      oidcRedirectUri: process.env.NUXT_PUBLIC_OIDC_REDIRECT_URI || "http://localhost:3000/auth/callback",
      oidcPostLogoutRedirectUri:
        process.env.NUXT_PUBLIC_OIDC_POST_LOGOUT_REDIRECT_URI || "http://localhost:3000/login",
      devAuthEnabled: process.env.NUXT_PUBLIC_DEV_AUTH_ENABLED !== "false",
    },
  },
  typescript: {
    strict: true,
    // A validação roda explicitamente em `pnpm typecheck`. Evita que o build
    // dispare uma segunda instância do vue-tsc com argumentos conflitantes.
    typeCheck: false,
  },
  app: {
    head: {
      htmlAttrs: { lang: "pt-BR" },
      title: "Painel de Equipamentos",
      meta: [
        { name: "description", content: "Painel de Equipamentos da área de Planejamento." },
        { name: "viewport", content: "width=device-width, initial-scale=1" },
        { name: "theme-color", content: "#304f7e" },
      ],
      link: [
        { rel: "icon", type: "image/png", href: "/brand/favicon.png" },
        { rel: "preconnect", href: "https://fonts.googleapis.com" },
        { rel: "preconnect", href: "https://fonts.gstatic.com", crossorigin: "anonymous" },
        {
          rel: "stylesheet",
          href: "https://fonts.googleapis.com/css2?family=Manrope:wght@400;500;600;700;800&display=swap",
        },
      ],
    },
  },
});
