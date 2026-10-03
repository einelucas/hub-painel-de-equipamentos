import { AxiosError, AxiosHeaders, type InternalAxiosRequestConfig } from "axios";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useApi } from "~/composables/useApi";
import { ApiError } from "~/services/api/error";
import { filenameFromContentDisposition, http, serializeQuery } from "~/services/api/http";

// "Servidor" falso: registra o que sairia pela rede e devolve a resposta
// escolhida pelo teste. Os testes olham só o contrato público do `useApi`
// (URL final, método, headers, corpo, dado devolvido e `ApiError`).
interface Wire {
  method: string;
  url: string;
  headers: Record<string, unknown>;
  data: unknown;
  responseType?: string;
}
type Reply = { status: number; body?: unknown; headers?: Record<string, string> } | "network" | "timeout";

let calls: Wire[] = [];
let replies: Reply[] = [];
const originalAdapter = http.defaults.adapter;

function serve(...queue: Reply[]): void {
  replies = queue;
}

function json(status: number, body?: unknown): Reply {
  return {
    status,
    body: body === undefined ? "" : JSON.stringify(body),
    headers: { "content-type": "application/json" },
  };
}

beforeEach(() => {
  calls = [];
  replies = [];
  vi.stubGlobal("useRuntimeConfig", () => ({ public: { apiBaseUrl: "http://api.test/api/v1" } }));
  vi.stubGlobal("useAuthStore", () => ({ token: "tok-123" }));
  http.defaults.adapter = async (config: InternalAxiosRequestConfig) => {
    calls.push({
      method: String(config.method).toUpperCase(),
      url: http.getUri(config),
      headers: AxiosHeaders.from(config.headers).toJSON(),
      data: config.data,
      responseType: config.responseType,
    });
    const reply = replies.shift() ?? json(200, {});
    if (reply === "network") throw new AxiosError("Network Error", AxiosError.ERR_NETWORK, config, {});
    if (reply === "timeout") throw new AxiosError("timeout exceeded", AxiosError.ECONNABORTED, config, {});
    const response = {
      data: reply.body,
      status: reply.status,
      statusText: "",
      headers: new AxiosHeaders(reply.headers ?? {}),
      config,
      request: {},
    };
    if (reply.status >= 200 && reply.status < 300) return response;
    throw new AxiosError(`Request failed with status code ${reply.status}`, AxiosError.ERR_BAD_RESPONSE, config, {}, response);
  };
});

afterEach(() => {
  http.defaults.adapter = originalAdapter;
  vi.unstubAllGlobals();
});

describe("useApi — métodos e corpo", () => {
  it("GET devolve o JSON da resposta e monta a URL a partir da baseURL", async () => {
    serve(json(200, { id: "eq-1" }));
    await expect(useApi().get("/equipments/eq-1")).resolves.toEqual({ id: "eq-1" });
    expect(calls).toHaveLength(1);
    expect(calls[0]).toMatchObject({ method: "GET", url: "http://api.test/api/v1/equipments/eq-1" });
  });

  it("acrescenta /api/v1 quando a baseURL configurada não tem versão", async () => {
    vi.stubGlobal("useRuntimeConfig", () => ({ public: { apiBaseUrl: "http://api.test/" } }));
    await useApi().get("/auth/me");
    expect(calls[0]!.url).toBe("http://api.test/api/v1/auth/me");
  });

  it("POST envia JSON e devolve o corpo do 201", async () => {
    serve(json(201, { id: "ct-1" }));
    const created = await useApi().post("/equipments/eq-1/contracts", { contractNumber: "CT-1", executedAt: null });
    expect(created).toEqual({ id: "ct-1" });
    expect(calls[0]!.method).toBe("POST");
    expect(JSON.parse(String(calls[0]!.data))).toEqual({ contractNumber: "CT-1", executedAt: null });
    expect(String(calls[0]!.headers["Content-Type"])).toContain("application/json");
  });

  it("PUT e PATCH enviam o corpo JSON com o método correto", async () => {
    const api = useApi();
    await api.put("/x/1", { a: 1 });
    await api.patch("/x/1", { b: 2 });
    expect(calls.map((call) => call.method)).toEqual(["PUT", "PATCH"]);
    expect(calls.map((call) => JSON.parse(String(call.data)))).toEqual([{ a: 1 }, { b: 2 }]);
  });

  it("DELETE aceita corpo e query, e 204 devolve undefined como antes", async () => {
    serve({ status: 204, body: "" });
    const result = await useApi().delete("/equipments/eq-1/suppliers/s-1", { reason: "x" }, { force: true });
    expect(result).toBeUndefined();
    expect(calls[0]).toMatchObject({
      method: "DELETE",
      url: "http://api.test/api/v1/equipments/eq-1/suppliers/s-1?force=true",
    });
    expect(JSON.parse(String(calls[0]!.data))).toEqual({ reason: "x" });
  });

  it("GET nunca envia corpo", async () => {
    await useApi().request("/x", { method: "GET", body: { ignorado: true } });
    expect(calls[0]!.data).toBeUndefined();
  });
});

describe("useApi — query params (mesma serialização do $fetch)", () => {
  it("serializa string, number, boolean, null, undefined e arrays", async () => {
    await useApi().get("/equipments", {
      page: 2,
      pageSize: 25,
      unit_id: "u-1",
      equipment_id: "eq-1",
      project_context_id: "pc-1",
      discipline_id: "d-1",
      responsible_user_id: "user-1",
      search: "bomba centrífuga & cia",
      active: false,
      stage: 0,
      area_id: null,
      work_package_id: undefined,
      ids: ["a", "b"],
    });
    expect(calls[0]!.url).toBe(
      "http://api.test/api/v1/equipments?page=2&pageSize=25&unit_id=u-1&equipment_id=eq-1" +
        "&project_context_id=pc-1&discipline_id=d-1&responsible_user_id=user-1" +
        "&search=bomba+centr%C3%ADfuga+%26+cia&active=false&stage=0&area_id&ids=a&ids=b",
    );
  });

  it("sem query (ou só com undefined) não acrescenta '?'", async () => {
    const api = useApi();
    await api.get("/disciplines");
    await api.get("/disciplines", { unit_id: undefined });
    expect(calls.map((call) => call.url)).toEqual([
      "http://api.test/api/v1/disciplines",
      "http://api.test/api/v1/disciplines",
    ]);
  });

  it("serializeQuery codifica caracteres especiais como o ufo", () => {
    expect(serializeQuery({ q: "a/b#c+d", "k=1": "x", empty: "" })).toBe("q=a%2Fb%23c%2Bd&k%3D1=x&empty");
  });
});

describe("useApi — autenticação", () => {
  it("envia Authorization Bearer com o token atual da store", async () => {
    await useApi().get("/auth/me");
    expect(calls[0]!.headers.Authorization).toBe("Bearer tok-123");
  });

  it("não envia Authorization quando não há token", async () => {
    vi.stubGlobal("useAuthStore", () => ({ token: null }));
    await useApi().get("/auth/me");
    expect(calls[0]!.headers).not.toHaveProperty("Authorization");
  });

  it("lê o token a cada chamada (login depois do setup do composable)", async () => {
    const store: { token: string | null } = { token: null };
    vi.stubGlobal("useAuthStore", () => store);
    const api = useApi();
    store.token = "dev-admin";
    await api.get("/auth/me");
    expect(calls[0]!.headers.Authorization).toBe("Bearer dev-admin");
  });

  it("headers explícitos do chamador prevalecem", async () => {
    await useApi().request("/x", { headers: { Authorization: "Bearer outro", "X-Extra": "1" } });
    expect(calls[0]!.headers).toMatchObject({ Authorization: "Bearer outro", "X-Extra": "1" });
  });
});

describe("useApi — normalização de erros", () => {
  async function failure(promise: Promise<unknown>): Promise<ApiError> {
    const caught = await promise.then(
      () => null,
      (error: unknown) => error,
    );
    expect(caught).toBeInstanceOf(ApiError);
    return caught as ApiError;
  }

  it.each([
    [400, { detail: "Requisição inválida." }, "Requisição inválida."],
    [401, { detail: "Token inválido." }, "Token inválido."],
    [403, { detail: "Sem permissão." }, "Sem permissão."],
    [404, { detail: "Equipamento não encontrado." }, "Equipamento não encontrado."],
    [409, { detail: "Já existe dispensa ativa." }, "Já existe dispensa ativa."],
    [500, { detail: "Erro interno." }, "Erro interno."],
  ])("status %i com FastAPI detail vira ApiError com status, mensagem e corpo", async (status, body, message) => {
    serve(json(status, body), json(status, body));
    const error = await failure(useApi().post("/x", {}));
    expect(error).toMatchObject({ status, message, data: body });
  });

  it("422 com detail em lista junta as mensagens de validação", async () => {
    serve(json(422, { detail: [{ msg: "campo obrigatório" }, { msg: "data inválida" }] }));
    const error = await failure(useApi().patch("/x", {}));
    expect(error.status).toBe(422);
    expect(error.message).toBe("campo obrigatório; data inválida");
  });

  it("usa `error`/`message` do corpo quando não há detail", async () => {
    serve(json(422, { error: "Requisitos pendentes para avançar." }), json(400, { message: "Mensagem do corpo." }));
    const api = useApi();
    expect((await failure(api.post("/a", {}))).message).toBe("Requisitos pendentes para avançar.");
    expect((await failure(api.post("/b", {}))).message).toBe("Mensagem do corpo.");
  });

  it("corpo vazio usa a mensagem genérica já existente", async () => {
    serve({ status: 500, body: "" });
    const error = await failure(useApi().post("/x", {}));
    expect(error).toMatchObject({ status: 500, message: "Não foi possível concluir a operação." });
  });

  it("falha de rede e timeout viram ApiError com status 0", async () => {
    serve("network");
    expect(await failure(useApi().post("/x", {}))).toMatchObject({
      status: 0,
      message: "Não foi possível concluir a operação.",
    });
    serve("timeout");
    expect((await failure(useApi().put("/x", {}))).status).toBe(0);
  });
});

describe("useApi — retry herdado do $fetch", () => {
  it("GET é repetido uma vez em 500 e em falha de rede", async () => {
    serve(json(500, { detail: "x" }), json(200, { ok: 1 }));
    await expect(useApi().get("/a")).resolves.toEqual({ ok: 1 });
    serve("network", json(200, { ok: 2 }));
    await expect(useApi().get("/b")).resolves.toEqual({ ok: 2 });
    expect(calls).toHaveLength(4);
  });

  it("GET repete só uma vez e então propaga o erro", async () => {
    serve(json(503, { detail: "indisponível" }), json(503, { detail: "indisponível" }), json(200, {}));
    await expect(useApi().get("/a")).rejects.toMatchObject({ status: 503, message: "indisponível" });
    expect(calls).toHaveLength(2);
  });

  it("GET com 4xx comum (404) não é repetido", async () => {
    serve(json(404, { detail: "não encontrado" }));
    await expect(useApi().get("/a")).rejects.toMatchObject({ status: 404 });
    expect(calls).toHaveLength(1);
  });

  it("métodos com payload nunca são repetidos", async () => {
    serve(json(500, {}), json(200, {}));
    await expect(useApi().post("/a", {})).rejects.toMatchObject({ status: 500 });
    expect(calls).toHaveLength(1);
  });
});

describe("useApi — upload e download de arquivo", () => {
  it("upload envia o FormData via PUT, com Authorization e sem Content-Type manual", async () => {
    serve(json(200, { id: "ct-1", file: { fileName: "novo.pdf" } }));
    const body = new FormData();
    body.append("file", new File(["pdf"], "novo.pdf"));
    const result = await useApi().upload("/equipments/eq-1/contracts/ct-1/file", body);
    expect(result).toEqual({ id: "ct-1", file: { fileName: "novo.pdf" } });
    expect(calls[0]).toMatchObject({ method: "PUT", url: "http://api.test/api/v1/equipments/eq-1/contracts/ct-1/file" });
    expect(calls[0]!.data).toBe(body);
    expect(calls[0]!.headers.Authorization).toBe("Bearer tok-123");
    expect(String(calls[0]!.headers["Content-Type"] ?? "")).not.toContain("boundary");
  });

  it("upload propaga erro normalizado", async () => {
    serve(json(422, { detail: "Arquivo inválido." }));
    await expect(useApi().upload("/f", new FormData())).rejects.toMatchObject({ status: 422, message: "Arquivo inválido." });
  });

  it("download devolve Blob, filename do Content-Disposition e content-type", async () => {
    const blob = new Blob(["%PDF"], { type: "application/pdf" });
    serve({
      status: 200,
      body: blob,
      headers: { "content-type": "application/pdf", "content-disposition": 'attachment; filename="contrato final.pdf"' },
    });
    const file = await useApi().download("/equipments/eq-1/contracts/ct-1/file");
    expect(file.blob).toBe(blob);
    expect(file.filename).toBe("contrato final.pdf");
    expect(file.contentType).toBe("application/pdf");
    expect(calls[0]).toMatchObject({ method: "GET", responseType: "blob" });
    expect(calls[0]!.headers.Authorization).toBe("Bearer tok-123");
  });

  it("download com erro HTTP vira ApiError com o detail, nunca um arquivo", async () => {
    const errorBody = new Blob([JSON.stringify({ detail: "Contrato sem arquivo." })], { type: "application/json" });
    serve({ status: 404, body: errorBody, headers: { "content-type": "application/json" } });
    await expect(useApi().download("/f")).rejects.toMatchObject({
      name: "ApiError",
      status: 404,
      message: "Contrato sem arquivo.",
      data: { detail: "Contrato sem arquivo." },
    });
  });

  it("filenameFromContentDisposition entende filename*, aspas e ausência", () => {
    expect(filenameFromContentDisposition("attachment; filename*=UTF-8''contrato%20%C3%A9.pdf")).toBe("contrato é.pdf");
    expect(filenameFromContentDisposition('attachment; filename="a.pdf"')).toBe("a.pdf");
    expect(filenameFromContentDisposition("attachment; filename=b.pdf")).toBe("b.pdf");
    expect(filenameFromContentDisposition("attachment")).toBeNull();
    expect(filenameFromContentDisposition(undefined)).toBeNull();
  });
});
