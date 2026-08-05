import type { WSEvent } from "../types/websocket";
import type { ConnectionStatus } from "../types/common";
import { tokenStorage } from "../utils/tokenStorage";

type AlertListener = (event: WSEvent) => void;
type StatusListener = (status: ConnectionStatus) => void;

const WS_BASE_URL = import.meta.env.VITE_WS_URL ?? "ws://localhost:8000/ws/alerts";
const MAX_RECONNECT_DELAY_MS = 15_000;

/**
 * Thin wrapper around the browser WebSocket API for backend/api/routes/websocket.py's
 * /ws/alerts endpoint. Handles reconnection with exponential backoff (the
 * backend doesn't need any client-side heartbeat protocol - see that
 * route's docstring - so this only needs to detect a closed/errored socket
 * and retry). One instance is created by WebSocketContext and shared app-wide.
 */
export class AlertSocket {
  private socket: WebSocket | null = null;
  private alertListeners = new Set<AlertListener>();
  private statusListeners = new Set<StatusListener>();
  private reconnectAttempt = 0;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private manuallyClosed = false;

  connect(): void {
    this.manuallyClosed = false;
    this.open();
  }

  private open(): void {
    const token = tokenStorage.getAccessToken();
    if (!token) {
      // No point opening a socket that the server will immediately reject
      // (see backend/api/routes/websocket.py) - stay "closed" until a
      // token exists (e.g. after login); WebSocketContext reconnects on
      // auth state changes rather than this class polling for one.
      this.setStatus("closed");
      return;
    }

    this.setStatus("connecting");
    this.socket = new WebSocket(`${WS_BASE_URL}?token=${encodeURIComponent(token)}`);

    this.socket.onopen = () => {
      this.reconnectAttempt = 0;
      this.setStatus("open");
    };

    this.socket.onmessage = (event: MessageEvent<string>) => {
      try {
        const parsed = JSON.parse(event.data) as WSEvent;
        this.alertListeners.forEach((listener) => listener(parsed));
      } catch {
        // Malformed message - ignore rather than crash the whole app over one bad frame.
      }
    };

    this.socket.onerror = () => {
      this.setStatus("error");
    };

    this.socket.onclose = () => {
      this.setStatus("closed");
      if (!this.manuallyClosed) {
        this.scheduleReconnect();
      }
    };
  }

  private scheduleReconnect(): void {
    const delay = Math.min(1000 * 2 ** this.reconnectAttempt, MAX_RECONNECT_DELAY_MS);
    this.reconnectAttempt += 1;
    this.reconnectTimer = setTimeout(() => this.open(), delay);
  }

  disconnect(): void {
    this.manuallyClosed = true;
    if (this.reconnectTimer) clearTimeout(this.reconnectTimer);
    this.socket?.close();
  }

  onAlert(listener: AlertListener): () => void {
    this.alertListeners.add(listener);
    return () => this.alertListeners.delete(listener);
  }

  onStatusChange(listener: StatusListener): () => void {
    this.statusListeners.add(listener);
    return () => this.statusListeners.delete(listener);
  }

  private setStatus(status: ConnectionStatus): void {
    this.statusListeners.forEach((listener) => listener(status));
  }
}
