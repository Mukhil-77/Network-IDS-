import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { AlertSocket } from "./websocketService";

// Minimal fake WebSocket - captures handlers assigned by AlertSocket and
// lets tests drive open/message/close/error manually, without a real
// network connection.
class FakeWebSocket {
  static instances: FakeWebSocket[] = [];
  onopen: (() => void) | null = null;
  onmessage: ((event: { data: string }) => void) | null = null;
  onerror: (() => void) | null = null;
  onclose: (() => void) | null = null;
  closed = false;

  constructor(public url: string) {
    FakeWebSocket.instances.push(this);
  }

  close() {
    this.closed = true;
    this.onclose?.();
  }
}

describe("AlertSocket", () => {
  beforeEach(() => {
    FakeWebSocket.instances = [];
    vi.stubGlobal("WebSocket", FakeWebSocket);
    vi.useFakeTimers();
    localStorage.setItem("soc_access_token", "fake-test-token");
  });

  afterEach(() => {
    localStorage.clear();
    vi.unstubAllGlobals();
    vi.useRealTimers();
  });

  it("transitions to 'open' status when the socket opens", () => {
    const socket = new AlertSocket();
    const statuses: string[] = [];
    socket.onStatusChange((s) => statuses.push(s));

    socket.connect();
    FakeWebSocket.instances[0].onopen?.();

    expect(statuses).toEqual(["connecting", "open"]);
  });

  it("parses and delivers a well-formed alert message to listeners", () => {
    const socket = new AlertSocket();
    const received: unknown[] = [];
    socket.onAlert((event) => received.push(event));

    socket.connect();
    const event = { type: "alert", payload: { id: "1", attack: "DoS" }, timestamp: "2026-07-24T10:00:00Z" };
    FakeWebSocket.instances[0].onmessage?.({ data: JSON.stringify(event) });

    expect(received).toHaveLength(1);
    expect(received[0]).toEqual(event);
  });

  it("silently ignores a malformed message instead of throwing", () => {
    const socket = new AlertSocket();
    const received: unknown[] = [];
    socket.onAlert((event) => received.push(event));

    socket.connect();
    expect(() => FakeWebSocket.instances[0].onmessage?.({ data: "not json" })).not.toThrow();
    expect(received).toHaveLength(0);
  });

  it("schedules a reconnect with backoff after an unexpected close", () => {
    const socket = new AlertSocket();
    socket.connect();
    FakeWebSocket.instances[0].onclose?.();

    expect(FakeWebSocket.instances).toHaveLength(1);
    vi.advanceTimersByTime(1000); // first backoff delay
    expect(FakeWebSocket.instances).toHaveLength(2); // reconnected
  });

  it("does not reconnect after an explicit disconnect() call", () => {
    const socket = new AlertSocket();
    socket.connect();
    socket.disconnect();

    vi.advanceTimersByTime(20_000);
    expect(FakeWebSocket.instances).toHaveLength(1); // no reconnect attempt
  });

  it("unsubscribe functions stop further delivery to that listener", () => {
    const socket = new AlertSocket();
    const received: unknown[] = [];
    const unsubscribe = socket.onAlert((event) => received.push(event));

    socket.connect();
    unsubscribe();
    FakeWebSocket.instances[0].onmessage?.({
      data: JSON.stringify({ type: "alert", payload: {}, timestamp: "x" }),
    });

    expect(received).toHaveLength(0);
  });
});
