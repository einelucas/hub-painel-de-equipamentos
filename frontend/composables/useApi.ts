import {
  responseData,
  sendRequest,
  toDownload,
  type ApiContext,
  type ApiDownload,
  type ApiQuery,
  type ApiRequestOptions,
} from "~/services/api/http";

export type { ApiDownload, ApiQuery, ApiRequestOptions } from "~/services/api/http";

/** Único ponto de acesso HTTP da aplicação (Axios por baixo; ver
 * `services/api/http.ts`). Erros chegam sempre como `ApiError`. */
export function useApi() {
  const config = useRuntimeConfig();
  const auth = useAuthStore();

  // Lido a cada chamada: o token pode mudar (login/logout) depois do setup.
  const context = (): ApiContext => ({ baseURL: config.public.apiBaseUrl, token: auth.token });

  async function request<T>(path: string, options: ApiRequestOptions = {}): Promise<T> {
    return responseData(await sendRequest<T>(context(), path, options));
  }

  /** Envia `FormData` (o boundary do multipart é definido pelo cliente HTTP). */
  function upload<T>(path: string, body: FormData, method: "POST" | "PUT" = "PUT"): Promise<T> {
    return request<T>(path, { method, body });
  }

  /** Baixa um arquivo; erro HTTP vira `ApiError`, nunca um Blob "válido". */
  async function download(path: string, query?: ApiQuery): Promise<ApiDownload> {
    return toDownload(await sendRequest<Blob>(context(), path, { method: "GET", query, responseType: "blob" }));
  }

  return {
    get: <T>(path: string, query?: ApiQuery) => request<T>(path, { method: "GET", query }),
    post: <T>(path: string, body?: unknown) => request<T>(path, { method: "POST", body }),
    put: <T>(path: string, body?: unknown) => request<T>(path, { method: "PUT", body }),
    patch: <T>(path: string, body?: unknown) => request<T>(path, { method: "PATCH", body }),
    delete: <T>(path: string, body?: unknown, query?: ApiQuery) =>
      request<T>(path, { method: "DELETE", body, query }),
    request,
    upload,
    download,
  };
}
