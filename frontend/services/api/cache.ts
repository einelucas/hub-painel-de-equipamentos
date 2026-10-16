import type { ApiContext, ApiQuery } from "~/services/api/http";
import { normalizedBaseUrl, serializeQuery } from "~/services/api/http";

const DATA_TTL_MS = 30_000;
const CATALOG_TTL_MS = 5 * 60_000;
const MAX_ENTRIES = 150;

interface CacheEntry {
  expiresAt: number;
  value: unknown;
}

const entries = new Map<string, CacheEntry>();
const pending = new Map<string, Promise<unknown>>();
let credentialScope: string | null | undefined;
let generation = 0;

/** Endpoints com estado de sessão ou efeitos colaterais de leitura nunca são cacheados. */
const UNCACHED_PREFIXES = ["/auth/", "/notifications", "/module-context/defaults"];
const CATALOG_PATHS = [
  /^\/units(?:\/[^/]+\/project-contexts)?$/,
  /^\/(?:disciplines|eap-nodes|work-packages|responsibles|suppliers)$/,
];
const DATA_PATHS = [/^\/equipments(?:\/[^/]+)?$/, /^\/dashboard\//, /^\/queues\//];

export interface ApiCacheOptions {
  /** Ignora uma entrada válida e renova o valor pela rede. */
  force?: boolean;
  /** Sobrescreve o TTL da política; zero desativa o cache nesta chamada. */
  ttlMs?: number;
}

export function cacheTtl(path: string): number {
  if (UNCACHED_PREFIXES.some((prefix) => path.startsWith(prefix))) return 0;
  if (CATALOG_PATHS.some((pattern) => pattern.test(path))) return CATALOG_TTL_MS;
  if (DATA_PATHS.some((pattern) => pattern.test(path))) return DATA_TTL_MS;
  return 0;
}

function cacheKey(context: ApiContext, path: string, query?: ApiQuery): string {
  const search = query ? serializeQuery(query) : "";
  return `${normalizedBaseUrl(context.baseURL)}${path}${search ? `?${search}` : ""}`;
}

function ensureCredentialScope(token: string | null | undefined): void {
  if (credentialScope === undefined) {
    credentialScope = token;
    return;
  }
  if (credentialScope !== token) {
    clearApiCache();
    credentialScope = token;
  }
}

function trimCache(): void {
  while (entries.size >= MAX_ENTRIES) {
    const oldest = entries.keys().next().value as string | undefined;
    if (!oldest) return;
    entries.delete(oldest);
  }
}

export async function cachedApiGet<T>(
  context: ApiContext,
  path: string,
  query: ApiQuery | undefined,
  options: ApiCacheOptions,
  load: () => Promise<T>,
): Promise<T> {
  const ttlMs = options.ttlMs ?? cacheTtl(path);
  if (import.meta.server || ttlMs <= 0) return load();

  ensureCredentialScope(context.token);
  const key = cacheKey(context, path, query);
  const now = Date.now();
  const hit = entries.get(key);
  if (!options.force && hit && hit.expiresAt > now) return hit.value as T;
  if (hit) entries.delete(key);

  const active = pending.get(key);
  if (!options.force && active) return active as Promise<T>;

  const requestGeneration = generation;
  const request = load()
    .then((value) => {
      // Uma escrita pode ter invalidado o cache enquanto este GET estava em
      // voo. Nesse caso o valor anterior à mutação nunca volta para o cache.
      if (requestGeneration === generation) {
        trimCache();
        entries.set(key, { value, expiresAt: Date.now() + ttlMs });
      }
      return value;
    })
    .finally(() => {
      if (pending.get(key) === request) pending.delete(key);
    });
  pending.set(key, request);
  return request;
}

/** Mutações invalidam todas as leituras: simples, seguro e sem dados cruzados entre usuários. */
export function clearApiCache(): void {
  generation += 1;
  entries.clear();
  pending.clear();
}

