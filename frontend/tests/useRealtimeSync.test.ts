import { afterEach, describe, expect, it, vi } from "vitest";
import { useRealtimeSync, type RealtimeChangeEvent } from "~/composables/useRealtimeSync";

class FakeBroadcastChannel {
  static instances: FakeBroadcastChannel[] = [];
  onmessage: ((message: MessageEvent<RealtimeChangeEvent>) => void) | null = null;
  postMessage = vi.fn();
  close = vi.fn();

  constructor(readonly name: string) {
    FakeBroadcastChannel.instances.push(this);
  }
}

function event(id: number, name = "updated"): RealtimeChangeEvent {
  return {
    id,
    eventType: name as RealtimeChangeEvent["eventType"],
    entityType: "equipment",
    entityId: "eq-sync",
    unitId: "unit-sync",
    projectContextId: "project-sync",
    equipmentId: "eq-sync",
    actorUserId: "user-sync",
    payload: { changedFields: ["name"] },
    createdAt: "2026-11-04T10:00:00Z",
  };
}

afterEach(() => {
  useRealtimeSync().stop();
  sessionStorage.clear();
  FakeBroadcastChannel.instances = [];
  vi.unstubAllGlobals();
});

describe("useRealtimeSync", () => {
  it("propaga SSE e mensagens entre abas sem entregar o mesmo evento duas vezes", async () => {
    const serverEvent = event(1001);
    const block = new TextEncoder().encode(
      `id: 1001\nevent: change\ndata: ${JSON.stringify(serverEvent)}\n\n`,
    );
    let reads = 0;
    const read = vi.fn(async () => {
      reads += 1;
      if (reads === 1) return { value: block, done: false };
      return await new Promise<{ value: undefined; done: boolean }>(() => {});
    });
    vi.stubGlobal("useRuntimeConfig", () => ({ public: { apiBaseUrl: "http://api.test/api/v1" } }));
    vi.stubGlobal("useAuthStore", () => ({ token: "token-sintetico" }));
    vi.stubGlobal("BroadcastChannel", FakeBroadcastChannel);
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({ ok: true, status: 200, body: { getReader: () => ({ read }) } }),
    );

    const sync = useRealtimeSync();
    const received: RealtimeChangeEvent[] = [];
    const unsubscribe = sync.subscribe((change) => {
      received.push(change);
    });
    sync.start();

    await vi.waitFor(() => expect(received).toHaveLength(1));
    const channel = FakeBroadcastChannel.instances[0]!;
    expect(channel.name).toBe("equipment-panel-sync");
    expect(channel.postMessage).toHaveBeenCalledWith(serverEvent);

    channel.onmessage?.({ data: event(1002) } as MessageEvent<RealtimeChangeEvent>);
    channel.onmessage?.({ data: event(1002) } as MessageEvent<RealtimeChangeEvent>);
    expect(received.map((item) => item.id)).toEqual([1001, 1002]);
    expect(sessionStorage.getItem("equipment-sync-cursor")).toBe("1002");

    unsubscribe();
  });
});
