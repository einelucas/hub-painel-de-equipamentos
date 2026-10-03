import axios, { type AxiosResponse } from "axios";
import { ApiError, apiErrorMessage } from "~/services/api/error";

/** Instância única do Axios da aplicação. Só `useApi` deve usá-la — páginas,
 * componentes e stores falam com a API exclusivamente pelo composable. */
export const http = axios.create();

export type ApiMethod = "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
export type ApiQuery = Record<string, unknown>;

export interface ApiRequestOptions {
  method?: ApiMethod;
  query?: ApiQuery;
  body?: unknown;
  headers?: Record<string, string>;
  responseType?: "json" | "text" | "blob";
}

export interface ApiContext {
  baseURL: string;
  token?: string | null;
}

export interface ApiDownload {
  blob: Blob;
  /** Nome vindo do `Content-Disposition`; `null` quando ausente ou não exposto
   * pelo CORS ao navegador. */
  filename: string | null;
  contentType: string | null;
}

// Mesmo comportamento padrão do `$fetch` (ofetch) usado antes: métodos com
// payload nunca são repetidos; os demais são repetidos uma vez, sem espera,
// em erro de rede ou nestes status.
const PAYLOAD_METHODS = new Set<ApiMethod>(["POST", "PUT", "PATCH", "DELETE"]);
const RETRY_STATUS = new Set([408, 409, 425, 429, 500, 502, 503, 504]);
const NULL_BODY_STATUS = new Set([101, 204, 205, 304]);

export function normalizedBaseUrl(value: string): string {
  const base = value.replace(/\/$/, "");
  return /\/api\/v\d+$/.test(base) ? base : `${base}/api/v1`;
}

// Serialização idêntica à do `ufo` (usada pelo `$fetch`): `undefined` é
// omitido; `null`/"" viram só a chave; arrays repetem a chave; espaço vira "+".
function encodeQueryValue(input: unknown): string {
  return encodeURI(typeof input === "string" ? input : JSON.stringify(input))
    .replace(/%7c/gi, "|")
    .replace(/\+/g, "%2B")
    .replace(/%20/gi, "+")
    .replace(/#/g, "%23")
    .replace(/&/g, "%26")
    .replace(/%60/gi, "`")
    .replace(/%5e/gi, "^")
    .replace(/\//g, "%2F");
}

function encodeQueryKey(key: string): string {
  return encodeQueryValue(key).replace(/=/g, "%3D");
}

function encodeQueryItem(key: string, raw: unknown): string {
  const value = typeof raw === "number" || typeof raw === "boolean" ? String(raw) : raw;
  if (!value) return encodeQueryKey(key);
  if (Array.isArray(value)) {
    return value.map((item) => `${encodeQueryKey(key)}=${encodeQueryValue(item)}`).join("&");
  }
  return `${encodeQueryKey(key)}=${encodeQueryValue(value)}`;
}

export function serializeQuery(query: ApiQuery): string {
  return Object.keys(query)
    .filter((key) => query[key] !== undefined)
    .map((key) => encodeQueryItem(key, query[key]))
    .filter(Boolean)
    .join("&");
}

function withQuery(path: string, query?: ApiQuery): string {
  const search = query ? serializeQuery(query) : "";
  if (!search) return path;
  return `${path}${path.includes("?") ? "&" : "?"}${search}`;
}

function shouldRetry(error: unknown): boolean {
  if (!axios.isAxiosError(error) || axios.isCancel(error)) return false;
  return RETRY_STATUS.has(error.response?.status ?? 500);
}

async function readErrorBody(data: unknown): Promise<unknown> {
  // Download (`responseType: "blob"`): o corpo do erro também chega como Blob.
  if (typeof Blob !== "undefined" && data instanceof Blob) {
    const text = await data.text();
    try {
      return JSON.parse(text);
    } catch {
      return text;
    }
  }
  return data;
}

/** Converte qualquer falha (HTTP, rede, timeout) no `ApiError` que os
 * consumidores já conhecem: status 0 quando não houve resposta. */
export async function toApiError(error: unknown): Promise<ApiError> {
  if (error instanceof ApiError) return error;
  const response = axios.isAxiosError(error) ? error.response : undefined;
  const data = await readErrorBody(response?.data);
  return new ApiError(apiErrorMessage(data), response?.status ?? 0, data);
}

export async function sendRequest<T>(
  context: ApiContext,
  path: string,
  options: ApiRequestOptions = {},
): Promise<AxiosResponse<T>> {
  const method = (options.method ?? "GET").toUpperCase() as ApiMethod;
  const retries = PAYLOAD_METHODS.has(method) ? 0 : 1;
  for (let attempt = 0; ; attempt += 1) {
    try {
      return await http.request<T>({
        url: withQuery(path, options.query),
        baseURL: normalizedBaseUrl(context.baseURL),
        method,
        data: PAYLOAD_METHODS.has(method) ? options.body : undefined,
        headers: {
          ...(context.token ? { Authorization: `Bearer ${context.token}` } : {}),
          ...(options.headers ?? {}),
        },
        responseType: options.responseType ?? "json",
      });
    } catch (error: unknown) {
      if (attempt < retries && shouldRetry(error)) continue;
      throw await toApiError(error);
    }
  }
}

/** Corpo da resposta; `undefined` para status sem corpo (ex.: 204), como antes. */
export function responseData<T>(response: AxiosResponse<T>): T {
  return NULL_BODY_STATUS.has(response.status) ? (undefined as T) : response.data;
}

export function filenameFromContentDisposition(header: unknown): string | null {
  if (typeof header !== "string" || !header) return null;
  const encoded = /filename\*\s*=\s*(?:utf-8)?''([^;]+)/i.exec(header);
  if (encoded?.[1]) {
    try {
      return decodeURIComponent(encoded[1].trim().replace(/^"|"$/g, ""));
    } catch {
      // Valor mal codificado: cai para o `filename=` simples.
    }
  }
  const plain = /filename\s*=\s*(?:"([^"]*)"|([^;]+))/i.exec(header);
  const name = (plain?.[1] ?? plain?.[2])?.trim();
  return name || null;
}

export function toDownload(response: AxiosResponse<Blob>): ApiDownload {
  const contentType = response.headers["content-type"];
  return {
    blob: response.data,
    filename: filenameFromContentDisposition(response.headers["content-disposition"]),
    contentType: typeof contentType === "string" ? contentType : null,
  };
}
