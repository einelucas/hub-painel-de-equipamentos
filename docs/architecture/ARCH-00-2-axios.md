# ARCH-00.2 — Cliente HTTP do frontend: `$fetch` → Axios

> **Baseline:** `main` @ `1d5a184` (CI verde).
> **Escopo:** trocar só o cliente HTTP **por dentro** do `useApi`. Backend, OpenAPI,
> endpoints, banco, regras de negócio e layout ficaram inalterados.

## Antes e depois

```
ANTES                                   DEPOIS
pages / components / stores             pages / components / stores
          │                                       │
       useApi                                  useApi                (composables/useApi.ts)
          │                                       │
   $fetch (ofetch, Nuxt)                 Axios — instância única     (services/api/http.ts)
          │                                       │
    FastAPI /api/v1                         FastAPI /api/v1
```

O Axios fica restrito a `services/api/http.ts`, onde está a instância única
(`http = axios.create()`). Só o `useApi` usa esse módulo. Páginas, componentes e
stores não importam o Axios.

## Dependência adicionada

| Pacote | Versão | Tipo |
|---|---|---|
| `axios` | `^1.20.0` (lock: 1.20.0, publicada em 2026-08-26) | `dependencies` |

O `pnpm-lock.yaml` ganhou o `axios` e as dependências transitivas dele
(`follow-redirects`, `form-data`, `proxy-from-env`, `https-proxy-agent`, `agent-base`,
`combined-stream`, `delayed-stream`, `asynckit`, `es-set-tostringtag`). **Nenhuma outra
biblioteca mudou de versão**, o que foi conferido comparando os dois lockfiles
pacote a pacote. O pnpm também recalculou o contexto de peer dependencies de alguns
snapshots já existentes (`nuxt`, `vue-tsc`, `@volar/typescript`, `@nuxt/vite-builder`,
`unplugin`), sem trocar versões.

O lockfile commitado estava formatado com Prettier, e o pnpm o regrava no próprio
formato. Para manter o diff revisável, ele foi reformatado com Prettier 3, que
reproduz byte a byte o estilo anterior. `pnpm install --frozen-lockfile` aceita o
arquivo.

## Arquivos alterados

| Arquivo | Mudança |
|---|---|
| `frontend/package.json` / `pnpm-lock.yaml` | Dependência `axios`. |
| `frontend/services/api/http.ts` (novo) | Instância Axios e lógica pura: URL, query, auth, retry, erros, filename. |
| `frontend/composables/useApi.ts` | Mesma API pública, implementada sobre `http.ts`, com novos `upload()` e `download()`. |
| `frontend/components/equipment/EquipmentContractsList.vue` | Upload e download passaram a usar `api.upload()` e `api.download()` (ver "Consumidores"). |
| `frontend/tests/EquipmentContractForm.test.ts` | Stub de `request` trocado por `upload`, com as mesmas verificações. |
| `frontend/tests/useApi.test.ts` (novo) | 32 testes do contrato público. |

## Contrato público do `useApi`

| Método | Antes | Depois |
|---|---|---|
| `get<T>(path, query?)` | ✔ | igual |
| `post<T>(path, body?)` | ✔ | igual |
| `put<T>(path, body?)` | ✔ | igual |
| `patch<T>(path, body?)` | ✔ | igual |
| `delete<T>(path, body?, query?)` | ✔ | igual |
| `request<T>(path, options)` | opções do ofetch | opções próprias e neutras: `method`, `query`, `body`, `headers`, `responseType` |
| `upload<T>(path, formData, method = "PUT")` | — | **novo** |
| `download(path, query?)` → `{ blob, filename, contentType }` | — | **novo** |

### Consumidores

- **Antes e depois:** 24 arquivos usam `useApi()`.
- **Alterado:** só `EquipmentContractsList.vue`, que era o único a passar opções
  específicas do ofetch (`body: FormData as never`, `responseType: "blob"`) para
  `request`. Ele passou para `upload()` e `download()`, e nenhuma opção de cliente
  HTTP fica mais no componente.
- **Comportamento visível:** o mesmo. Para o nome do arquivo baixado, o componente
  continua usando `item.file.fileName` e só cai para o `Content-Disposition` se esse
  nome faltar.

## Autenticação

O comportamento é o mesmo, sem interceptor:

- o `Authorization: Bearer <token>` é montado **por requisição**, com o token lido da
  `useAuthStore()` (cookie `painel_equipamentos_access_token`) no momento da chamada;
- sem token, a requisição sai sem `Authorization`;
- headers explícitos do chamador continuam prevalecendo;
- login de desenvolvimento (`dev-<role>`) e OIDC não mudaram.

Um interceptor global foi descartado porque precisaria acessar a store do Pinia fora
do contexto do Nuxt, sem ganho real em relação ao header por requisição.

## Equivalências mantidas com o `$fetch`

| Aspecto | Comportamento preservado |
|---|---|
| baseURL | `runtimeConfig.public.apiBaseUrl`, com `/api/v1` acrescentado quando falta a versão. |
| Query | Mesma serialização do `ufo` (que o `$fetch` usava): `undefined` é omitido; `null` e `""` viram só a chave (`?area_id`); arrays repetem a chave (`ids=a&ids=b`); espaço vira `+`. Conferido contra o `stringifyQuery` real do ufo 1.6.4. O serializador padrão do Axios **não** foi usado, porque mudaria `null` e arrays. |
| Corpo | JSON para objetos; `FormData` sem `Content-Type` manual, com o boundary definido pelo navegador; GET nunca envia corpo. |
| Resposta vazia | 101/204/205/304 devolvem `undefined`, como antes. |
| Retry | Igual ao padrão do ofetch: GET é repetido **uma vez**, sem espera, em erro de rede ou nos status 408, 409, 425, 429, 500, 502, 503 e 504. POST, PUT, PATCH e DELETE nunca são repetidos. |
| Timeout | Nenhum, como antes. |
| SSR | Mesmo fluxo: no servidor o Axios usa o adapter HTTP do Node, com a mesma URL absoluta da configuração. |

## Tratamento de erro

Toda falha continua chegando ao consumidor como `ApiError` (`message`, `status`,
`data`), via o mesmo `apiErrorMessage`, sem mensagens novas:

- FastAPI `detail` em string vira a mensagem; `detail` em lista (422) junta os `msg`;
- sem `detail`, usa `message` ou `error` do corpo; corpo vazio usa a mensagem genérica
  já existente;
- 400, 401, 403, 404, 409, 422 e 500 trazem o `status` correspondente;
- falha de rede e timeout dão `status 0` e a mensagem genérica;
- no download, o corpo de erro chega como `Blob` e é lido como JSON. Assim um 404
  nunca vira "arquivo válido" e a mensagem do backend é preservada. **Antes**, esse
  caso caía na mensagem genérica.

## Testes

`frontend/tests/useApi.test.ts` simula o servidor com um adapter falso na instância
HTTP e verifica só o que sai pela rede (método, URL final, headers, corpo) e o que o
consumidor recebe. Cobre:
- GET, POST, PUT, PATCH e DELETE;
- query params (string, number, boolean, `null`, `undefined`, arrays, `page`,
  `pageSize`, `unit_id`, `equipment_id`, `project_context_id`, `discipline_id`,
  `responsible_user_id`);
- Authorization, ausência de token e token lido a cada chamada;
- 2xx e 204;
- 400, 401, 403, 404, 409, 422 e 500, FastAPI `detail`, `message` e `error`, corpo
  vazio;
- erro de rede e timeout;
- retry;
- upload de FormData e download de Blob (incluindo erro em Blob);
- parsing do `Content-Disposition`.

## Riscos residuais

| Risco | Nível | Observação |
|---|---|---|
| `Content-Disposition` não legível no navegador | Baixo | O backend não declara `expose_headers` no CORS, então em cross-origin `download().filename` vem `null`. O componente usa o nome cadastrado e não é afetado. Expor o header é uma decisão de backend, fora desta etapa. |
| Header `Accept` | Baixo | O Axios envia `application/json, text/plain, */*` e o ofetch enviava `application/json` só com corpo JSON. O FastAPI não faz negociação de conteúdo nessas rotas. |
| Query embutida no `path` | Baixo | O ofetch mesclava query do path com `query`. Nenhum consumidor usa `?` no path; se usar, os dois são concatenados com `&`. |
| Bundle | Baixo | O Axios entra no bundle do cliente e no do servidor. No build de verificação, o chunk do cliente que o contém (com outros módulos compartilhados) tem 54 kB, ou 20 kB com gzip. |
| Testes com adapter falso | Médio | Não exercitam o XHR real do navegador. O fluxo ponta a ponta (login, listas, upload e download de contrato) deve ser conferido manualmente contra o backend de desenvolvimento. |

## Validação E2E em navegador

A ARCH-00.2 foi validada com Playwright num ambiente isolado:

- PostgreSQL temporário próprio, com dados fictícios criados pela API;
- backend FastAPI em `:8010`;
- frontend em build de produção (`nuxt build` servido pelo Nitro) em `:3010`, com
  `NUXT_PUBLIC_API_BASE_URL` apontando para o backend isolado;
- nenhuma conexão com DEV ou produção.

| Fluxo | Resultado |
|---|---|
| Login DEV / `auth/me` | OK |
| `Authorization: Bearer` em todas as chamadas | OK |
| Dashboard | OK |
| Filtros e query params (disciplina, etapa, `unit_id`, `project_context_id`, paginação) | OK |
| Busca com espaço (`search=Compressor+E2E`) | OK |
| Upload de contrato via `multipart/form-data` (FormData, boundary definido pelo navegador) | OK |
| Download do arquivo do contrato | OK, nome e conteúdo preservados byte a byte |
| Exclusão de contrato (204) | OK |
| Erro 409 exibido com a mensagem do backend | OK |
| 401 no SSR / token inválido: cookie limpo e redirecionamento para o login | OK |
| Console do navegador | Sem erros JavaScript novos |

Observações:

- O login corporativo (OIDC) não foi testado nesta etapa.
- O erro de download não foi reproduzido pela interface, mas está coberto pelos
  testes automatizados do `useApi`.
- Logo após o login, algumas chamadas do dashboard ocorrem duas vezes. O mesmo
  comportamento foi reproduzido no baseline `1d5a184`, anterior ao Axios, então é
  preexistente e **não** é regressão da ARCH-00.2. Num carregamento direto do
  dashboard, cada chamada ocorre uma vez.
- Essa duplicação deve ser tratada separadamente, se necessário.
