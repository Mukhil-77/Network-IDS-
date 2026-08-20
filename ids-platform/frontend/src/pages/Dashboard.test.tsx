import { describe, it, expect, vi, beforeEach } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import { renderWithProviders } from "../test/utils/renderWithProviders";

vi.mock("../services/statisticsService", () => ({
  statisticsService: {
    get: vi.fn().mockResolvedValue({
      threat_count: 42,
      threats_per_minute: [{ minute: "2026-07-24T10:00", count: 3 }],
      threats_by_type: { DoS: 30, PortScan: 12 },
      threats_by_severity: { High: 20, Low: 22 },
      top_source_ips: [{ source_ip: "10.0.0.1", count: 5 }],
      detection_accuracy: 0.91,
      average_prediction_latency_ms: 4.2,
    }),
    topAttacks: vi.fn().mockResolvedValue([]),
  },
}));

vi.mock("../services/healthService", () => ({
  healthService: {
    getSystemHealth: vi.fn().mockResolvedValue({
      status: "healthy",
      model_status: "loaded",
      model_version: "v1",
      active_flows: 0,
      alerts_last_minute: 2,
      timestamp: "2026-07-24T10:00:00Z",
    }),
    getApiHealth: vi.fn().mockResolvedValue({ status: "healthy", model_status: "loaded", version: "1.0.0", uptime_seconds: 120 }),
  },
}));

vi.mock("../context/WebSocketContext", () => ({
  useWebSocketAlerts: () => ({ status: "open", liveAlerts: [] }),
}));

vi.mock("../services/captureService", () => ({
  captureService: {
    status: vi.fn().mockResolvedValue({
      running: true,
      interface: "Ethernet",
      backend: "ScapyCaptureBackend",
      active_flows: 3,
      packet_count: 120,
      protocols: ["tcp", "udp"],
      predictions_count: 5,
      average_prediction_latency_ms: 4.2,
    }),
    interfaces: vi.fn().mockResolvedValue([
      { name: "Ethernet", description: "Ethernet · NPF_ETH0" },
      { name: "Wi-Fi", description: "Wi-Fi · NPF_WIFI0" },
    ]),
    start: vi.fn().mockResolvedValue({ message: "Capture started", bpf_filter: "(ip or ip6) and (tcp or udp)" }),
    stop: vi.fn().mockResolvedValue({ message: "Capture stopped" }),
  },
}));

import Dashboard from "./Dashboard";

describe("Dashboard", () => {
  beforeEach(() => vi.clearAllMocks());

  it("renders summary stat cards once statistics load", async () => {
    renderWithProviders(<Dashboard />);

    expect(await screen.findByText("42")).toBeInTheDocument(); // Total Threats
    // Avg Prediction Time comes from the live capture session and is shown
    // both on the StatCard and inside CaptureControl's status block.
    expect(screen.getAllByText("4.20 ms").length).toBeGreaterThan(0);
  });

  it("renders the threats-today figure derived from per-minute buckets", async () => {
    renderWithProviders(<Dashboard />);
    await waitFor(() => {
      expect(screen.getByText("3")).toBeInTheDocument(); // sum of threats_per_minute counts
    });
  });

  it("renders system health once loaded", async () => {
    renderWithProviders(<Dashboard />);
    expect(await screen.findByText("All systems operational")).toBeInTheDocument();
  });

  it("shows the detection accuracy as a percentage", async () => {
    renderWithProviders(<Dashboard />);
    expect(await screen.findByText("91.0%")).toBeInTheDocument();
  });
});
