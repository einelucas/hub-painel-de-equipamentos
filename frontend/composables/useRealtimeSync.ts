import { ref } from "vue";
import { clearApiCache } from "~/services/api/cache";
import { normalizedBaseUrl } from "~/services/api/http";

export interface RealtimeChangeEvent {
  id: number;
  eventType: "created" | "updated" | "deleted" | "revalidate";
  entityType: "equipment" | "project_context" | string;
  entityId: string;
  unitId: string;
  projectContextId: string | null;
  equipmentId: string | null;
  actorUserId: string | null;
  payload: Record<string, unknown> | null;
  createdAt: string;
}

type Listener = (event: RealtimeChangeEvent) => void | Promise<void>;
const listeners = new Set<Listener>();
const connected = ref(false);
const reconnecting = ref(false);
let controller: AbortController | null = null;
let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
let reconnectAttempt = 0;
let stopped = true;
let lastEventId = 0;
let channel: BroadcastChannel | null = null;

function savedCursor(): number {
  if (typeof sessionStorage === "undefined") return 0;
  return Number(sessionStorage.getItem("equipment-sync-cursor") || 0) || 0;
}

function dispatch(event: RealtimeChangeEvent, broadcast = false): void {
  if (event.eventType !== "revalidate") {
    if (event.id <= lastEventId) return;
    lastEventId = event.id;
    sessionStorage.setItem("equipment-sync-cursor", String(lastEventId));
  }
  clearApiCache();
  if (broadcast) channel?.postMessage(event);
  for (const listener of listeners) void listener(event);
}

function parseBlock(block: string): RealtimeChangeEvent | null {
  const data = block
    .split("\n")
    .filter((line) => line.startsWith("data:"))
    .map((line) => line.slice(5).trimStart())
    .join("\n");
  if (!data) return null;
  try {
    return JSON.parse(data) as RealtimeChangeEvent;
  } catch {
    return null;
  }
}

async function connect(baseUrl: string, token: string): Promise<void> {
  if (stopped || controller) return;
  controller = new AbortController();
  try {
    const response = await fetch(
      `${normalizedBaseUrl(baseUrl)}/sync/events/stream?after=${lastEventId}`,
      {
        headers: { Authorization: `Bearer ${token}`, Accept: "text/event-stream" },
        cache: "no-store",
        signal: controller.signal,
      },
    );
    if (!response.ok || !response.body) throw new Error(`SSE ${response.status}`);
    connected.value = true;
    reconnecting.value = false;
    reconnectAttempt = 0;
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    while (!stopped) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true }).replace(/\r\n/g, "\n");
      let boundary = buffer.indexOf("\n\n");
      while (boundary >= 0) {
        const event = parseBlock(buffer.slice(0, boundary));
        buffer = buffer.slice(boundary + 2);
        if (event) dispatch(event, true);
        boundary = buffer.indexOf("\n\n");
      }
    }
  } catch (error) {
    if (!stopped && !(error instanceof DOMException && error.name === "AbortError")) {
      connected.value = false;
    }
  } finally {
    controller = null;
    connected.value = false;
    if (!stopped) {
      reconnecting.value = true;
      const delay = Math.min(30_000, 2_000 * 2 ** reconnectAttempt++);
      reconnectTimer = setTimeout(() => void connect(baseUrl, token), delay);
    }
  }
}

export function useRealtimeSync() {
  function start(): void {
    const auth = useAuthStore();
    if (typeof window === "undefined" || !auth.token || !stopped) return;
    const config = useRuntimeConfig();
    stopped = false;
    lastEventId = savedCursor();
    channel ??= new BroadcastChannel("equipment-panel-sync");
    channel.onmessage = (message: MessageEvent<RealtimeChangeEvent>) => dispatch(message.data);
    void connect(config.public.apiBaseUrl, auth.token);
  }

  function stop(): void {
    stopped = true;
    controller?.abort();
    controller = null;
    if (reconnectTimer) clearTimeout(reconnectTimer);
    reconnectTimer = null;
    channel?.close();
    channel = null;
    connected.value = false;
  }

  function subscribe(listener: Listener): () => void {
    listeners.add(listener);
    return () => listeners.delete(listener);
  }

  function revalidate(): void {
    dispatch({
      id: lastEventId,
      eventType: "revalidate",
      entityType: "all",
      entityId: "",
      unitId: "",
      projectContextId: null,
      equipmentId: null,
      actorUserId: null,
      payload: null,
      createdAt: new Date().toISOString(),
    });
    const auth = useAuthStore();
    if (!connected.value && auth.token) {
      const config = useRuntimeConfig();
      controller?.abort();
      void connect(config.public.apiBaseUrl, auth.token);
    }
  }

  return { connected, reconnecting, start, stop, subscribe, revalidate };
}
