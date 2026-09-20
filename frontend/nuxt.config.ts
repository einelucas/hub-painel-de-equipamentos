export default defineNuxtConfig({
  compatibilityDate: "2025-07-15",
  devtools: { enabled: true },
  modules: ["@pinia/nuxt", "@nuxtjs/tailwindcss", "@nuxt/eslint"],
  components: [{ path: "~/components", pathPrefix: false }],
  css: ["~/assets/css/vue.css"],
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
